"""Real, code-level Market Intelligence adapter: queries a search API and
turns organic results into OpportunitySignals. This is the "backend calls
a search API by itself" option (see docs/ROADMAP.md) alongside the
externally-submitted path (POST /api/market-intelligence/signals, meant
for an agent-driven web research process).

What to query with comes from app/pipeline/market_research_planner.py --
continuous Etsy-bestseller tracking plus whichever seasonal occasions are
currently inside their research lead-time window (see
config/seasonal_calendar.yaml) -- never a fixed, season-blind query list.

Ships against SerpAPI (https://serpapi.com) as a concrete, well-documented
example of "a real search API" -- requires SERPAPI_KEY. Raises
ProviderError with a clear message if unconfigured, following the same
pattern as every other unconfigured real vendor adapter in this codebase
(app/providers/factory.py) rather than silently returning fake data.
"""

from __future__ import annotations

import datetime

import httpx

from app.config import get_settings
from app.pipeline.market_intelligence import OpportunitySignal
from app.pipeline.market_research_planner import ResearchQuery, build_research_plan
from app.providers.base import ProviderError

_SERPAPI_URL = "https://serpapi.com/search"
_MAX_RESULTS_PER_QUERY = 5


def _confidence_from_position(position: int) -> float:
    """Higher-ranked organic results are a (weak) proxy for how strongly a
    query's premise is actually trending right now -- not a guarantee, so
    this stays a modest, bounded heuristic rather than a claim of
    certainty."""
    return max(0.3, 0.75 - 0.08 * position)


class WebSearchMarketIntelligenceAdapter:
    name = "web_search_market_intelligence"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        research_plan: list[ResearchQuery] | None = None,
        today: datetime.date | None = None,
        client: httpx.AsyncClient | None = None,
    ):
        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.serpapi_key
        self._plan = research_plan if research_plan is not None else build_research_plan(today)
        self._client = client

    async def fetch_signals(self) -> list[OpportunitySignal]:
        if not self._api_key:
            raise ProviderError(
                "WebSearchMarketIntelligenceAdapter requires SERPAPI_KEY to be set "
                "(see .env.example) -- no signal source is available without it, "
                "and this adapter never fabricates trend data."
            )

        signals: list[OpportunitySignal] = []
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=15.0)
        try:
            for rq in self._plan:
                signals.extend(await self._fetch_one(client, rq))
        finally:
            if owns_client:
                await client.aclose()
        return signals

    async def _fetch_one(self, client: httpx.AsyncClient, rq: ResearchQuery) -> list[OpportunitySignal]:
        try:
            resp = await client.get(
                _SERPAPI_URL,
                params={"q": rq.query, "engine": "google", "api_key": self._api_key, "num": _MAX_RESULTS_PER_QUERY},
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"search API request failed for query '{rq.query}': {exc}") from exc

        results = data.get("organic_results", [])[:_MAX_RESULTS_PER_QUERY]
        signals: list[OpportunitySignal] = []
        for position, result in enumerate(results):
            title = result.get("title", "")
            snippet = result.get("snippet", "")
            description = f"{title} - {snippet}".strip(" -") if snippet else title
            if not description:
                continue
            signals.append(
                OpportunitySignal(
                    category=rq.category,
                    description=description[:2000],
                    confidence=_confidence_from_position(position),
                    source=f"serpapi:google_search:{rq.query}",
                )
            )
        return signals
