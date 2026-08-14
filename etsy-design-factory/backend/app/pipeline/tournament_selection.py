"""Tournament Selection: among a concept's QC_PASSED candidates, rank by
the full score vector under configurable weights and mark winner(s)
SELECTED, the rest ELIMINATED (with reasoning recorded)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.enums import CandidateStatus
from app.db.models.evaluation import SCORE_DIMENSIONS, Evaluation
from app.db.models.generation import GenerationCandidate
from app.pipeline.quality_config import get_quality_config


def weighted_score(evaluation: Evaluation, weights: dict[str, float]) -> float:
    scores = evaluation.scores()
    return sum(scores[dim]["value"] * weights.get(dim, 0) for dim in SCORE_DIMENSIONS)


def latest_evaluation(session: Session, candidate_id) -> Evaluation | None:
    stmt = (
        select(Evaluation)
        .where(Evaluation.generation_candidate_id == candidate_id)
        .order_by(Evaluation.created_at.desc())
        .limit(1)
    )
    return session.execute(stmt).scalars().first()


def run_tournament(session: Session, *, concept_id, winners: int = 1) -> list[GenerationCandidate]:
    weights = get_quality_config()["tournament_weights"]

    stmt = select(GenerationCandidate).where(
        GenerationCandidate.concept_id == concept_id,
        GenerationCandidate.status == CandidateStatus.QC_PASSED.value,
    )
    candidates = list(session.execute(stmt).scalars().all())
    if not candidates:
        return []

    ranked: list[tuple[float, GenerationCandidate, Evaluation]] = []
    for c in candidates:
        ev = latest_evaluation(session, c.id)
        if ev is None:
            continue
        ranked.append((weighted_score(ev, weights), c, ev))
    ranked.sort(key=lambda t: t[0], reverse=True)

    selected: list[GenerationCandidate] = []
    for rank, (score, candidate, _ev) in enumerate(ranked):
        if rank < winners:
            candidate.status = CandidateStatus.SELECTED.value
            selected.append(candidate)
        else:
            candidate.status = CandidateStatus.ELIMINATED.value
            candidate.elimination_reason = (
                f"tournament_selection: ranked #{rank + 1} of {len(ranked)} "
                f"(weighted_score={score:.3f}); lost to {winners} winner slot(s)."
            )
    session.flush()
    return selected
