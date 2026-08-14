"""Market Intelligence: external signal gathering. See
docs/AGENT_CONTRACTS.md -- non-fatal to the daily cycle, and returns an
empty signal set (never a fabricated trend) when no real signal source is
configured. No adapter is implemented in this repository yet (see
docs/ROADMAP.md "Explicit non-goals"); this stage exists so the
Opportunity Engine and Production Controller have a stable interface to
call once one is.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class OpportunitySignal:
    category: str
    description: str
    confidence: float
    source: str


class MarketIntelligenceAdapter(Protocol):
    name: str

    async def fetch_signals(self) -> list[OpportunitySignal]: ...


class NullMarketIntelligenceAdapter:
    name = "null_market_intelligence"

    async def fetch_signals(self) -> list[OpportunitySignal]:
        return []


@dataclass
class MarketIntelligenceReport:
    signals: list[OpportunitySignal] = field(default_factory=list)


async def run_market_intelligence(adapter: MarketIntelligenceAdapter | None = None) -> MarketIntelligenceReport:
    adapter = adapter or NullMarketIntelligenceAdapter()
    signals = await adapter.fetch_signals()
    return MarketIntelligenceReport(signals=signals)
