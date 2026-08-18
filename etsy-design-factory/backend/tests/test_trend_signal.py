import asyncio
import datetime

from app.pipeline.market_intelligence import OpportunitySignal
from app.pipeline.seasonal_calendar import Occasion
from app.pipeline.trend_signal import (
    _find_onset,
    default_trend_watch_terms,
    fetch_rising_topics,
    fetch_seasonal_onset_signals,
    refresh_real_market_signals,
)
from app.providers.google_trends import RisingQuery, TrendPoint


class _StubTrendsAdapter:
    """Minimal stand-in for GoogleTrendsAdapter -- these tests exercise
    signal-building logic, not HTTP parsing (already covered by
    test_google_trends.py), so no network mocking is needed here."""

    def __init__(self, *, rising_by_term: dict | None = None, points_by_keyword: dict | None = None):
        self._rising_by_term = rising_by_term or {}
        self._points_by_keyword = points_by_keyword or {}

    async def rising_queries(self, *, keyword: str, geo: str = "US"):
        return self._rising_by_term.get(keyword, [])

    async def interest_over_time(self, *, keyword: str, date_range: str, geo: str = "US"):
        return self._points_by_keyword.get(keyword, [])


def test_default_trend_watch_terms_loads_from_real_config():
    terms = default_trend_watch_terms()
    assert "wall art" in terms
    assert len(terms) > 0


def test_fetch_rising_topics_builds_signals_per_term():
    adapter = _StubTrendsAdapter(
        rising_by_term={
            "wall art": [RisingQuery(query="christmas wall art", value_label="+250%")],
            "home decor": [RisingQuery(query="cozy home decor", value_label="Breakout")],
        }
    )
    signals = asyncio.run(fetch_rising_topics(adapter, terms=["wall art", "home decor"]))
    assert len(signals) == 2
    assert signals[0].category == "rising_trend"
    assert "christmas wall art" in signals[0].description
    assert signals[0].source == "google_trends:related_queries:wall art"
    assert signals[1].source == "google_trends:related_queries:home decor"


def test_fetch_rising_topics_caps_results_per_term():
    many = [RisingQuery(query=f"q{i}", value_label="+10%") for i in range(10)]
    adapter = _StubTrendsAdapter(rising_by_term={"wall art": many})
    signals = asyncio.run(fetch_rising_topics(adapter, terms=["wall art"]))
    assert len(signals) == 5


def _points_rising_to_peak(*, start: datetime.date, weeks: int, onset_week_index: int, peak: int = 100) -> list[TrendPoint]:
    """A synthetic weekly series: near-zero baseline, then a clean rise
    starting at onset_week_index up to `peak` at the final week. The
    value at onset_week_index itself starts comfortably above a 20%
    threshold (and the week before stays comfortably below it), so the
    boundary _find_onset detects lands exactly on onset_week_index."""
    points = []
    rise_weeks = max(1, weeks - 1 - onset_week_index)
    for i in range(weeks):
        if i < onset_week_index:
            value = 2
        else:
            progress = (i - onset_week_index) / rise_weeks
            value = int(30 + progress * (peak - 30))
        points.append(TrendPoint(date=start + datetime.timedelta(weeks=i), value=value))
    points[-1] = TrendPoint(date=points[-1].date, value=peak)
    return points


def test_find_onset_detects_the_real_rise_point():
    start = datetime.date(2025, 8, 1)
    points = _points_rising_to_peak(start=start, weeks=12, onset_week_index=6)
    onset = _find_onset(points, threshold_fraction=0.2)
    assert onset == points[6].date


def test_find_onset_returns_none_for_empty_or_flat_zero_series():
    assert _find_onset([], threshold_fraction=0.2) is None
    flat = [TrendPoint(date=datetime.date(2025, 1, i), value=0) for i in range(1, 5)]
    assert _find_onset(flat, threshold_fraction=0.2) is None


def test_find_onset_handles_out_of_order_points():
    start = datetime.date(2025, 8, 1)
    points = _points_rising_to_peak(start=start, weeks=8, onset_week_index=3)
    shuffled = [points[4], points[0], points[7], points[2], points[1], points[3], points[6], points[5]]
    onset = _find_onset(shuffled, threshold_fraction=0.2)
    assert onset == points[3].date


