"""Controlled mutation: strong designs become parents, offspring keep some
DNA blocks and mutate others at configured probabilities. Also implements
the approval-action -> genome-edit mapping (docs/DESIGN_GENOME_SCHEMA.md,
"Approval-action -> genome mutation mapping").

Mutation never produces fully random genomes: each block's replacement is
sampled from its own enum/range domain, optionally constrained to a
collection's boundaries, so offspring stay recognizably related to the
family they came from.
"""
from __future__ import annotations

import random
import uuid

from app.genome.schema import (
    Balance,
    CompositionDNA,
    DesignGenome,
    DetailDensity,
    DetailDNA,
    GenomeCreatedBy,
    LayoutType,
    PaletteDNA,
    RenderingStyle,
    SubjectDNA,
    SurfaceTexture,
    Temperature,
    TextureDNA,
)

MutationSpec = dict[str, float]

DEFAULT_MUTATION_SPEC: MutationSpec = {
    "style_dna": 0.0,
    "texture_dna": 0.0,
    "era_dna": 0.0,
    "composition_dna": 0.70,
    "subject_dna": 0.40,
    "palette_dna": 0.20,
    "medium_dna": 0.0,
    "mood_dna": 0.10,
    "detail_dna": 0.10,
    "print_dna": 0.0,
    "commercial_dna": 0.0,
}

_SUBJECT_POOL = [
    "monstera leaf study", "abstract arches", "sun and moon motif",
    "wildflower field", "coastal cliffs", "terracotta vessels",
    "citrus grove", "desert cacti", "flock of birds", "geometric mountains",
]
_PALETTE_POOL = [
    {"palette_name": "sage-clay", "primary_colors": ["#7C8B6F"], "accent_colors": ["#C77B4D"], "background_color": "#F3EFE6", "temperature": Temperature.WARM},
    {"palette_name": "dusk-plum", "primary_colors": ["#5B4B6A"], "accent_colors": ["#E8A87C"], "background_color": "#EDE6E3", "temperature": Temperature.COOL},
    {"palette_name": "ochre-ink", "primary_colors": ["#C98A2C"], "accent_colors": ["#22303C"], "background_color": "#F7F1E1", "temperature": Temperature.WARM},
    {"palette_name": "seafoam-neutral", "primary_colors": ["#89B7A5"], "accent_colors": ["#D9C6A5"], "background_color": "#FBFAF7", "temperature": Temperature.NEUTRAL},
]


def _mutate_subject(rng: random.Random, current: SubjectDNA) -> SubjectDNA:
    new_subject = rng.choice([s for s in _SUBJECT_POOL if s != current.primary_subject] or _SUBJECT_POOL)
    return current.model_copy(update={"primary_subject": new_subject})


def _mutate_composition(rng: random.Random, current: CompositionDNA) -> CompositionDNA:
    return current.model_copy(update={
        "layout_type": rng.choice(list(LayoutType)),
        "balance": rng.choice(list(Balance)),
        "negative_space_ratio": round(min(1.0, max(0.0, current.negative_space_ratio + rng.uniform(-0.25, 0.25))), 2),
    })


def _mutate_palette(rng: random.Random, current: PaletteDNA, boundaries: dict | None = None) -> PaletteDNA:
    pool = _PALETTE_POOL
    if boundaries and boundaries.get("allowed_palette_names"):
        allowed = set(boundaries["allowed_palette_names"])
        pool = [p for p in _PALETTE_POOL if p["palette_name"] in allowed] or _PALETTE_POOL
    choice = rng.choice([p for p in pool if p["palette_name"] != current.palette_name] or pool)
    return current.model_copy(update=choice)


def _mutate_texture(rng: random.Random, current: TextureDNA) -> TextureDNA:
    return current.model_copy(update={
        "surface_texture": rng.choice(list(SurfaceTexture)),
        "texture_intensity": round(min(1.0, max(0.0, current.texture_intensity + rng.uniform(-0.3, 0.3))), 2),
    })


def _mutate_detail(rng: random.Random, current: DetailDNA) -> DetailDNA:
    return current.model_copy(update={"detail_density": rng.choice(list(DetailDensity))})


_BLOCK_MUTATORS = {
    "subject_dna": _mutate_subject,
    "composition_dna": _mutate_composition,
    "texture_dna": _mutate_texture,
    "detail_dna": _mutate_detail,
}


