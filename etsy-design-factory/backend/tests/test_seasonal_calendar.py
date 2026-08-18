import datetime

from app.pipeline.seasonal_calendar import (
    Occasion,
    active_occasions,
    load_occasions,
    next_occurrence,
    previous_occurrence,
)

HALLOWEEN = Occasion(name="Halloween", month=10, day=31, lead_weeks=12, keywords=("halloween wall art",))
NEW_YEAR = Occasion(name="New Year", month=1, day=1, lead_weeks=6, keywords=("new year wall art",))


def test_next_occurrence_this_year_when_still_upcoming():
    today = datetime.date(2026, 8, 14)
    assert next_occurrence(today, month=10, day=31) == datetime.date(2026, 10, 31)


def test_next_occurrence_rolls_to_next_year_when_already_passed():
    today = datetime.date(2026, 11, 15)
    assert next_occurrence(today, month=10, day=31) == datetime.date(2027, 10, 31)


def test_next_occurrence_today_counts_as_this_year():
    today = datetime.date(2026, 10, 31)
    assert next_occurrence(today, month=10, day=31) == today


def test_previous_occurrence_this_year_when_already_passed():
    today = datetime.date(2026, 11, 15)
    assert previous_occurrence(today, month=10, day=31) == datetime.date(2026, 10, 31)


def test_previous_occurrence_rolls_to_last_year_when_still_upcoming():
    today = datetime.date(2026, 8, 14)
    assert previous_occurrence(today, month=10, day=31) == datetime.date(2025, 10, 31)


def test_previous_occurrence_today_does_not_count_as_past():
    today = datetime.date(2026, 10, 31)
    assert previous_occurrence(today, month=10, day=31) == datetime.date(2025, 10, 31)


def test_halloween_is_active_in_mid_august_matching_real_etsy_seller_lead_time():
    # This is the scenario named explicitly: mid-August is well within
    # Halloween's typical prep window for Etsy sellers.
    today = datetime.date(2026, 8, 14)
    active = active_occasions(today, occasions=(HALLOWEEN,))
    assert len(active) == 1
    assert active[0].occasion.name == "Halloween"
    assert 10.0 < active[0].weeks_until < 12.0


def test_halloween_is_not_active_far_outside_lead_window():
    today = datetime.date(2026, 3, 1)  # ~35 weeks before Halloween
    active = active_occasions(today, occasions=(HALLOWEEN,))
    assert active == []


def test_year_boundary_new_year_active_in_december():
    today = datetime.date(2026, 12, 1)
    active = active_occasions(today, occasions=(NEW_YEAR,))
    assert len(active) == 1
    assert active[0].occasion_date == datetime.date(2027, 1, 1)


def test_multiple_occasions_sorted_by_closeness():
    today = datetime.date(2026, 8, 14)
    active = active_occasions(today, occasions=(HALLOWEEN, NEW_YEAR))
    # NEW_YEAR (~20 weeks away, lead_weeks=6) is not active; only Halloween should be
    assert [a.occasion.name for a in active] == ["Halloween"]


def test_load_occasions_from_real_config_file_parses():
    occasions = load_occasions()
    assert len(occasions) >= 5
    names = {o.name for o in occasions}
    assert "Halloween" in names
    for o in occasions:
        assert 1 <= o.month <= 12
        assert 1 <= o.day <= 31
        assert o.lead_weeks > 0
        assert len(o.keywords) > 0
