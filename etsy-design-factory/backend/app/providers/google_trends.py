"""Real Google Trends adapter via SerpAPI's `google_trends` engine
(https://serpapi.com/google-trends-api) -- same SERPAPI_KEY as
app/providers/web_search_market_intelligence.py. Two things this exists
for (see app/pipeline/trend_signal.py):

1. What's actually rising in search interest for the category right now
   (`rising_queries`) -- not a fixed, hand-written query list.
2. Weekly interest-over-time for a keyword across an arbitrary date range
   (`interest_over_time`), used to empirically measure when interest in a
   seasonal occasion started rising last year, compared against the
   hand-set `lead_weeks` hypothesis in config/seasonal_calendar.yaml.

Field names below (`related_queries.rising`, `interest_over_time.
timeline_data[].values[].extracted_value`, `.timestamp`) follow SerpAPI's
documented Google Trends response shape; parsing is defensive (skips a
malformed row rather than crashing) since this hasn't been exercised
against a live key in this sandbox -- verify against a real response once
SERPAPI_KEY is configured, and adjust field names here if they've drifted.

Raises ProviderError with a clear message if SERPAPI_KEY is unconfigured,
same pattern as every other real-vendor adapter in this codebase.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

import httpx

from app.config import get_settings
from app.providers.base import ProviderError

_TRENDS_URL = "https://serpapi.com/search"


@dataclass(frozen=True)
class TrendPoint:
    date: datetime.date
    value: int


@dataclass(frozen=True)
class RisingQuery:
    query: str
    value_label: str


class GoogleTrendsAdapter:
    name = "google_trends"

    def __init__(self, *, api_key: str | None = None, client: httpx.AsyncClient | None = None):
        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.serpapi_key
        self._client = client

    def _require_key(self) -> str:
        if not self._api_key:
            raise ProviderError(
                "GoogleTrendsAdapter requires SERPAPI_KEY to be set (see .env.example) -- "
                "no trend data source is available without it, and this adapter never "
                "fabricates a trend."
            )
        return self._api_key

    async def _get(self, client: httpx.AsyncClient, params: dict) -> dict:
        try:
            resp = await client.get(_TRENDS_URL, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Google Trends request failed: {exc}") from exc

    async def rising_queries(self, *, keyword: str, geo: str = "US") -> list[RisingQuery]:
        api_key = self._require_key()
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=15.0)
        try:
            data = await self._get(
                client,
                {"engine": "google_trends", "q": keyword, "data_type": "RELATED_QUERIES", "geo": geo, "api_key": api_key},
            )
        finally:
            if owns_client:
                await client.aclose()

        rising = (data.get("related_queries") or {}).get("rising") or []
        results: list[RisingQuery] = []
        for item in rising:
            query = item.get("query")
            if not query:
                continue
            value = item.get("value")
            results.append(RisingQuery(query=str(query), value_label=str(value) if value is not None else ""))
        return results

    async def interest_over_time(self, *, keyword: str, date_range: str, geo: str = "US") -> list[TrendPoint]:
        """`date_range` is a SerpAPI Google Trends `date` param value,
        e.g. "2025-08-01 2025-12-31" for a custom range."""
        api_key = self._require_key()
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=15.0)
        try:
            data = await self._get(
                client,
                {
                    "engine": "google_trends",
                    "q": keyword,
                    "data_type": "TIMESERIES",
                    "date": date_range,
                    "geo": geo,
                    "api_key": api_key,
                },
            )
        finally:
            if owns_client:
                await client.aclose()

        timeline = (data.get("interest_over_time") or {}).get("timeline_data") or []
        points: list[TrendPoint] = []
        for row in timeline:
            values = row.get("values") or []
            if not values:
                continue
            extracted = values[0].get("extracted_value")
            timestamp = row.get("timestamp")
            if extracted is None or timestamp is None:
                continue
            try:
                point_date = datetime.datetime.fromtimestamp(int(timestamp), tz=datetime.timezone.utc).date()
            except (ValueError, TypeError, OSError):
                continue
            points.append(TrendPoint(date=point_date, value=int(extracted)))
        return points
