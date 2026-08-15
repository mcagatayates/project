"""Persistence for what's already been archived to Google Drive. See
app/pipeline/drive_archive.py and app/db/models/drive_archive.py -- only
ever records what was actually uploaded, so re-running the sync never
re-uploads a design already in the Drive archive, and a SKU lookup here
is always backed by a real, previously-successful upload."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.artwork import Artwork
from app.db.models.drive_archive import DriveArchiveRecord


def archived_artwork_ids(session: Session) -> set[uuid.UUID]:
    stmt = select(DriveArchiveRecord.artwork_id)
    return set(session.execute(stmt).scalars().all())


def not_yet_archived_artworks(session: Session, *, limit: int = 100) -> list[Artwork]:
    already = archived_artwork_ids(session)
    stmt = select(Artwork).order_by(Artwork.approved_at.asc())
    artworks = list(session.execute(stmt).scalars().all())
    return [a for a in artworks if a.id not in already][:limit]


def record_archive(
    session: Session, *, artwork_id: uuid.UUID, sku: str, drive_file_id: str, drive_file_url: str
) -> DriveArchiveRecord:
    record = DriveArchiveRecord(artwork_id=artwork_id, sku=sku, drive_file_id=drive_file_id, drive_file_url=drive_file_url)
    session.add(record)
    session.flush()
    return record


def find_by_sku(session: Session, *, sku: str) -> DriveArchiveRecord | None:
    stmt = select(DriveArchiveRecord).where(DriveArchiveRecord.sku == sku)
    return session.execute(stmt).scalar_one_or_none()


def recent_archives(session: Session, *, limit: int = 20) -> list[DriveArchiveRecord]:
    stmt = select(DriveArchiveRecord).order_by(DriveArchiveRecord.created_at.desc()).limit(limit)
    return list(session.execute(stmt).scalars().all())
