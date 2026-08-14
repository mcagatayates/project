"""Collection Planner: turns a DailyProductionPlan's slot counts into
concrete Collection assignments (existing collections when capacity
allows, new ones when it doesn't), and applies the DISCOVERY -> PRODUCTION
graduation rule. See docs/AGENT_CONTRACTS.md."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.approval import Approval
from app.db.models.artwork import Artwork
from app.db.models.collection import Collection
from app.db.models.enums import ApprovalAction, CollectionStatus, PortfolioBucket, ProductionMode
from app.db.models.evaluation import Evaluation
from app.db.models.generation import GenerationCandidate
from app.db.models.production import DailyProductionPlan
from app.pipeline.production_controller import get_production_policy


@dataclass
class SlotAssignment:
    collection: Collection
    slots: int
    bucket: str
    parent_artwork_id: uuid.UUID | None = None


def approved_count_for_collection(session: Session, collection_id: uuid.UUID) -> int:
    stmt = select(func.count(Artwork.id)).where(Artwork.collection_id == collection_id)
    return int(session.execute(stmt).scalar_one())


def open_capacity(session: Session, collection: Collection) -> int:
    return max(0, collection.target_design_count - approved_count_for_collection(session, collection.id))


def acceptance_rate_for_collection(session: Session, collection_id: uuid.UUID) -> float | None:
    from app.db.models.concept import Concept

    stmt = (
        select(Approval.action)
        .join(GenerationCandidate, Approval.generation_candidate_id == GenerationCandidate.id)
        .join(Concept, GenerationCandidate.concept_id == Concept.id)
        .where(Concept.collection_id == collection_id)
        .where(Approval.action.in_([ApprovalAction.APPROVE.value, ApprovalAction.REJECT.value]))
    )
    actions = list(session.execute(stmt).scalars().all())
    if not actions:
        return None
    approved = sum(1 for a in actions if a == ApprovalAction.APPROVE.value)
    return approved / len(actions)


def maybe_graduate_collection(session: Session, collection: Collection) -> Collection:
    if collection.status != CollectionStatus.DISCOVERY.value:
        return collection
    policy = get_production_policy()["graduation"]
    approved = approved_count_for_collection(session, collection.id)
    if approved < policy["min_approved_for_production"]:
        return collection
    rate = acceptance_rate_for_collection(session, collection.id)
    if rate is not None and rate >= policy["min_acceptance_rate"]:
        collection.status = CollectionStatus.PRODUCTION.value
        collection.mode = ProductionMode.PRODUCTION.value
        session.flush()
    return collection


def maybe_saturate_collection(session: Session, collection: Collection) -> Collection:
    if collection.status == CollectionStatus.RETIRED.value:
        return collection
    if open_capacity(session, collection) <= 0:
        collection.status = CollectionStatus.SATURATED.value
        session.flush()
    return collection


def _existing_collections(session: Session, status: str) -> list[Collection]:
    stmt = select(Collection).where(Collection.status == status)
    return list(session.execute(stmt).scalars().all())


def _bootstrap_collection(session: Session, archetype: dict) -> Collection:
    collection = Collection(
        name=archetype["name"],
        thesis=archetype["thesis"],
        target_aesthetic=archetype["target_aesthetic"],
        target_customer_hypothesis=archetype["target_customer_hypothesis"],
        palette_boundaries=archetype["palette_boundaries"],
        medium=archetype["medium"],
        subject_families=archetype["subject_families"],
        composition_diversity_requirements={"min_layout_types": 2},
        target_design_count=get_production_policy()["collection_capacity_default"],
        experimental_variables={},
        status=CollectionStatus.DISCOVERY.value,
        mode=ProductionMode.DISCOVERY.value,
    )
    session.add(collection)
    session.flush()
    return collection


def _top_recent_artwork(session: Session, *, exclude_collection_ids: set[uuid.UUID] | None = None) -> Artwork | None:
    """Pick a recent winner to seed WINNER_MUTATION slots: highest average
    of aesthetic+commercial_potential among the most recent evaluations."""
    weights = ("aesthetic", "commercial_potential")
    stmt = select(Evaluation).order_by(Evaluation.created_at.desc()).limit(200)
    evaluations = list(session.execute(stmt).scalars().all())
    scored: list[tuple[float, Evaluation]] = []
    for ev in evaluations:
        scores = ev.scores()
        avg = sum(scores[w]["value"] for w in weights) / len(weights)
        scored.append((avg, ev))
    scored.sort(key=lambda t: t[0], reverse=True)

    for _score, ev in scored:
        stmt2 = select(Artwork).where(Artwork.generation_candidate_id == ev.generation_candidate_id)
        artwork = session.execute(stmt2).scalar_one_or_none()
        if artwork and (not exclude_collection_ids or artwork.collection_id not in exclude_collection_ids):
            return artwork
    return None


def plan_collections(session: Session, *, plan: DailyProductionPlan) -> list[SlotAssignment]:
    policy = get_production_policy()
    archetypes = policy["bootstrap_collection_archetypes"]
    allocation = dict(plan.portfolio_allocation)

    for c in _existing_collections(session, CollectionStatus.DISCOVERY.value):
        maybe_graduate_collection(session, c)
    for c in _existing_collections(session, CollectionStatus.PRODUCTION.value):
        maybe_saturate_collection(session, c)

    assignments: list[SlotAssignment] = []

    # PROVEN + GROWING -> existing PRODUCTION collections with open capacity.
    production_needed = allocation.get(PortfolioBucket.PROVEN.value, 0) + allocation.get(
        PortfolioBucket.GROWING.value, 0
    )
    production_collections = [
        c for c in _existing_collections(session, CollectionStatus.PRODUCTION.value) if open_capacity(session, c) > 0
    ]
    production_collections.sort(key=lambda c: approved_count_for_collection(session, c.id))

    remaining = production_needed
    production_slot_counts: dict[uuid.UUID, int] = {}
    if production_collections:
        # Round-robin across collections (least-produced first, already
        # sorted above) so no single collection absorbs the whole bucket.
        i = 0
        while remaining > 0:
            c = production_collections[i % len(production_collections)]
            production_slot_counts[c.id] = production_slot_counts.get(c.id, 0) + 1
            remaining -= 1
            i += 1
    for c in production_collections:
        if production_slot_counts.get(c.id):
            assignments.append(
                SlotAssignment(collection=c, slots=production_slot_counts[c.id], bucket="PROVEN_OR_GROWING")
            )
    unmet_production = remaining  # falls through to EXPERIMENTAL below (mission: never zero out silently)

    # WINNER_MUTATION -> seed from a recent strong Artwork's collection.
    winner_slots = allocation.get(PortfolioBucket.WINNER_MUTATION.value, 0)
    if winner_slots > 0:
        seed = _top_recent_artwork(session)
        if seed is not None:
            seed_collection = session.get(Collection, seed.collection_id)
            if seed_collection is not None:
                assignments.append(
                    SlotAssignment(
                        collection=seed_collection,
                        slots=winner_slots,
                        bucket="WINNER_MUTATION",
                        parent_artwork_id=seed.id,
                    )
                )
                winner_slots = 0
    # no eligible winner yet (e.g. day one) -> fall through to EXPERIMENTAL

    # EXPERIMENTAL + WILDCARD (+ any unmet PROVEN/GROWING or WINNER_MUTATION
    # shortfall) -> existing DISCOVERY collections, then bootstrap new ones.
    experimental_needed = (
        allocation.get(PortfolioBucket.EXPERIMENTAL.value, 0)
        + allocation.get(PortfolioBucket.WILDCARD.value, 0)
        + unmet_production
        + winner_slots
    )
    discovery_collections = [
        c for c in _existing_collections(session, CollectionStatus.DISCOVERY.value) if open_capacity(session, c) > 0
    ]

    remaining = experimental_needed
    archetype_idx = 0
    while remaining > 0:
        if discovery_collections:
            c = discovery_collections.pop(0)
        else:
            archetype = archetypes[archetype_idx % len(archetypes)]
            archetype_idx += 1
            existing_names = {a.collection.name for a in assignments}
            if archetype["name"] in existing_names and archetype_idx <= len(archetypes):
                continue
            c = _bootstrap_collection(session, archetype)
        cap = open_capacity(session, c)
        take = min(cap, remaining) if cap > 0 else remaining
        take = max(take, 1)
        assignments.append(SlotAssignment(collection=c, slots=take, bucket="EXPERIMENTAL_OR_WILDCARD"))
        remaining -= take

    plan.collections = [
        {
            "collection_id": str(a.collection.id),
            "collection_name": a.collection.name,
            "slots": a.slots,
            "bucket": a.bucket,
            "mode": a.collection.mode,
            "parent_artwork_id": str(a.parent_artwork_id) if a.parent_artwork_id else None,
        }
        for a in assignments
    ]
    session.flush()
    return assignments
