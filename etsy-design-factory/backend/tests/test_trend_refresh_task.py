"""Exercises the daily market-intelligence-refresh Celery task in eager
mode (no Redis needed) -- see app/queue/tasks/trend_refresh.py."""

from __future__ import annotations

from app.queue.tasks.trend_refresh import refresh_market_intelligence_task


def test_refresh_market_intelligence_task_runs_without_serpapi_key_configured(db_session, monkeypatch):
    from app.config import get_settings

    monkeypatch.delenv("SERPAPI_KEY", raising=False)
    get_settings.cache_clear()

    # No SERPAPI_KEY -> every real source is skipped, task still succeeds
    # with zero signals found rather than crashing the daily schedule.
    count = refresh_market_intelligence_task.apply().get()
    assert count == 0

    get_settings.cache_clear()


def test_refresh_market_intelligence_task_is_registered_for_beat(db_session):
    from app.queue.celery_app import celery_app

    schedule = celery_app.conf.beat_schedule
    assert "daily-market-intelligence-refresh" in schedule
    entry = schedule["daily-market-intelligence-refresh"]
    assert entry["task"] == "app.queue.tasks.trend_refresh.refresh_market_intelligence"
