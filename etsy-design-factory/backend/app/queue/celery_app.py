"""Celery app + queue routing. See docs/EVENTS.md for the queue catalog
and dead-letter behavior this module implements.

In tests, CELERY_TASK_ALWAYS_EAGER=true runs tasks synchronously in-process
with no Redis broker required — the same task code path is exercised, just
without the network hop, which is what lets the 30-design acceptance
simulation run with zero external services.
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

QUEUES = ("analysis", "concepts", "generation", "vision_qc", "repair", "image_processing", "mockups", "exports")
DEAD_LETTER_QUEUES = tuple(f"{q}.dlq" for q in QUEUES)

# Every module that defines a @celery_app.task -- a real worker process
# (`celery -A app.queue.celery_app worker`) only knows about tasks whose
# module it has actually imported, so this list is what makes `.delay()`/
# `.apply_async()` and the beat schedule below resolve to a real task
# instead of failing with "Received unregistered task."
TASK_MODULES = (
    "app.queue.tasks.analysis",
    "app.queue.tasks.concepts",
    "app.queue.tasks.generation",
    "app.queue.tasks.vision_qc",
    "app.queue.tasks.repair",
    "app.queue.tasks.trend_refresh",
)


def build_celery_app() -> Celery:
    settings = get_settings()
    app = Celery("design_factory", broker=settings.redis_url, backend=settings.redis_url)
    app.conf.update(
        task_always_eager=settings.celery_task_always_eager,
        # False so eager-mode autoretry actually loops (apply() re-invokes
        # itself on a Retry signal) instead of letting the internal Retry
        # signal bubble out raw. Final, non-retry failures are still
        # re-raised by EagerResult.get() regardless of this setting.
        task_eager_propagates=False,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        task_default_queue="analysis",
        imports=TASK_MODULES,
        task_routes={
            "app.queue.tasks.analysis.*": {"queue": "analysis"},
            "app.queue.tasks.concepts.*": {"queue": "concepts"},
            "app.queue.tasks.generation.*": {"queue": "generation"},
            "app.queue.tasks.vision_qc.*": {"queue": "vision_qc"},
            "app.queue.tasks.repair.*": {"queue": "repair"},
            "app.queue.tasks.image_processing.*": {"queue": "image_processing"},
            "app.queue.tasks.mockups.*": {"queue": "mockups"},
            "app.queue.tasks.exports.*": {"queue": "exports"},
        },
        # Runs the real (previously dormant) web-search + Google Trends
        # signal refresh once daily -- see
        # app/pipeline/trend_signal.py:refresh_real_market_signals(). A
        # missing SERPAPI_KEY makes each source a no-op, not a crash, so
        # this is safe to leave scheduled even before it's configured.
        beat_schedule={
            "daily-market-intelligence-refresh": {
                "task": "app.queue.tasks.trend_refresh.refresh_market_intelligence",
                "schedule": crontab(hour=13, minute=0),
            },
        },
    )
    return app


celery_app = build_celery_app()
