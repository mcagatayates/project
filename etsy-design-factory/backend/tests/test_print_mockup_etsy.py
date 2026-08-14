import asyncio
from datetime import datetime, timezone

from app.db.models.artwork import Artwork
from app.genome.codec import to_row
from app.pipeline.concept_generation import create_concept
from app.pipeline.etsy_package import build_etsy_package
from app.pipeline.generation import generate_candidate
from app.pipeline.mockup_factory import generate_all_mockups, get_mockup_templates
from app.pipeline.print_factory import RATIO_ASPECTS, export_all_ratios
from tests.factories import make_genome


async def _make_approved_artwork(db_session, registry, collection, genome):
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
    return artwork


def test_export_all_ratios_produces_real_pixel_dimensions_matching_aspect(db_session, registry, collection):
    genome = make_genome(collection_id=collection.id)
    artwork = asyncio.run(_make_approved_artwork(db_session, registry, collection, genome))

    exports = asyncio.run(export_all_ratios(db_session, registry, artwork=artwork, genome=genome))
    assert len(exports) == len(RATIO_ASPECTS)

    for export in exports:
        assert export.actual_width_px > 0
        assert export.actual_height_px > 0
        target_aspect = RATIO_ASPECTS[export.ratio]
        actual_aspect = export.actual_width_px / export.actual_height_px
        # portrait master -> portrait crop; compare against whichever
        # orientation the crop actually produced
        assert abs(actual_aspect - target_aspect) < 0.02 or abs(actual_aspect - 1 / target_aspect) < 0.02
        # never below the genome's recommended minimum long edge
        assert max(export.actual_width_px, export.actual_height_px) >= genome.print_dna.recommended_min_long_edge_px


def test_export_ratio_upscales_when_crop_is_smaller_than_recommended(db_session, registry, collection):
    genome = make_genome(collection_id=collection.id)
    artwork = asyncio.run(_make_approved_artwork(db_session, registry, collection, genome))

    exports = asyncio.run(export_all_ratios(db_session, registry, artwork=artwork, genome=genome, ratios=("2:3",)))
    export = exports[0]
    # master is only 512x512 (fake provider), recommended min long edge is
    # 6000 by default -- every export must have gone through a real upscale.
    assert export.upscaled is True
    assert export.upscale_provider is not None


def test_generate_mockups_are_separate_assets_from_master(db_session, registry, collection):
    genome = make_genome(collection_id=collection.id)
    artwork = asyncio.run(_make_approved_artwork(db_session, registry, collection, genome))

    mockups = asyncio.run(generate_all_mockups(db_session, registry, artwork=artwork))
    assert len(mockups) == len(get_mockup_templates())
    for m in mockups:
        assert m.storage_key != artwork.master_storage_key
        assert m.storage_key.startswith(f"mockups/{artwork.id}/")


def test_build_etsy_package_assembles_structured_data_with_no_network_call(db_session, registry, collection):
    genome = make_genome(collection_id=collection.id)
    artwork = asyncio.run(_make_approved_artwork(db_session, registry, collection, genome))

    exports = asyncio.run(
        export_all_ratios(db_session, registry, artwork=artwork, genome=genome, ratios=("2:3", "3:4"))
    )
    mockups = asyncio.run(
        generate_all_mockups(db_session, registry, artwork=artwork, template_ids=["gallery_no_frame"])
    )

    package = build_etsy_package(
        db_session, artwork=artwork, genome=genome, collection=collection, print_exports=exports, mockups=mockups
    )

    assert package.internal_sku == artwork.sku
    assert len(package.title_concepts) >= 1
    assert package.subject == genome.subject_dna.primary_subject
    assert package.style == genome.style_dna.art_movement
    assert 0 < len(package.tags) <= 13
    assert all(len(t) <= 20 for t in package.tags)
    assert len(package.print_export_ids) == 2
    assert len(package.mockup_ids) == 1
    assert package.published_at is None
    assert package.external_listing_id is None
