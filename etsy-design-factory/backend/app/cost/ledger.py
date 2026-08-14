"""Every paid (or simulated) operation is recorded here. See
docs/DATABASE.md `cost_events` and docs/DOMAIN_MODEL.md invariant 4: no
CostEvent exists without a provider call actually made."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models.cost import CostEvent


def record_cost(
    session: Session,
    *,
    provider: str,
    model: str,
    operation: str,
    generation_cost_usd: float = 0.0,
    processing_cost_usd: float = 0.0,
    tokens_input: int | None = None,
    tokens_output: int | None = None,
    collection_id: uuid.UUID | None = None,
    design_genome_id: uuid.UUID | None = None,
    generation_candidate_id: uuid.UUID | None = None,
    is_simulated: bool | None = None,
) -> CostEvent:
    if is_simulated is None:
        is_simulated = get_settings().provider_mode == "fake" or get_settings().is_test
    event = CostEvent(
        provider=provider,
        model=model,
        operation=operation,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        generation_cost_usd=generation_cost_usd,
        processing_cost_usd=processing_cost_usd,
        collection_id=collection_id,
        design_genome_id=design_genome_id,
        generation_candidate_id=generation_candidate_id,
        is_simulated=is_simulated,
    )
    session.add(event)
    session.flush()
    return event
