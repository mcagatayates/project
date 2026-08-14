"""ExperimentMemory: persistent record of hypothesis-driven creative work,
and the lookup future concept generation must use before proposing
something already tried. See docs/AGENT_CONTRACTS.md "Concept Generation"
(mandatory prior-art query) and "Experiment" in docs/DOMAIN_MODEL.md.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.evaluation import SCORE_DIMENSIONS, Evaluation
from app.db.models.experiment import Experiment
from app.db.models.generation import GenerationCandidate


def record_experiment(
    session: Session,
    *,
    hypothesis: str,
    design_genome_id: uuid.UUID | None,
    collection_id: uuid.UUID | None,
    variables_tested: dict,
    provider: str,
    model: str,
    params: dict,
    candidate_ids: list[uuid.UUID],
    winner_candidate_id: uuid.UUID | None,
    cost_usd: float,
    failure_summary: str | None = None,
) -> Experiment:
    scores_summary: dict[str, dict] = {}
    for candidate_id in candidate_ids:
        stmt = (
            select(Evaluation)
            .where(Evaluation.generation_candidate_id == candidate_id)
            .order_by(Evaluation.created_at.desc())
            .limit(1)
        )
        evaluation = session.execute(stmt).scalars().first()
        if evaluation is None:
            continue
        scores = evaluation.scores()
        scores_summary[str(candidate_id)] = {dim: scores[dim]["value"] for dim in SCORE_DIMENSIONS}

    experiment = Experiment(
        hypothesis=hypothesis,
        design_genome_id=design_genome_id,
        collection_id=collection_id,
        variables_tested=variables_tested,
        provider=provider,
        model=model,
        params=params,
        output_candidate_ids=[str(c) for c in candidate_ids],
        scores_summary=scores_summary,
        winner_candidate_id=winner_candidate_id,
        failure_summary=failure_summary,
        cost_usd=cost_usd,
    )
    session.add(experiment)
    session.flush()
    return experiment


def relevant_experiments(
    session: Session, *, collection_id: uuid.UUID | None = None, limit: int = 10
) -> list[Experiment]:
    stmt = select(Experiment).order_by(Experiment.created_at.desc()).limit(limit)
    if collection_id is not None:
        stmt = stmt.where(Experiment.collection_id == collection_id)
    return list(session.execute(stmt).scalars().all())


def record_commercial_outcome(session: Session, *, experiment_id: uuid.UUID, outcome: dict) -> Experiment | None:
    """Attaches real commercial performance to a past experiment once it
    becomes available (see app/memory/commercial_memory.py). Never
    fabricates an outcome -- `outcome` must come from an actual
    CommercialObservation rollup."""
    experiment = session.get(Experiment, experiment_id)
    if experiment is None:
        return None
    experiment.commercial_outcome = outcome
    session.flush()
    return experiment


def candidate_belongs_to_experiment(
    session: Session, *, candidate: GenerationCandidate, search_limit: int = 500
) -> Experiment | None:
    """Not indexed -- JSON-array containment isn't portable across the
    Postgres/SQLite dialects this codebase supports (see
    docs/DATABASE.md), so this scans recent experiments in Python rather
    than relying on a dialect-specific JSON operator."""
    candidate_id = str(candidate.id)
    stmt = select(Experiment).order_by(Experiment.created_at.desc()).limit(search_limit)
    for experiment in session.execute(stmt).scalars().all():
        if candidate_id in (experiment.output_candidate_ids or []):
            return experiment
    return None
