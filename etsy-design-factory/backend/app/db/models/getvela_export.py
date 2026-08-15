from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import GUID, Base, CreatedAtMixin, UUIDPKMixin


class GetvelaExportBatch(UUIDPKMixin, CreatedAtMixin, Base):
    """One CSV export run -- see app/pipeline/getvela_export.py. Append-only:
    a batch records what was actually exported, matching the mission's
    "every decision is traceable" requirement. The user reviews/edits each
    batch's listings inside Getvela's own archive and activates them day by
    day; this table only tracks "have we already handed this artwork to
    Getvela," so re-running the export never duplicates a listing."""

    __tablename__ = "getvela_export_batches"

    requested_by: Mapped[str] = mapped_column(String(200))
    row_count: Mapped[int] = mapped_column(Integer)
    listing_count: Mapped[int] = mapped_column(Integer)


class GetvelaExportRecord(UUIDPKMixin, CreatedAtMixin, Base):
    """One row per Artwork actually included in a GetvelaExportBatch."""

    __tablename__ = "getvela_export_records"

    batch_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("getvela_export_batches.id"), index=True)
    artwork_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("artworks.id"), unique=True, index=True)
