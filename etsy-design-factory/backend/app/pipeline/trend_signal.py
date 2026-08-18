"""Two real-data signals surfaced into market_signals (see
app/pipeline/market_intelligence.py), both backed by
app/providers/google_trends.py (SerpAPI's Google Trends engine):

1. Rising topics: what's actually climbing in search interest for the
   category right now (config/market_research_queries.yaml's
   trend_watch_terms), not a canned query list.
2. Seasonal onset learning: for each occasion in
   config/seasonal_calendar.yaml, how many weeks before the occasion did
   real search interest actually start rising LAST YEAR -- compared
   against the hand-set `lead_weeks` hypothesis. This never silently
   rewrites seasonal_calendar.yaml; it surfaces the evidence as a real
   signal (like everything else in market_signals) so a human can decide
   whether to adjust the config, and so it already feeds
   app/pipeline/opportunity_engine.py / archetype_affinity.py like any
   other signal without further wiring.
"""

from __future__ import annotations

import datetime
from functools import lru_cache
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from app.pipeline.market_intelligence import OpportunitySignal, ingest_signals, run_market_intelligence
from app.pipeline.market_research_planner import DEFAULT_QUERIES_PATH
from app.pipeline.seasonal_calendar import Occasion, load_occasions, previous_occurrence
from app.providers.base import ProviderError
from app.providers.google_trends import GoogleTrendsAdapter, TrendPoint
from app.providers.web_search_market_intelligence import WebSearchMarketIntelligenceAdapter

# Interest crossing this fraction of last year's peak counts as "started
# rising" -- a deliberately loose threshold since real search-interest
# curves are noisy, not a clean step function.
_ONSET_THRESHOLD_FRACTION = 0.2

# Extra weeks of history fetched before the *configured* lead_weeks, so a
# real onset earlier than the current hypothesis can actually be seen
# rather than being cut off by the query window itself.
_LOOKBACK_BUFFER_WEEKS = 6

_MAX_RISING_PER_TERM = 5


@lru_cache
def _load_queries_config(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text()) or {}


def default_trend_watch_terms(path: str | None = None) -> list[str]:
    base = _load_queries_config(path or str(DEFAULT_QUERIES_PATH))
    return list(base.get("trend_watch_terms") or [])


async def fetch_rising_topics(adapter: GoogleTrendsAdapter, *, terms: list[str] | None = None) -> list[OpportunitySignal]:
    """What's actually climbing in search interest near each watched
    term right now -- real Google Trends "rising related queries," not a
    hand-written list."""
    terms = terms if terms is not None else default_trend_watch_terms()
    signals: list[OpportunitySignal] = []
    for term in terms:
        rising = await adapter.rising_queries(keyword=term)
        for rq in rising[:_MAX_RISING_PER_TERM]:
            label = f" ({rq.value_label})" if rq.value_label else ""
            signals.append(
                OpportunitySignal(
                    category="rising_trend",
                    description=f"'{rq.query}' is rising in search interest{label}, related to '{term}'",
                    confidence=0.6,
                    source=f"google_trends:related_queries:{term}",
                )
            )
    return signals


def _find_onset(points: list[TrendPoint], *, threshold_fraction: float) -> datetime.date | None:
    """The earliest date, scanning backward from the window's peak, past
    which interest stayed at or above threshold_fraction * peak all the
    way to the peak. If the whole window is already above threshold, the
    window's first date is returned (the lookback buffer wasn't long
    enough to see a real pre-rise baseline -- a data-quality limit, not a
    bug)."""
    if not points:
        return None
    ordered = sorted(points, key=lambda p: p.date)
    peak = max(p.value for p in ordered)
    if peak <= 0:
        return None
    threshold = peak * threshold_fraction
    peak_index = max(range(len(ordered)), key=lambda i: ordered[i].value)

    onset_index = 0
    for i in range(peak_index, -1, -1):
        if ordered[i].value < threshold:
            onset_index = i + 1
            break
    return ordered[onset_index].date


async def fetch_seasonal_onset_signals(
    adapter: GoogleTrendsAdapter,
    *,
    today: datetime.date | None = None,
    occasions: tuple[Occasion, ...] | None = None,
) -> list[OpportunitySignal]:
    """For each configured occasion, learns from last year's real search
    interest when demand actually started rising, and reports it against
    the currently-configured lead_weeks -- evidence for a human to review,
    never an automatic config change."""
    today = today or datetime.date.today()
    occasions = occasions if occasions is not None else load_occasions()

    signals: list[OpportunitySignal] = []
    for occ in occasions:
        if not occ.keywords:
            continue
        keyword = occ.keywords[0]
        last_occ_date = previous_occurrence(today, month=occ.month, day=occ.day)
        window_start = last_occ_date - datetime.timedelta(weeks=occ.lead_weeks + _LOOKBACK_BUFFER_WEEKS)
        window_end = last_occ_date + datetime.timedelta(weeks=1)
        date_range = f"{window_start.isoformat()} {window_end.isoformat()}"

        points = await adapter.interest_over_time(keyword=keyword, date_range=date_range)
        onset = _find_onset(points, threshold_fraction=_ONSET_THRESHOLD_FRACTION)
        if onset is None:
            continue

        learned_lead_weeks = (last_occ_date - onset).days / 7.0
        diff = learned_lead_weeks - occ.lead_weeks
        if diff > 1:
            comparison = f"starts rising earlier than the configured {occ.lead_weeks}-week lead time"
        elif diff < -1:
            comparison = f"starts rising later than the configured {occ.lead_weeks}-week lead time"
        else:
            comparison = f"roughly matches the configured {occ.lead_weeks}-week lead time"

        signals.append(
            OpportunitySignal(
                category=f"trend_onset:{occ.name}",
                description=(
                    f"Last year, real search interest for '{keyword}' first crossed "
                    f"{int(_ONSET_THRESHOLD_FRACTION * 100)}% of its peak about {learned_lead_weeks:.1f} weeks "
                    f"before {occ.name} ({last_occ_date.isoformat()}) -- {comparison}."
                ),
                confidence=0.55,
                source=f"google_trends:interest_over_time:{keyword}",
            )
        )
    return signals


async def refresh_real_market_signals(session: Session) -> list[OpportunitySignal]:
    """Runs every configured real signal source once and persists
    whatever each one actually found: the existing (previously dormant)
    WebSearchMarketIntelligenceAdapter organic-search path, plus this
    module's Google Trends rising-topics and seasonal-onset-learning
    paths. Each source is wrapped independently -- an unconfigured or
    failing source is skipped, not fatal to the others, since all three
    currently share SERPAPI_KEY and this is called unconditionally by
    the daily Celery beat schedule (app/queue/tasks/trend_refresh.py)
    as well as an on-demand catch-up run
    (POST /api/market-intelligence/refresh)."""
    found: list[OpportunitySignal] = []

    try:
        report = await run_market_intelligence(WebSearchMarketIntelligenceAdapter())
        found.extend(report.signals)
    except ProviderError:
        pass

    trends_adapter = GoogleTrendsAdapter()
    try:
        found.extend(await fetch_rising_topics(trends_adapter))
    except ProviderError:
        pass
    try:
        found.extend(await fetch_seasonal_onset_signals(trends_adapter))
    except ProviderError:
        pass

    if found:
        ingest_signals(session, signals=found)
    return found
