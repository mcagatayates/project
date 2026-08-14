"""Generation: Concept + DesignGenome -> GenerationCandidate.

Builds provider params FROM the genome (never a hand-written prompt), asks
the ImageGenProvider role for pixels, persists them through the
StorageProvider role, and records checksum/perceptual-hash + cost.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.cost.ledger import record_cost
from app.db.models.concept import Concept
from app.db.models.enums import CandidateStatus
from app.db.models.generation import GenerationCandidate, GenerationJob
from app.genome.compiler import compile_prompt
from app.genome.schema import DesignGenome
from app.providers.base import ImageGenResult
from app.providers.fake.image_stats import checksum_sha256, perceptual_hash
from app.providers.registry import ProviderRegistry


def build_generation_params(genome: DesignGenome, *, quality_seed: float, variation_seed: int) -> dict:
    primary_hex, background_hex = genome.primary_and_background_hex()
    return {
        "primary_color_hex": primary_hex,
        "background_color_hex": background_hex,
        "negative_space_ratio": genome.composition_dna.negative_space_ratio,
        "texture_intensity": genome.texture_dna.texture_intensity,
        "quality_seed": max(0.0, min(1.0, quality_seed)),
        "variation_seed": variation_seed,
    }


async def generate_candidate(
    session: Session,
    registry: ProviderRegistry,
    *,
    concept: Concept,
    genome: DesignGenome,
    attempt_number: int,
    collection_thesis: str | None = None,
    quality_seed: float = 0.85,
    role: str = "image_gen.exploration",
    is_repair: bool = False,
    params_override: dict | None = None,
) -> GenerationCandidate:
    prompt = compile_prompt(genome, collection_thesis=collection_thesis, variation_seed=attempt_number)
    params = params_override or build_generation_params(
        genome, quality_seed=quality_seed, variation_seed=attempt_number
    )

    idempotency_key = f"generate:{concept.id}:{attempt_number}"
    existing = session.query(GenerationJob).filter_by(idempotency_key=idempotency_key).one_or_none()
    if existing is not None:
        job = existing
    else:
        job = GenerationJob(
            concept_id=concept.id,
            attempt_number=attempt_number,
            provider=role,
            model="pending",
            compiled_prompt=prompt,
            params=params,
            status=CandidateStatus.GENERATING.value,
            idempotency_key=idempotency_key,
        )
        session.add(job)
        session.flush()

    result: ImageGenResult = await registry.call(role, "generate", prompt=prompt, width=512, height=512, params=params)

    storage_key = f"candidates/{concept.id}/{attempt_number}.png"
    await registry.call("storage.default", "put", key=storage_key, data=result.image_bytes, content_type="image/png")

    job.model = registry.get(role).name
    job.status = CandidateStatus.GENERATED.value

    candidate = GenerationCandidate(
        generation_job_id=job.id,
        concept_id=concept.id,
        design_genome_id=genome.id,
        storage_key=storage_key,
        width_px=result.width_px,
        height_px=result.height_px,
        checksum_sha256=checksum_sha256(result.image_bytes),
        perceptual_hash=perceptual_hash(result.image_bytes),
        status=CandidateStatus.GENERATED.value,
        is_repair=is_repair,
    )
    session.add(candidate)
    session.flush()

    record_cost(
        session,
        provider=job.model,
        model=job.model,
        operation="generate_candidate",
        generation_cost_usd=result.cost_usd,
        collection_id=concept.collection_id,
        design_genome_id=genome.id,
        generation_candidate_id=candidate.id,
    )
    return candidate
