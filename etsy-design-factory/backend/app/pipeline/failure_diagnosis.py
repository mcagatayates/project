"""Failure Diagnosis: classify a QC failure so Selective Repair can decide
whether another generation attempt is worth its expected cost."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models.enums import CandidateStatus, FailureClass
from app.db.models.evaluation import SCORE_DIMENSIONS, Evaluation
from app.db.models.failure import FailureRecord
from app.db.models.generation import GenerationCandidate
from app.pipeline.quality_config import get_quality_config

DIAGNOSER_ID = "rule_based_diagnoser_v1"


def classify(evaluation: Evaluation) -> tuple[str, list[str], str]:
    cfg = get_quality_config()
    scores = evaluation.scores()
    problems: list[str] = []
    for dim in SCORE_DIMENSIONS:
        problems.extend(scores[dim]["problems"])

    for dim in cfg["hard_floor_dimensions"]:
        if scores[dim]["value"] < cfg["hard_floor_value"]:
            reasoning = (
                f"{dim}={scores[dim]['value']:.2f} is below the hard floor "
                f"({cfg['hard_floor_value']}) — defects at this severity are not "
                "repairable by another generation attempt with the same brief."
            )
            return FailureClass.TERMINAL_FAILURE.value, problems, reasoning

    creative_dims = ("aesthetic", "originality", "commercial_potential")
    creative_avg = sum(scores[d]["value"] for d in creative_dims) / len(creative_dims)
    if creative_avg >= cfg["repair"]["promising_min_avg"]:
        reasoning = (
            f"creative average={creative_avg:.2f} clears the promising bar "
            f"({cfg['repair']['promising_min_avg']}); the failure looks isolated "
            "to a fixable technical/print dimension."
        )
        return FailureClass.PROMISING.value, problems, reasoning

    reasoning = f"creative average={creative_avg:.2f}; standard repairable failure, no standout strength."
    return FailureClass.REPAIRABLE_FAILURE.value, problems, reasoning


def diagnose_failure(session: Session, *, candidate: GenerationCandidate, evaluation: Evaluation) -> FailureRecord:
    failure_class, problems, reasoning = classify(evaluation)
    record = FailureRecord(
        generation_candidate_id=candidate.id,
        failure_class=failure_class,
        detected_problems=problems,
        diagnosis_reasoning=reasoning,
        diagnosed_by=DIAGNOSER_ID,
    )
    session.add(record)
    candidate.status = CandidateStatus.DIAGNOSED.value
    session.flush()
    return record
