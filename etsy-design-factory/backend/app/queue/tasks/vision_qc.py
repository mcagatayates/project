"""`vision_qc` queue."""

from __future__ import annotations

import asyncio
import uuid

from app.db.models.generation import GenerationCandidate
from app.genome.schema import DesignGenome
from app.pipeline.vision_qc import run_vision_qc
from app.queue.base_task import ResilientTask
from app.queue.celery_app import celery_app
from app.queue.context import task_context


@celery_app.task(bind=True, base=ResilientTask, name="app.queue.tasks.vision_qc.run_vision_qc")
def run_vision_qc_task(self, candidate_id: str, genome_json: dict) -> bool:
    self.queue_name = "vision_qc"
    genome = DesignGenome.model_validate(genome_json)

    with task_context() as (session, registry):
        candidate = session.get(GenerationCandidate, uuid.UUID(candidate_id))
        if candidate is None:
            raise ValueError(f"GenerationCandidate {candidate_id} not found")
        evaluation = asyncio.run(run_vision_qc(session, registry, candidate=candidate, genome=genome))
        overall_pass = evaluation.overall_pass
    return overall_pass
