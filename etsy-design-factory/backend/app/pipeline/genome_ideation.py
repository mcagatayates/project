"""Design Genome (creation): produces a fresh DesignGenome for a collection
slot. See docs/AGENT_CONTRACTS.md "Design Genome (creation)".

This is a deterministic, pool-based generator, not real trend-informed
ideation -- that is Market Intelligence / Opportunity Engine territory
(Phase 5), which has no live signal source wired up yet (see
docs/ROADMAP.md "Explicit non-goals"). What this function guarantees is
narrower but load-bearing: every genome it produces respects the
collection's medium/subject_families/palette_boundaries, and consecutive
slots are varied enough (different subject/composition/palette/mood
combinations) to give Diversity Control something real to work with,
rather than N copies of the same genome.
"""

from __future__ import annotations

import random
from typing import Any, TypeVar, cast

from app.db.models.collection import Collection
from app.genome.schema import (
    Balance,
    CommercialDNA,
    CompositionDNA,
    DesignGenome,
    DetailDensity,
    DetailDNA,
    EraDNA,
    LayoutType,
    LineWeight,
    Medium,
    MediumDNA,
    MoodDNA,
    Orientation,
    PaletteDNA,
    PriceTier,
    PrintDNA,
    RenderingStyle,
    StyleDNA,
    SubjectCategory,
    SubjectDNA,
    SurfaceTexture,
    Temperature,
    TextureDNA,
)

_SUBJECTS_BY_CATEGORY: dict[str, list[str]] = {
    "botanical": [
        "monstera leaf study",
        "wildflower field",
        "citrus grove",
        "fern silhouettes",
        "olive branch",
        "eucalyptus sprig",
        "palm frond study",
        "wild grasses",
        "orchid stem",
        "pressed leaf collection",
        "banana leaf close-up",
        "trailing ivy",
    ],
    "animal": [
        "flock of birds",
        "resting fox",
        "coastal heron",
        "moth study",
        "hare in tall grass",
        "swimming koi",
        "perched owl",
        "running deer",
        "cat in window light",
        "butterfly collection",
        "songbird on branch",
        "tortoise study",
    ],
    "abstract": [
        "sun and moon motif",
        "layered arches",
        "organic blob forms",
        "gestural brushwork",
        "concentric rings",
        "color field study",
        "flowing ribbons",
        "fragmented shapes",
        "ink blot study",
        "wave pattern",
        "cloud formation abstraction",
        "textured gradient field",
    ],
    "landscape": [
        "desert cliffs at dusk",
        "rolling hills",
        "coastal cliffs",
        "mountain horizon",
        "quiet lakeshore",
        "canyon layers",
        "misty forest edge",
        "sand dune ridge",
        "terraced hillside",
        "riverbank at dawn",
        "salt flat horizon",
        "pine ridge silhouette",
    ],
    "geometric": [
        "interlocking triangles",
        "grid of arches",
        "radiating lines",
        "stacked circles",
        "checker pattern",
        "diamond lattice",
        "concentric squares",
        "chevron rows",
        "hexagon tile field",
        "spiral grid",
        "offset dot matrix",
        "layered semicircles",
    ],
    "still_life": [
        "terracotta vessels",
        "dried flowers in a vase",
        "citrus on linen",
        "ceramic bowls",
        "glass carafes",
        "woven basket study",
        "stacked books",
        "fruit bowl arrangement",
        "candle and dish",
        "vintage teapot",
        "pressed botanicals in frame",
        "stoneware jug",
    ],
    "architectural": [
        "archway study",
        "staircase silhouette",
        "window grid",
        "colonnade",
        "rooftop skyline",
        "courtyard arches",
        "spiral staircase",
        "facade detail",
        "bridge silhouette",
        "domed ceiling study",
    ],
    "typography": [
        "hand-lettered mantra",
        "botanical alphabet motif",
        "minimal numeral study",
        "single-word poster",
        "script quote study",
        "monogram design",
    ],
    "figurative": [
        "seated figure sketch",
        "dancer silhouette",
        "portrait study in profile",
        "reclining figure",
        "hands in motion study",
        "crowd silhouette",
    ],
}
_ART_MOVEMENTS = [
    "japandi",
    "art-deco",
    "mid-century-modern",
    "boho",
    "bauhaus",
    "cottagecore",
    "modern linework",
    "scandinavian minimalism",
    "brutalist",
    "arts-and-crafts",
    "memphis",
    "coastal grandmother",
]
_MOODS = ["calm", "energetic", "wistful", "grounded", "playful", "serene", "bold", "moody", "hopeful", "contemplative"]
_ERAS = ["timeless", "1960s", "victorian", "futuristic", "art-nouveau", "1920s", "1970s", "renaissance-inspired"]

