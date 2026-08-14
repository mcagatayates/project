import datetime

from app.pipeline.market_research_planner import build_research_plan


def test_plan_always_includes_bestseller_tracking_and_evergreen():
    plan = build_research_plan(datetime.date(2026, 7, 1))  # far from any occasion's lead window
    categories = {rq.category for rq in plan}
    assert "bestseller_tracking" in categories
    assert "evergreen_trend" in categories
    assert not any(c.startswith("seasonal:") for c in categories)


def test_plan_adds_seasonal_queries_when_an_occasion_is_active():
    plan = build_research_plan(datetime.date(2026, 8, 14))  # Halloween's lead window
    seasonal = [rq for rq in plan if rq.category == "seasonal:Halloween"]
    assert len(seasonal) > 0
    assert all("Halloween" in rq.reason and "weeks away" in rq.reason for rq in seasonal)
    assert any("halloween" in rq.query.lower() for rq in seasonal)


def test_plan_does_not_add_seasonal_queries_outside_any_lead_window():
    plan = build_research_plan(datetime.date(2026, 7, 1))
    assert not any(rq.category.startswith("seasonal:") for rq in plan)
