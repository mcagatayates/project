"""`analysis` queue: cheap, DB-only planning stages. See docs/EVENTS.md."""

from __future__ import annotations

import asyncio
import datetime

from app.pipeline.collection_planner import plan_collections
from app.pipeline.opportunity_engine import fetch_current_opportunities
from app.pipeline.production_controller import build_daily_plan
from app.queue.base_task import ResilientTask
from app.queue.celery_app import celery_app
from app.queue.context import task_context


@celery_app.task(bind=True, base=ResilientTask, name="app.queue.tasks.analysis.plan_daily_production")
def plan_daily_production_task(self, plan_date_iso: str, target_final_designs: int | None = None) -> str:
    self.queue_name = "analysis"
    plan_date = datetime.date.fromisoformat(plan_date_iso)
    with task_context() as (session, _registry):
        plan = build_daily_plan(session, plan_date=plan_date, target_final_designs=target_final_designs)
        plan_id = str(plan.id)
    return plan_id


@celery_app.task(bind=True, base=ResilientTask, name="app.queue.tasks.analysis.plan_collections")
def plan_collections_task(self, plan_id: str) -> int:
    self.queue_name = "analysis"
    import uuid

    from app.db.models.production import DailyProductionPlan

    with task_context() as (session, _registry):
        plan = session.get(DailyProductionPlan, uuid.UUID(plan_id))
        if plan is None:
            raise ValueError(f"DailyProductionPlan {plan_id} not found")
        opportunities = asyncio.run(fetch_current_opportunities(session))
        assignments = plan_collections(session, plan=plan, opportunities=opportunities)
        count = len(assignments)
    return count
