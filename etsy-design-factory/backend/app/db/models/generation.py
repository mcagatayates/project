from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import GUID, Base, CreatedUpdatedMixin, JSONVariant, UUIDPKMixin
from app.db.models.enums import CandidateStatus


class GenerationJob(UUIDPKMixin, CreatedUpdatedMixin, Base):
    __tablename__ = "generation_jobs"

    concept_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("concepts.id"), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(100))
    compiled_prompt: Mapped[str] = mapped_column(String(4000))
    params: Mapped[dict] = mapped_column(JSONVariant, default=dict)
    status: Mapped[str] = mapped_column(String(30), default=CandidateStatus.QUEUED.value)
    idempotency_key: Mapped[str] = mapped_column(String(300), unique=True, index=True)


class GenerationCandidate(UUIDPKMixin, CreatedUpdatedMixin, Base):
    __tablename__ = "generation_candidates"

    generation_job_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("generation_jobs.id"), index=True)
    concept_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("concepts.id"), index=True)
    design_genome_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("design_genomes.id"), index=True)
    storage_key: Mapped[str] = mapped_column(String(500))
    width_px: Mapped[int] = mapped_column(Integer)
    height_px: Mapped[int] = mapped_column(Integer)
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    perceptual_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(30), default=CandidateStatus.QUEUED.value, index=True)
    is_repair: Mapped[bool] = mapped_column(Boolean, default=False)
    # Informational only (no FK constraint) to avoid a circular FK cycle with
    # repair_attempts.resulting_candidate_id, which is the canonical link.
    repair_attempt_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    # Populated when tournament_selection or diversity_control moves this
    # candidate to ELIMINATED, so every rejection stays traceable.
    elimination_reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)
