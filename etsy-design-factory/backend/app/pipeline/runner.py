"""Orchestrates one Concept through Generation -> Vision QC -> Failure
Diagnosis -> Selective Repair -> Tournament Selection -> Diversity Control.

This is the synchronous "what a Celery chain/chord does" logic, factored
out so it can be unit-tested directly and reused by the Celery task
wrappers in app/queue/tasks (Phase 2) without duplicating orchestration.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models.collection import Collection
from app.db.models.concept import Concept
from app.db.models.enums import CandidateStatus
from app.db.models.generation import GenerationCandidate
from app.genome.schema import DesignGenome
from app.pipeline.diversity_control import run_diversity_control
from app.pipeline.failure_diagnosis import diagnose_failure
from app.pipeline.generation import generate_candidate
from app.pipeline.selective_repair import finalize_repair_outcome, run_repair, should_repair
from app.pipeline.tournament_selection import latest_evaluation, run_tournament
from app.pipeline.vision_qc import run_vision_qc
from app.providers.registry import ProviderRegistry


async def run_concept_to_selection(
    session: Session,
    registry: ProviderRegistry,
    *,
    concept: Concept,
    genome: DesignGenome,
    collection: Collection,
    quality_seed_fn=None,
    winners: int = 1,
) -> list[GenerationCandidate]:
    """Runs generation through diversity control for one concept and
    returns the surviving (kept) SELECTED candidate(s), if any."""
    quality_seed_fn = quality_seed_fn or (lambda attempt: 0.85)

    resolved_candidates: list[GenerationCandidate] = []
    for attempt in range(1, concept.planned_candidate_count + 1):
        candidate = await generate_candidate(
            session,
            registry,
            concept=concept,
            genome=genome,
            attempt_number=attempt,
            collection_thesis=collection.thesis,
            quality_seed=quality_seed_fn(attempt),
        )
        await run_vision_qc(session, registry, candidate=candidate, genome=genome)
        resolved_candidates.append(
            await _resolve_through_repair(
                session, registry, candidate=candidate, concept=concept, genome=genome, collection=collection
            )
        )

    selected = run_tournament(session, concept_id=concept.id, winners=winners)

    kept: list[GenerationCandidate] = []
    for candidate in selected:
        ok, _conflict = run_diversity_control(session, candidate=candidate, genome=genome)
        if ok:
            kept.append(candidate)
    return kept


async def _resolve_through_repair(
    session: Session,
    registry: ProviderRegistry,
    *,
    candidate: GenerationCandidate,
    concept: Concept,
    genome: DesignGenome,
    collection: Collection,
) -> GenerationCandidate:
    """If `candidate` failed QC, diagnose it and optionally repair,
    returning the final candidate in the chain (repaired or original)."""
    if candidate.status != CandidateStatus.QC_FAILED.value:
        return candidate

    evaluation = latest_evaluation(session, candidate.id)
    if evaluation is None:
        raise ValueError(f"candidate {candidate.id} is QC_FAILED but has no Evaluation row")
    failure_record = diagnose_failure(session, candidate=candidate, evaluation=evaluation)

    ok, _reason = should_repair(session, failure_record=failure_record, concept_id=concept.id)
    if not ok:
        candidate.status = CandidateStatus.TERMINAL.value
        session.flush()
        return candidate

    repair, new_candidate = await run_repair(
        session,
        registry,
        failure_record=failure_record,
        failed_candidate=candidate,
        concept=concept,
        genome=genome,
        collection_thesis=collection.thesis,
    )
    await run_vision_qc(session, registry, candidate=new_candidate, genome=genome)
    finalize_repair_outcome(session, repair=repair, improved=new_candidate.status == CandidateStatus.QC_PASSED.value)

    if new_candidate.status == CandidateStatus.QC_FAILED.value:
        # one repair attempt already spent; a further recursive repair is
        # still eligible up to the configured cap via should_repair's own check.
        return await _resolve_through_repair(
            session, registry, candidate=new_candidate, concept=concept, genome=genome, collection=collection
        )

    return new_candidate
