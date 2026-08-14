from __future__ import annotations

import uuid

from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import GUID, Base, CreatedAtMixin, JSONVariant, UUIDPKMixin


class Experiment(UUIDPKMixin, CreatedAtMixin, Base):
    """Persistent record of a hypothesis-driven unit of creative work.

    Never forget experiments: future concept generation must query this
    table for relevant prior art before creating new concepts.
    """

    __tablename__ = "experiments"

    hypothesis: Mapped[str] = mapped_column(String(2000))
    design_genome_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    collection_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    variables_tested: Mapped[dict] = mapped_column(JSONVariant, default=dict)
    provider: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(100))
    params: Mapped[dict] = mapped_column(JSONVariant, default=dict)
    output_candidate_ids: Mapped[list] = mapped_column(JSONVariant, default=list)
    scores_summary: Mapped[dict] = mapped_column(JSONVariant, default=dict)
    winner_candidate_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    failure_summary: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 4), default=0)
    commercial_outcome: Mapped[dict | None] = mapped_column(JSONVariant, nullable=True)
