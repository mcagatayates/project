"""Performance Ingestion: pulls whatever a commercial adapter actually
returns for published listings and records it. See
docs/AGENT_CONTRACTS.md "Performance Ingestion" -- no adapter configured
(or no data returned) means no rows, never an error and never a guess.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models.artwork import EtsyListingPackage
from app.memory.commercial_memory import record_observation
from app.providers.commercial_feedback import CommercialFeedbackAdapter


async def ingest_performance(
    session: Session, adapter: CommercialFeedbackAdapter, *, listings: list[EtsyListingPackage]
) -> int:
    recorded = 0
    now = datetime.now(timezone.utc)
    for listing in listings:
        if not listing.external_listing_id:
            continue  # never published -- nothing to ingest
        metrics = await adapter.fetch_metrics(external_listing_id=listing.external_listing_id)
        for metric_name, metric_value in metrics.items():
            record_observation(
                session,
                source=adapter.name,
                metric_name=metric_name,
                metric_value=metric_value,
                observed_at=now,
                artwork_id=listing.artwork_id,
                external_listing_id=listing.external_listing_id,
            )
            recorded += 1
    return recorded
