from __future__ import annotations

from datetime import date as date_type

from sqlalchemy import Date, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, CreatedAtMixin, JSONVariant, UUIDPKMixin


class DailyProductionPlan(UUIDPKMixin, CreatedAtMixin, Base):
    __tablename__ = "daily_production_plans"

    plan_date: Mapped[date_type] = mapped_column(Date, unique=True, index=True)
    target_final_designs: Mapped[int] = mapped_column(Integer)
    portfolio_allocation: Mapped[dict] = mapped_column(JSONVariant, default=dict)
    collections: Mapped[list] = mapped_column(JSONVariant, default=list)
    experimental_slots: Mapped[int] = mapped_column(Integer, default=0)
    winner_mutation_slots: Mapped[int] = mapped_column(Integer, default=0)
    production_slots: Mapped[int] = mapped_column(Integer, default=0)
    budget_cap_usd: Mapped[float] = mapped_column(Numeric(10, 2))
    policy_version: Mapped[str] = mapped_column(String(50))
    rationale: Mapped[str] = mapped_column(String(4000))
