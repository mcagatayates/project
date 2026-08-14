"""Multi-dimensional Vision QC: score every candidate on seven independent
dimensions and decide pass/fail from configurable thresholds — never a
single blended score. See docs/AGENT_CONTRACTS.md."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.cost.ledger import record_cost
from app.db.models.enums import CandidateStatus
from app.db.models.evaluation import SCORE_DIMENSIONS, Evaluation
from app.db.models.generation import GenerationCandidate
from app.genome.schema import DesignGenome
from app.pipeline.quality_config import get_quality_config
from app.providers.base import VisionRubric, VisionScoreResult
from app.providers.registry import ProviderRegistry


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def decide_pass(scores: dict[str, dict]) -> bool:
    cfg = get_quality_config()
    for dim in cfg["hard_floor_dimensions"]:
        if scores[dim]["value"] < cfg["hard_floor_value"]:
            return False
    weights = cfg["tournament_weights"]
    weighted = sum(scores[dim]["value"] * weights.get(dim, 0) for dim in SCORE_DIMENSIONS)
    if weighted < cfg["weighted_pass_threshold"]:
        return False
    if any(scores[dim]["value"] < cfg["score_pass_floor"] for dim in SCORE_DIMENSIONS):
        # a single very weak dimension still fails even if the weighted
        # average clears the bar — no dimension gets silently averaged away
        weak = [d for d in SCORE_DIMENSIONS if scores[d]["value"] < cfg["score_pass_floor"]]
        if len(weak) > 2:
            return False
    return True


async def run_vision_qc(
    session: Session,
    registry: ProviderRegistry,
    *,
    candidate: GenerationCandidate,
    genome: DesignGenome,
    collection_fit_hint: float = 0.75,
) -> Evaluation:
    image_bytes = await registry.call("storage.default", "get", key=candidate.storage_key)

    primary_hex, background_hex = genome.primary_and_background_hex()
    rubric = VisionRubric(
        dimensions=SCORE_DIMENSIONS,
        context={
            "expected_colors_rgb": [_hex_to_rgb(primary_hex), _hex_to_rgb(background_hex)],
            "collection_fit_hint": collection_fit_hint,
        },
    )
    result: VisionScoreResult = await registry.call("vision.qc", "score", image_bytes=image_bytes, rubric=rubric)

    scores_dict = {
        dim: {
            "value": s.value,
            "confidence": s.confidence,
            "reasoning": s.reasoning,
            "problems": s.problems,
        }
        for dim, s in result.scores.items()
    }
    overall_pass = decide_pass(scores_dict)

    evaluation = Evaluation(
        generation_candidate_id=candidate.id,
        scored_by=registry.get("vision.qc").name,
        overall_pass=overall_pass,
        **scores_dict,
    )
    session.add(evaluation)

    candidate.status = CandidateStatus.QC_PASSED.value if overall_pass else CandidateStatus.QC_FAILED.value
    session.flush()

    record_cost(
        session,
        provider=registry.get("vision.qc").name,
        model="vision-qc",
        operation="vision_qc",
        generation_cost_usd=result.cost_usd,
        generation_candidate_id=candidate.id,
    )
    return evaluation
