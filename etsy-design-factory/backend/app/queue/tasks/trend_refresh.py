"""`analysis` queue: the daily real market-signal refresh (organic
search + Google Trends). See app/pipeline/trend_signal.py -- runs
unconditionally on the Celery beat schedule; sources with no
SERPAPI_KEY configured are skipped, not fatal."""

from __future__ import annotations

import asyncio

from app.pipeline.trend_signal import refresh_real_market_signals
from app.queue.base_task import ResilientTask
from app.queue.celery_app import celery_app
from app.queue.context import task_context


@celery_app.task(bind=True, base=ResilientTask, name="app.queue.tasks.trend_refresh.refresh_market_intelligence")
def refresh_market_intelligence_task(self) -> int:
    self.queue_name = "analysis"
    with task_context() as (session, _registry):
        found = asyncio.run(refresh_real_market_signals(session))
        count = len(found)
    return count
