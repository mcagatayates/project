"""Celery app + queue routing. See docs/EVENTS.md for the queue catalog
and dead-letter behavior this module implements.

In tests, CELERY_TASK_ALWAYS_EAGER=true runs tasks synchronously in-process
with no Redis broker required — the same task code path is exercised, just
without the network hop, which is what lets the 30-design acceptance
simulation run with zero external services.
"""

from __future__ import annotations

from celery import Celery

from app.config import get_settings

QUEUES = ("analysis", "concepts", "generation", "vision_qc", "repair", "image_processing", "mockups", "exports")
DEAD_LETTER_QUEUES = tuple(f"{q}.dlq" for q in QUEUES)


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
    )
    return app


celery_app = build_celery_app()
