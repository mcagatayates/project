"""Convert between the Pydantic DesignGenome (creative-domain model) and
the SQLAlchemy DesignGenome row (persistence model). Field names are kept
identical by design (see docs/DESIGN_GENOME_SCHEMA.md / DATABASE.md) so
this is a straight structural mapping, not a translation layer that can
drift silently.
"""

from __future__ import annotations

from app.db.models.genome import DesignGenome as DesignGenomeRow
from app.genome.schema import DNA_BLOCK_NAMES, DesignGenome, GenomeCreatedBy


def to_row(genome: DesignGenome) -> DesignGenomeRow:
    kwargs = {name: getattr(genome, name).model_dump(mode="json") for name in DNA_BLOCK_NAMES}
    return DesignGenomeRow(
        id=genome.id,
        design_lineage_id=genome.design_lineage_id,
        version=genome.version,
        parent_genome_id=genome.parent_genome_id,
        derived_from_version_id=genome.derived_from_version_id,
        generation_number=genome.generation_number,
        collection_id=genome.collection_id,
        created_by=genome.created_by.value,
        mutation_map=genome.mutation_map,
        **kwargs,
    )


def from_row(row: DesignGenomeRow) -> DesignGenome:
    kwargs = {name: getattr(row, name) for name in DNA_BLOCK_NAMES}
    return DesignGenome(
        id=row.id,
        design_lineage_id=row.design_lineage_id,
        version=row.version,
        parent_genome_id=row.parent_genome_id,
        derived_from_version_id=row.derived_from_version_id,
        generation_number=row.generation_number,
        collection_id=row.collection_id,
        created_by=GenomeCreatedBy(row.created_by),
        mutation_map=row.mutation_map,
        **kwargs,
    )
