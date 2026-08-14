"""Candidate grid + image serving. Images are streamed through the
StorageProvider (never a raw filesystem path handed to the client) so the
storage backend can be swapped (local -> S3) without changing the API
contract, and so a candidate id can't be used to read an arbitrary path
off disk (see docs/SECURITY "safe remote image downloading" / general
input validation requirements)."""

from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.schemas import CandidateListResponse, CandidateSummary, ScoreSummary
from app.db.models.collection import Collection
from app.db.models.concept import Concept
from app.db.models.enums import CandidateStatus
from app.db.models.evaluation import Evaluation
from app.db.models.generation import GenerationCandidate
from app.db.models.genome import DesignGenome as DesignGenomeRow
from app.providers.factory import build_registry

router = APIRouter(prefix="/api/candidates", tags=["candidates"])

_VALID_STATUSES = {s.value for s in CandidateStatus}


def _latest_evaluation(session: Session, candidate_id: uuid.UUID) -> Evaluation | None:
    stmt = (
        select(Evaluation)
        .where(Evaluation.generation_candidate_id == candidate_id)
        .order_by(Evaluation.created_at.desc())
        .limit(1)
    )
    return session.execute(stmt).scalars().first()


@router.get("", response_model=CandidateListResponse)
def list_candidates(
    session: Session = Depends(get_db),
    status: str = Query(default=CandidateStatus.AWAITING_APPROVAL.value),
    collection_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> CandidateListResponse:
    if status not in _VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"invalid status '{status}'")

    stmt = select(GenerationCandidate).where(GenerationCandidate.status == status)
    if collection_id is not None:
        stmt = stmt.join(Concept, GenerationCandidate.concept_id == Concept.id).where(
            Concept.collection_id == collection_id
        )
    stmt = stmt.order_by(GenerationCandidate.created_at.desc()).offset(offset).limit(limit)
    candidates = list(session.execute(stmt).scalars().all())

    items: list[CandidateSummary] = []
    for c in candidates:
        concept = session.get(Concept, c.concept_id)
        collection = session.get(Collection, concept.collection_id) if concept else None
        genome_row = session.get(DesignGenomeRow, c.design_genome_id)
        evaluation = _latest_evaluation(session, c.id)

        scores = None
        if evaluation is not None:
            raw = evaluation.scores()
            scores = {dim: ScoreSummary(**raw[dim]) for dim in raw}

        items.append(
            CandidateSummary(
                id=c.id,
                concept_id=c.concept_id,
                design_genome_id=c.design_genome_id,
                collection_id=collection.id if collection else None,
                collection_name=collection.name if collection else None,
                status=c.status,
                image_url=f"/api/candidates/{c.id}/image",
                width_px=c.width_px,
                height_px=c.height_px,
                is_repair=c.is_repair,
                created_at=c.created_at,
                scores=scores,
                subject=genome_row.subject_dna.get("primary_subject") if genome_row else None,
                style=genome_row.style_dna.get("art_movement") if genome_row else None,
                palette=genome_row.palette_dna.get("palette_name") if genome_row else None,
            )
        )

    return CandidateListResponse(items=items, total=len(items))


@router.get("/{candidate_id}/image")
def get_candidate_image(candidate_id: uuid.UUID, session: Session = Depends(get_db)) -> Response:
    candidate = session.get(GenerationCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="candidate not found")

    registry = build_registry()

    async def _fetch() -> bytes:
        return await registry.call("storage.default", "get", key=candidate.storage_key)

    try:
        data = asyncio.run(_fetch())
    except Exception as exc:  # noqa: BLE001 - surfaced as a clean 404/502, not a stack trace
        raise HTTPException(status_code=502, detail="could not load image from storage") from exc

    return Response(content=data, media_type="image/png")
