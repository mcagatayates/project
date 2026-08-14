"""`generation` queue. See docs/AGENT_CONTRACTS.md "Generation" failure
policy: on provider exhaustion, no candidate row is created -- a
FailureRecord(TERMINAL_FAILURE) is written against the concept instead, so
the concept never silently vanishes."""

from __future__ import annotations

import asyncio
import uuid

from app.db.models.concept import Concept
from app.db.models.enums import FailureClass
from app.db.models.failure import FailureRecord
from app.genome.schema import DesignGenome
from app.pipeline.generation import generate_candidate
from app.providers.base import ProviderError
from app.queue.base_task import ResilientTask
from app.queue.celery_app import celery_app
from app.queue.context import task_context


@celery_app.task(bind=True, base=ResilientTask, name="app.queue.tasks.generation.generate_candidate")
def generate_candidate_task(
    self,
    concept_id: str,
    genome_json: dict,
    attempt_number: int,
    collection_thesis: str | None = None,
    quality_seed: float = 0.85,
) -> str:
    self.queue_name = "generation"
    genome = DesignGenome.model_validate(genome_json)

    with task_context() as (session, registry):
        concept = session.get(Concept, uuid.UUID(concept_id))
        if concept is None:
            raise ValueError(f"Concept {concept_id} not found")

        try:
            candidate = asyncio.run(
                generate_candidate(
                    session,
                    registry,
                    concept=concept,
                    genome=genome,
                    attempt_number=attempt_number,
                    collection_thesis=collection_thesis,
                    quality_seed=quality_seed,
                )
            )
        except ProviderError as exc:
            is_final_attempt = self.request.retries >= self.max_retries
            if is_final_attempt:
                session.add(
                    FailureRecord(
                        generation_candidate_id=None,
                        concept_id=concept.id,
                        failure_class=FailureClass.TERMINAL_FAILURE.value,
                        detected_problems=[str(exc)],
                        diagnosis_reasoning=(
                            "provider exhausted all adapter-level retries/fallbacks, and the "
                            f"task-level retry budget ({self.max_retries}) is also exhausted."
                        ),
                        diagnosed_by="provider_exhausted",
                    )
                )
                # Commit explicitly: task_context() rolls back on the
                # exception we're about to re-raise, but this failure record
                # must survive that rollback so the concept stays traceable.
                session.commit()
            raise
        candidate_id = str(candidate.id)
    return candidate_id
