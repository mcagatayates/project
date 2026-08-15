import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.db.models.artwork import Artwork
from app.main import app


def _make_artwork(db_session, collection, *, sku: str, storage_key: str) -> Artwork:
    artwork = Artwork(
        generation_candidate_id=uuid.uuid4(),
        design_genome_id=uuid.uuid4(),
        collection_id=collection.id,
        master_storage_key=storage_key,
        master_width_px=512,
        master_height_px=512,
        approved_at=datetime.now(timezone.utc),
        approved_by="test",
        sku=sku,
    )
    db_session.add(artwork)
    db_session.flush()
    return artwork


def test_sync_uploads_pending_artworks_and_lookup_finds_them(db_session, registry, collection):
    import asyncio

    artwork = _make_artwork(db_session, collection, sku="WA-11112222", storage_key="masters/z/master.png")
    asyncio.run(registry.call("storage.default", "put", key=artwork.master_storage_key, data=b"real-bytes"))
    db_session.commit()

    client = TestClient(app)

    resp = client.get("/api/drive-archive/pending-count")
    assert resp.status_code == 200
    assert resp.json()["pending_count"] == 1

    resp = client.post("/api/drive-archive/sync")
    assert resp.status_code == 200
    body = resp.json()
    assert body["archived_count"] == 1
    assert body["failed_count"] == 0
    assert artwork.sku in body["skus"]

    resp2 = client.get("/api/drive-archive/pending-count")
    assert resp2.json()["pending_count"] == 0

    resp3 = client.get(f"/api/drive-archive/lookup?sku={artwork.sku}")
    assert resp3.status_code == 200
    lookup = resp3.json()
    assert lookup["sku"] == artwork.sku
    assert lookup["drive_file_url"]

    resp4 = client.get("/api/drive-archive/lookup?sku=NOT-A-REAL-SKU")
    assert resp4.status_code == 404

    resp5 = client.get("/api/drive-archive/records")
    assert resp5.status_code == 200
    assert len(resp5.json()["items"]) == 1


def test_sync_returns_404_when_nothing_pending(db_session, registry, collection):
    client = TestClient(app)
    resp = client.post("/api/drive-archive/sync")
    assert resp.status_code == 404
