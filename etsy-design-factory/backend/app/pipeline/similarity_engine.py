"""Creative Fatigue Protection: similarity across perceptual hash, palette
and DesignGenome fields. A visually attractive design is still rejected
when it is excessively similar to previous inventory (mission requirement).
"""

from __future__ import annotations

import imagehash

from app.genome.schema import DesignGenome

_CATEGORICAL_FIELDS: tuple[tuple[str, str], ...] = (
    ("subject_dna", "subject_category"),
    ("subject_dna", "primary_subject"),
    ("style_dna", "art_movement"),
    ("style_dna", "rendering_style"),
    ("composition_dna", "layout_type"),
    ("palette_dna", "palette_name"),
    ("medium_dna", "medium"),
    ("era_dna", "era_reference"),
    ("mood_dna", "primary_mood"),
)


def phash_hamming_distance(hash_a: str, hash_b: str) -> int:
    return imagehash.hex_to_hash(hash_a) - imagehash.hex_to_hash(hash_b)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return (128, 128, 128)
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def palette_similarity(a: DesignGenome, b: DesignGenome) -> float:
    """1.0 = identical primary/background colors, 0.0 = maximally different."""
    a_primary, a_bg = a.primary_and_background_hex()
    b_primary, b_bg = b.primary_and_background_hex()
    max_dist = (255**2 * 3) ** 0.5

    def color_sim(hex_a: str, hex_b: str) -> float:
        ra, ga, ba = _hex_to_rgb(hex_a)
        rb, gb, bb = _hex_to_rgb(hex_b)
        dist = ((ra - rb) ** 2 + (ga - gb) ** 2 + (ba - bb) ** 2) ** 0.5
        return 1.0 - (dist / max_dist)

    return (color_sim(a_primary, b_primary) + color_sim(a_bg, b_bg)) / 2.0


def genome_similarity(a: DesignGenome, b: DesignGenome) -> float:
    """Fraction of tracked categorical DNA fields that match exactly, blended
    with palette color-distance similarity. 1.0 = same creative family and
    nearly the same subject/palette; 0.0 = unrelated."""
    matches = 0
    for block, field in _CATEGORICAL_FIELDS:
        a_val = getattr(getattr(a, block), field)
        b_val = getattr(getattr(b, block), field)
        if a_val == b_val:
            matches += 1
    categorical_score = matches / len(_CATEGORICAL_FIELDS)
    palette_score = palette_similarity(a, b)
    return 0.7 * categorical_score + 0.3 * palette_score


class SimilarityMatch:
    __slots__ = ("reference_id", "phash_distance", "genome_score", "palette_score", "reason")

    def __init__(self, reference_id, phash_distance: int, genome_score: float, palette_score: float, reason: str):
        self.reference_id = reference_id
        self.phash_distance = phash_distance
        self.genome_score = genome_score
        self.palette_score = palette_score
        self.reason = reason

    def __repr__(self) -> str:  # pragma: no cover - debug convenience
        return f"SimilarityMatch({self.reference_id}, {self.reason})"
