"""Human Approval: structured actions that either finalize a candidate or
mutate its DesignGenome and re-enter the pipeline. Never concatenates text
onto a prompt — see docs/DESIGN_GENOME_SCHEMA.md."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models.approval import Approval
from app.db.models.artwork import Artwork
from app.db.models.collection import Collection
from app.db.models.concept import Concept
from app.db.models.enums import ApprovalAction, CandidateStatus
from app.db.models.generation import GenerationCandidate
from app.db.models.genome import DesignGenome as DesignGenomeRow
from app.genome.codec import from_row, to_row
from app.genome.mutation import apply_approval_action
from app.pipeline.concept_generation import create_concept

GENOME_MUTATING_ACTIONS = {
    ApprovalAction.MORE_ORIGINAL.value,
    ApprovalAction.CLOSER_TO_COLLECTION.value,
    ApprovalAction.CHANGE_COMPOSITION.value,
    ApprovalAction.CHANGE_PALETTE.value,
    ApprovalAction.MORE_TEXTURE.value,
    ApprovalAction.LESS_TEXTURE.value,
    ApprovalAction.MORE_MINIMAL.value,
    ApprovalAction.MORE_DETAILED.value,
    ApprovalAction.CREATE_VARIATIONS.value,
}


def _generate_sku(artwork_id: uuid.UUID) -> str:
    return f"WA-{artwork_id.hex[:10].upper()}"


def apply_approval(
    session: Session,
    *,
    candidate: GenerationCandidate,
    action: str,
    actor: str,
    notes: str | None = None,
    collection: Collection,
) -> tuple[Approval, Artwork | None, Concept | None]:
    """Returns (approval_row, artwork_or_none, new_concept_or_none)."""
    resulting_genome_id: uuid.UUID | None = None
    artwork: Artwork | None = None
    new_concept: Concept | None = None

    if action == ApprovalAction.APPROVE.value:
        candidate.status = CandidateStatus.APPROVED.value
        artwork = Artwork(
            generation_candidate_id=candidate.id,
            design_genome_id=candidate.design_genome_id,
            collection_id=collection.id,
            master_storage_key=candidate.storage_key,
            master_width_px=candidate.width_px,
            master_height_px=candidate.height_px,
            approved_at=datetime.now(timezone.utc),
            approved_by=actor,
            sku="PENDING",
        )
        session.add(artwork)
        session.flush()
        artwork.sku = _generate_sku(artwork.id)
        session.flush()

    elif action == ApprovalAction.REJECT.value:
        candidate.status = CandidateStatus.REJECTED.value

    elif action in GENOME_MUTATING_ACTIONS:
        genome_row = session.get(DesignGenomeRow, candidate.design_genome_id)
        if genome_row is None:
            raise ValueError(f"design genome {candidate.design_genome_id} not found")
        genome = from_row(genome_row)
        edited = apply_approval_action(genome, action)
        edited_row = to_row(edited)
        session.add(edited_row)
        session.flush()
        resulting_genome_id = edited_row.id

        new_concept = create_concept(
            session,
            genome_row=edited_row,
            collection=collection,
            production_mode="DISCOVERY",
            planned_candidate_count=1 if action != ApprovalAction.CREATE_VARIATIONS.value else 3,
        )
        candidate.status = CandidateStatus.REJECTED.value
    else:
        raise ValueError(f"unknown approval action '{action}'")

    approval = Approval(
        generation_candidate_id=candidate.id,
        action=action,
        actor=actor,
        resulting_genome_id=resulting_genome_id,
        notes=notes,
    )
    session.add(approval)
    session.flush()
    return approval, artwork, new_concept
