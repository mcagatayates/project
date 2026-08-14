"""Selective Repair: only regenerate when expected value justifies it.

Expected value = P(repair improves it) * value_of_an_extra_accepted_design
              vs. cost of one more generation attempt.
We don't have a live dollar value for "an accepted design" wired up yet
(that's commercial_learning territory, Phase 5), so the gate here is:
  1. failure_class must be REPAIRABLE_FAILURE or PROMISING (never TERMINAL),
  2. under the per-concept repair attempt cap,
  3. historical repair success rate (FailureMemory) is not proven poor —
     PROMISING failures are always worth one attempt; REPAIRABLE failures
     need either no history yet (optimistic first try) or a success rate
     above a configurable floor.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models.enums import CandidateStatus, FailureClass, RepairOutcome
from app.db.models.failure import FailureRecord, RepairAttempt
from app.db.models.generation import GenerationCandidate, GenerationJob
from app.genome.schema import DesignGenome
from app.memory.failure_memory import repair_attempt_count_for_concept, repair_success_rate
from app.pipeline.generation import build_generation_params, generate_candidate
from app.pipeline.quality_config import get_quality_config
from app.providers.registry import ProviderRegistry

MIN_HISTORICAL_SUCCESS_RATE = 0.25


def should_repair(session: Session, *, failure_record: FailureRecord, concept_id) -> tuple[bool, str]:
    cfg = get_quality_config()["repair"]

    if failure_record.failure_class == FailureClass.TERMINAL_FAILURE.value:
        return False, "TERMINAL_FAILURE is never repaired."

    attempts_so_far = repair_attempt_count_for_concept(session, concept_id=concept_id)
    if attempts_so_far >= cfg["max_attempts_per_concept"]:
        return False, f"repair cap reached ({attempts_so_far}/{cfg['max_attempts_per_concept']})."

    if failure_record.failure_class == FailureClass.PROMISING.value:
        return True, "PROMISING failure — strong creative scores justify one more attempt."

    rate = repair_success_rate(session, failure_class=failure_record.failure_class)
    if rate is None:
        return True, "no repair history yet for this failure class — optimistic first attempt."
    if rate >= MIN_HISTORICAL_SUCCESS_RATE:
        return True, f"historical repair success rate {rate:.2f} clears the floor ({MIN_HISTORICAL_SUCCESS_RATE})."
    return False, f"historical repair success rate {rate:.2f} is below the floor ({MIN_HISTORICAL_SUCCESS_RATE})."


async def run_repair(
    session: Session,
    registry: ProviderRegistry,
    *,
    failure_record: FailureRecord,
    failed_candidate: GenerationCandidate,
    concept,
    genome: DesignGenome,
    collection_thesis: str | None = None,
) -> tuple[RepairAttempt, GenerationCandidate]:
    cfg = get_quality_config()["repair"]

    original_job = session.get(GenerationJob, failed_candidate.generation_job_id)
    original_params = dict(original_job.params) if original_job else {}
    boosted_quality_seed = min(1.0, float(original_params.get("quality_seed", 0.5)) + cfg["quality_boost_per_attempt"])

    attempt_number = repair_attempt_count_for_concept(session, concept_id=concept.id) + 1
    new_params = build_generation_params(
        genome,
        quality_seed=boosted_quality_seed,
        variation_seed=int(original_params.get("variation_seed", 0)) + 1000 * attempt_number,
    )

    repair = RepairAttempt(
        failure_record_id=failure_record.id,
        attempt_number=attempt_number,
        genome_delta={},
        prompt_delta="boosted generation quality parameters after diagnosis",
        provider="repair_orchestrator",
        model="n/a",
        outcome=RepairOutcome.PENDING.value,
    )
    session.add(repair)
    session.flush()

    new_candidate = await generate_candidate(
        session,
        registry,
        concept=concept,
        genome=genome,
        attempt_number=1000 * attempt_number + int(original_params.get("variation_seed", 0)),
        collection_thesis=collection_thesis,
        is_repair=True,
        params_override=new_params,
    )
    new_candidate.repair_attempt_id = repair.id
    failed_candidate.status = CandidateStatus.REPAIR_QUEUED.value

    repair.resulting_candidate_id = new_candidate.id
    session.flush()
    return repair, new_candidate


def finalize_repair_outcome(session: Session, *, repair: RepairAttempt, improved: bool) -> None:
    repair.outcome = RepairOutcome.IMPROVED.value if improved else RepairOutcome.NO_IMPROVEMENT.value
    session.flush()
