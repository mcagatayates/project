from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import GUID, Base, CreatedAtMixin, JSONVariant, UUIDPKMixin

SCORE_DIMENSIONS = (
    "aesthetic",
    "originality",
    "commercial_potential",
    "technical_quality",
    "printability",
    "collection_fit",
    "diversity",
)


class Evaluation(UUIDPKMixin, CreatedAtMixin, Base):
    """One scoring pass. Append-only — re-scoring inserts a new row.

    Each score column is a JSON object: {value, confidence, reasoning, problems: []}.
    """

    __tablename__ = "evaluations"

    generation_candidate_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("generation_candidates.id"), index=True
    )
    scored_by: Mapped[str] = mapped_column(String(100))

    aesthetic: Mapped[dict] = mapped_column(JSONVariant)
    originality: Mapped[dict] = mapped_column(JSONVariant)
    commercial_potential: Mapped[dict] = mapped_column(JSONVariant)
    technical_quality: Mapped[dict] = mapped_column(JSONVariant)
    printability: Mapped[dict] = mapped_column(JSONVariant)
    collection_fit: Mapped[dict] = mapped_column(JSONVariant)
    diversity: Mapped[dict] = mapped_column(JSONVariant)

    overall_pass: Mapped[bool] = mapped_column(Boolean)

    def scores(self) -> dict[str, dict]:
        return {dim: getattr(self, dim) for dim in SCORE_DIMENSIONS}
