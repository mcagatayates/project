"""Wires the ProviderRegistry's health-event callback to persisted
ProviderHealthLog rows, without the registry itself needing a DB session."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models.cost import ProviderHealthLog


def make_db_health_hook(session: Session):
    def _hook(
        provider: str, operation_type: str, success: bool, latency_ms: int, error_class: str | None, circuit_state: str
    ) -> None:
        session.add(
            ProviderHealthLog(
                provider=provider,
                operation_type=operation_type,
                success=success,
                latency_ms=latency_ms,
                error_class=error_class,
                circuit_state=circuit_state,
            )
        )
        session.flush()

    return _hook
