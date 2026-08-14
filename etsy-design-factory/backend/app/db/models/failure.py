from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import GUID, Base, CreatedAtMixin, JSONVariant, UUIDPKMixin
from app.db.models.enums import RepairOutcome


class FailureRecord(UUIDPKMixin, CreatedAtMixin, Base):
    __tablename__ = "failure_records"

    # Nullable: a provider-exhausted Generation failure (see
    # docs/AGENT_CONTRACTS.md "Generation" failure policy) has no candidate
    # row to attach to -- generation never reached GENERATED. concept_id is
    # always set so the failure is still traceable to a concept.
    generation_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("generation_candidates.id"), nullable=True, index=True
    )
    concept_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("concepts.id"), nullable=True, index=True)
    failure_class: Mapped[str] = mapped_column(String(30), index=True)
    detected_problems: Mapped[list] = mapped_column(JSONVariant, default=list)
    diagnosis_reasoning: Mapped[str] = mapped_column(String(2000))
    diagnosed_by: Mapped[str] = mapped_column(String(100))


class RepairAttempt(UUIDPKMixin, CreatedAtMixin, Base):
    __tablename__ = "repair_attempts"

    failure_record_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("failure_records.id"), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    genome_delta: Mapped[dict] = mapped_column(JSONVariant, default=dict)
    prompt_delta: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    provider: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(100))
    resulting_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("generation_candidates.id"), nullable=True
    )
    outcome: Mapped[str] = mapped_column(String(20), default=RepairOutcome.PENDING.value)
    cost_event_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("cost_events.id"), nullable=True)
