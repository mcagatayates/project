from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import GUID, Base, CreatedAtMixin, UUIDPKMixin
from app.db.models.enums import GateStatus, ProductionMode


class Concept(UUIDPKMixin, CreatedAtMixin, Base):
    __tablename__ = "concepts"

    design_genome_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("design_genomes.id"), index=True)
    collection_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("collections.id"), index=True)
    production_mode: Mapped[str] = mapped_column(String(20), default=ProductionMode.DISCOVERY.value)
    planned_candidate_count: Mapped[int] = mapped_column(Integer, default=2)
    gate_status: Mapped[str] = mapped_column(String(20), default=GateStatus.PENDING.value)
    gate_reasoning: Mapped[str | None] = mapped_column(String(2000), nullable=True)
