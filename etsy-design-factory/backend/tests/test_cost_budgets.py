import datetime

from app.cost.budgets import (
    cost_for_collection,
    cost_per_approved_design,
    daily_spend,
    get_budget_status,
    monthly_spend,
)
from app.cost.ledger import record_cost


def test_daily_and_monthly_spend_roll_up(db_session, collection):
    record_cost(
        db_session,
        provider="fake",
        model="x",
        operation="generate",
        generation_cost_usd=1.5,
        collection_id=collection.id,
    )
    record_cost(
        db_session,
        provider="fake",
        model="x",
        operation="generate",
        generation_cost_usd=2.5,
        collection_id=collection.id,
    )
    db_session.flush()

    today = datetime.datetime.now(datetime.timezone.utc).date()
    assert daily_spend(db_session, on_date=today) == 4.0
    assert monthly_spend(db_session, year=today.year, month=today.month) == 4.0
    assert cost_for_collection(db_session, collection_id=collection.id) == 4.0


def test_cost_per_approved_design_is_none_without_approvals(db_session, collection):
    record_cost(
        db_session,
        provider="fake",
        model="x",
        operation="generate",
        generation_cost_usd=3.0,
        collection_id=collection.id,
    )
    db_session.flush()
    assert cost_per_approved_design(db_session, collection_id=collection.id) is None


def test_cost_per_approved_design_divides_correctly(db_session, collection):
    import uuid
    from datetime import timezone

    from app.db.models.artwork import Artwork

    record_cost(
        db_session,
        provider="fake",
        model="x",
        operation="generate",
        generation_cost_usd=10.0,
        collection_id=collection.id,
    )
    for _ in range(2):
        db_session.add(
            Artwork(
                generation_candidate_id=uuid.uuid4(),
                design_genome_id=uuid.uuid4(),
                collection_id=collection.id,
                master_storage_key="x",
                master_width_px=512,
                master_height_px=512,
                approved_at=datetime.datetime.now(timezone.utc),
                approved_by="test",
                sku=f"WA-{uuid.uuid4().hex[:8].upper()}",
            )
        )
    db_session.flush()
    assert cost_per_approved_design(db_session, collection_id=collection.id) == 5.0


def test_budget_status_reports_remaining_and_exceeded(db_session):
    today = datetime.datetime.now(datetime.timezone.utc).date()
    status = get_budget_status(db_session, on_date=today)
    assert status.daily_spent_usd == 0
    assert status.daily_remaining_usd == status.daily_budget_usd
    assert status.daily_exceeded is False

    record_cost(
        db_session, provider="fake", model="x", operation="generate", generation_cost_usd=status.daily_budget_usd + 1
    )
    db_session.flush()
    status2 = get_budget_status(db_session, on_date=today)
    assert status2.daily_exceeded is True
    assert status2.daily_remaining_usd == 0