_DEFAULT_PALETTES: list[dict[str, Any]] = [
    {
        "palette_name": "sage-clay",
        "primary_colors": ["#7C8B6F"],
        "accent_colors": ["#C77B4D"],
        "background_color": "#F3EFE6",
        "temperature": Temperature.WARM,
    },
    {
        "palette_name": "dusk-plum",
        "primary_colors": ["#5B4B6A"],
        "accent_colors": ["#E8A87C"],
        "background_color": "#EDE6E3",
        "temperature": Temperature.COOL,
    },
    {
        "palette_name": "ochre-ink",
        "primary_colors": ["#C98A2C"],
        "accent_colors": ["#22303C"],
        "background_color": "#F7F1E1",
        "temperature": Temperature.WARM,
    },
    {
        "palette_name": "seafoam-neutral",
        "primary_colors": ["#89B7A5"],
        "accent_colors": ["#D9C6A5"],
        "background_color": "#FBFAF7",
        "temperature": Temperature.NEUTRAL,
    },
]

_MEDIUM_BY_NAME = {m.value: m for m in Medium}

_T = TypeVar("_T")


def _pick(rng: random.Random, seq: list[_T]) -> _T:
    """Equivalent to rng.choice(seq), but via indexing to sidestep a mypy
    quirk (see the _enum_pool casts below)."""
    return seq[rng.randrange(len(seq))]


# `list(SomeStrEnumClass)` type-checks as `list[str]`, not
# `list[SomeStrEnumClass]`, under this mypy version -- every StrEnum member
# is itself a str instance, and mypy's inference for iterating an Enum
# class collapses to that structural supertype. cast() is the one place
# that fact is papered over; every call site downstream then gets the real
# enum type back out of `_pick`.
_LAYOUT_TYPES = cast("list[LayoutType]", list(LayoutType))
_BALANCES = cast("list[Balance]", list(Balance))
_RENDERING_STYLES = cast("list[RenderingStyle]", list(RenderingStyle))
_SURFACE_TEXTURES = cast("list[SurfaceTexture]", list(SurfaceTexture))
_DETAIL_DENSITIES = cast("list[DetailDensity]", list(DetailDensity))
_LINE_WEIGHTS = cast("list[LineWeight]", list(LineWeight))
_ORIENTATIONS = cast("list[Orientation]", list(Orientation))
_PRICE_TIERS = cast("list[PriceTier]", list(PriceTier))


def _diffused_seed(value: int) -> int:
    """Small sequential integer seeds (0, 1, 2, ...) can leave
    random.Random's early `choice()` outputs correlated across nearby
    seeds -- observed empirically as the same era/mood/style winning far
    more often than its 1/N odds across consecutive slot indices. Hashing
    through SHA-256 first gives each seed a fully-diffused starting state
    regardless of how close the inputs are."""
    import hashlib

    return int.from_bytes(hashlib.sha256(str(value).encode()).digest()[:8], "big")


