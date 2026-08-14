from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import GUID, Base, CreatedUpdatedMixin, JSONVariant, UUIDPKMixin
from app.db.models.enums import CollectionStatus, ProductionMode


class Collection(UUIDPKMixin, CreatedUpdatedMixin, Base):
    __tablename__ = "collections"

    name: Mapped[str] = mapped_column(String(200))
    thesis: Mapped[str] = mapped_column(String(2000))
    target_aesthetic: Mapped[str] = mapped_column(String(500))
    target_customer_hypothesis: Mapped[str] = mapped_column(String(1000))
    palette_boundaries: Mapped[dict] = mapped_column(JSONVariant, default=dict)
    medium: Mapped[str] = mapped_column(String(100))
    subject_families: Mapped[list] = mapped_column(JSONVariant, default=list)
    composition_diversity_requirements: Mapped[dict] = mapped_column(JSONVariant, default=dict)
    target_design_count: Mapped[int] = mapped_column(default=10)
    experimental_variables: Mapped[dict] = mapped_column(JSONVariant, default=dict)
    status: Mapped[str] = mapped_column(String(20), default=CollectionStatus.DISCOVERY.value)
    mode: Mapped[str] = mapped_column(String(20), default=ProductionMode.DISCOVERY.value)
    creative_family_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("creative_families.id"), nullable=True
    )
