"""Common resilience behavior for pipeline Celery tasks: bounded retry with
exponential backoff (delegating to Celery's own retry, configured from
app settings so tests can shrink it), and best-effort dead-lettering to
`<queue>.dlq` on final exhaustion. See docs/EVENTS.md.

Task bodies are responsible for writing whatever domain-level failure
record makes sense for that stage (see docs/AGENT_CONTRACTS.md per-stage
failure policy) BEFORE re-raising -- this base class only handles the
queueing/retry mechanics, never domain data.
"""

from __future__ import annotations

import logging

from celery import Task

from app.config import get_settings

logger = logging.getLogger("design_factory.tasks")


class ResilientTask(Task):
    autoretry_for = (Exception,)
    retry_backoff = True
    retry_jitter = True
    queue_name = "analysis"

    @property
    def retry_backoff_max(self) -> float:  # type: ignore[override]
        return get_settings().celery_retry_backoff_max

    @property
    def max_retries(self) -> int:  # type: ignore[override]
        return get_settings().celery_max_retries

    def on_failure(self, exc, task_id, args, kwargs, einfo):  # noqa: D102
        settings = get_settings()
        if settings.celery_task_always_eager:
            # Eager mode means "no real broker" (local dev / tests) --
            # send_task() ignores task_always_eager and always tries the
            # network (Celery warns AlwaysEagerIgnored), which would just
            # hang/fail slowly here. The domain-level failure record that
            # task bodies write before re-raising is the durable trace in
            # this mode; skip the network hop entirely.
            logger.error(
                "task %s (%s) exhausted retries (eager mode, no dead-letter queue): %s", self.name, task_id, exc
            )
            return
        try:
            self.app.send_task(self.name, args=args, kwargs=kwargs, queue=f"{self.queue_name}.dlq")
        except Exception:  # noqa: BLE001 - broker may be unavailable; logging still happens
            logger.error(
                "task %s (%s) exhausted retries and could not be dead-lettered (no broker?): %s",
                self.name,
                task_id,
                exc,
                exc_info=True,
            )
        else:
            logger.error(
                "task %s (%s) exhausted retries, routed to %s.dlq: %s", self.name, task_id, self.queue_name, exc
            )
