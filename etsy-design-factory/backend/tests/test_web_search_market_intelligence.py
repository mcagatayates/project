import asyncio

import httpx
import pytest

from app.providers.base import ProviderError
from app.providers.web_search_market_intelligence import WebSearchMarketIntelligenceAdapter


def test_raises_clear_error_without_api_key():
    adapter = WebSearchMarketIntelligenceAdapter(api_key=None, queries=["etsy wall art trends"])
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
        api_key="fake-key", queries=["etsy wall art trends"], client=_mock_client(payload)
    )
    signals = asyncio.run(adapter.fetch_signals())
    assert len(signals) == 2
    assert "Etsy wall art trends" in signals[0].description
    assert signals[0].source == "serpapi:google_search:etsy wall art trends"
    assert 0.0 < signals[0].confidence <= 1.0
    # earlier-ranked result should have >= confidence of a later one
    assert signals[0].confidence >= signals[1].confidence


def test_multiple_queries_are_all_fetched():
    payload = {"organic_results": [{"title": "x trend", "snippet": "y"}]}
    queries = ["etsy wall art trends", "trending home decor color palette"]
    adapter = WebSearchMarketIntelligenceAdapter(api_key="fake-key", queries=queries, client=_mock_client(payload))
    signals = asyncio.run(adapter.fetch_signals())
    assert len(signals) == len(queries)
    assert {s.category for s in signals} == set(queries)


def test_empty_results_produce_no_signals():
    adapter = WebSearchMarketIntelligenceAdapter(
        api_key="fake-key", queries=["obscure query"], client=_mock_client({"organic_results": []})
    )
    signals = asyncio.run(adapter.fetch_signals())
    assert signals == []


def test_http_error_raises_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = WebSearchMarketIntelligenceAdapter(api_key="fake-key", queries=["x"], client=client)
    with pytest.raises(ProviderError):
        asyncio.run(adapter.fetch_signals())