def mutate(
    parent: DesignGenome,
    *,
    spec: MutationSpec | None = None,
    collection_palette_boundaries: dict | None = None,
    rng: random.Random | None = None,
) -> DesignGenome:
    """Produce an evolutionary offspring genome from a parent (winner)."""
    spec = spec or DEFAULT_MUTATION_SPEC
    rng = rng or random.Random()

    mutation_map: dict[str, dict] = {}
    updates: dict = {}

    for block_name, probability in spec.items():
        current = getattr(parent, block_name)
        triggered = rng.random() < probability
        if not triggered:
            mutation_map[block_name] = {"action": "kept"}
            continue
        mutation_map[block_name] = {"action": "mutated", "probability": probability}
        if block_name == "palette_dna":
            updates[block_name] = _mutate_palette(rng, current, collection_palette_boundaries)
        elif block_name in _BLOCK_MUTATORS:
            updates[block_name] = _BLOCK_MUTATORS[block_name](rng, current)
        # blocks without a registered mutator (style/medium/era/print/mood/
        # commercial by default) are left unchanged even if "triggered" —
        # they simply have no defined mutation operator yet, tracked as such.
        else:
            mutation_map[block_name] = {"action": "kept", "reason": "no_mutator_defined"}

    offspring = parent.model_copy(update={
        "id": uuid.uuid4(),
        "design_lineage_id": uuid.uuid4(),
        "version": 1,
        "parent_genome_id": parent.id,
        "derived_from_version_id": None,
        "generation_number": parent.generation_number + 1,
        "created_by": GenomeCreatedBy.SYSTEM_MUTATION,
        "mutation_map": mutation_map,
        **updates,
    })
    return offspring


# ---- Approval-action -> genome edit mapping -------------------------------

def apply_approval_action(genome: DesignGenome, action: str, rng: random.Random | None = None) -> DesignGenome:
    """Structured genome transform for a human approval action. Always
    returns a NEW genome version (same design_lineage_id); never edits a
    prompt string directly."""
    rng = rng or random.Random()
    updates: dict = {}

    if action == "CHANGE_PALETTE":
        updates["palette_dna"] = _mutate_palette(rng, genome.palette_dna)
    elif action == "CHANGE_COMPOSITION":
        updates["composition_dna"] = _mutate_composition(rng, genome.composition_dna)
    elif action == "MORE_TEXTURE":
        t = genome.texture_dna
        updates["texture_dna"] = t.model_copy(update={"texture_intensity": min(1.0, t.texture_intensity + 0.25)})
    elif action == "LESS_TEXTURE":
        t = genome.texture_dna
        updates["texture_dna"] = t.model_copy(update={"texture_intensity": max(0.0, t.texture_intensity - 0.25)})
    elif action == "MORE_MINIMAL":
        d = genome.detail_dna
        c = genome.composition_dna
        updates["detail_dna"] = d.model_copy(update={"detail_density": DetailDensity.MINIMAL})
        updates["composition_dna"] = c.model_copy(update={"negative_space_ratio": max(c.negative_space_ratio, 0.6)})
    elif action == "MORE_DETAILED":
        d = genome.detail_dna
        updates["detail_dna"] = d.model_copy(update={"detail_density": DetailDensity.INTRICATE})
    elif action == "MORE_ORIGINAL":
        updates["subject_dna"] = _mutate_subject(rng, genome.subject_dna)
        updates["composition_dna"] = _mutate_composition(rng, genome.composition_dna)
    elif action == "CLOSER_TO_COLLECTION":
        # Pull composition/detail back toward defaults; a no-op placeholder
        # transform in the absence of a live collection-centroid comparison,
        # still produces a new version so it re-enters the pipeline.
        updates["composition_dna"] = genome.composition_dna.model_copy(update={"layout_type": LayoutType.CENTERED})
    elif action == "CREATE_VARIATIONS":
        updates["subject_dna"] = _mutate_subject(rng, genome.subject_dna)
    else:
        raise ValueError(f"'{action}' is not a genome-mutating approval action")

    return genome.model_copy(update={
        "id": uuid.uuid4(),
        "version": genome.version + 1,
        "parent_genome_id": None,
        "derived_from_version_id": genome.id,
        "created_by": GenomeCreatedBy.HUMAN_EDIT,
        "mutation_map": {"approval_action": action},
        **updates,
    })
