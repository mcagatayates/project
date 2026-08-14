from app.genome.compiler import compile_prompt
from app.genome.mutation import DEFAULT_MUTATION_SPEC, apply_approval_action, mutate
from app.genome.schema import GenomeCreatedBy
from tests.factories import make_genome


def test_compile_prompt_is_deterministic():
    genome = make_genome()
    p1 = compile_prompt(genome, collection_thesis="calm botanical studies")
    p2 = compile_prompt(genome, collection_thesis="calm botanical studies")
    assert p1 == p2
    assert "monstera leaf study" in p1
    assert "japandi" in p1


def test_compile_prompt_varies_with_seed():
    genome = make_genome()
    p1 = compile_prompt(genome, variation_seed=1)
    p2 = compile_prompt(genome, variation_seed=2)
    assert p1 != p2


def test_mutation_keeps_style_texture_era_by_default():
    parent = make_genome()
    import random

    offspring = mutate(parent, spec=DEFAULT_MUTATION_SPEC, rng=random.Random(42))

    assert offspring.style_dna == parent.style_dna
    assert offspring.era_dna == parent.era_dna
    assert offspring.parent_genome_id == parent.id
    assert offspring.generation_number == parent.generation_number + 1
    assert offspring.created_by == GenomeCreatedBy.SYSTEM_MUTATION
    assert offspring.design_lineage_id != parent.design_lineage_id
    assert offspring.mutation_map["style_dna"]["action"] == "kept"


def test_mutation_respects_probability_over_many_trials():
    import random

    parent = make_genome()
    mutated_composition_count = 0
    trials = 400
    for i in range(trials):
        offspring = mutate(parent, spec=DEFAULT_MUTATION_SPEC, rng=random.Random(i))
        if offspring.mutation_map["composition_dna"]["action"] == "mutated":
            mutated_composition_count += 1
    rate = mutated_composition_count / trials
    assert 0.55 < rate < 0.85  # configured 0.70 +/- noise


def test_approval_action_more_texture_increases_intensity_and_versions():
    genome = make_genome()
    edited = apply_approval_action(genome, "MORE_TEXTURE")
    assert edited.texture_dna.texture_intensity > genome.texture_dna.texture_intensity
    assert edited.version == genome.version + 1
    assert edited.derived_from_version_id == genome.id
    assert edited.design_lineage_id == genome.design_lineage_id
    assert edited.created_by == GenomeCreatedBy.HUMAN_EDIT


def test_approval_action_change_palette_produces_different_palette():
    genome = make_genome()
    edited = apply_approval_action(genome, "CHANGE_PALETTE")
    assert edited.palette_dna.palette_name != genome.palette_dna.palette_name


def test_approval_action_unknown_raises():
    genome = make_genome()
    import pytest

    with pytest.raises(ValueError):
        apply_approval_action(genome, "NOT_A_REAL_ACTION")
