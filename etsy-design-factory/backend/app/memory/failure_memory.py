"""FailureMemory: queryable history of what tends to fail and what repairs
tend to work, per failure class. Backed directly by failure_records /
repair_attempts (no separate cache table) so it never drifts from the
append-only history it summarizes."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.enums import RepairOutcome
from app.db.models.failure import FailureRecord, RepairAttempt


def repair_success_rate(session: Session, *, failure_class: str, min_sample: int = 3) -> float | None:
    """Historical fraction of repair attempts for this failure_class that
    resulted in IMPROVED. Returns None when there isn't enough history yet
    (caller should fall back to an optimistic prior, not a fabricated rate)."""
    stmt = (
        select(RepairAttempt.outcome)
        .join(FailureRecord, RepairAttempt.failure_record_id == FailureRecord.id)
        .where(FailureRecord.failure_class == failure_class)
        .where(RepairAttempt.outcome != RepairOutcome.PENDING.value)
    )
    outcomes = list(session.execute(stmt).scalars().all())
    if len(outcomes) < min_sample:
        return None
    improved = sum(1 for o in outcomes if o == RepairOutcome.IMPROVED.value)
    return improved / len(outcomes)


def repair_attempt_count_for_concept(session: Session, *, concept_id) -> int:
    from app.db.models.generation import GenerationCandidate

    stmt = (
        select(RepairAttempt)
        .join(FailureRecord, RepairAttempt.failure_record_id == FailureRecord.id)
        .join(GenerationCandidate, FailureRecord.generation_candidate_id == GenerationCandidate.id)
        .where(GenerationCandidate.concept_id == concept_id)
    )
    return len(list(session.execute(stmt).scalars().all()))
