"""Market Intelligence: external signal gathering. See
docs/AGENT_CONTRACTS.md -- non-fatal to the daily cycle, and returns an
empty signal set (never a fabricated trend) when no real signal source is
available. Every signal that reaches the Opportunity Engine traces back to
something a real adapter fetched or a real caller submitted -- see
app/db/models/market_signal.py.

Two ways real signals get in (see docs/ROADMAP.md):
1. Code-level: a WebSearchMarketIntelligenceAdapter
   (app/providers/web_search_market_intelligence.py) calls a real search
   API inline, during `run_market_intelligence()`.
2. Externally submitted: POST /api/market-intelligence/signals lets an
   out-of-process researcher (a scheduled Claude agent doing real web
   research, or a human) write findings directly into market_signals.
   DatabaseMarketIntelligenceAdapter is what turns those into the signals
   the Opportunity Engine sees.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy.orm import Session

from app.memory.market_signal_memory import recent_signals, record_signal


@dataclass
class OpportunitySignal:
    category: str
    description: str
    confidence: float
    source: str


class MarketIntelligenceAdapter(Protocol):
    name: str

    async def fetch_signals(self) -> list[OpportunitySignal]:
        """Returns real signals this adapter actually obtained. An empty
        list means "nothing found," never a fabricated trend."""
        ...


class NullMarketIntelligenceAdapter:
    """No signal source configured. Always returns []."""

    name = "null_market_intelligence"

    async def fetch_signals(self) -> list[OpportunitySignal]:
        return []


class DatabaseMarketIntelligenceAdapter:
    """Reads whatever has actually been persisted to market_signals
    recently -- by a prior code-level adapter run, or by the ingestion API
    (app/api/routes/market_intelligence.py) that an agent-driven web
    research process posts to. This is the adapter the daily cycle uses by
    default: it accumulates real findings from whichever source fed them
    in, rather than requiring one specific integration."""

    name = "database_market_intelligence"

    def __init__(self, session: Session, *, within_days: int = 7):
        self._session = session
        self._within_days = within_days

    async def fetch_signals(self) -> list[OpportunitySignal]:
        rows = recent_signals(self._session, within_days=self._within_days)
        return [
            OpportunitySignal(
                category=r.category, description=r.description, confidence=float(r.confidence), source=r.source
            )
            for r in rows
        ]


@dataclass
class MarketIntelligenceReport:
    signals: list[OpportunitySignal] = field(default_factory=list)


async def run_market_intelligence(adapter: MarketIntelligenceAdapter | None = None) -> MarketIntelligenceReport:
    adapter = adapter or NullMarketIntelligenceAdapter()
    signals = await adapter.fetch_signals()
    return MarketIntelligenceReport(signals=signals)


def ingest_signals(
    session: Session, *, signals: list[OpportunitySignal], source_override: str | None = None
) -> list[OpportunitySignal]:
    """Persists a batch of already-obtained signals (from a live adapter
    run, or from an external submitter) into market_signals. Never invents
    a signal -- this only records what it's handed."""
    for s in signals:
        record_signal(
            session,
            category=s.category,
            description=s.description,
            confidence=s.confidence,
            source=source_override or s.source,
        )
    return signals