def test_fetch_seasonal_onset_signals_compares_learned_vs_configured_lead_time():
    # Halloween-like occasion, Oct 31, configured lead_weeks=12. Real
    # interest actually only started rising 8 weeks before -- later
    # (closer to the date) than the 12-week hypothesis.
    occ = Occasion(name="Halloween", month=10, day=31, lead_weeks=12, keywords=("halloween wall art",))
    today = datetime.date(2026, 8, 15)
    last_year_halloween = datetime.date(2025, 10, 31)

    onset_date = last_year_halloween - datetime.timedelta(weeks=8)
    window_start = last_year_halloween - datetime.timedelta(weeks=12 + 6)
    total_weeks = int((last_year_halloween - window_start).days / 7) + 2
    onset_index = int((onset_date - window_start).days / 7)
    points = _points_rising_to_peak(start=window_start, weeks=total_weeks, onset_week_index=onset_index)

    adapter = _StubTrendsAdapter(points_by_keyword={"halloween wall art": points})
    signals = asyncio.run(fetch_seasonal_onset_signals(adapter, today=today, occasions=(occ,)))

    assert len(signals) == 1
    sig = signals[0]
    assert sig.category == "trend_onset:Halloween"
    assert "halloween wall art" in sig.description
    assert "8.0 weeks" in sig.description
    assert "starts rising later than the configured 12-week lead time" in sig.description


def test_fetch_seasonal_onset_signals_skips_occasion_with_no_keywords():
    occ = Occasion(name="No Keywords", month=1, day=1, lead_weeks=4, keywords=())
    adapter = _StubTrendsAdapter()
    signals = asyncio.run(fetch_seasonal_onset_signals(adapter, today=datetime.date(2026, 1, 1), occasions=(occ,)))
    assert signals == []


def test_fetch_seasonal_onset_signals_skips_occasion_with_no_data():
    occ = Occasion(name="No Data", month=6, day=1, lead_weeks=4, keywords=("no data keyword",))
    adapter = _StubTrendsAdapter(points_by_keyword={})
    signals = asyncio.run(fetch_seasonal_onset_signals(adapter, today=datetime.date(2026, 1, 1), occasions=(occ,)))
    assert signals == []


def test_refresh_real_market_signals_persists_whatever_sources_actually_found(db_session, monkeypatch):
    async def fake_run_market_intelligence(adapter):
        from app.pipeline.market_intelligence import MarketIntelligenceReport

        return MarketIntelligenceReport(
            signals=[OpportunitySignal(category="x", description="real web finding", confidence=0.5, source="web")]
        )

    async def fake_fetch_rising_topics(adapter, *, terms=None):
        return [OpportunitySignal(category="rising_trend", description="real rising topic", confidence=0.6, source="t")]

    async def fake_fetch_seasonal_onset_signals(adapter, *, today=None, occasions=None):
        return []

    monkeypatch.setattr("app.pipeline.trend_signal.run_market_intelligence", fake_run_market_intelligence)
    monkeypatch.setattr("app.pipeline.trend_signal.fetch_rising_topics", fake_fetch_rising_topics)
    monkeypatch.setattr("app.pipeline.trend_signal.fetch_seasonal_onset_signals", fake_fetch_seasonal_onset_signals)

    found = asyncio.run(refresh_real_market_signals(db_session))
    assert len(found) == 2

    from app.memory.market_signal_memory import recent_signals

    rows = recent_signals(db_session, within_days=1)
    assert {r.description for r in rows} == {"real web finding", "real rising topic"}


def test_refresh_real_market_signals_skips_unconfigured_sources_without_crashing(db_session, monkeypatch):
    from app.config import get_settings

    monkeypatch.delenv("SERPAPI_KEY", raising=False)
    get_settings.cache_clear()

    found = asyncio.run(refresh_real_market_signals(db_session))
    assert found == []
    get_settings.cache_clear()
