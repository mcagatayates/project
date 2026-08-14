import asyncio

import httpx
import pytest

from app.pipeline.market_research_planner import ResearchQuery
from app.providers.base import ProviderError
from app.providers.web_search_market_intelligence import WebSearchMarketIntelligenceAdapter


def _rq(query: str, category: str = "evergreen_trend") -> ResearchQuery:
    return ResearchQuery(query=query, category=category, reason="test")


def test_raises_clear_error_without_api_key():
    adapter = WebSearchMarketIntelligenceAdapter(api_key=None, research_plan=[_rq("etsy wall art trends")])
    with pytest.raises(ProviderError, match="SERPAPI_KEY"):
        asyncio.run(adapter.fetch_signals())


def _mock_client(payload: dict) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_parses_organic_results_into_signals():
    payload = {
        "organic_results": [
            {"title": "10 Etsy wall art trends for 2026", "snippet": "Muted botanicals and bold linework are up."},
            {"title": "Home decor palettes trending now", "snippet": "Warm neutrals dominate."},
        ]
    }
    adapter = WebSearchMarketIntelligenceAdapter(
        api_key="fake-key", research_plan=[_rq("etsy wall art trends")], client=_mock_client(payload)
    )
    signals = asyncio.run(adapter.fetch_signals())
    assert len(signals) == 2
    assert "Etsy wall art trends" in signals[0].description
    assert signals[0].source == "serpapi:google_search:etsy wall art trends"
    assert signals[0].category == "evergreen_trend"
    assert 0.0 < signals[0].confidence <= 1.0
    # earlier-ranked result should have >= confidence of a later one
    assert signals[0].confidence >= signals[1].confidence


def test_multiple_queries_are_all_fetched():
    payload = {"organic_results": [{"title": "x trend", "snippet": "y"}]}
    queries = [_rq("etsy wall art trends"), _rq("trending home decor color palette")]
    adapter = WebSearchMarketIntelligenceAdapter(
        api_key="fake-key", research_plan=queries, client=_mock_client(payload)
    )
    signals = asyncio.run(adapter.fetch_signals())
    assert len(signals) == len(queries)
    assert {s.source for s in signals} == {f"serpapi:google_search:{q.query}" for q in queries}


def test_empty_results_produce_no_signals():
    adapter = WebSearchMarketIntelligenceAdapter(
        api_key="fake-key", research_plan=[_rq("obscure query")], client=_mock_client({"organic_results": []})
    )
    signals = asyncio.run(adapter.fetch_signals())
    assert signals == []


def test_http_error_raises_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = WebSearchMarketIntelligenceAdapter(api_key="fake-key", research_plan=[_rq("x")], client=client)
    with pytest.raises(ProviderError):
        asyncio.run(adapter.fetch_signals())


def test_default_research_plan_includes_bestseller_tracking():
    # No explicit research_plan/today -> pulls from
    # app.pipeline.market_research_planner.build_research_plan(), which
    # always includes continuous bestseller-tracking queries.
    adapter = WebSearchMarketIntelligenceAdapter(api_key="fake-key", client=_mock_client({"organic_results": []}))
    categories = {rq.category for rq in adapter._plan}  # noqa: SLF001 - white-box check that wiring is correct
    assert "bestseller_tracking" in categories
