"""In-memory async token bucket, one per provider adapter name.

Production note: this is single-process. A multi-worker deployment needs a
Redis-backed bucket keyed by `provider:{name}` (see
docs/PROVIDER_ARCHITECTURE.md) sharing the same `acquire()` interface so it
can be swapped in without touching call sites — that Redis-backed variant
is not implemented in this repository yet (see docs/ROADMAP.md).
"""
from __future__ import annotations

import asyncio
import time


class TokenBucket:
    def __init__(self, rate_per_minute: float, burst: int | None = None):
        self.rate_per_second = rate_per_minute / 60.0
        self.capacity = float(burst if burst is not None else max(1, rate_per_minute))
        self.tokens = self.capacity
        self.updated_at = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self.updated_at
                self.updated_at = now
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate_per_second)
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                wait_s = (1 - self.tokens) / self.rate_per_second if self.rate_per_second > 0 else 0.01
                await asyncio.sleep(min(wait_s, 1.0))


class RateLimiterRegistry:
    def __init__(self):
        self._buckets: dict[str, TokenBucket] = {}

    def get(self, provider_name: str, rate_per_minute: float, burst: int | None = None) -> TokenBucket:
        if provider_name not in self._buckets:
            self._buckets[provider_name] = TokenBucket(rate_per_minute, burst)
        return self._buckets[provider_name]
