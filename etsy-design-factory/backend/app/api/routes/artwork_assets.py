"""Public image serving for approved artwork assets (print exports,
mockups) -- streamed through the StorageProvider, same pattern as
app/api/routes/candidates.py's candidate image endpoint. These are what
app/pipeline/getvela_export.py's Photo columns point at: Getvela fetches
them over the internet, so this route (behind PUBLIC_BASE_URL) must
actually be reachable from outside this deployment."""

from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models.artwork import Mockup, PrintExport
from app.providers.factory import build_registry

router = APIRouter(prefix="/api", tags=["artwork-assets"])


async def _fetch_image(storage_key: str) -> bytes:
    registry = build_registry()
    try:
        return await registry.call("storage.default", "get", key=storage_key)
    except Exception as exc:  # noqa: BLE001 - surfaced as a clean 404/502, not a stack trace
        raise HTTPException(status_code=502, detail="could not load image from storage") from exc


@router.get("/print-exports/{print_export_id}/image")
def get_print_export_image(print_export_id: uuid.UUID, session: Session = Depends(get_db)) -> Response:
    print_export = session.get(PrintExport, print_export_id)
    if print_export is None:
        raise HTTPException(status_code=404, detail="print export not found")
    data = asyncio.run(_fetch_image(print_export.storage_key))
    return Response(content=data, media_type="image/png")


@router.get("/mockups/{mockup_id}/image")
def get_mockup_image(mockup_id: uuid.UUID, session: Session = Depends(get_db)) -> Response:
    mockup = session.get(Mockup, mockup_id)
    if mockup is None:
        raise HTTPException(status_code=404, detail="mockup not found")
    data = asyncio.run(_fetch_image(mockup.storage_key))
    return Response(content=data, media_type="image/png")
