from app.pipeline.genome_ideation import create_genome


def test_create_genome_respects_collection_boundaries(collection):
    genome = create_genome(collection, slot_index=0)
    assert genome.collection_id == collection.id
    assert genome.palette_dna.palette_name in collection.palette_boundaries["allowed_palette_names"]
    assert (
        genome.subject_dna.subject_category.value in collection.subject_families
        or genome.subject_dna.subject_category.value == "abstract"
    )


def test_create_genome_varies_across_slot_indices(collection):
    genomes = [create_genome(collection, slot_index=i) for i in range(8)]
    subjects = {g.subject_dna.primary_subject for g in genomes}
    layouts = {g.composition_dna.layout_type for g in genomes}
    assert len(subjects) > 1
    assert len(layouts) > 1


def test_create_genome_is_deterministic_for_same_slot(collection):
    a = create_genome(collection, slot_index=3, seed=42)
    b = create_genome(collection, slot_index=3, seed=42)
    assert a.subject_dna.primary_subject == b.subject_dna.primary_subject
    assert a.palette_dna.palette_name == b.palette_dna.palette_name
