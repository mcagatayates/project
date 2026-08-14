from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import GUID, Base, CreatedAtMixin, JSONVariant, UUIDPKMixin, new_uuid
from app.db.models.enums import GenomeCreatedBy


class DesignGenome(UUIDPKMixin, CreatedAtMixin, Base):
    """Structured creative DNA. Immutable — never updated after insert.

    See docs/DESIGN_GENOME_SCHEMA.md for the field-level contract.
    """

    __tablename__ = "design_genomes"

    design_lineage_id: Mapped[uuid.UUID] = mapped_column(GUID(), default=new_uuid, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    parent_genome_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("design_genomes.id"), nullable=True, index=True
    )
    derived_from_version_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("design_genomes.id"), nullable=True
    )
    generation_number: Mapped[int] = mapped_column(Integer, default=0)
    collection_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("collections.id"), nullable=True, index=True
    )
    created_by: Mapped[str] = mapped_column(String(30), default=GenomeCreatedBy.SYSTEM_DISCOVERY.value)

    subject_dna: Mapped[dict] = mapped_column(JSONVariant)
    style_dna: Mapped[dict] = mapped_column(JSONVariant)
    composition_dna: Mapped[dict] = mapped_column(JSONVariant)
    palette_dna: Mapped[dict] = mapped_column(JSONVariant)
    texture_dna: Mapped[dict] = mapped_column(JSONVariant)
    medium_dna: Mapped[dict] = mapped_column(JSONVariant)
    era_dna: Mapped[dict] = mapped_column(JSONVariant)
    mood_dna: Mapped[dict] = mapped_column(JSONVariant)
    detail_dna: Mapped[dict] = mapped_column(JSONVariant)
    print_dna: Mapped[dict] = mapped_column(JSONVariant)
    commercial_dna: Mapped[dict] = mapped_column(JSONVariant)

    mutation_map: Mapped[dict | None] = mapped_column(JSONVariant, nullable=True)
