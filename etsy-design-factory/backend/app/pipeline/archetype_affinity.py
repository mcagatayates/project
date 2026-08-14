"""Biases which bootstrap collection archetype a new DISCOVERY collection
gets, from real market-intelligence signals ranked by the Opportunity
Engine. This is what closes the gap docs/ROADMAP.md used to name: the
Opportunity Engine ranked real signals correctly, but nothing fed that
ranking back into the Collection Planner's archetype choice.

Falls back to the archetypes' declared order whenever no opportunity's
text meaningfully overlaps with any archetype's vocabulary -- this never
invents an affinity that isn't there, it only surfaces one that is.
"""

from __future__ import annotations

import re

from app.pipeline.opportunity_engine import Opportunity

_STOPWORDS = frozenset(
    {
        "a", "an", "the", "for", "and", "or", "with", "of", "in", "on", "to", "is", "are",
        "this", "that", "no", "not", "at", "as", "by", "be", "it", "its", "than", "into",
        "now", "up", "top", "new", "etsy", "wall", "art", "home", "decor", "trend", "trends",
        "trending",
    }
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> set[str]:
    return {w for w in _TOKEN_RE.findall(text.lower()) if w not in _STOPWORDS and len(w) > 2}


def _archetype_tokens(archetype: dict) -> set[str]:
    parts = [archetype["name"], archetype["thesis"], archetype["target_aesthetic"], archetype["medium"]]
    parts.extend(archetype.get("subject_families", []))
    return _tokenize(" ".join(parts))


def rank_archetypes_by_opportunities(
    archetypes: list[dict], opportunities: list[Opportunity]
) -> list[tuple[dict, str | None]]:
    """Returns archetypes paired with a human-readable note explaining why
    it moved up (None if it wasn't moved). `opportunities` should already
    be filtered to genuine external market signals -- see
    app/pipeline/collection_planner.py, which excludes the Opportunity
    Engine's "continue proven collection" fallback before calling this."""
    if not opportunities:
        return [(a, None) for a in archetypes]

    scored: list[tuple[float, int, dict, Opportunity | None]] = []
    for idx, archetype in enumerate(archetypes):
        tokens = _archetype_tokens(archetype)
        best_score = 0.0
        best_opp: Opportunity | None = None
        for opp in opportunities:
            overlap = tokens & _tokenize(opp.description)
            score = opp.confidence * len(overlap)
            if score > best_score:
                best_score = score
                best_opp = opp
        scored.append((best_score, idx, archetype, best_opp))

    if all(score == 0.0 for score, _, _, _ in scored):
        return [(a, None) for a in archetypes]

    scored.sort(key=lambda t: (-t[0], t[1]))
    result: list[tuple[dict, str | None]] = []
    for score, _idx, archetype, matched_opp in scored:
        note = None
        if score > 0.0 and matched_opp is not None:
            note = (
                f"prioritized by market signal (confidence={matched_opp.confidence:.2f}): "
                f"{matched_opp.description[:200]}"
            )
        result.append((archetype, note))
    return result
