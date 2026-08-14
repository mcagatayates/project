from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import GUID, Base, CreatedAtMixin, UUIDPKMixin
from app.db.models.enums import CircuitState


class CostEvent(UUIDPKMixin, CreatedAtMixin, Base):
    __tablename__ = "cost_events"

    provider: Mapped[str] = mapped_column(String(100), index=True)
    model: Mapped[str] = mapped_column(String(100))
    operation: Mapped[str] = mapped_column(String(100))
    tokens_input: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_output: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generation_cost_usd: Mapped[float] = mapped_column(Numeric(10, 4), default=0)
    processing_cost_usd: Mapped[float] = mapped_column(Numeric(10, 4), default=0)
    project: Mapped[str] = mapped_column(String(100), default="etsy-wall-art")
    collection_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("collections.id"), nullable=True, index=True
    )
    design_genome_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    generation_candidate_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False)

    @property
    def total_cost_usd(self) -> float:
        return float(self.generation_cost_usd) + float(self.processing_cost_usd)


class ProviderHealthLog(UUIDPKMixin, CreatedAtMixin, Base):
    __tablename__ = "provider_health_logs"

    provider: Mapped[str] = mapped_column(String(100), index=True)
    operation_type: Mapped[str] = mapped_column(String(100))
    success: Mapped[bool] = mapped_column(Boolean)
    latency_ms: Mapped[int] = mapped_column(Integer)
    error_class: Mapped[str | None] = mapped_column(String(200), nullable=True)
    circuit_state: Mapped[str] = mapped_column(String(20), default=CircuitState.CLOSED.value)
