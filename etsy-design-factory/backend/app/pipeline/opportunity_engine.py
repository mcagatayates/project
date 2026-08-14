"""Opportunity Engine: ranks what's worth producing next from Market
Intelligence signals + CommercialMemory + collection saturation state. See
docs/AGENT_CONTRACTS.md -- falls back to "continue proven collections
only" when there are no external signals, rather than inventing one.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models.collection import Collection
from app.db.models.enums import CollectionStatus
from app.pipeline.collection_planner import open_capacity
from app.pipeline.market_intelligence import MarketIntelligenceReport


@dataclass
class Opportunity:
    description: str
    rationale: str
    confidence: float


def rank_opportunities(session: Session, *, report: MarketIntelligenceReport) -> list[Opportunity]:
    opportunities: list[Opportunity] = [
        Opportunity(description=s.description, rationale=f"market signal ({s.source})", confidence=s.confidence)
        for s in report.signals
    ]

    if not opportunities:
        # No external signal source configured/returned anything: fall
        # back to "continue proven collections with remaining capacity,"
        # per the documented failure policy -- not a fabricated opportunity.
        from sqlalchemy import select

        stmt = select(Collection).where(Collection.status == CollectionStatus.PRODUCTION.value)
        for collection in session.execute(stmt).scalars().all():
            if open_capacity(session, collection) > 0:
                opportunities.append(
                    Opportunity(
                        description=f"continue {collection.name}",
                        rationale="no external market signal available; proven collection has open capacity",
                        confidence=0.5,
                    )
                )

    opportunities.sort(key=lambda o: o.confidence, reverse=True)
    return opportunities
