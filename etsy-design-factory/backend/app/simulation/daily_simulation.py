"""Runs one full autonomous production day end-to-end: DailyProductionPlan
-> Collection Planner -> DesignGenome -> Concept -> Generation -> Vision QC
-> Failure Diagnosis -> Selective Repair -> Tournament Selection ->
Diversity Control -> (simulated bulk) Approval -> Print Factory -> Mockup
Factory -> Etsy Package.

This is the callable behind the mission's acceptance test
(tests/test_acceptance_30_designs.py) and can also be invoked directly
(e.g. from a CLI or the API) to smoke-test the system with fake providers.
"""

from __future__ import annotations

import datetime
from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.db.models.artwork import Artwork
from app.db.models.collection import Collection
from app.db.models.concept import Concept
from app.db.models.enums import ApprovalAction, CandidateStatus, FailureClass, GateStatus
from app.db.models.failure import FailureRecord, RepairAttempt
from app.db.models.generation import GenerationCandidate
from app.db.models.genome import DesignGenome as DesignGenomeRow
from app.db.models.production import DailyProductionPlan
from app.genome.codec import from_row, to_row
from app.genome.mutation import mutate as mutate_genome
from app.pipeline.approval import apply_approval
from app.pipeline.collection_planner import SlotAssignment, plan_collections
from app.pipeline.concept_gate import gate_concept
from app.pipeline.concept_generation import create_concept
from app.pipeline.etsy_package import build_etsy_package
from app.pipeline.genome_ideation import create_genome
from app.pipeline.mockup_factory import generate_all_mockups
from app.pipeline.print_factory import export_all_ratios
from app.pipeline.production_controller import build_daily_plan
from app.pipeline.runner import run_concept_to_selection
from app.providers.base import ProviderError
from app.providers.registry import ProviderRegistry

# Kept small so the simulation runs in seconds; Phase 4's dedicated tests
# already verify the real 6000px-default upscale path.
DEFAULT_TEST_LONG_EDGE_PX = 800


def default_quality_seed(index: int) -> float:
    """A realistic mix: mostly clean generations, a steady trickle of
    repairable failures, and the occasional total write-off -- not a
    uniform "everything passes" happy path. A concept whose provider draw
    is a total write-off contributes zero winners (by design -- that is
    what TERMINAL_FAILURE means), so this stays a rare event rather than a
    frequent one, matching real generation-quality distributions."""
    if index % 29 == 17:
        return 0.15  # terminal
    if index % 6 == 3:
        return 0.55  # repairable, boosted quality_seed on repair should pass
    return 0.90


@dataclass
class DailySimulationResult:
    plan: DailyProductionPlan
    assignments: list[SlotAssignment] = field(default_factory=list)
    total_concepts: int = 0
    gated_concepts: int = 0
    rejected_concepts: int = 0
    total_generation_candidates: int = 0
    kept_candidates: list[GenerationCandidate] = field(default_factory=list)
    approved_artworks: list[Artwork] = field(default_factory=list)
    failure_record_count: int = 0
    repair_attempt_count: int = 0


def _genome_for_slot(session: Session, collection: Collection, assignment: SlotAssignment, slot_offset: int):
    if assignment.parent_artwork_id is not None:
        parent_artwork = session.get(Artwork, assignment.parent_artwork_id)
        if parent_artwork is not None:
            parent_genome_row = session.get(DesignGenomeRow, parent_artwork.design_genome_id)
            if parent_genome_row is not None:
                return mutate_genome(
                    from_row(parent_genome_row), collection_palette_boundaries=collection.palette_boundaries
                )
    # Explicit monotonic seed (not the default collection.id-derived hash):
    # keeps the simulation's creative output reproducible run-to-run
    # despite collections getting fresh random UUIDs each time, which
    # matters for a stable, repeatable acceptance test.
    return create_genome(collection, slot_index=slot_offset, seed=slot_offset)


def _collection_for_candidate(session: Session, candidate: GenerationCandidate) -> Collection:
    concept = session.get(Concept, candidate.concept_id)
    assert concept is not None
    collection = session.get(Collection, concept.collection_id)
    assert collection is not None
    return collection


