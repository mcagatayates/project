"""Daily Production Controller: decides WHAT should be produced today
before any image generation begins. See docs/AGENT_CONTRACTS.md.

Reads: historical designs/winners/failures (via Artwork/Evaluation counts),
active collections + saturation, cost-to-date (budget), configured
allocation policy. Writes: one DailyProductionPlan row per plan_date
(upsert on the unique plan_date constraint, per the stage's documented
idempotency key `daily_plan:{date}`).
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime, time, timezone
from functools import lru_cache
from pathlib import Path

import yaml
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models.artwork import Artwork
from app.db.models.cost import CostEvent
from app.db.models.production import DailyProductionPlan
from app.pipeline.portfolio import allocate, scale_down

DEFAULT_POLICY_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "production_policy.yaml"

POLICY_VERSION = "production_policy.v1"


@lru_cache
def get_production_policy(path: str | None = None) -> dict:
    p = Path(path) if path else DEFAULT_POLICY_PATH
    return yaml.safe_load(p.read_text())


def spend_on_date(session: Session, *, on_date: date_type) -> float:
    start = datetime.combine(on_date, time.min, tzinfo=timezone.utc)
    end = datetime.combine(on_date, time.max, tzinfo=timezone.utc)
    stmt = select(func.coalesce(func.sum(CostEvent.generation_cost_usd + CostEvent.processing_cost_usd), 0)).where(
        CostEvent.created_at >= start, CostEvent.created_at <= end
    )
    return float(session.execute(stmt).scalar_one())


def approved_designs_count(session: Session, *, on_date: date_type | None = None) -> int:
    stmt = select(func.count(Artwork.id))
    if on_date is not None:
        start = datetime.combine(on_date, time.min, tzinfo=timezone.utc)
        end = datetime.combine(on_date, time.max, tzinfo=timezone.utc)
        stmt = stmt.where(Artwork.approved_at >= start, Artwork.approved_at <= end)
    return int(session.execute(stmt).scalar_one())


def build_daily_plan(
    session: Session,
    *,
    plan_date: date_type,
    target_final_designs: int | None = None,
    policy_path: str | None = None,
) -> DailyProductionPlan:
    settings = get_settings()
    policy = get_production_policy(policy_path)

    target = target_final_designs or policy["default_target_final_designs"]

    portfolio_allocation = allocate(target, policy["portfolio_allocation_fractions"])

    spent_today = spend_on_date(session, on_date=plan_date)
    remaining_daily_budget = max(0.0, settings.daily_budget_usd - spent_today)
    requested_budget_cap = target * settings.per_design_budget_usd * 1.5  # funnel headroom (repairs, exploration)
    budget_cap_usd = min(remaining_daily_budget, requested_budget_cap)

    rationale_parts = [
        f"target={target} designs.",
        f"portfolio_allocation={portfolio_allocation} (policy={POLICY_VERSION}).",
        f"spent_today=${spent_today:.2f}, daily_budget=${settings.daily_budget_usd:.2f}, "
        f"remaining=${remaining_daily_budget:.2f}.",
    ]

    if budget_cap_usd < requested_budget_cap:
        scale_factor = budget_cap_usd / requested_budget_cap if requested_budget_cap > 0 else 0.0
        portfolio_allocation = scale_down(portfolio_allocation, scale_factor)
        target = sum(portfolio_allocation.values())
        rationale_parts.append(
            f"budget-constrained: scaled allocation down by factor {scale_factor:.2f} "
            f"(no single bucket dropped to zero unless its fraction already was)."
        )

    production_slots = portfolio_allocation.get("PROVEN", 0) + portfolio_allocation.get("GROWING", 0)
    experimental_slots = portfolio_allocation.get("EXPERIMENTAL", 0) + portfolio_allocation.get("WILDCARD", 0)
    winner_mutation_slots = portfolio_allocation.get("WINNER_MUTATION", 0)

    existing = session.execute(
        select(DailyProductionPlan).where(DailyProductionPlan.plan_date == plan_date)
    ).scalar_one_or_none()

    if existing is not None:
        existing.target_final_designs = target
        existing.portfolio_allocation = portfolio_allocation
        existing.experimental_slots = experimental_slots
        existing.winner_mutation_slots = winner_mutation_slots
        existing.production_slots = production_slots
        existing.budget_cap_usd = budget_cap_usd
        existing.policy_version = POLICY_VERSION
        existing.rationale = " ".join(rationale_parts)
        session.flush()
        return existing

    plan = DailyProductionPlan(
        plan_date=plan_date,
        target_final_designs=target,
        portfolio_allocation=portfolio_allocation,
        collections=[],
        experimental_slots=experimental_slots,
        winner_mutation_slots=winner_mutation_slots,
        production_slots=production_slots,
        budget_cap_usd=budget_cap_usd,
        policy_version=POLICY_VERSION,
        rationale=" ".join(rationale_parts),
    )
    session.add(plan)
    session.flush()
    return plan
