"""Concept Gate: cheap check before any paid image generation happens."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.cost.ledger import record_cost
from app.db.models.collection import Collection
from app.db.models.concept import Concept
from app.db.models.enums import GateStatus
from app.db.models.genome import DesignGenome as DesignGenomeRow
from app.genome.codec import from_row
from app.providers.base import LLMResult
from app.providers.registry import ProviderRegistry


async def gate_concept(
    session: Session,
    registry: ProviderRegistry,
    *,
    concept: Concept,
    genome_row: DesignGenomeRow,
    collection: Collection,
) -> Concept:
    genome = from_row(genome_row)

    boundaries = collection.palette_boundaries or {}
    allowed_names = boundaries.get("allowed_palette_names")
    if allowed_names and genome.palette_dna.palette_name not in allowed_names:
        concept.gate_status = GateStatus.REJECTED.value
        concept.gate_reasoning = (
            f"palette '{genome.palette_dna.palette_name}' is outside collection "
            f"palette boundaries {allowed_names} — rejected without a provider call."
        )
        session.flush()
        return concept

    result: LLMResult = await registry.call(
        "llm.cheap",
        "complete",
        system="You are a concept gate for a print-on-demand wall-art factory. "
        "Reject concepts that are incoherent or violate the collection brief.",
        prompt=(
            f"Subject: {genome.subject_dna.primary_subject}. Style: {genome.style_dna.art_movement}. "
            f"Collection thesis: {collection.thesis}."
        ),
        temperature=0.1,
        max_tokens=200,
    )
    record_cost(
        session,
        provider=registry.get("llm.cheap").name,
        model="concept-gate",
        operation="concept_gate",
        generation_cost_usd=result.cost_usd,
        tokens_input=result.tokens_input,
        tokens_output=result.tokens_output,
        collection_id=collection.id,
        design_genome_id=genome_row.id,
    )

    concept.gate_status = GateStatus.PASSED.value
    concept.gate_reasoning = result.text
    session.flush()
    return concept
