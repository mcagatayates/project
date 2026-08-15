"""Persistence for what's already been handed to Getvela. See
app/pipeline/getvela_export.py and app/db/models/getvela_export.py --
this only ever records what was actually written into a CSV, so re-running
an export never produces a duplicate listing."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.artwork import Artwork
from app.db.models.getvela_export import GetvelaExportBatch, GetvelaExportRecord


def exported_artwork_ids(session: Session) -> set[uuid.UUID]:
    stmt = select(GetvelaExportRecord.artwork_id)
    return set(session.execute(stmt).scalars().all())


def not_yet_exported_artworks(session: Session, *, collection_id: uuid.UUID | None = None, limit: int = 100) -> list[Artwork]:
    already = exported_artwork_ids(session)
    stmt = select(Artwork).order_by(Artwork.approved_at.asc())
    if collection_id is not None:
        stmt = stmt.where(Artwork.collection_id == collection_id)
    artworks = list(session.execute(stmt).scalars().all())
    return [a for a in artworks if a.id not in already][:limit]


def record_batch(
    session: Session, *, requested_by: str, artwork_ids: list[uuid.UUID], row_count: int
) -> GetvelaExportBatch:
    batch = GetvelaExportBatch(requested_by=requested_by, row_count=row_count, listing_count=len(artwork_ids))
    session.add(batch)
    session.flush()
    for artwork_id in artwork_ids:
        session.add(GetvelaExportRecord(batch_id=batch.id, artwork_id=artwork_id))
    session.flush()
    return batch


def recent_batches(session: Session, *, limit: int = 20) -> list[GetvelaExportBatch]:
    stmt = select(GetvelaExportBatch).order_by(GetvelaExportBatch.created_at.desc()).limit(limit)
    return list(session.execute(stmt).scalars().all())
