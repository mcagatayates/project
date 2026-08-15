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
    build_export_for_artworks,
    build_listing_rows,
    get_pricing_policy,
    get_shop_defaults,
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


def test_build_listing_rows_one_row_per_ratio_with_continuation_rows_blank(db_session, registry, collection):
    genome = make_genome(collection_id=collection.id)
    artwork, package, print_exports, mockups = asyncio.run(_make_listing(db_session, registry, collection, genome))

    rows = build_listing_rows(
        artwork=artwork,
        package=package,
        collection=collection,
        print_exports=print_exports,
        mockups=mockups,
        public_base_url="https://factory.example.com",
    )

    assert len(rows) == 3
    assert rows[0]["Title"] == package.title_concepts[0][:140]
    assert rows[0]["SKU"] == artwork.sku
    assert rows[0]["Product type"] == "Physical"
    assert rows[0]["Photo 1"].startswith("https://factory.example.com/api/mockups/")
    # continuation rows carry no listing-level fields, only the variation block
    for row in rows[1:]:
        assert row["Title"] == ""
        assert row["Description"] == ""
        assert row["SKU"] == ""
        assert row["Photo 1"] == ""
        assert row["Var SKU"] != ""
        assert row["Var Price"] != ""


def test_build_listing_rows_prices_scale_by_size_multiplier(db_session, registry, collection):
    genome = make_genome(collection_id=collection.id)
    artwork, package, print_exports, mockups = asyncio.run(_make_listing(db_session, registry, collection, genome))

    pricing = {
        "default_base_price_usd": 20.0,
        "collection_base_price_usd": {},
        "size_price_multiplier": {"4:5": 1.0, "3:4": 1.2, "2:3": 1.5},
    }
    rows = build_listing_rows(
        artwork=artwork,
        package=package,
        collection=collection,
        print_exports=print_exports,
        mockups=mockups,
        public_base_url="https://factory.example.com",
        pricing=pricing,
    )
    by_ratio = {}
    for pe, row in zip(print_exports, rows, strict=False):
        by_ratio[pe.ratio] = float(row["Var Price"])

    assert by_ratio["4:5"] == pytest.approx(20.0)
    assert by_ratio["3:4"] == pytest.approx(24.0)
    assert by_ratio["2:3"] == pytest.approx(30.0)
    # listing-level Price is the lowest variation price
    assert float(rows[0]["Price"]) == pytest.approx(20.0)


def test_build_listing_rows_uses_collection_override_price(db_session, registry, collection):
    genome = make_genome(collection_id=collection.id)
    artwork, package, print_exports, mockups = asyncio.run(
        _make_listing(db_session, registry, collection, genome, ratios=("4:5",))
    )

    pricing = {
        "default_base_price_usd": 18.0,
        "collection_base_price_usd": {collection.name: 30.0},
        "size_price_multiplier": {"4:5": 1.0},
    }
    rows = build_listing_rows(
        artwork=artwork,
        package=package,
        collection=collection,
        print_exports=print_exports,
        mockups=mockups,
        public_base_url="https://factory.example.com",
        pricing=pricing,
    )
    assert float(rows[0]["Var Price"]) == pytest.approx(30.0)


def test_build_listing_rows_raises_on_artwork_without_known_ratio_exports(db_session, registry, collection):
    genome = make_genome(collection_id=collection.id)
    artwork, package, _print_exports, mockups = asyncio.run(
        _make_listing(db_session, registry, collection, genome, ratios=("2:3",))
    )
    with pytest.raises(ValueError, match="no print exports"):
        build_listing_rows(
            artwork=artwork,
            package=package,
            collection=collection,
            print_exports=[],  # simulate a design with no eligible print exports
            mockups=mockups,
            public_base_url="https://factory.example.com",
        )


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
    assert row_count == 6  # 3 ratios per artwork x 2 artworks
    assert csv_text.count(artwork1.sku) >= 1
    assert csv_text.count(artwork2.sku) >= 1

    get_settings.cache_clear()


def test_shop_defaults_and_pricing_load_from_real_config_files():
    shop = get_shop_defaults()
    assert shop["product_type"] == "Physical"
    assert set(shop["size_labels"]) == {"2:3", "3:4", "4:5"}

    pricing = get_pricing_policy()
    assert pricing["default_base_price_usd"] > 0
    assert set(pricing["size_price_multiplier"]) == {"2:3", "3:4", "4:5"}
