"""Ingestion point for real market-intelligence findings, and a read
endpoint for the dashboard. See app/pipeline/market_intelligence.py for
why this exists: an out-of-process researcher (a scheduled agent doing
real web research, or a human) submits findings here; the Opportunity
Engine reads them back via DatabaseMarketIntelligenceAdapter. Nothing on
this path fabricates data -- every signal traces to what the caller
actually submitted.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.schemas import (
    MarketSignalIngestRequest,
    MarketSignalListResponse,
    MarketSignalOut,
)
from app.config import get_settings
from app.memory.market_signal_memory import recent_signals
from app.pipeline.market_intelligence import OpportunitySignal, ingest_signals

router = APIRouter(prefix="/api/market-intelligence", tags=["market-intelligence"])


def require_ingestion_token(x_ingestion_token: str | None = Header(default=None)) -> None:
    configured = get_settings().market_signal_ingestion_token
    if configured is None:
        return  # open in dev/local; see config.py docstring on this setting
    if x_ingestion_token != configured:
        raise HTTPException(status_code=401, detail="missing or invalid X-Ingestion-Token")


@router.post("/signals", response_model=MarketSignalListResponse, dependencies=[Depends(require_ingestion_token)])
def submit_signals(body: MarketSignalIngestRequest, session: Session = Depends(get_db)) -> MarketSignalListResponse:
    persisted = ingest_signals(
        session,
        signals=[
            OpportunitySignal(category=s.category, description=s.description, confidence=s.confidence, source=s.source)
            for s in body.signals
        ],
    )
    rows = recent_signals(session, within_days=1, limit=len(persisted) + 5)
    return MarketSignalListResponse(
        items=[
            MarketSignalOut(
                id=r.id,
                category=r.category,
                description=r.description,
                confidence=float(r.confidence),
                source=r.source,
                created_at=r.created_at,
            )
            for r in rows[: len(persisted)]
        ]
    )


@router.get("/signals", response_model=MarketSignalListResponse)
def list_signals(within_days: int = 7, session: Session = Depends(get_db)) -> MarketSignalListResponse:
    rows = recent_signals(session, within_days=within_days, limit=100)
    return MarketSignalListResponse(
        items=[
            MarketSignalOut(
                id=r.id,
                category=r.category,
                description=r.description,
                confidence=float(r.confidence),
                source=r.source,
                created_at=r.created_at,
            )
            for r in rows
        ]
    )
