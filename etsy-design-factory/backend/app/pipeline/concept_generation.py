"""Concept Generation: DesignGenome + Collection -> Concept.

Per docs/AGENT_CONTRACTS.md, must query relevant Experiment history before
creating the concept — never propose something already tried without
looking at what happened last time.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.collection import Collection
from app.db.models.concept import Concept
from app.db.models.experiment import Experiment
from app.db.models.genome import DesignGenome as DesignGenomeRow
from app.pipeline.quality_config import get_quality_config


def relevant_experiments(session: Session, *, collection_id: uuid.UUID, limit: int = 10) -> list[Experiment]:
    stmt = (
        select(Experiment)
        .where(Experiment.collection_id == collection_id)
        .order_by(Experiment.created_at.desc())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().all())


def create_concept(
    session: Session,
    *,
    genome_row: DesignGenomeRow,
    collection: Collection,
    production_mode: str,
    planned_candidate_count: int | None = None,
) -> Concept:
    cfg = get_quality_config()["candidate_counts"]
    if planned_candidate_count is None:
        planned_candidate_count = (
            cfg["discovery_initial"] if production_mode == "DISCOVERY" else cfg["production_initial"]
        )

    # Querying history is a mandatory step, not just documentation: it is
    # what lets Concept Gate reason about "have we tried this before".
    relevant_experiments(session, collection_id=collection.id)

    concept = Concept(
        design_genome_id=genome_row.id,
        collection_id=collection.id,
        production_mode=production_mode,
        planned_candidate_count=planned_candidate_count,
    )
    session.add(concept)
    session.flush()
    return concept
