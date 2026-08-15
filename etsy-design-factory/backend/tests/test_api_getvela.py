import asyncio
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.db.models.artwork import Artwork
from app.genome.codec import to_row
from app.main import app
from app.pipeline.concept_generation import create_concept
from app.pipeline.etsy_package import build_etsy_package
from app.pipeline.generation import generate_candidate
from app.pipeline.mockup_factory import generate_all_mockups
from app.pipeline.print_factory import export_all_ratios
from tests.factories import make_genome


async def _make_approved_listing(db_session, registry, collection):
    genome = make_genome(collection_id=collection.id)
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
    print_exports = await export_all_ratios(
        db_session, registry, artwork=artwork, genome=genome, ratios=("2:3", "3:4", "4:5")
    )
    mockups = await generate_all_mockups(db_session, registry, artwork=artwork, template_ids=["living_room_light_frame"])
    build_etsy_package(
        db_session, artwork=artwork, genome=genome, collection=collection, print_exports=print_exports, mockups=mockups
    )
    db_session.commit()
    return artwork


def test_export_requires_public_base_url(db_session, registry, collection, monkeypatch):
    from app.config import get_settings

    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    get_settings.cache_clear()

    asyncio.run(_make_approved_listing(db_session, registry, collection))

    client = TestClient(app)
    resp = client.post("/api/getvela/export", json={"requested_by": "tester"})
    assert resp.status_code == 400
    assert "PUBLIC_BASE_URL" in resp.json()["detail"]
    get_settings.cache_clear()


def test_export_returns_csv_and_records_batch_so_rerun_excludes_it(db_session, registry, collection, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("PUBLIC_BASE_URL", "https://factory.example.com")
    get_settings.cache_clear()

    artwork = asyncio.run(_make_approved_listing(db_session, registry, collection))

    client = TestClient(app)
    resp = client.get("/api/getvela/pending-count")
    assert resp.status_code == 200
    assert resp.json()["pending_count"] == 1

    resp = client.post("/api/getvela/export", json={"requested_by": "tester"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["listing_count"] == 1
    assert body["row_count"] == 3
    assert artwork.sku in body["skus"]
    assert artwork.sku in body["csv"]
    assert body["csv"].splitlines()[0].startswith("Title,Description,Category")

    # a second call with nothing new to export returns 404, not an empty CSV
    resp2 = client.post("/api/getvela/export", json={"requested_by": "tester"})
    assert resp2.status_code == 404

    resp3 = client.get("/api/getvela/pending-count")
    assert resp3.json()["pending_count"] == 0

    resp4 = client.get("/api/getvela/exports")
    assert resp4.status_code == 200
    history = resp4.json()["items"]
    assert len(history) == 1
    assert history[0]["listing_count"] == 1
    assert history[0]["requested_by"] == "tester"

    get_settings.cache_clear()


def test_print_export_and_mockup_image_endpoints_serve_real_bytes(db_session, registry, collection):
    artwork = asyncio.run(_make_approved_listing(db_session, registry, collection))

    from app.db.models.artwork import Mockup, PrintExport

    print_export = db_session.query(PrintExport).filter(PrintExport.artwork_id == artwork.id).first()
    mockup = db_session.query(Mockup).filter(Mockup.artwork_id == artwork.id).first()

    client = TestClient(app)
    resp = client.get(f"/api/print-exports/{print_export.id}/image")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert len(resp.content) > 0

    resp2 = client.get(f"/api/mockups/{mockup.id}/image")
    assert resp2.status_code == 200
    assert resp2.headers["content-type"] == "image/png"
    assert len(resp2.content) > 0

    resp3 = client.get("/api/print-exports/00000000-0000-0000-0000-000000000000/image")
    assert resp3.status_code == 404
