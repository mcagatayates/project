import asyncio

from app.db.models.artwork import EtsyListingPackage
from app.db.models.enums import CreativeFamilyStatus
from app.memory.commercial_memory import record_observation
from app.pipeline.champion_challenger import (
    family_signature,
    find_or_create_family,
    generate_challenger_genome,
    maybe_promote_to_champion,
)
from app.pipeline.commercial_learning import run_commercial_learning
from app.pipeline.market_intelligence import run_market_intelligence
from app.pipeline.opportunity_engine import rank_opportunities
from app.pipeline.performance_ingestion import ingest_performance
from app.providers.commercial_feedback import NullCommercialFeedbackAdapter
from tests.factories import make_genome


def test_market_intelligence_returns_empty_without_a_configured_adapter():
    report = asyncio.run(run_market_intelligence())
    assert report.signals == []


def test_opportunity_engine_falls_back_to_proven_collections_when_no_signals(db_session, collection):
    from app.db.models.enums import CollectionStatus, ProductionMode

    collection.status = CollectionStatus.PRODUCTION.value
    collection.mode = ProductionMode.PRODUCTION.value
    db_session.flush()

    report = asyncio.run(run_market_intelligence())
    opportunities = rank_opportunities(db_session, report=report)
    assert len(opportunities) >= 1
    assert "no external market signal" in opportunities[0].rationale


def test_null_commercial_feedback_adapter_ingests_nothing(db_session, collection):
    import uuid
    from datetime import datetime, timezone

    package = EtsyListingPackage(
        artwork_id=uuid.uuid4(),
        title_concepts=["x"],
        description_data={},
        keyword_candidates=[],
        tags=[],
        style="japandi",
        subject="leaf",
        palette="sage-clay",
        orientation="portrait",
        collection_id=collection.id,
        internal_sku="WA-TEST",
        print_export_ids=[],
        mockup_ids=[],
        published_at=datetime.now(timezone.utc),
        external_listing_id="etsy-123",
    )
    db_session.add(package)
    db_session.flush()

    count = asyncio.run(ingest_performance(db_session, NullCommercialFeedbackAdapter(), listings=[package]))
    assert count == 0


def test_champion_challenger_family_grouping_and_promotion(db_session, collection):
    genome_a = make_genome(collection_id=collection.id)
    genome_b = make_genome(collection_id=collection.id)  # identical signature by default factory

    family_a = find_or_create_family(db_session, genome=genome_a)
    family_b = find_or_create_family(db_session, genome=genome_b)
    assert family_a.id == family_b.id  # same signature -> same family
    assert family_a.status == CreativeFamilyStatus.CHALLENGER.value
    assert len(family_a.member_genome_ids) == 2

    # not enough members yet
    maybe_promote_to_champion(db_session, family=family_a)
    assert family_a.status == CreativeFamilyStatus.CHALLENGER.value

    # add a third member and real commercial observations
    genome_c = make_genome(collection_id=collection.id)
    family_a = find_or_create_family(db_session, genome=genome_c)
    assert len(family_a.member_genome_ids) == 3

    from datetime import datetime, timezone

    for genome in (genome_a, genome_b, genome_c):
        record_observation(
            db_session,
            source="etsy",
            metric_name="favorites",
            metric_value=12.0,
            observed_at=datetime.now(timezone.utc),
            design_genome_id=genome.id,
        )

    maybe_promote_to_champion(db_session, family=family_a)
    assert family_a.status == CreativeFamilyStatus.CHAMPION.value
    assert family_a.performance_summary["average"] == 12.0


def test_champion_never_promoted_without_real_commercial_data(db_session, collection):
    for _ in range(4):
        genome = make_genome(collection_id=collection.id)
        family = find_or_create_family(db_session, genome=genome)

    maybe_promote_to_champion(db_session, family=family)
    assert family.status == CreativeFamilyStatus.CHALLENGER.value  # no observations -> never promoted


def test_generate_challenger_genome_inherits_signature_not_the_genome(db_session, collection):
    champion_genome = make_genome(collection_id=collection.id)
    family = find_or_create_family(db_session, genome=champion_genome)
    family.status = CreativeFamilyStatus.CHAMPION.value
    db_session.flush()

    challenger = generate_challenger_genome(collection, champion=family, slot_index=0, seed=1)
    assert challenger.id != champion_genome.id
    assert challenger.style_dna.art_movement == family_signature(champion_genome)["art_movement"]


def test_run_commercial_learning_is_a_noop_report_when_nothing_qualifies(db_session, collection):
    result = run_commercial_learning(db_session)
    assert result == {"families_promoted": [], "collections_graduated": []}
