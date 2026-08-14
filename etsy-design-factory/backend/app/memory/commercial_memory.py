"""CommercialMemory: real product-performance history and nothing else.
Every value here traces back to an actual CommercialObservation row --
this module has no code path that invents a number when an adapter
returned none. See docs/DOMAIN_MODEL.md CommercialObservation /
docs/AGENT_CONTRACTS.md "Performance Ingestion"."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.commercial import CommercialObservation


def record_observation(
    session: Session,
    *,
    source: str,
    metric_name: str,
    metric_value: float | None,
    observed_at: datetime,
    artwork_id: uuid.UUID | None = None,
    design_genome_id: uuid.UUID | None = None,
    external_listing_id: str | None = None,
) -> CommercialObservation:
    obs = CommercialObservation(
        artwork_id=artwork_id,
        design_genome_id=design_genome_id,
        external_listing_id=external_listing_id,
        source=source,
        metric_name=metric_name,
        metric_value=metric_value,
        observed_at=observed_at,
        ingested_at=datetime.now(observed_at.tzinfo),
    )
    session.add(obs)
    session.flush()
    return obs


def average_metric_for_genome(session: Session, *, design_genome_id: uuid.UUID, metric_name: str) -> float | None:
    stmt = select(func.avg(CommercialObservation.metric_value)).where(
        CommercialObservation.design_genome_id == design_genome_id,
        CommercialObservation.metric_name == metric_name,
        CommercialObservation.metric_value.isnot(None),
    )
    value = session.execute(stmt).scalar_one()
    return float(value) if value is not None else None


def average_metric_for_genomes(
    session: Session, *, design_genome_ids: list[uuid.UUID], metric_name: str
) -> float | None:
    if not design_genome_ids:
        return None
    stmt = select(func.avg(CommercialObservation.metric_value)).where(
        CommercialObservation.design_genome_id.in_(design_genome_ids),
        CommercialObservation.metric_name == metric_name,
        CommercialObservation.metric_value.isnot(None),
    )
    value = session.execute(stmt).scalar_one()
    return float(value) if value is not None else None


def observation_count_for_genome(session: Session, *, design_genome_id: uuid.UUID) -> int:
    stmt = select(func.count(CommercialObservation.id)).where(
        CommercialObservation.design_genome_id == design_genome_id
    )
    return int(session.execute(stmt).scalar_one())
