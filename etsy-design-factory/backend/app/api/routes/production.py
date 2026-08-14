"""Manual trigger + read for the Daily Production Controller. In normal
operation a scheduled Celery beat job calls
app.queue.tasks.analysis.plan_daily_production_task; this endpoint exists
for manual/catch-up runs from the dashboard (see docs/ARCHITECTURE.md
"Scheduling the daily cycle")."""

from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.schemas import ProductionPlanRequest, ProductionPlanResponse
from app.db.models.production import DailyProductionPlan
from app.pipeline.production_controller import build_daily_plan

router = APIRouter(prefix="/api/production", tags=["production"])


def _to_response(plan: DailyProductionPlan) -> ProductionPlanResponse:
    return ProductionPlanResponse(
        id=plan.id,
        plan_date=plan.plan_date.isoformat(),
        target_final_designs=plan.target_final_designs,
        portfolio_allocation=plan.portfolio_allocation,
        production_slots=plan.production_slots,
        experimental_slots=plan.experimental_slots,
        winner_mutation_slots=plan.winner_mutation_slots,
        budget_cap_usd=float(plan.budget_cap_usd),
        rationale=plan.rationale,
    )


@router.post("/plan", response_model=ProductionPlanResponse)
def create_or_update_plan(body: ProductionPlanRequest, session: Session = Depends(get_db)) -> ProductionPlanResponse:
    try:
        plan_date = datetime.date.fromisoformat(body.plan_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="plan_date must be an ISO date (YYYY-MM-DD)") from exc

    plan = build_daily_plan(session, plan_date=plan_date, target_final_designs=body.target_final_designs)
    return _to_response(plan)


@router.get("/plan/{plan_date}", response_model=ProductionPlanResponse)
def get_plan(plan_date: str, session: Session = Depends(get_db)) -> ProductionPlanResponse:
    try:
        parsed = datetime.date.fromisoformat(plan_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="plan_date must be an ISO date (YYYY-MM-DD)") from exc

    stmt = select(DailyProductionPlan).where(DailyProductionPlan.plan_date == parsed)
    plan = session.execute(stmt).scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=404, detail="no plan for that date")
    return _to_response(plan)
