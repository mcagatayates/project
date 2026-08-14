"""`repair` queue."""

from __future__ import annotations

import asyncio
import uuid

from app.db.models.concept import Concept
from app.db.models.failure import FailureRecord
from app.db.models.generation import GenerationCandidate
from app.genome.schema import DesignGenome
from app.pipeline.selective_repair import run_repair
from app.queue.base_task import ResilientTask
from app.queue.celery_app import celery_app
from app.queue.context import task_context


@celery_app.task(bind=True, base=ResilientTask, name="app.queue.tasks.repair.run_repair")
def run_repair_task(
    self,
    failure_record_id: str,
    failed_candidate_id: str,
    concept_id: str,
    genome_json: dict,
    collection_thesis: str | None = None,
) -> str:
    self.queue_name = "repair"
    genome = DesignGenome.model_validate(genome_json)

    with task_context() as (session, registry):
        failure_record = session.get(FailureRecord, uuid.UUID(failure_record_id))
        failed_candidate = session.get(GenerationCandidate, uuid.UUID(failed_candidate_id))
        concept = session.get(Concept, uuid.UUID(concept_id))
        if failure_record is None or failed_candidate is None or concept is None:
            raise ValueError("failure_record, failed_candidate or concept not found")

        _repair, new_candidate = asyncio.run(
            run_repair(
                session,
                registry,
                failure_record=failure_record,
                failed_candidate=failed_candidate,
                concept=concept,
                genome=genome,
                collection_thesis=collection_thesis,
            )
        )
        new_candidate_id = str(new_candidate.id)
    return new_candidate_id
