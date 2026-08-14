"""Cost rollups + budget checks. See docs/DATABASE.md `cost_events` and
the mission's GENERATION ECONOMICS / COST CONTROL requirements: cost per
design, cost per approved design, cost per collection, daily/monthly
spend, and budget gates the Production Controller can check before
committing to a plan.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date as date_type
from datetime import datetime, time, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models.artwork import Artwork
from app.db.models.cost import CostEvent


def _day_bounds(on_date: date_type) -> tuple[datetime, datetime]:
    return (
        datetime.combine(on_date, time.min, tzinfo=timezone.utc),
        datetime.combine(on_date, time.max, tzinfo=timezone.utc),
    )


def _month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    end_month, end_year = (month + 1, year) if month < 12 else (1, year + 1)
    end = datetime(end_year, end_month, 1, tzinfo=timezone.utc)
    return start, end


def _total_cost_expr():
    return CostEvent.generation_cost_usd + CostEvent.processing_cost_usd


def spend_between(session: Session, *, start: datetime, end: datetime) -> float:
    stmt = select(func.coalesce(func.sum(_total_cost_expr()), 0)).where(
        CostEvent.created_at >= start, CostEvent.created_at < end
    )
    return float(session.execute(stmt).scalar_one())


def daily_spend(session: Session, *, on_date: date_type) -> float:
    start, end = _day_bounds(on_date)
    return spend_between(session, start=start, end=end)


def monthly_spend(session: Session, *, year: int, month: int) -> float:
    start, end = _month_bounds(year, month)
    return spend_between(session, start=start, end=end)


def cost_for_collection(session: Session, *, collection_id: uuid.UUID) -> float:
    stmt = select(func.coalesce(func.sum(_total_cost_expr()), 0)).where(CostEvent.collection_id == collection_id)
    return float(session.execute(stmt).scalar_one())


def cost_per_approved_design(session: Session, *, collection_id: uuid.UUID | None = None) -> float | None:
    """Total attributable spend / number of approved Artworks. Scoped to a
    collection when given, otherwise system-wide. Returns None rather than
    a fabricated 0.0 when there is no approved design yet to divide by."""
    cost_stmt = select(func.coalesce(func.sum(_total_cost_expr()), 0))
    count_stmt = select(func.count(Artwork.id))
    if collection_id is not None:
        cost_stmt = cost_stmt.where(CostEvent.collection_id == collection_id)
        count_stmt = count_stmt.where(Artwork.collection_id == collection_id)

    total_cost = float(session.execute(cost_stmt).scalar_one())
    approved_count = int(session.execute(count_stmt).scalar_one())
    if approved_count == 0:
        return None
    return total_cost / approved_count


@dataclass
class BudgetStatus:
    daily_spent_usd: float
    daily_budget_usd: float
    monthly_spent_usd: float
    monthly_budget_usd: float

    @property
    def daily_remaining_usd(self) -> float:
        return max(0.0, self.daily_budget_usd - self.daily_spent_usd)

    @property
    def monthly_remaining_usd(self) -> float:
        return max(0.0, self.monthly_budget_usd - self.monthly_spent_usd)

    @property
    def daily_exceeded(self) -> bool:
        return self.daily_spent_usd >= self.daily_budget_usd

    @property
    def monthly_exceeded(self) -> bool:
        return self.monthly_spent_usd >= self.monthly_budget_usd


def get_budget_status(session: Session, *, on_date: date_type) -> BudgetStatus:
    settings = get_settings()
    return BudgetStatus(
        daily_spent_usd=daily_spend(session, on_date=on_date),
        daily_budget_usd=settings.daily_budget_usd,
        monthly_spent_usd=monthly_spend(session, year=on_date.year, month=on_date.month),
        monthly_budget_usd=settings.monthly_budget_usd,
    )