async def run_daily_simulation(
    session: Session,
    registry: ProviderRegistry,
    *,
    plan_date: datetime.date,
    target_final_designs: int = 30,
    quality_seed_fn: Callable[[int], float] | None = None,
    approve_up_to: int | None = None,
    ratios: tuple[str, ...] = ("2:3", "3:4", "4:5"),
    mockup_template_ids: list[str] | None = None,
) -> DailySimulationResult:
    quality_seed_fn = quality_seed_fn or default_quality_seed
    mockup_template_ids = mockup_template_ids or ["living_room_light_frame"]

    plan = build_daily_plan(session, plan_date=plan_date, target_final_designs=target_final_designs)
    assignments = plan_collections(session, plan=plan)

    result = DailySimulationResult(plan=plan, assignments=assignments)
    concept_index = 0
    all_kept: list[GenerationCandidate] = []

    for assignment in assignments:
        collection = assignment.collection
        for slot in range(assignment.slots):
            genome = _genome_for_slot(session, collection, assignment, slot + result.total_concepts)
            genome = genome.model_copy(
                update={
                    "print_dna": genome.print_dna.model_copy(
                        update={"recommended_min_long_edge_px": DEFAULT_TEST_LONG_EDGE_PX}
                    )
                }
            )
            genome_row = to_row(genome)
            session.add(genome_row)
            session.flush()

            concept = create_concept(
                session, genome_row=genome_row, collection=collection, production_mode=collection.mode
            )
            result.total_concepts += 1

            await gate_concept(session, registry, concept=concept, genome_row=genome_row, collection=collection)
            if concept.gate_status != GateStatus.PASSED.value:
                result.rejected_concepts += 1
                continue
            result.gated_concepts += 1

            qseed = quality_seed_fn(concept_index)
            concept_index += 1

            try:
                kept = await run_concept_to_selection(
                    session,
                    registry,
                    concept=concept,
                    genome=genome,
                    collection=collection,
                    quality_seed_fn=lambda _attempt, _qseed=qseed: _qseed,
                )
            except ProviderError as exc:
                # A worker/provider failure on one concept must not corrupt
                # the day: record it and move on to the next concept, the
                # same isolation a real deployment gets for free from each
                # concept's work living in independent Celery tasks (see
                # app/queue/tasks/generation.py for the task-level version
                # of this same policy).
                session.add(
                    FailureRecord(
                        generation_candidate_id=None,
                        concept_id=concept.id,
                        failure_class=FailureClass.TERMINAL_FAILURE.value,
                        detected_problems=[str(exc)],
                        diagnosis_reasoning="provider exhausted during the daily simulation run for this concept.",
                        diagnosed_by="provider_exhausted",
                    )
                )
                session.flush()
                continue
            all_kept.extend(kept)

    result.kept_candidates = all_kept
    result.total_generation_candidates = session.query(GenerationCandidate).count()
    result.failure_record_count = session.query(FailureRecord).count()
    result.repair_attempt_count = session.query(RepairAttempt).count()

    to_approve = all_kept if approve_up_to is None else all_kept[:approve_up_to]
    for candidate in to_approve:
        candidate.status = CandidateStatus.AWAITING_APPROVAL.value
        session.flush()

        approved_genome_row = session.get(DesignGenomeRow, candidate.design_genome_id)
        assert approved_genome_row is not None
        collection_row = _collection_for_candidate(session, candidate)

        _approval, artwork, _new_concept = apply_approval(
            session,
            candidate=candidate,
            action=ApprovalAction.APPROVE.value,
            actor="autonomous-simulation",
            collection=collection_row,
        )
        if artwork is None:
            continue

        approved_genome = from_row(approved_genome_row)
        exports = await export_all_ratios(session, registry, artwork=artwork, genome=approved_genome, ratios=ratios)
        mockups = await generate_all_mockups(session, registry, artwork=artwork, template_ids=mockup_template_ids)
        build_etsy_package(
            session,
            artwork=artwork,
            genome=approved_genome,
            collection=collection_row,
            print_exports=exports,
            mockups=mockups,
        )
        result.approved_artworks.append(artwork)

    return result
