import asyncio
from datetime import datetime, timezone

from app.db.models.artwork import Artwork
from app.genome.codec import to_row
from app.pipeline.diversity_control import run_diversity_control
from app.pipeline.generation import generate_candidate
from app.pipeline.vision_qc import run_vision_qc
from tests.factories import make_genome


async def _make_approved_artwork(db_session, registry, collection, genome):
    from app.pipeline.concept_generation import create_concept

    genome_row = to_row(genome)
    db_session.add(genome_row)
    db_session.flush()
    concept = create_concept(
        db_session,
        genome_row=genome_row,
        collection=collection,
        production_mode="PRODUCTION",
        planned_candidate_count=1,
    )
    candidate = await generate_candidate(
        db_session,
        registry,
        concept=concept,
        genome=genome,
        attempt_number=1,
        collection_thesis=collection.thesis,
        quality_seed=0.9,
    )
    await run_vision_qc(db_session, registry, candidate=candidate, genome=genome)

    artwork = Artwork(
        generation_candidate_id=candidate.id,
        design_genome_id=genome.id,
        collection_id=collection.id,
        master_storage_key=candidate.storage_key,
        master_width_px=candidate.width_px,
        master_height_px=candidate.height_px,
        approved_at=datetime.now(timezone.utc),
        approved_by="test",
        sku=f"WA-{candidate.id.hex[:8].upper()}",
    )
    db_session.add(artwork)
    db_session.flush()
    return artwork, candidate


def test_near_identical_genome_and_pixels_is_rejected_as_duplicate(db_session, registry, collection):
    genome_a = make_genome(collection_id=collection.id)
    asyncio.run(_make_approved_artwork(db_session, registry, collection, genome_a))

    # Same genome content (new id/lineage) generated with the SAME variation
    # seed via attempt_number=1 -> should render near-identical pixels.
    genome_b = make_genome(collection_id=collection.id)

    from app.pipeline.concept_generation import create_concept

    genome_b_row = to_row(genome_b)
    db_session.add(genome_b_row)
    db_session.flush()
    concept_b = create_concept(
        db_session,
        genome_row=genome_b_row,
        collection=collection,
        production_mode="PRODUCTION",
        planned_candidate_count=1,
    )

    candidate_b = asyncio.run(
        generate_candidate(
            db_session,
            registry,
            concept=concept_b,
            genome=genome_b,
            attempt_number=1,
            collection_thesis=collection.thesis,
            quality_seed=0.9,
        )
    )
    asyncio.run(run_vision_qc(db_session, registry, candidate=candidate_b, genome=genome_b))

    from app.db.models.enums import CandidateStatus

    candidate_b.status = CandidateStatus.SELECTED.value
    db_session.flush()

    kept, conflict = run_diversity_control(db_session, candidate=candidate_b, genome=genome_b)
    assert kept is False
    assert conflict is not None
    assert candidate_b.status == CandidateStatus.ELIMINATED.value
    assert candidate_b.elimination_reason is not None


def test_genuinely_different_design_is_kept(db_session, registry, collection):
    genome_a = make_genome(collection_id=collection.id)
    asyncio.run(_make_approved_artwork(db_session, registry, collection, genome_a))

    from app.genome.schema import (
        Balance,
        CompositionDNA,
        LayoutType,
        PaletteDNA,
        SubjectCategory,
        SubjectDNA,
        Temperature,
    )

    genome_b = make_genome(
        collection_id=collection.id,
        subject_dna=SubjectDNA(
            primary_subject="desert cacti at dusk", subject_category=SubjectCategory.LANDSCAPE, subject_tags=["desert"]
        ),
        composition_dna=CompositionDNA(
            layout_type=LayoutType.REPEATING_PATTERN,
            focal_point="horizon line",
            negative_space_ratio=0.15,
            balance=Balance.RADIAL,
        ),
        palette_dna=PaletteDNA(
            palette_name="ochre-ink",
            primary_colors=["#C98A2C"],
            accent_colors=["#22303C"],
            background_color="#F7F1E1",
            saturation_level=0.6,
            contrast_level=0.7,
            temperature=Temperature.WARM,
        ),
    )

    from app.pipeline.concept_generation import create_concept

    genome_b_row = to_row(genome_b)
    db_session.add(genome_b_row)
    db_session.flush()
    concept_b = create_concept(
        db_session,
        genome_row=genome_b_row,
        collection=collection,
        production_mode="PRODUCTION",
        planned_candidate_count=1,
    )

    candidate_b = asyncio.run(
        generate_candidate(
            db_session,
            registry,
            concept=concept_b,
            genome=genome_b,
            attempt_number=7,
            collection_thesis=collection.thesis,
            quality_seed=0.9,
        )
    )
    asyncio.run(run_vision_qc(db_session, registry, candidate=candidate_b, genome=genome_b))

    from app.db.models.enums import CandidateStatus

    candidate_b.status = CandidateStatus.SELECTED.value
    db_session.flush()

    kept, conflict = run_diversity_control(db_session, candidate=candidate_b, genome=genome_b)
    assert kept is True
    assert conflict is None
    assert candidate_b.status == CandidateStatus.SELECTED.value
