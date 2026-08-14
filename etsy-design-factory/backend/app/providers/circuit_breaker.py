from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.db.models.enums import CircuitState


@dataclass
class CircuitBreaker:
    """Per-adapter rolling failure tracker with CLOSED/OPEN/HALF_OPEN states.

    CLOSED -> OPEN when failure_rate over the trailing window crosses
    `failure_threshold`. OPEN -> HALF_OPEN after `cooldown_seconds`. A
    single HALF_OPEN probe success closes it; a probe failure reopens it
    and resets the cooldown clock.
    """

    failure_threshold: float = 0.5
    window_size: int = 20
    cooldown_seconds: float = 30.0

    _outcomes: list[bool] = field(default_factory=list)
    _state: str = field(default=CircuitState.CLOSED.value)
    _opened_at: float | None = field(default=None)

    @property
    def state(self) -> str:
        if self._state == CircuitState.OPEN.value and self._opened_at is not None:
            if time.monotonic() - self._opened_at >= self.cooldown_seconds:
                self._state = CircuitState.HALF_OPEN.value
        return self._state

    def allow_request(self) -> bool:
        return self.state != CircuitState.OPEN.value

    def record(self, success: bool) -> None:
        if self.state == CircuitState.HALF_OPEN.value:
            self._state = CircuitState.CLOSED.value if success else CircuitState.OPEN.value
            self._opened_at = None if success else time.monotonic()
            self._outcomes.clear()
            return

        self._outcomes.append(success)
        if len(self._outcomes) > self.window_size:
            self._outcomes.pop(0)
        if len(self._outcomes) >= max(4, self.window_size // 4):
            failure_rate = 1 - (sum(self._outcomes) / len(self._outcomes))
            if failure_rate >= self.failure_threshold:
                self._state = CircuitState.OPEN.value
                self._opened_at = time.monotonic()


class CircuitBreakerRegistry:
    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}

    def get(self, provider_name: str) -> CircuitBreaker:
        if provider_name not in self._breakers:
            self._breakers[provider_name] = CircuitBreaker()
        return self._breakers[provider_name]
