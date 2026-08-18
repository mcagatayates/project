import asyncio
import datetime

import httpx
import pytest

from app.providers.base import ProviderError
from app.providers.google_trends import GoogleTrendsAdapter


def _mock_client(payload: dict) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_raises_clear_error_without_api_key():
    adapter = GoogleTrendsAdapter(api_key=None)
    with pytest.raises(ProviderError, match="SERPAPI_KEY"):
        asyncio.run(adapter.rising_queries(keyword="wall art"))
    with pytest.raises(ProviderError, match="SERPAPI_KEY"):
        asyncio.run(adapter.interest_over_time(keyword="wall art", date_range="2025-01-01 2025-02-01"))


def test_rising_queries_parses_related_queries():
    payload = {
        "related_queries": {
            "rising": [
                {"query": "christmas wall art", "value": "+250%"},
                {"query": "minimalist wall art", "value": "Breakout"},
                {"query": "unlabeled entry", "value": None},
            ]
        }
    }
    adapter = GoogleTrendsAdapter(api_key="fake-key", client=_mock_client(payload))
    results = asyncio.run(adapter.rising_queries(keyword="wall art"))
    assert len(results) == 3
    assert results[0].query == "christmas wall art"
    assert results[0].value_label == "+250%"
    assert results[1].value_label == "Breakout"
    assert results[2].value_label == ""  # a real query with no magnitude label is still kept


def test_rising_queries_skips_entries_missing_query():
    payload = {"related_queries": {"rising": [{"value": "+100%"}]}}
    adapter = GoogleTrendsAdapter(api_key="fake-key", client=_mock_client(payload))
    assert asyncio.run(adapter.rising_queries(keyword="wall art")) == []


def test_rising_queries_handles_missing_related_queries_key():
    adapter = GoogleTrendsAdapter(api_key="fake-key", client=_mock_client({}))
    assert asyncio.run(adapter.rising_queries(keyword="wall art")) == []


def test_interest_over_time_parses_timeline_with_timestamps():
    ts1 = int(datetime.datetime(2025, 9, 1, tzinfo=datetime.timezone.utc).timestamp())
    ts2 = int(datetime.datetime(2025, 9, 8, tzinfo=datetime.timezone.utc).timestamp())
    payload = {
        "interest_over_time": {
            "timeline_data": [
                {"date": "Sep 1 - 7, 2025", "timestamp": str(ts1), "values": [{"query": "x", "extracted_value": 12}]},
                {"date": "Sep 8 - 14, 2025", "timestamp": str(ts2), "values": [{"query": "x", "extracted_value": 40}]},
            ]
        }
    }
    adapter = GoogleTrendsAdapter(api_key="fake-key", client=_mock_client(payload))
    points = asyncio.run(adapter.interest_over_time(keyword="wall art", date_range="2025-09-01 2025-09-14"))
    assert len(points) == 2
    assert points[0].date == datetime.date(2025, 9, 1)
    assert points[0].value == 12
    assert points[1].value == 40


def test_interest_over_time_skips_rows_missing_timestamp_or_value():
    payload = {
        "interest_over_time": {
            "timeline_data": [
                {"date": "no timestamp", "values": [{"extracted_value": 5}]},
                {"date": "no values", "timestamp": "1700000000", "values": []},
            ]
        }
    }
    adapter = GoogleTrendsAdapter(api_key="fake-key", client=_mock_client(payload))
    points = asyncio.run(adapter.interest_over_time(keyword="wall art", date_range="2025-09-01 2025-09-14"))
    assert points == []


def test_http_error_raises_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = GoogleTrendsAdapter(api_key="fake-key", client=client)
    with pytest.raises(ProviderError):
        asyncio.run(adapter.rising_queries(keyword="wall art"))
