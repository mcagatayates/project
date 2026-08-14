from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import GUID, Base, CreatedAtMixin, UUIDPKMixin
from app.db.models.enums import ApprovalAction


class Approval(UUIDPKMixin, CreatedAtMixin, Base):
    __tablename__ = "approvals"

    generation_candidate_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("generation_candidates.id"), index=True
    )
    action: Mapped[str] = mapped_column(String(30), default=ApprovalAction.APPROVE.value)
    actor: Mapped[str] = mapped_column(String(200))
    resulting_genome_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
