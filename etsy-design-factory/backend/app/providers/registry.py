"""ProviderRegistry: pipeline stages ask for a ROLE, never a vendor name.

Wraps every call with: rate limiting (per adapter), a circuit breaker (per
adapter), bounded retry with exponential backoff + jitter, and an ordered
fallback chain. Every attempt — success or failure — is reported through
`on_health_event` so the caller can persist a ProviderHealthLog row without
this module needing a DB session itself.

See docs/PROVIDER_ARCHITECTURE.md.
"""
from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.providers.base import ProviderError
from app.providers.circuit_breaker import CircuitBreakerRegistry
from app.providers.rate_limit import RateLimiterRegistry

HealthEventHook = Callable[[str, str, bool, int, str | None, str], None]


@dataclass
class AdapterSpec:
    name: str
    instance: Any
    rate_per_minute: float = 120.0
    max_retries: int = 3
    backoff_base_s: float = 0.5
    backoff_max_s: float = 20.0


@dataclass
class RoleConfig:
    primary: AdapterSpec
    fallbacks: list[AdapterSpec] = field(default_factory=list)

    @property
    def chain(self) -> list[AdapterSpec]:
        return [self.primary, *self.fallbacks]


class ProviderRegistry:
    def __init__(self, on_health_event: HealthEventHook | None = None):
        self._roles: dict[str, RoleConfig] = {}
        self._circuits = CircuitBreakerRegistry()
        self._limiters = RateLimiterRegistry()
        self._on_health_event = on_health_event

    def register_role(self, role: str, primary: AdapterSpec, fallbacks: list[AdapterSpec] | None = None) -> None:
        self._roles[role] = RoleConfig(primary=primary, fallbacks=fallbacks or [])

    def get(self, role: str) -> Any:
        """Direct access to the primary adapter for a role (bypasses
        resilience wrapping) — used for cheap, non-critical calls."""
        return self._roles[role].primary.instance

    async def call(self, role: str, method_name: str, /, **kwargs) -> Any:
        if role not in self._roles:
            raise ProviderError(f"no adapter registered for role '{role}'")

        last_error: Exception | None = None
        for spec in self._roles[role].chain:
            circuit = self._circuits.get(spec.name)
            if not circuit.allow_request():
                continue

            limiter = self._limiters.get(spec.name, spec.rate_per_minute)
            method: Callable[..., Awaitable[Any]] = getattr(spec.instance, method_name)

            for attempt in range(1, spec.max_retries + 1):
                await limiter.acquire()
                start = time.monotonic()
                try:
                    result = await method(**kwargs)
                except Exception as exc:  # noqa: BLE001 - adapter errors are provider-shaped
                    latency_ms = int((time.monotonic() - start) * 1000)
                    circuit.record(success=False)
                    self._report(spec.name, method_name, False, latency_ms, type(exc).__name__, circuit.state)
                    last_error = exc
                    if attempt >= spec.max_retries:
                        break
                    backoff = min(spec.backoff_max_s, spec.backoff_base_s * (2 ** (attempt - 1)))
                    backoff += random.uniform(0, backoff * 0.25)
                    await asyncio.sleep(backoff)
                    continue
                else:
                    latency_ms = int((time.monotonic() - start) * 1000)
                    circuit.record(success=True)
                    self._report(spec.name, method_name, True, latency_ms, None, circuit.state)
                    return result

        raise ProviderError(f"all adapters exhausted for role '{role}'") from last_error

    def _report(self, provider: str, operation_type: str, success: bool, latency_ms: int, error_class: str | None, circuit_state: str) -> None:
        if self._on_health_event:
            self._on_health_event(provider, operation_type, success, latency_ms, error_class, circuit_state)
