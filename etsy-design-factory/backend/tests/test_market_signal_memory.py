import asyncio

from app.memory.market_signal_memory import recent_signals
from app.pipeline.market_intelligence import (
    DatabaseMarketIntelligenceAdapter,
    OpportunitySignal,
    ingest_signals,
    run_market_intelligence,
)
from app.pipeline.opportunity_engine import rank_opportunities


def test_ingest_signals_persists_and_is_readable_back(db_session):
    ingest_signals(
        db_session,
        signals=[
            OpportunitySignal(
                category="etsy wall art trends",
                description="Muted botanicals trending up",
                confidence=0.6,
                source="claude_web_research",
            )
        ],
    )
    rows = recent_signals(db_session)
    assert len(rows) == 1
    assert rows[0].description == "Muted botanicals trending up"
    assert rows[0].source == "claude_web_research"


def test_database_adapter_reads_ingested_signals_and_feeds_opportunity_engine(db_session):
    ingest_signals(
        db_session,
        signals=[
            OpportunitySignal(
                category="trending home decor color palette",
                description="Warm neutrals",
                confidence=0.7,
                source="serpapi:google_search:trending home decor color palette",
            )
        ],
    )

    adapter = DatabaseMarketIntelligenceAdapter(db_session)
    report = asyncio.run(run_market_intelligence(adapter))
    assert len(report.signals) == 1

    opportunities = rank_opportunities(db_session, report=report)
    assert len(opportunities) == 1
    assert opportunities[0].description == "Warm neutrals"
    assert "serpapi" in opportunities[0].rationale


def test_database_adapter_ignores_signals_older_than_window(db_session):
    from datetime import datetime, timedelta, timezone

    from app.memory.market_signal_memory import record_signal

    signal = record_signal(db_session, category="x", description="old", confidence=0.5, source="test")
    signal.created_at = datetime.now(timezone.utc) - timedelta(days=30)
    db_session.flush()

    adapter = DatabaseMarketIntelligenceAdapter(db_session, within_days=7)
    report = asyncio.run(run_market_intelligence(adapter))
    assert report.signals == []
