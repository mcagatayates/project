import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models.artwork import Artwork
from app.memory.getvela_export_memory import not_yet_exported_artworks, recent_batches, record_batch


def _make_artwork(db_session, collection, *, sku: str) -> Artwork:
    artwork = Artwork(
        generation_candidate_id=uuid.uuid4(),
        design_genome_id=uuid.uuid4(),
        collection_id=collection.id,
        master_storage_key="x",
        master_width_px=512,
        master_height_px=512,
        approved_at=datetime.now(timezone.utc),
        approved_by="test",
        sku=sku,
    )
    db_session.add(artwork)
    db_session.flush()
    return artwork


def test_not_yet_exported_artworks_excludes_already_recorded(db_session, collection):
    a1 = _make_artwork(db_session, collection, sku="WA-AAAA1111")
    a2 = _make_artwork(db_session, collection, sku="WA-BBBB2222")

    pending_before = not_yet_exported_artworks(db_session)
    assert {a.id for a in pending_before} == {a1.id, a2.id}

    record_batch(db_session, requested_by="tester", artwork_ids=[a1.id], row_count=3)

    pending_after = not_yet_exported_artworks(db_session)
    assert {a.id for a in pending_after} == {a2.id}


def test_record_batch_is_idempotent_per_artwork_via_unique_constraint(db_session, collection):
    a1 = _make_artwork(db_session, collection, sku="WA-CCCC3333")
    record_batch(db_session, requested_by="tester", artwork_ids=[a1.id], row_count=3)
    db_session.commit()

    with pytest.raises(IntegrityError):
        record_batch(db_session, requested_by="tester-again", artwork_ids=[a1.id], row_count=3)
    db_session.rollback()


def test_recent_batches_orders_newest_first(db_session, collection):
    a1 = _make_artwork(db_session, collection, sku="WA-DDDD4444")
    a2 = _make_artwork(db_session, collection, sku="WA-EEEE5555")

    b1 = record_batch(db_session, requested_by="tester", artwork_ids=[a1.id], row_count=3)
    b2 = record_batch(db_session, requested_by="tester", artwork_ids=[a2.id], row_count=3)

    batches = recent_batches(db_session)
    assert batches[0].id == b2.id
    assert batches[1].id == b1.id


def test_not_yet_exported_artworks_filters_by_collection(db_session, collection):
    from app.db.models.collection import Collection
    from app.db.models.enums import CollectionStatus, ProductionMode

    other = Collection(
        name="Other Collection",
        thesis="x",
        target_aesthetic="x",
        target_customer_hypothesis="x",
        palette_boundaries={"allowed_palette_names": ["sage-clay"]},
        medium="ink",
        subject_families=["landscape"],
        composition_diversity_requirements={"min_layout_types": 2},
        target_design_count=10,
        experimental_variables={},
        status=CollectionStatus.DISCOVERY.value,
        mode=ProductionMode.DISCOVERY.value,
    )
    db_session.add(other)
    db_session.flush()

    a1 = _make_artwork(db_session, collection, sku="WA-FFFF6666")
    _a2 = _make_artwork(db_session, other, sku="WA-GGGG7777")

    pending = not_yet_exported_artworks(db_session, collection_id=collection.id)
    assert {a.id for a in pending} == {a1.id}
