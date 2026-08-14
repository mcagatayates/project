"""Diversity / Fatigue Control: the last gate before a candidate is
presented for human approval. Compares a SELECTED candidate against the
historical artwork library and against other candidates selected the same
day, and demotes it back to ELIMINATED if it's too close to something that
already exists — regardless of how good it otherwise scored.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.artwork import Artwork
from app.db.models.enums import CandidateStatus
from app.db.models.generation import GenerationCandidate
from app.db.models.genome import DesignGenome as DesignGenomeRow
from app.genome.codec import from_row
from app.genome.schema import DesignGenome
from app.pipeline.quality_config import get_quality_config
from app.pipeline.similarity_engine import (
    SimilarityMatch,
    genome_similarity,
    palette_similarity,
    phash_hamming_distance,
)


def _find_conflict(
    candidate: GenerationCandidate,
    genome: DesignGenome,
    *,
    reference_phash: str,
    reference_genome: DesignGenome,
    reference_id,
    thresholds: dict,
) -> SimilarityMatch | None:
    phash_dist = phash_hamming_distance(candidate.perceptual_hash, reference_phash)
    g_score = genome_similarity(genome, reference_genome)
    p_score = palette_similarity(genome, reference_genome)

    if phash_dist <= thresholds["phash_hamming_threshold"]:
        return SimilarityMatch(
            reference_id, phash_dist, g_score, p_score, f"near-duplicate pixels (phash distance {phash_dist})"
        )
    if g_score >= thresholds["genome_similarity_threshold"]:
        return SimilarityMatch(
            reference_id, phash_dist, g_score, p_score, f"near-duplicate creative DNA (genome similarity {g_score:.2f})"
        )
    if (
        p_score >= thresholds["palette_similarity_threshold"]
        and g_score >= thresholds["genome_similarity_threshold"] * 0.8
    ):
        return SimilarityMatch(
            reference_id,
            phash_dist,
            g_score,
            p_score,
            f"repeated palette + related DNA (palette similarity {p_score:.2f})",
        )
    return None


def run_diversity_control(
    session: Session,
    *,
    candidate: GenerationCandidate,
    genome: DesignGenome,
    same_day_window_hours: int = 20,
) -> tuple[bool, SimilarityMatch | None]:
    """Returns (kept, conflict). On conflict, candidate.status is set to
    ELIMINATED with elimination_reason recorded; SELECTED is left as-is
    when kept=True (caller already set it via tournament_selection)."""
    thresholds = get_quality_config()["similarity"]

    # 1. Historical artwork library (approved designs).
    artwork_stmt = select(Artwork.id, Artwork.generation_candidate_id, Artwork.design_genome_id)
    for artwork_id, gen_candidate_id, design_genome_id in session.execute(artwork_stmt).all():
        ref_candidate = session.get(GenerationCandidate, gen_candidate_id)
        ref_genome_row = session.get(DesignGenomeRow, design_genome_id)
        if ref_candidate is None or ref_genome_row is None:
            continue
        conflict = _find_conflict(
            candidate,
            genome,
            reference_phash=ref_candidate.perceptual_hash,
            reference_genome=from_row(ref_genome_row),
            reference_id=artwork_id,
            thresholds=thresholds,
        )
        if conflict:
            candidate.status = CandidateStatus.ELIMINATED.value
            candidate.elimination_reason = f"diversity_control vs artwork {artwork_id}: {conflict.reason}"
            session.flush()
            return False, conflict

    # 2. Siblings selected earlier today (avoid two near-identical designs
    #    in the same batch, before either has become an Artwork yet).
    cutoff = datetime.now(timezone.utc) - timedelta(hours=same_day_window_hours)
    sibling_stmt = (
        select(GenerationCandidate)
        .where(GenerationCandidate.status == CandidateStatus.SELECTED.value)
        .where(GenerationCandidate.id != candidate.id)
        .where(GenerationCandidate.created_at >= cutoff)
    )
    for sibling in session.execute(sibling_stmt).scalars().all():
        sibling_genome_row = session.get(DesignGenomeRow, sibling.design_genome_id)
        if sibling_genome_row is None:
            continue
        conflict = _find_conflict(
            candidate,
            genome,
            reference_phash=sibling.perceptual_hash,
            reference_genome=from_row(sibling_genome_row),
            reference_id=sibling.id,
            thresholds=thresholds,
        )
        if conflict:
            candidate.status = CandidateStatus.ELIMINATED.value
            candidate.elimination_reason = f"diversity_control vs sibling candidate {sibling.id}: {conflict.reason}"
            session.flush()
            return False, conflict

    return True, None
