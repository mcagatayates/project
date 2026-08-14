"""Champion / Challenger: strong historical creative families become
Champions; new hypotheses become Challengers. Champion artwork is never
copied -- only high-level DNA characteristics associated with performance
are extracted and used as constraints for structurally new challengers.
See docs/AGENT_CONTRACTS.md, docs/DOMAIN_MODEL.md CreativeFamily.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.collection import Collection
from app.db.models.commercial import CreativeFamily
from app.db.models.enums import CreativeFamilyStatus
from app.genome.schema import DesignGenome
from app.memory.commercial_memory import average_metric_for_genomes
from app.pipeline.genome_ideation import create_genome

# Promotion requires real, repeated commercial signal -- never inferred
# from QC/aesthetic scores alone, which measure creative quality, not
# market performance.
MIN_MEMBERS_FOR_CHAMPION = 3
MIN_OBSERVATIONS_FOR_CHAMPION = 3


def family_signature(genome: DesignGenome) -> dict:
    """High-level characteristics, not the genome itself -- this is what
    a challenger is allowed to inherit from a champion."""
    return {
        "art_movement": genome.style_dna.art_movement,
        "subject_category": genome.subject_dna.subject_category.value,
        "medium": genome.medium_dna.medium.value,
        "palette_name": genome.palette_dna.palette_name,
    }


def find_or_create_family(session: Session, *, genome: DesignGenome) -> CreativeFamily:
    signature = family_signature(genome)
    stmt = select(CreativeFamily).where(CreativeFamily.status != CreativeFamilyStatus.RETIRED.value)
    for family in session.execute(stmt).scalars().all():
        if family.defining_dna_signature == signature:
            members = list(family.member_genome_ids or [])
            if str(genome.id) not in members:
                members.append(str(genome.id))
                family.member_genome_ids = members
                session.flush()
            return family

    family = CreativeFamily(
        name=f"{signature['art_movement']}-{signature['subject_category']}-{signature['palette_name']}",
        defining_dna_signature=signature,
        status=CreativeFamilyStatus.CHALLENGER.value,
        member_genome_ids=[str(genome.id)],
    )
    session.add(family)
    session.flush()
    return family


def maybe_promote_to_champion(
    session: Session, *, family: CreativeFamily, metric_name: str = "favorites"
) -> CreativeFamily:
    """Only promotes on REAL commercial signal: enough members, enough
    observations, and a positive average of the named metric. Silently
    no-ops (stays CHALLENGER) when that evidence doesn't exist yet --
    never promotes on creative/QC scores alone."""
    if family.status != CreativeFamilyStatus.CHALLENGER.value:
        return family
    member_ids = [uuid.UUID(m) for m in (family.member_genome_ids or [])]
    if len(member_ids) < MIN_MEMBERS_FOR_CHAMPION:
        return family

    avg_metric = average_metric_for_genomes(session, design_genome_ids=member_ids, metric_name=metric_name)
    if avg_metric is None:
        return family

    family.status = CreativeFamilyStatus.CHAMPION.value
    family.performance_summary = {"metric": metric_name, "average": avg_metric, "member_count": len(member_ids)}
    session.flush()
    return family


def generate_challenger_genome(
    collection: Collection, *, champion: CreativeFamily, slot_index: int, seed: int | None = None
) -> DesignGenome:
    """A structurally new design constrained by (not copied from) a
    Champion family's signature: same art movement + medium (the traits
    associated with its performance), everything else independently
    ideated so it is a genuine new creative attempt, not a reproduction."""
    base = create_genome(collection, slot_index=slot_index, seed=seed)
    signature = champion.defining_dna_signature
    return base.model_copy(
        update={
            "style_dna": base.style_dna.model_copy(
                update={"art_movement": signature.get("art_movement", base.style_dna.art_movement)}
            ),
        }
    )
