import asyncio
from datetime import datetime, timezone

import pytest

from app.db.models.artwork import Artwork
from app.genome.codec import to_row
from app.pipeline.concept_generation import create_concept
from app.pipeline.etsy_package import build_etsy_package
from app.pipeline.generation import generate_candidate
from app.pipeline.getvela_export import (
    CSV_HEADERS,
    VariationOffer,
    build_export_for_artworks,
    build_listing_rows,
    get_shop_defaults,
    get_variation_template,
    render_csv,
)
from app.pipeline.mockup_factory import generate_all_mockups
from app.pipeline.print_factory import export_all_ratios
from tests.factories import make_genome


async def _make_listing(db_session, registry, collection, genome, ratios=("2:3", "3:4", "4:5")):
    genome_row = to_row(genome)
    db_session.add(genome_row)
    db_session.flush()
    concept = create_concept(
        db_session, genome_row=genome_row, collection=collection, production_mode="PRODUCTION", planned_candidate_count=1
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

    print_exports = await export_all_ratios(db_session, registry, artwork=artwork, genome=genome, ratios=ratios)
    mockups = await generate_all_mockups(db_session, registry, artwork=artwork, template_ids=["living_room_light_frame"])
    package = build_etsy_package(
        db_session, artwork=artwork, genome=genome, collection=collection, print_exports=print_exports, mockups=mockups
    )
    return artwork, package, print_exports, mockups


def _custom_offers() -> tuple[VariationOffer, ...]:
    return (
        VariationOffer(size="A4 | 21x29.7 cm", material="Print Only", price_usd=25.0, visible=True),
        VariationOffer(size="A4 | 21x29.7 cm", material="Framed Canvas", price_usd=90.0, visible=True),
        VariationOffer(size="A3 | 29.7x42 cm", material="Print Only", price_usd=35.0, visible=False),
    )


def test_build_listing_rows_one_row_per_real_variation_offer(db_session, registry, collection):
    genome = make_genome(collection_id=collection.id)
    artwork, package, print_exports, mockups = asyncio.run(_make_listing(db_session, registry, collection, genome))

    rows = build_listing_rows(
        artwork=artwork,
        package=package,
        collection=collection,
        print_exports=print_exports,
        mockups=mockups,
        public_base_url="https://factory.example.com",
        variation_offers=_custom_offers(),
    )

    assert len(rows) == 3
    assert rows[0]["Title"] == package.title_concepts[0][:140]
    assert rows[0]["SKU"] == artwork.sku
    assert rows[0]["Product type"] == "Physical"
    assert rows[0]["Variation 1"] == "Size"
    assert rows[0]["V1 Option"] == "A4 | 21x29.7 cm"
    assert rows[0]["Variation 2"] == "Material"
    assert rows[0]["V2 Option"] == "Print Only"
    assert rows[0]["Var Price"] == "25.00"
    assert rows[0]["Var Visibility"] == "On"
    assert rows[0]["Photo 1"].startswith("https://factory.example.com/api/mockups/")

    # continuation rows carry no listing-level fields, only the variation block
    for row in rows[1:]:
        assert row["Title"] == ""
        assert row["Description"] == ""
        assert row["SKU"] == ""
        assert row["Photo 1"] == ""
        assert row["V1 Option"] != ""
        assert row["V2 Option"] != ""
        assert row["Var Price"] != ""

    assert rows[2]["V1 Option"] == "A3 | 29.7x42 cm"
    assert rows[2]["Var Price"] == "35.00"
    assert rows[2]["Var Visibility"] == "Off"


def test_listing_price_is_lowest_among_visible_offers_only(db_session, registry, collection):
    genome = make_genome(collection_id=collection.id)
    artwork, package, print_exports, mockups = asyncio.run(_make_listing(db_session, registry, collection, genome))

    offers = (
        VariationOffer(size="A5 | 14.8x21 cm", material="Print Only", price_usd=1.00, visible=False),
        VariationOffer(size="A4 | 21x29.7 cm", material="Print Only", price_usd=25.00, visible=True),
        VariationOffer(size="A3 | 29.7x42 cm", material="Print Only", price_usd=15.00, visible=True),
    )
    rows = build_listing_rows(
        artwork=artwork,
        package=package,
        collection=collection,
        print_exports=print_exports,
        mockups=mockups,
        public_base_url="https://factory.example.com",
        variation_offers=offers,
    )
    # the cheapest offer (1.00) is hidden (Off) -- the displayed "from"
    # price must reflect what a buyer can actually purchase, not it.
    assert rows[0]["Price"] == "15.00"


def test_render_csv_matches_real_getvela_template_headers():
    assert CSV_HEADERS[0] == "Title"
    assert CSV_HEADERS[-1] == "Digital file 5"
    assert "Var Price" in CSV_HEADERS
    assert "Photo 10" in CSV_HEADERS

    csv_text = render_csv([{h: "" for h in CSV_HEADERS}])
    header_line = csv_text.splitlines()[0]
    assert header_line == ",".join(CSV_HEADERS)


def test_build_export_for_artworks_requires_public_base_url(db_session, registry, collection, monkeypatch):
    from app.config import get_settings

    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    get_settings.cache_clear()

    genome = make_genome(collection_id=collection.id)
    artwork, _package, _print_exports, _mockups = asyncio.run(_make_listing(db_session, registry, collection, genome))

    with pytest.raises(ValueError, match="PUBLIC_BASE_URL"):
        build_export_for_artworks(db_session, artworks=[artwork])
    get_settings.cache_clear()


def test_build_export_for_artworks_produces_one_listing_per_artwork(db_session, registry, collection, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("PUBLIC_BASE_URL", "https://factory.example.com")
    get_settings.cache_clear()

    genome1 = make_genome(collection_id=collection.id)
    genome2 = make_genome(collection_id=collection.id)
    artwork1, _p1, _pe1, _m1 = asyncio.run(_make_listing(db_session, registry, collection, genome1))
    artwork2, _p2, _pe2, _m2 = asyncio.run(_make_listing(db_session, registry, collection, genome2))

    csv_text, skus, row_count = build_export_for_artworks(db_session, artworks=[artwork1, artwork2])
    assert set(skus) == {artwork1.sku, artwork2.sku}
    assert row_count == 2 * len(get_variation_template())
    assert csv_text.count(artwork1.sku) >= 1
    assert csv_text.count(artwork2.sku) >= 1

    get_settings.cache_clear()


def test_shop_defaults_load_from_real_config_file():
    shop = get_shop_defaults()
    assert shop["product_type"] == "Physical"
    assert shop["production_partners"] == "Printify"
    assert shop["variation_1_name"] == "Size"
    assert shop["variation_2_name"] == "Material"


def test_variation_template_loads_the_real_reference_grid():
    offers = get_variation_template()
    # 28 real sizes x 9 real materials, taken from an actual Getvela
    # export -- see config/getvela_variation_template.csv.
    assert len(offers) == 252
    sizes = {o.size for o in offers}
    materials = {o.material for o in offers}
    assert len(sizes) == 28
    assert len(materials) == 9
    assert "Print Only" in materials
    assert "Canvas Ready to Hang" in materials
    assert any(o.size.startswith("A1") and o.material == "Print Only" for o in offers)
