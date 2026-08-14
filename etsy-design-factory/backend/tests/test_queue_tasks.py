"""Exercises the Celery task wrappers in eager mode (no Redis needed) and
verifies worker/provider failure resilience: a task whose provider is
exhausted must not corrupt the concept, must record a traceable
FailureRecord, and must not silently disappear (docs/EVENTS.md)."""

from __future__ import annotations

from app.db.models.enums import FailureClass, GateStatus
from app.db.models.failure import FailureRecord
from app.genome.codec import to_row
from app.pipeline.concept_generation import create_concept
from app.providers.base import ProviderError
from app.queue.tasks.analysis import plan_collections_task, plan_daily_production_task
from app.queue.tasks.concepts import create_and_gate_concept_task
from app.queue.tasks.generation import generate_candidate_task
from app.queue.tasks.vision_qc import run_vision_qc_task
from tests.factories import make_genome


def test_plan_daily_production_task_creates_a_plan(db_session):
    plan_id = plan_daily_production_task.apply(args=["2026-08-14", 20]).get()
    assert plan_id

    from app.db.models.production import DailyProductionPlan

    plan = db_session.get(DailyProductionPlan, __import__("uuid").UUID(plan_id))
    assert plan.target_final_designs == 20


def test_plan_collections_task_assigns_slots(db_session):
    plan_id = plan_daily_production_task.apply(args=["2026-08-18", 10]).get()
    count = plan_collections_task.apply(args=[plan_id]).get()
    assert count > 0


def test_create_and_gate_concept_task(db_session, collection):
    genome = make_genome(collection_id=collection.id)
    genome_row = to_row(genome)
    db_session.add(genome_row)
    db_session.flush()

    concept_id = create_and_gate_concept_task.apply(
        args=[str(genome_row.id), str(collection.id), "PRODUCTION", 2]
    ).get()
    assert concept_id

    from app.db.models.concept import Concept

    concept = db_session.get(Concept, __import__("uuid").UUID(concept_id))
    assert concept.gate_status == GateStatus.PASSED.value


def test_generate_and_qc_tasks_round_trip(db_session, collection):
    genome = make_genome(collection_id=collection.id)
    genome_row = to_row(genome)
    db_session.add(genome_row)
    db_session.flush()
    concept = create_concept(
        db_session,
        genome_row=genome_row,
        collection=collection,
        production_mode="PRODUCTION",
        planned_candidate_count=1,
    )

    genome_json = genome.model_dump(mode="json")
    candidate_id = generate_candidate_task.apply(args=[str(concept.id), genome_json, 1, collection.thesis, 0.9]).get()
    assert candidate_id

    passed = run_vision_qc_task.apply(args=[candidate_id, genome_json]).get()
    assert passed is True


class _AlwaysFailingImageGen:
    name = "always_failing_image_gen"

    async def generate(self, **kwargs):
        raise RuntimeError("simulated provider outage")


def test_generation_task_exhaustion_writes_traceable_failure_without_corrupting_concept(
    db_session, collection, monkeypatch
):
    genome = make_genome(collection_id=collection.id)
    genome_row = to_row(genome)
    db_session.add(genome_row)
    db_session.flush()
    concept = create_concept(
        db_session,
        genome_row=genome_row,
        collection=collection,
        production_mode="PRODUCTION",
        planned_candidate_count=1,
    )
    concept_id = str(concept.id)
    # Commit (not just flush): the task below runs against its own DB
    # session (task_context() opens a fresh one, as a real worker process
    # would), and in the SQLite/StaticPool test setup a rollback on that
    # session shares the underlying connection with this fixture's session
    # -- committing here keeps the concept durable across that boundary,
    # matching how a real deployment hands off already-committed work.
    db_session.commit()

    import app.providers.factory as factory_module

    original_build_registry = factory_module.build_registry

    def _broken_registry(*args, **kwargs):
        registry = original_build_registry(*args, **kwargs)
        from app.providers.registry import AdapterSpec

        registry.register_role(
            "image_gen.exploration",
            primary=AdapterSpec(
                name="always_failing_image_gen",
                instance=_AlwaysFailingImageGen(),
                max_retries=1,
                backoff_base_s=0.001,
                backoff_max_s=0.001,
                rate_per_minute=6000,
            ),
        )
        return registry

    monkeypatch.setattr("app.queue.context.build_registry", _broken_registry)

    genome_json = genome.model_dump(mode="json")

    raised = False
    try:
        generate_candidate_task.apply(args=[concept_id, genome_json, 1, collection.thesis, 0.9]).get()
    except ProviderError:
        raised = True
    assert raised

    # the concept itself must be untouched and still queryable
    from app.db.models.concept import Concept

    reloaded_concept = db_session.get(Concept, concept.id)
    assert reloaded_concept is not None
    assert reloaded_concept.id == concept.id

    failures = db_session.query(FailureRecord).filter_by(concept_id=concept.id).all()
    assert len(failures) == 1
    assert failures[0].failure_class == FailureClass.TERMINAL_FAILURE.value
    assert failures[0].generation_candidate_id is None
    assert failures[0].diagnosed_by == "provider_exhausted"
