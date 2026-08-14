from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import GUID, Base, CreatedAtMixin, JSONVariant, UUIDPKMixin


class Artwork(UUIDPKMixin, CreatedAtMixin, Base):
    __tablename__ = "artworks"

    generation_candidate_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("generation_candidates.id"), unique=True, index=True
    )
    design_genome_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("design_genomes.id"), index=True)
    collection_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("collections.id"), index=True)
    master_storage_key: Mapped[str] = mapped_column(String(500))
    master_width_px: Mapped[int] = mapped_column(Integer)
    master_height_px: Mapped[int] = mapped_column(Integer)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str] = mapped_column(String(200))
    sku: Mapped[str] = mapped_column(String(50), unique=True)


class PrintExport(UUIDPKMixin, CreatedAtMixin, Base):
    __tablename__ = "print_exports"
    __table_args__ = ()

    artwork_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("artworks.id"), index=True)
    ratio: Mapped[str] = mapped_column(String(10))
    target_long_edge_px: Mapped[int] = mapped_column(Integer)
    actual_width_px: Mapped[int] = mapped_column(Integer)
    actual_height_px: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(500))
    upscaled: Mapped[bool] = mapped_column(Boolean, default=False)
    upscale_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)


class Mockup(UUIDPKMixin, CreatedAtMixin, Base):
    __tablename__ = "mockups"

    artwork_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("artworks.id"), index=True)
    template_id: Mapped[str] = mapped_column(String(100))
    storage_key: Mapped[str] = mapped_column(String(500))


class EtsyListingPackage(UUIDPKMixin, CreatedAtMixin, Base):
    __tablename__ = "etsy_listing_packages"

    artwork_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("artworks.id"), unique=True, index=True)
    title_concepts: Mapped[list] = mapped_column(JSONVariant, default=list)
    description_data: Mapped[dict] = mapped_column(JSONVariant, default=dict)
    keyword_candidates: Mapped[list] = mapped_column(JSONVariant, default=list)
    tags: Mapped[list] = mapped_column(JSONVariant, default=list)
    style: Mapped[str] = mapped_column(String(100))
    subject: Mapped[str] = mapped_column(String(200))
    palette: Mapped[str] = mapped_column(String(100))
    orientation: Mapped[str] = mapped_column(String(20))
    collection_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("collections.id"))
    internal_sku: Mapped[str] = mapped_column(String(50))
    print_export_ids: Mapped[list] = mapped_column(JSONVariant, default=list)
    mockup_ids: Mapped[list] = mapped_column(JSONVariant, default=list)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    external_listing_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
