from __future__ import annotations

from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, CreatedAtMixin, UUIDPKMixin


class MarketSignal(UUIDPKMixin, CreatedAtMixin, Base):
    """A single real, attributable market-intelligence data point. Never
    written except by an adapter that actually fetched or was actually
    given the underlying data -- see docs/AGENT_CONTRACTS.md
    "Market Intelligence" and app/pipeline/market_intelligence.py.

    `source` records provenance precisely (e.g. "serpapi:google_search" for
    the code-level search-API adapter, or "claude_web_research" for a
    human/agent-submitted finding via the ingestion API) so a signal's
    origin is always auditable, matching the mission's "every decision is
    traceable" requirement.
    """

    __tablename__ = "market_signals"

    category: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(2000))
    confidence: Mapped[float] = mapped_column(Numeric(4, 3))
    source: Mapped[str] = mapped_column(String(200), index=True)