def create_genome(collection: Collection, *, slot_index: int, seed: int | None = None) -> DesignGenome:
    raw_seed = seed if seed is not None else hash((str(collection.id), slot_index)) & 0xFFFFFFFF
    rng = random.Random(_diffused_seed(raw_seed))

    subject_families = collection.subject_families or ["abstract"]
    category_name = subject_families[slot_index % len(subject_families)]
    subject_pool = _SUBJECTS_BY_CATEGORY.get(category_name, _SUBJECTS_BY_CATEGORY["abstract"])
    # _pick (not slot_index % len) for every non-category field below:
    # deterministic modulo indexing on same-length-ish pools causes fields
    # to lock-step and repeat together every few slots, producing
    # near-duplicate genomes far more often than genuine creative variety
    # would. Independent random draws decorrelate them.
    primary_subject = _pick(rng, subject_pool)

    boundaries = collection.palette_boundaries or {}
    allowed_names = boundaries.get("allowed_palette_names")
    palette_pool = (
        [p for p in _DEFAULT_PALETTES if p["palette_name"] in allowed_names] if allowed_names else _DEFAULT_PALETTES
    ) or _DEFAULT_PALETTES
    # Palette stays evenly cycled (not random): collections deliberately
    # have narrow, curated palette boundaries, so even round-robin coverage
    # of the allowed set is intentional rather than a diversity risk.
    palette_choice = palette_pool[slot_index % len(palette_pool)]

    layout = _pick(rng, _LAYOUT_TYPES)
    balance = _pick(rng, _BALANCES)
    rendering_style = _pick(rng, _RENDERING_STYLES)
    surface_texture = _pick(rng, _SURFACE_TEXTURES)
    detail_density = _pick(rng, _DETAIL_DENSITIES)
    line_weight = _pick(rng, _LINE_WEIGHTS)
    orientation = _pick(rng, _ORIENTATIONS)
    price_tier = _pick(rng, _PRICE_TIERS)
    art_movement = _pick(rng, _ART_MOVEMENTS)
    mood = _pick(rng, _MOODS)
    era = _pick(rng, _ERAS)

    medium = _MEDIUM_BY_NAME.get(collection.medium, Medium.DIGITAL_PAINTING)
    valid_categories = {c.value for c in SubjectCategory}
    subject_category = SubjectCategory(category_name) if category_name in valid_categories else SubjectCategory.ABSTRACT

    return DesignGenome(
        collection_id=collection.id,
        subject_dna=SubjectDNA(
            primary_subject=primary_subject,
            subject_category=subject_category,
            secondary_elements=[],
            subject_tags=[category_name, art_movement],
        ),
        style_dna=StyleDNA(art_movement=art_movement, rendering_style=rendering_style),
        composition_dna=CompositionDNA(
            layout_type=layout,
            focal_point=primary_subject,
            negative_space_ratio=round(rng.uniform(0.25, 0.65), 2),
            balance=balance,
        ),
        palette_dna=PaletteDNA(
            palette_name=str(palette_choice["palette_name"]),
            primary_colors=list(palette_choice["primary_colors"]),
            accent_colors=list(palette_choice["accent_colors"]),
            background_color=str(palette_choice["background_color"]),
            saturation_level=round(rng.uniform(0.2, 0.6), 2),
            contrast_level=round(rng.uniform(0.3, 0.7), 2),
            temperature=palette_choice["temperature"],
        ),
        texture_dna=TextureDNA(surface_texture=surface_texture, texture_intensity=round(rng.uniform(0.1, 0.4), 2)),
        medium_dna=MediumDNA(medium=medium),
        era_dna=EraDNA(era_reference=era, nostalgia_level=round(rng.uniform(0.0, 0.4), 2)),
        mood_dna=MoodDNA(primary_mood=mood, energy_level=round(rng.uniform(0.1, 0.7), 2)),
        detail_dna=DetailDNA(detail_density=detail_density, line_weight=line_weight),
        print_dna=PrintDNA(orientation=orientation),
        commercial_dna=CommercialDNA(
            target_customer_segment=collection.target_customer_hypothesis,
            price_tier=price_tier,
            seasonal_relevance=[],
            gift_occasion=[],
            room_type_fit=["living-room", "bedroom"],
            trend_alignment_score=round(rng.uniform(0.4, 0.8), 2),
        ),
    )
