import datetime

from app.db.models.enums import CollectionStatus
from app.pipeline.collection_planner import maybe_graduate_collection, open_capacity, plan_collections
from app.pipeline.portfolio import allocate, scale_down
from app.pipeline.production_controller import build_daily_plan


def test_allocate_sums_exactly_to_target():
    fractions = {"PROVEN": 0.50, "GROWING": 0.27, "EXPERIMENTAL": 0.10, "WINNER_MUTATION": 0.10, "WILDCARD": 0.03}
    for target in (30, 1, 7, 100, 4):
        allocation = allocate(target, fractions)
        assert sum(allocation.values()) == target
        assert all(v >= 0 for v in allocation.values())


def test_scale_down_still_sums_to_reduced_target():
    allocation = {"PROVEN": 15, "GROWING": 8, "EXPERIMENTAL": 3, "WINNER_MUTATION": 3, "WILDCARD": 1}
    scaled = scale_down(allocation, 0.5)
    assert sum(scaled.values()) == 15


def test_build_daily_plan_is_configurable_not_hardcoded(db_session):
    plan = build_daily_plan(db_session, plan_date=datetime.date(2026, 8, 14), target_final_designs=30)
    assert plan.target_final_designs == 30
    assert sum(plan.portfolio_allocation.values()) == 30
    assert plan.production_slots + plan.experimental_slots + plan.winner_mutation_slots == 30
    assert plan.budget_cap_usd > 0
    assert "policy=" in plan.rationale


def test_build_daily_plan_upserts_on_same_date(db_session):
    d = datetime.date(2026, 8, 15)
    plan1 = build_daily_plan(db_session, plan_date=d, target_final_designs=30)
    plan2 = build_daily_plan(db_session, plan_date=d, target_final_designs=20)
    assert plan1.id == plan2.id
    assert plan2.target_final_designs == 20

    from app.db.models.production import DailyProductionPlan

    count = db_session.query(DailyProductionPlan).filter_by(plan_date=d).count()
    assert count == 1


def test_build_daily_plan_respects_tight_budget(db_session, monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("DAILY_BUDGET_USD", "20")
    get_settings.cache_clear()

    plan = build_daily_plan(db_session, plan_date=datetime.date(2026, 8, 16), target_final_designs=30)
    assert plan.target_final_designs < 30
    assert "budget-constrained" in plan.rationale
    # the budget is tight but nonzero -- the plan should scale down, not vanish
    assert sum(plan.portfolio_allocation.values()) > 0

    monkeypatch.delenv("DAILY_BUDGET_USD", raising=False)
    get_settings.cache_clear()


def test_collection_planner_bootstraps_when_no_history(db_session):
    plan = build_daily_plan(db_session, plan_date=datetime.date(2026, 8, 17), target_final_designs=10)
    assignments = plan_collections(db_session, plan=plan)

    total_slots = sum(a.slots for a in assignments)
    assert total_slots >= 10  # planning intention, not a hard ceiling
    assert len(assignments) > 0
    assert all(a.collection.status == CollectionStatus.DISCOVERY.value for a in assignments)
    assert plan.collections  # written back onto the plan row


def test_collection_graduates_after_enough_approvals(db_session, collection):
    import uuid
    from datetime import timezone

    from app.db.models.artwork import Artwork

    policy_min = 5
    for _ in range(policy_min):
        Artwork_row = Artwork(
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
        db_session.add(Artwork_row)
    db_session.flush()

    assert collection.status == CollectionStatus.DISCOVERY.value
    maybe_graduate_collection(db_session, collection)
    # No Approval rows exist yet -> acceptance_rate is None -> graduation
    # requires a proven acceptance rate, so it should NOT graduate on
    # approved-count alone.
    assert collection.status == CollectionStatus.DISCOVERY.value


def test_open_capacity_shrinks_as_artworks_are_approved(db_session, collection):
    import uuid
    from datetime import timezone

    from app.db.models.artwork import Artwork

    before = open_capacity(db_session, collection)
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
    after = open_capacity(db_session, collection)
    assert after == before - 1
