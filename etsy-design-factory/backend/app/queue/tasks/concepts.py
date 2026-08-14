"""`concepts` queue: Concept Generation + Concept Gate. See docs/EVENTS.md."""

from __future__ import annotations

import asyncio
import uuid

from app.db.models.collection import Collection
from app.db.models.genome import DesignGenome as DesignGenomeRow
from app.pipeline.concept_gate import gate_concept
from app.pipeline.concept_generation import create_concept
from app.queue.base_task import ResilientTask
from app.queue.celery_app import celery_app
from app.queue.context import task_context


@celery_app.task(bind=True, base=ResilientTask, name="app.queue.tasks.concepts.create_and_gate_concept")
def create_and_gate_concept_task(
    self, genome_row_id: str, collection_id: str, production_mode: str, planned_candidate_count: int | None = None
) -> str:
    self.queue_name = "concepts"
    with task_context() as (session, registry):
        genome_row = session.get(DesignGenomeRow, uuid.UUID(genome_row_id))
        collection = session.get(Collection, uuid.UUID(collection_id))
        if genome_row is None or collection is None:
            raise ValueError("genome_row or collection not found")

        concept = create_concept(
            session,
            genome_row=genome_row,
            collection=collection,
            production_mode=production_mode,
            planned_candidate_count=planned_candidate_count,
        )
        asyncio.run(gate_concept(session, registry, concept=concept, genome_row=genome_row, collection=collection))
        concept_id = str(concept.id)
    return concept_id
