"""Google Drive master-image archive -- see app/pipeline/drive_archive.py.
Syncs approved-but-not-yet-archived artworks to Drive, and exposes a
SKU lookup so a human fulfilling an Etsy order can find the master image
immediately. Nothing here calls Etsy or Getvela."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.schemas import (
    DriveArchiveHistoryResponse,
    DriveArchivePendingCountResponse,
    DriveArchiveRecordOut,
    DriveArchiveSyncResponse,
)
from app.memory.drive_archive_memory import find_by_sku, not_yet_archived_artworks, recent_archives
from app.pipeline.drive_archive import archive_artworks
from app.providers.factory import build_registry

router = APIRouter(prefix="/api/drive-archive", tags=["drive-archive"])


def _to_out(record) -> DriveArchiveRecordOut:
    return DriveArchiveRecordOut(
        artwork_id=record.artwork_id,
        sku=record.sku,
        drive_file_id=record.drive_file_id,
        drive_file_url=record.drive_file_url,
        created_at=record.created_at,
    )


@router.get("/pending-count", response_model=DriveArchivePendingCountResponse)
def get_pending_count(session: Session = Depends(get_db)) -> DriveArchivePendingCountResponse:
    pending = not_yet_archived_artworks(session, limit=10_000)
    return DriveArchivePendingCountResponse(pending_count=len(pending))


@router.post("/sync", response_model=DriveArchiveSyncResponse)
def sync_to_drive(limit: int = Query(default=50, ge=1, le=200), session: Session = Depends(get_db)) -> DriveArchiveSyncResponse:
    artworks = not_yet_archived_artworks(session, limit=limit)
    if not artworks:
        raise HTTPException(status_code=404, detail="no approved artworks are waiting for a Drive archive")

    registry = build_registry()
    records = asyncio.run(archive_artworks(session, registry, artworks=artworks))
    return DriveArchiveSyncResponse(
        archived_count=len(records),
        failed_count=len(artworks) - len(records),
        skus=[r.sku for r in records],
    )


@router.get("/lookup", response_model=DriveArchiveRecordOut)
def lookup_by_sku(sku: str, session: Session = Depends(get_db)) -> DriveArchiveRecordOut:
    record = find_by_sku(session, sku=sku)
    if record is None:
        raise HTTPException(status_code=404, detail=f"no Drive archive record for SKU '{sku}'")
    return _to_out(record)


@router.get("/records", response_model=DriveArchiveHistoryResponse)
def get_archive_history(session: Session = Depends(get_db)) -> DriveArchiveHistoryResponse:
    records = recent_archives(session)
    return DriveArchiveHistoryResponse(items=[_to_out(r) for r in records])
