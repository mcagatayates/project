"""GET /api/dashboard/today -- the Human Control Center's headline KPI
row. See docs/SYSTEM_VISION.md "Human Control Center"."""

from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.schemas import DashboardSummary
from app.cost.budgets import cost_per_approved_design, daily_spend
from app.db.models.enums import CandidateStatus
from app.db.models.generation import GenerationCandidate
from app.db.models.production import DailyProductionPlan

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

_GENERATED_STATUSES = (
    CandidateStatus.GENERATED.value,
    CandidateStatus.QC_IN_PROGRESS.value,
    CandidateStatus.QC_PASSED.value,
    CandidateStatus.QC_FAILED.value,
    CandidateStatus.DIAGNOSED.value,
    CandidateStatus.REPAIR_QUEUED.value,
    CandidateStatus.REPAIRING.value,
    CandidateStatus.REPAIRED.value,
    CandidateStatus.SELECTION_PENDING.value,
    CandidateStatus.SELECTED.value,
    CandidateStatus.ELIMINATED.value,
    CandidateStatus.AWAITING_APPROVAL.value,
    CandidateStatus.APPROVED.value,
    CandidateStatus.REJECTED.value,
)
_REPAIRING_STATUSES = (
    CandidateStatus.REPAIR_QUEUED.value,
    CandidateStatus.REPAIRING.value,
)


def _count(session: Session, statuses: tuple[str, ...]) -> int:
    stmt = select(func.count(GenerationCandidate.id)).where(GenerationCandidate.status.in_(statuses))
    return int(session.execute(stmt).scalar_one())


@router.get("/today", response_model=DashboardSummary)
def get_today_summary(
    session: Session = Depends(get_db),
    plan_date: datetime.date | None = Query(default=None, description="Defaults to today (UTC)"),
) -> DashboardSummary:
    on_date = plan_date or datetime.datetime.now(datetime.timezone.utc).date()

    plan_stmt = select(DailyProductionPlan).where(DailyProductionPlan.plan_date == on_date)
    plan = session.execute(plan_stmt).scalar_one_or_none()

    cost_today = daily_spend(session, on_date=on_date)
    cost_per_design = cost_per_approved_design(session)

    return DashboardSummary(
        plan_date=on_date.isoformat(),
        target_final_designs=plan.target_final_designs if plan else None,
        generated=_count(session, _GENERATED_STATUSES),
        qc_passed=_count(session, (CandidateStatus.QC_PASSED.value, CandidateStatus.SELECTED.value)),
        repairing=_count(session, _REPAIRING_STATUSES),
        awaiting_approval=_count(session, (CandidateStatus.AWAITING_APPROVAL.value,)),
        approved=_count(session, (CandidateStatus.APPROVED.value,)),
        rejected=_count(session, (CandidateStatus.REJECTED.value, CandidateStatus.TERMINAL.value)),
        today_cost_usd=round(cost_today, 4),
        cost_per_approved_design_usd=round(cost_per_design, 4) if cost_per_design is not None else None,
    )
