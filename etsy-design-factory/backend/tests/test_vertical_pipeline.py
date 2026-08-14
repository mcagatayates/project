import asyncio

from app.db.models.enums import ApprovalAction, CandidateStatus, GateStatus
from app.db.models.evaluation import Evaluation
from app.db.models.generation import GenerationCandidate
from app.genome.codec import to_row
from app.pipeline.approval import apply_approval
from app.pipeline.concept_gate import gate_concept
from app.pipeline.concept_generation import create_concept
from app.pipeline.runner import run_concept_to_selection
from tests.factories import make_genome


def _make_concept(db_session, collection, *, planned_candidate_count=3):
    genome = make_genome(collection_id=collection.id)
    genome_row = to_row(genome)
    db_session.add(genome_row)
    db_session.flush()

    concept = create_concept(
        db_session,
        genome_row=genome_row,
        collection=collection,
        production_mode="PRODUCTION",
        planned_candidate_count=planned_candidate_count,
    )
    return genome, genome_row, concept


def test_concept_gate_passes_for_in_boundary_palette(db_session, registry, collection):
    genome, genome_row, concept = _make_concept(db_session, collection)
    asyncio.run(gate_concept(db_session, registry, concept=concept, genome_row=genome_row, collection=collection))
    assert concept.gate_status == GateStatus.PASSED.value
    assert concept.gate_reasoning


def test_concept_gate_rejects_out_of_boundary_palette_without_provider_call(db_session, registry, collection):
    genome, genome_row, concept = _make_concept(db_session, collection)
    genome_row.palette_dna = {**genome_row.palette_dna, "palette_name": "neon-clash"}
    db_session.flush()

    asyncio.run(gate_concept(db_session, registry, concept=concept, genome_row=genome_row, collection=collection))
    assert concept.gate_status == GateStatus.REJECTED.value
    assert "palette" in concept.gate_reasoning


def test_high_quality_run_produces_a_selected_and_kept_candidate(db_session, registry, collection):
    genome, genome_row, concept = _make_concept(db_session, collection, planned_candidate_count=3)
    asyncio.run(gate_concept(db_session, registry, concept=concept, genome_row=genome_row, collection=collection))
    assert concept.gate_status == GateStatus.PASSED.value

    kept = asyncio.run(
        run_concept_to_selection(
            db_session,
            registry,
            concept=concept,
            genome=genome,
            collection=collection,
            quality_seed_fn=lambda attempt: 0.9,
        )
    )
    assert len(kept) == 1
    assert kept[0].status == CandidateStatus.SELECTED.value

    evaluations = db_session.query(Evaluation).filter_by(generation_candidate_id=kept[0].id).all()
    assert len(evaluations) == 1
    assert evaluations[0].overall_pass is True


def test_low_quality_run_triggers_repair_and_can_still_recover(db_session, registry, collection):
    genome, genome_row, concept = _make_concept(db_session, collection, planned_candidate_count=1)
    asyncio.run(gate_concept(db_session, registry, concept=concept, genome_row=genome_row, collection=collection))

    asyncio.run(
        run_concept_to_selection(
            db_session,
            registry,
            concept=concept,
            genome=genome,
            collection=collection,
            quality_seed_fn=lambda attempt: 0.55,  # fails QC but not TERMINAL -> repair path
        )
    )
    all_candidates = db_session.query(GenerationCandidate).filter_by(concept_id=concept.id).all()
    assert len(all_candidates) >= 2  # original + at least one repair attempt
    assert any(c.is_repair for c in all_candidates)

    from app.db.models.failure import FailureRecord, RepairAttempt

    failures = db_session.query(FailureRecord).all()
    repairs = db_session.query(RepairAttempt).all()
    assert len(failures) >= 1
    assert len(repairs) >= 1
    assert repairs[0].outcome in ("IMPROVED", "NO_IMPROVEMENT")


def test_full_flow_through_approval_creates_artwork(db_session, registry, collection):
    genome, genome_row, concept = _make_concept(db_session, collection, planned_candidate_count=2)
    asyncio.run(gate_concept(db_session, registry, concept=concept, genome_row=genome_row, collection=collection))

    kept = asyncio.run(
        run_concept_to_selection(
            db_session,
            registry,
            concept=concept,
            genome=genome,
            collection=collection,
            quality_seed_fn=lambda attempt: 0.92,
        )
    )
    assert kept

    candidate = kept[0]
    candidate.status = CandidateStatus.AWAITING_APPROVAL.value
    db_session.flush()

    approval, artwork, new_concept = apply_approval(
        db_session,
        candidate=candidate,
        action=ApprovalAction.APPROVE.value,
        actor="test-user",
        collection=collection,
    )
    assert artwork is not None
    assert artwork.sku.startswith("WA-")
    assert candidate.status == CandidateStatus.APPROVED.value
    assert new_concept is None


def test_approval_mutating_action_creates_new_genome_version_and_concept(db_session, registry, collection):
    genome, genome_row, concept = _make_concept(db_session, collection, planned_candidate_count=2)
    asyncio.run(gate_concept(db_session, registry, concept=concept, genome_row=genome_row, collection=collection))

    kept = asyncio.run(
        run_concept_to_selection(
            db_session,
            registry,
            concept=concept,
            genome=genome,
            collection=collection,
            quality_seed_fn=lambda attempt: 0.92,
        )
    )
    candidate = kept[0]
    candidate.status = CandidateStatus.AWAITING_APPROVAL.value
    db_session.flush()

    approval, artwork, new_concept = apply_approval(
        db_session,
        candidate=candidate,
        action=ApprovalAction.CHANGE_PALETTE.value,
        actor="test-user",
        collection=collection,
    )
    assert artwork is None
    assert new_concept is not None
    assert candidate.status == CandidateStatus.REJECTED.value
    assert approval.resulting_genome_id is not None

    from app.db.models.genome import DesignGenome as DesignGenomeRow

    new_row = db_session.get(DesignGenomeRow, approval.resulting_genome_id)
    assert new_row.design_lineage_id == genome_row.design_lineage_id
    assert new_row.version == genome_row.version + 1
    assert new_row.palette_dna["palette_name"] != genome_row.palette_dna["palette_name"]
