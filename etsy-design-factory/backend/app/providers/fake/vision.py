"""Deterministic fake VisionProvider.

Derives all seven score dimensions from real, cheap statistics computed on
the actual generated pixels (see image_stats.py) rather than returning
random numbers — so the same image always scores the same way, and images
engineered (via FakeImageGenProvider's quality_seed) to be flawed actually
score lower on technical_quality/printability.

NOTE: `originality` here is a weak per-image proxy only. The system's real
duplicate/fatigue detection is app/pipeline/similarity_engine.py, which
compares a candidate against the historical artwork library — that is the
authoritative "creative fatigue protection" mechanism, not this score.
"""

from __future__ import annotations

import time

from app.providers.base import DimensionScore, VisionRubric, VisionScoreResult
from app.providers.fake.image_stats import (
    edge_density,
    load_array,
    luminance_contrast,
    outlier_pixel_ratio,
    saturation_level,
)


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


class FakeVisionProvider:
    name = "fake_vision"

    def __init__(self, price_per_score_usd: float = 0.005):
        self.price_per_score_usd = price_per_score_usd

    async def score(self, *, image_bytes: bytes, rubric: VisionRubric) -> VisionScoreResult:
        start = time.monotonic()
        arr = load_array(image_bytes)

        contrast = luminance_contrast(arr)
        saturation = saturation_level(arr)
        edges = edge_density(arr)

        expected_colors = rubric.context.get("expected_colors_rgb", [])
        outlier_ratio = outlier_pixel_ratio(arr, expected_colors) if expected_colors else 0.0

        technical_quality = _clamp(1.0 - outlier_ratio * 3.0)
        printability = _clamp(1.0 - outlier_ratio * 2.5)
        aesthetic = _clamp(0.25 + contrast * 0.45 + saturation * 0.3 - outlier_ratio * 0.5)
        originality = _clamp(0.5 + edges * 1.5 - outlier_ratio * 0.3)
        commercial_potential = _clamp(0.35 + saturation * 0.35 + contrast * 0.2)

        expected_palette_fit = rubric.context.get("collection_fit_hint", 0.75)
        collection_fit = _clamp(float(expected_palette_fit) - outlier_ratio * 0.4)

        diversity = _clamp(0.5 + edges * 0.8 - outlier_ratio * 0.2)

        def problems_for(value: float, label: str) -> list[str]:
            return [f"{label} below acceptable floor ({value:.2f})"] if value < 0.5 else []

        scores = {
            "aesthetic": DimensionScore(
                aesthetic,
                0.8,
                f"contrast={contrast:.2f} saturation={saturation:.2f}",
                problems_for(aesthetic, "aesthetic"),
            ),
            "originality": DimensionScore(
                originality,
                0.6,
                f"edge_density={edges:.2f} (per-image proxy; see similarity_engine for real dedup)",
                problems_for(originality, "originality"),
            ),
            "commercial_potential": DimensionScore(
                commercial_potential,
                0.7,
                f"saturation={saturation:.2f} contrast={contrast:.2f}",
                problems_for(commercial_potential, "commercial_potential"),
            ),
            "technical_quality": DimensionScore(
                technical_quality,
                0.85,
                f"artifact_ratio={outlier_ratio:.3f}",
                problems_for(technical_quality, "technical_quality"),
            ),
            "printability": DimensionScore(
                printability, 0.85, f"artifact_ratio={outlier_ratio:.3f}", problems_for(printability, "printability")
            ),
            "collection_fit": DimensionScore(
                collection_fit,
                0.6,
                f"palette_hint={expected_palette_fit}",
                problems_for(collection_fit, "collection_fit"),
            ),
            "diversity": DimensionScore(
                diversity, 0.5, f"edge_density={edges:.2f}", problems_for(diversity, "diversity")
            ),
        }

        latency_ms = int((time.monotonic() - start) * 1000) + 1
        return VisionScoreResult(
            scores=scores,
            cost_usd=self.price_per_score_usd,
            latency_ms=latency_ms,
            raw_metadata={"provider": self.name, "outlier_ratio": outlier_ratio},
        )
