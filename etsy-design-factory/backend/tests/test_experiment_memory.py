import uuid

from app.memory.experiment_memory import (
    candidate_belongs_to_experiment,
    record_commercial_outcome,
    record_experiment,
    relevant_experiments,
)


def test_record_and_query_relevant_experiments(db_session, collection):
    genome_id = uuid.uuid4()
    candidate_id = uuid.uuid4()
    exp = record_experiment(
        db_session,
        hypothesis="muted palette variant might read as calmer",
        design_genome_id=genome_id,
        collection_id=collection.id,
        variables_tested={"palette_dna": "mutated"},
        provider="fake_image_gen",
        model="fake",
        params={},
        candidate_ids=[candidate_id],
        winner_candidate_id=candidate_id,
        cost_usd=0.15,
    )
    assert exp.id is not None
    found = relevant_experiments(db_session, collection_id=collection.id)
    assert exp.id in [e.id for e in found]


def test_candidate_belongs_to_experiment_lookup(db_session, collection):
    candidate_id = uuid.uuid4()
    other_id = uuid.uuid4()
    exp = record_experiment(
        db_session,
        hypothesis="h",
        design_genome_id=None,
        collection_id=collection.id,
        variables_tested={},
        provider="fake",
        model="fake",
        params={},
        candidate_ids=[candidate_id, other_id],
        winner_candidate_id=None,
        cost_usd=0.0,
    )

    class FakeCandidate:
        id = candidate_id

    found = candidate_belongs_to_experiment(db_session, candidate=FakeCandidate())
    assert found is not None
    assert found.id == exp.id

    class UnrelatedCandidate:
        id = uuid.uuid4()

    assert candidate_belongs_to_experiment(db_session, candidate=UnrelatedCandidate()) is None


def test_record_commercial_outcome_updates_experiment(db_session, collection):
    exp = record_experiment(
        db_session,
        hypothesis="h",
        design_genome_id=None,
        collection_id=collection.id,
        variables_tested={},
        provider="fake",
        model="fake",
        params={},
        candidate_ids=[],
        winner_candidate_id=None,
        cost_usd=0.0,
    )
    assert exp.commercial_outcome is None
    updated = record_commercial_outcome(db_session, experiment_id=exp.id, outcome={"views": 42})
    assert updated is not None
    assert updated.commercial_outcome == {"views": 42}
