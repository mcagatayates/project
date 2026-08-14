"""Commercial feedback adapter interface. Real vendor adapters (Etsy, ...)
are NOT implemented in this repository (see docs/ROADMAP.md "Explicit
non-goals") -- the NullCommercialFeedbackAdapter is the default and only
adapter shipped, and it always returns "no data," never a guessed number.
This keeps app/pipeline/performance_ingestion.py honest by construction:
it can only write a CommercialObservation for a metric an adapter actually
returned.
"""

from __future__ import annotations

from typing import Protocol


class CommercialFeedbackAdapter(Protocol):
    name: str

    async def fetch_metrics(self, *, external_listing_id: str) -> dict[str, float]:
        """Returns whatever metrics are actually available for this
        listing. Missing/unsupported metrics are simply absent from the
        dict -- never represented as 0 or any other placeholder."""
        ...


class NullCommercialFeedbackAdapter:
    """No commercial data source configured. Always returns {}."""

    name = "null_commercial_feedback"

    async def fetch_metrics(self, *, external_listing_id: str) -> dict[str, float]:
        return {}
