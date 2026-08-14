from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import GUID, Base, CreatedAtMixin, CreatedUpdatedMixin, JSONVariant, UUIDPKMixin
from app.db.models.enums import CreativeFamilyStatus


class CommercialObservation(UUIDPKMixin, CreatedAtMixin, Base):
    """One real metric value from a commercial adapter. Never fabricated —
    if the adapter has no value for a metric, no row is written."""

    __tablename__ = "commercial_observations"

    artwork_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("artworks.id"), nullable=True, index=True)
    design_genome_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("design_genomes.id"), nullable=True, index=True
    )
    external_listing_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source: Mapped[str] = mapped_column(String(50))
    metric_name: Mapped[str] = mapped_column(String(100))
    metric_value: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CreativeFamily(UUIDPKMixin, CreatedUpdatedMixin, Base):
    __tablename__ = "creative_families"

    name: Mapped[str] = mapped_column(String(200))
    defining_dna_signature: Mapped[dict] = mapped_column(JSONVariant, default=dict)
    status: Mapped[str] = mapped_column(String(20), default=CreativeFamilyStatus.CHALLENGER.value)
    member_genome_ids: Mapped[list] = mapped_column(JSONVariant, default=list)
    performance_summary: Mapped[dict | None] = mapped_column(JSONVariant, nullable=True)
