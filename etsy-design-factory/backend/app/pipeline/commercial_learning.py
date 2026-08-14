"""Commercial Learning: folds real CommercialObservations into
CreativeFamily.performance_summary and Collection graduation state. Never
rewrites historical DesignGenome/Experiment rows -- only the mutable
aggregates (CreativeFamily, Collection) are updated in place, per
docs/DOMAIN_MODEL.md invariant 1. See docs/AGENT_CONTRACTS.md.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.commercial import CreativeFamily
from app.db.models.enums import CollectionStatus, CreativeFamilyStatus
from app.pipeline.champion_challenger import maybe_promote_to_champion


def run_commercial_learning(session: Session, *, metric_name: str = "favorites") -> dict:
    promoted: list[str] = []
    stmt = select(CreativeFamily).where(CreativeFamily.status == CreativeFamilyStatus.CHALLENGER.value)
    for family in session.execute(stmt).scalars().all():
        before = family.status
        maybe_promote_to_champion(session, family=family, metric_name=metric_name)
        if family.status != before:
            promoted.append(str(family.id))

    from app.db.models.collection import Collection
    from app.pipeline.collection_planner import maybe_graduate_collection, maybe_saturate_collection

    graduated: list[str] = []
    stmt2 = select(Collection).where(Collection.status == CollectionStatus.DISCOVERY.value)
    for collection in session.execute(stmt2).scalars().all():
        before = collection.status
        maybe_graduate_collection(session, collection)
        if collection.status != before:
            graduated.append(str(collection.id))

    stmt3 = select(Collection).where(Collection.status == CollectionStatus.PRODUCTION.value)
    for collection in session.execute(stmt3).scalars().all():
        maybe_saturate_collection(session, collection)

    return {"families_promoted": promoted, "collections_graduated": graduated}
