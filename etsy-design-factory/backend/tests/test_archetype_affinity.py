from app.pipeline.archetype_affinity import rank_archetypes_by_opportunities
from app.pipeline.opportunity_engine import Opportunity
from app.pipeline.production_controller import get_production_policy


def _archetypes() -> list[dict]:
    return get_production_policy()["bootstrap_collection_archetypes"]


def test_no_opportunities_keeps_declared_order():
    archetypes = _archetypes()
    ranked = rank_archetypes_by_opportunities(archetypes, [])
    assert [a["name"] for a, _note in ranked] == [a["name"] for a in archetypes]
    assert all(note is None for _a, note in ranked)


def test_non_matching_opportunities_keep_declared_order():
    archetypes = _archetypes()
    opportunities = [Opportunity(description="quantum blockchain synergy widgets", rationale="x", confidence=0.9)]
    ranked = rank_archetypes_by_opportunities(archetypes, opportunities)
    assert [a["name"] for a, _note in ranked] == [a["name"] for a in archetypes]


def test_strong_signal_promotes_matching_archetype_ahead_of_declared_order():
    archetypes = _archetypes()
    assert archetypes[0]["name"] == "Botanical Calm"
    # "Desert Horizon" is declared second, not first -- a real signal about
    # desert/mid-century decor should move it to the front.
    opportunities = [
        Opportunity(
            description="Desert horizon mid-century wall art is climbing Etsy search this month",
            rationale="market signal (serpapi:google_search:etsy wall art trends)",
            confidence=0.8,
        )
    ]
    ranked = rank_archetypes_by_opportunities(archetypes, opportunities)
    assert ranked[0][0]["name"] == "Desert Horizon"
    assert ranked[0][1] is not None
    assert "market signal" in ranked[0][1]


def test_higher_confidence_signal_outranks_lower_confidence_match():
    archetypes = _archetypes()
    opportunities = [
        Opportunity(
            description="geometric bauhaus prints",
            rationale="market signal (a)",
            confidence=0.3,
        ),
        Opportunity(
            description="coastal linework art is trending",
            rationale="market signal (b)",
            confidence=0.9,
        ),
    ]
    ranked = rank_archetypes_by_opportunities(archetypes, opportunities)
    assert ranked[0][0]["name"] == "Coastal Ink"
