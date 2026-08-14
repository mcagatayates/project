"""Builds *what to research today*: always-on bestseller/trend tracking
plus whichever occasions are currently inside their lead-time window (see
app/pipeline/seasonal_calendar.py). This is what
WebSearchMarketIntelligenceAdapter queries with, and what
GET /api/market-intelligence/research-queries hands to an agent-driven
research job -- one deterministic, testable source of "what to look for,"
separate from "how to actually find it" (real web search).
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from app.pipeline.seasonal_calendar import active_occasions

DEFAULT_QUERIES_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "market_research_queries.yaml"


@dataclass(frozen=True)
class ResearchQuery:
    query: str
    category: str
    reason: str


@lru_cache
def _load_base_queries(path: str | None = None) -> dict:
    p = Path(path) if path else DEFAULT_QUERIES_PATH
    return yaml.safe_load(p.read_text())


def build_research_plan(today: datetime.date | None = None, *, queries_path: str | None = None) -> list[ResearchQuery]:
    today = today or datetime.date.today()
    base = _load_base_queries(queries_path)

    plan: list[ResearchQuery] = []
    for q in base.get("bestseller_tracking", []):
        plan.append(
            ResearchQuery(query=q, category="bestseller_tracking", reason="continuous Etsy bestseller monitoring")
        )
    for q in base.get("evergreen_trends", []):
        plan.append(ResearchQuery(query=q, category="evergreen_trend", reason="ongoing general trend tracking"))

    for active in active_occasions(today):
        reason = (
            f"{active.occasion.name} is {active.weeks_until:.1f} weeks away "
            f"(within its {active.occasion.lead_weeks}-week research lead time)"
        )
        for kw in active.occasion.keywords:
            plan.append(ResearchQuery(query=kw, category=f"seasonal:{active.occasion.name}", reason=reason))

    return plan
