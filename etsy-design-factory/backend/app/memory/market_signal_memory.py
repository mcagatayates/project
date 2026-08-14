"""Persistence for real market-intelligence findings. Every row here
traces back to something an adapter actually fetched or a caller actually
submitted -- see app/pipeline/market_intelligence.py and
app/db/models/market_signal.py."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.market_signal import MarketSignal


def record_signal(session: Session, *, category: str, description: str, confidence: float, source: str) -> MarketSignal:
    signal = MarketSignal(
        category=category,
        description=description[:2000],
        confidence=max(0.0, min(1.0, confidence)),
        source=source,
    )
    session.add(signal)
    session.flush()
    return signal


def recent_signals(session: Session, *, within_days: int = 7, limit: int = 50) -> list[MarketSignal]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=within_days)
    stmt = (
        select(MarketSignal)
        .where(MarketSignal.created_at >= cutoff)
        .order_by(MarketSignal.created_at.desc())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().all())
