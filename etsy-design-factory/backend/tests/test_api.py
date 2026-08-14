import asyncio

from fastapi.testclient import TestClient

from app.db.models.enums import CandidateStatus
from app.genome.codec import to_row
from app.main import app
from app.pipeline.concept_gate import gate_concept
from app.pipeline.concept_generation import create_concept
from app.pipeline.runner import run_concept_to_selection
from tests.factories import make_genome


def test_health_check():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_dashboard_summary_empty_state(db_session):
    client = TestClient(app)
    resp = client.get("/api/dashboard/today")
    assert resp.status_code == 200
    body = resp.json()
    assert body["generated"] == 0
    assert body["approved"] == 0
    assert body["cost_per_approved_design_usd"] is None


def test_production_plan_create_and_fetch(db_session):
    client = TestClient(app)
    resp = client.post("/api/production/plan", json={"plan_date": "2026-08-14", "target_final_designs": 20})
    assert resp.status_code == 200
    body = resp.json()
    assert body["target_final_designs"] == 20
    assert sum(body["portfolio_allocation"].values()) == 20

    resp2 = client.get("/api/production/plan/2026-08-14")
    assert resp2.status_code == 200
    assert resp2.json()["id"] == body["id"]

    resp3 = client.get("/api/production/plan/2099-01-01")
    assert resp3.status_code == 404


def test_candidates_list_and_approval_flow(db_session, registry, collection):
    genome = make_genome(collection_id=collection.id)
    genome_row = to_row(genome)
    db_session.add(genome_row)
    db_session.flush()
    concept = create_concept(
        db_session,
        genome_row=genome_row,
        collection=collection,
        production_mode="PRODUCTION",
        planned_candidate_count=2,
    )
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
    db_session.commit()

    client = TestClient(app)
    resp = client.get("/api/candidates", params={"status": "AWAITING_APPROVAL"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["id"] == str(candidate.id)
    assert item["subject"] == genome.subject_dna.primary_subject

    img_resp = client.get(item["image_url"])
    assert img_resp.status_code == 200
    assert img_resp.headers["content-type"] == "image/png"
    assert img_resp.content[:8] == b"\x89PNG\r\n\x1a\n"

    approve_resp = client.post(
        f"/api/candidates/{candidate.id}/approval",
        json={"action": "APPROVE", "actor": "dashboard-user"},
    )
    assert approve_resp.status_code == 200
    approve_body = approve_resp.json()
    assert approve_body["artwork_id"] is not None

    # already approved -> re-approving should now conflict
    resp_again = client.post(
        f"/api/candidates/{candidate.id}/approval",
        json={"action": "APPROVE", "actor": "dashboard-user"},
    )
    assert resp_again.status_code == 409


def test_invalid_status_query_returns_400(db_session):
    client = TestClient(app)
    resp = client.get("/api/candidates", params={"status": "NOT_A_REAL_STATUS"})
    assert resp.status_code == 400


def test_approval_of_unknown_candidate_returns_404(db_session):
    import uuid

    client = TestClient(app)
    resp = client.post(
        f"/api/candidates/{uuid.uuid4()}/approval",
        json={"action": "APPROVE", "actor": "x"},
    )
    assert resp.status_code == 404
