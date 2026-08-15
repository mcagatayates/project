"""Getvela CSV export -- see app/pipeline/getvela_export.py. Triggers a
CSV of approved-but-not-yet-exported artworks; the human downloads it and
imports it through Getvela's own "Import" button. Nothing here calls
Getvela or Etsy over the network."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.schemas import (
    GetvelaExportBatchOut,
    GetvelaExportHistoryResponse,
    GetvelaExportRequest,
    GetvelaExportResponse,
    GetvelaPendingCountResponse,
)
from app.memory.getvela_export_memory import not_yet_exported_artworks, recent_batches, record_batch
from app.pipeline.getvela_export import build_export_for_artworks

router = APIRouter(prefix="/api/getvela", tags=["getvela"])


@router.get("/pending-count", response_model=GetvelaPendingCountResponse)
def get_pending_count(session: Session = Depends(get_db)) -> GetvelaPendingCountResponse:
    pending = not_yet_exported_artworks(session, limit=10_000)
    return GetvelaPendingCountResponse(pending_count=len(pending))


@router.post("/export", response_model=GetvelaExportResponse)
def export_to_getvela(body: GetvelaExportRequest, session: Session = Depends(get_db)) -> GetvelaExportResponse:
    artworks = not_yet_exported_artworks(session, collection_id=body.collection_id, limit=body.limit)
    if not artworks:
        raise HTTPException(status_code=404, detail="no approved artworks are waiting for a Getvela export")

    try:
        csv_text, skus, row_count = build_export_for_artworks(session, artworks=artworks)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    batch = record_batch(
        session, requested_by=body.requested_by, artwork_ids=[a.id for a in artworks], row_count=row_count
    )
    return GetvelaExportResponse(
        batch_id=batch.id, listing_count=len(artworks), row_count=row_count, skus=skus, csv=csv_text
    )


@router.get("/exports", response_model=GetvelaExportHistoryResponse)
def get_export_history(session: Session = Depends(get_db)) -> GetvelaExportHistoryResponse:
    batches = recent_batches(session)
    return GetvelaExportHistoryResponse(
        items=[
            GetvelaExportBatchOut(
                id=b.id,
                requested_by=b.requested_by,
                listing_count=b.listing_count,
                row_count=b.row_count,
                created_at=b.created_at,
            )
            for b in batches
        ]
    )
