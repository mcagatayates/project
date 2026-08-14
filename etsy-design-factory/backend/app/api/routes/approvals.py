"""Human Approval actions, single and bulk. Every action here is a
structured DesignGenome transform or a terminal decision (see
docs/DESIGN_GENOME_SCHEMA.md "Approval-action -> genome mutation
mapping") -- never a free-text prompt edit."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.schemas import (
    ApprovalRequest,
    ApprovalResult,
    BulkApprovalRequest,
    BulkApprovalResponse,
)
from app.db.models.collection import Collection
from app.db.models.concept import Concept
from app.db.models.enums import CandidateStatus
from app.db.models.generation import GenerationCandidate
from app.pipeline.approval import apply_approval

router = APIRouter(prefix="/api/candidates", tags=["approvals"])

_APPROVABLE_STATUSES = {
    CandidateStatus.AWAITING_APPROVAL.value,
    CandidateStatus.SELECTED.value,
}


def _apply_one(
    session: Session, candidate: GenerationCandidate, action: str, actor: str, notes: str | None
) -> ApprovalResult:
    if candidate.status not in _APPROVABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"candidate {candidate.id} is '{candidate.status}', not awaiting approval",
        )
    concept = session.get(Concept, candidate.concept_id)
    if concept is None:
        raise HTTPException(status_code=500, detail="candidate has no concept (data integrity issue)")
    collection = session.get(Collection, concept.collection_id)
    if collection is None:
        raise HTTPException(status_code=500, detail="concept has no collection (data integrity issue)")

    try:
        approval, artwork, new_concept = apply_approval(
            session, candidate=candidate, action=action, actor=actor, notes=notes, collection=collection
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ApprovalResult(
        candidate_id=candidate.id,
        action=approval.action,
        artwork_id=artwork.id if artwork else None,
        new_concept_id=new_concept.id if new_concept else None,
    )


@router.post("/{candidate_id}/approval", response_model=ApprovalResult)
def apply_single_approval(
    candidate_id: uuid.UUID, body: ApprovalRequest, session: Session = Depends(get_db)
) -> ApprovalResult:
    candidate = session.get(GenerationCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="candidate not found")
    return _apply_one(session, candidate, body.action.value, body.actor, body.notes)


@router.post("/bulk-approval", response_model=BulkApprovalResponse)
def apply_bulk_approval(body: BulkApprovalRequest, session: Session = Depends(get_db)) -> BulkApprovalResponse:
    results: list[ApprovalResult] = []
    for candidate_id in body.candidate_ids:
        candidate = session.get(GenerationCandidate, candidate_id)
        if candidate is None:
            raise HTTPException(status_code=404, detail=f"candidate {candidate_id} not found")
        results.append(_apply_one(session, candidate, body.action.value, body.actor, None))
    return BulkApprovalResponse(results=results)
