import asyncio
import uuid
from datetime import datetime, timezone

from app.db.models.artwork import Artwork
from app.memory.drive_archive_memory import (
    find_by_sku,
    not_yet_archived_artworks,
    recent_archives,
    record_archive,
)
from app.pipeline.drive_archive import archive_artwork, archive_artworks
from app.providers.base import ProviderError


def _make_artwork(db_session, collection, *, sku: str, storage_key: str = "masters/x/master.png") -> Artwork:
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


async def _seed_master_image(registry, storage_key: str) -> None:
    await registry.call("storage.default", "put", key=storage_key, data=b"fake-png-bytes")


def test_archive_artwork_uploads_and_records(db_session, registry, collection):
    artwork = _make_artwork(db_session, collection, sku="WA-AAAA1111", storage_key="masters/a/master.png")
    asyncio.run(_seed_master_image(registry, artwork.master_storage_key))

    record = asyncio.run(archive_artwork(db_session, registry, artwork=artwork))

    assert record.artwork_id == artwork.id
    assert record.sku == "WA-AAAA1111"
    assert record.drive_file_id
    assert record.drive_file_url

    looked_up = find_by_sku(db_session, sku="WA-AAAA1111")
    assert looked_up is not None
    assert looked_up.drive_file_url == record.drive_file_url


def test_fake_drive_provider_is_deterministic_per_filename_and_content():
    from app.providers.fake.drive_archive import FakeDriveArchiveProvider

    provider = FakeDriveArchiveProvider()
    r1 = asyncio.run(provider.upload(filename="WA-X.png", data=b"same-bytes"))
    r2 = asyncio.run(provider.upload(filename="WA-X.png", data=b"same-bytes"))
    r3 = asyncio.run(provider.upload(filename="WA-Y.png", data=b"same-bytes"))
    assert r1.file_id == r2.file_id
    assert r1.file_id != r3.file_id


def test_not_yet_archived_artworks_excludes_already_recorded(db_session, collection):
    a1 = _make_artwork(db_session, collection, sku="WA-CCCC3333")
    a2 = _make_artwork(db_session, collection, sku="WA-DDDD4444")

    pending_before = not_yet_archived_artworks(db_session)
    assert {a.id for a in pending_before} == {a1.id, a2.id}

    record_archive(db_session, artwork_id=a1.id, sku=a1.sku, drive_file_id="fake-1", drive_file_url="https://x/1")

    pending_after = not_yet_archived_artworks(db_session)
    assert {a.id for a in pending_after} == {a2.id}


def test_archive_artworks_batch_skips_failures_without_aborting(db_session, registry, collection, monkeypatch):
    good = _make_artwork(db_session, collection, sku="WA-EEEE5555", storage_key="masters/e/master.png")
    asyncio.run(_seed_master_image(registry, good.master_storage_key))
    bad = _make_artwork(db_session, collection, sku="WA-FFFF6666", storage_key="masters/does-not-exist/master.png")

    records = asyncio.run(archive_artworks(db_session, registry, artworks=[bad, good]))

    assert len(records) == 1
    assert records[0].sku == "WA-EEEE5555"
    pending = not_yet_archived_artworks(db_session)
    assert {a.id for a in pending} == {bad.id}


def test_recent_archives_orders_newest_first(db_session, collection):
    a1 = _make_artwork(db_session, collection, sku="WA-GGGG7777")
    a2 = _make_artwork(db_session, collection, sku="WA-HHHH8888")
    r1 = record_archive(db_session, artwork_id=a1.id, sku=a1.sku, drive_file_id="fake-1", drive_file_url="https://x/1")
    r2 = record_archive(db_session, artwork_id=a2.id, sku=a2.sku, drive_file_id="fake-2", drive_file_url="https://x/2")

    archives = recent_archives(db_session)
    assert archives[0].id == r2.id
    assert archives[1].id == r1.id


def test_google_drive_provider_raises_clear_error_without_config():
    from app.providers.google_drive import GoogleDriveArchiveProvider

    provider = GoogleDriveArchiveProvider(service_account_json_path=None, folder_id=None)
    try:
        asyncio.run(provider.upload(filename="x.png", data=b"x"))
    except ProviderError as exc:
        assert "GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON" in str(exc)
        assert "GOOGLE_DRIVE_FOLDER_ID" in str(exc)
    else:
        raise AssertionError("expected ProviderError")
