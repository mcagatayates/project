from fastapi.testclient import TestClient

from app.main import app


def test_submit_and_list_signals_open_when_no_token_configured(db_session):
    client = TestClient(app)
    resp = client.post(
        "/api/market-intelligence/signals",
        json={
            "signals": [
                {
                    "category": "etsy wall art trends",
                    "description": "Muted botanicals trending up this month",
                    "confidence": 0.65,
                    "source": "claude_web_research:2026-08-14",
                }
            ]
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["source"] == "claude_web_research:2026-08-14"

    resp2 = client.get("/api/market-intelligence/signals")
    assert resp2.status_code == 200
    assert len(resp2.json()["items"]) == 1


def test_submit_signals_requires_token_when_configured(db_session, monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("MARKET_SIGNAL_INGESTION_TOKEN", "secret-token")
    get_settings.cache_clear()

    client = TestClient(app)
    body = {"signals": [{"category": "x", "description": "y", "confidence": 0.5, "source": "test"}]}

    resp_no_token = client.post("/api/market-intelligence/signals", json=body)
    assert resp_no_token.status_code == 401

    resp_wrong_token = client.post("/api/market-intelligence/signals", json=body, headers={"X-Ingestion-Token": "nope"})
    assert resp_wrong_token.status_code == 401

    resp_ok = client.post("/api/market-intelligence/signals", json=body, headers={"X-Ingestion-Token": "secret-token"})
    assert resp_ok.status_code == 200

    monkeypatch.delenv("MARKET_SIGNAL_INGESTION_TOKEN", raising=False)
    get_settings.cache_clear()


def test_submit_signals_validates_confidence_range(db_session):
    client = TestClient(app)
    resp = client.post(
        "/api/market-intelligence/signals",
        json={"signals": [{"category": "x", "description": "y", "confidence": 1.5, "source": "test"}]},
    )
    assert resp.status_code == 422


def test_research_queries_endpoint_returns_todays_plan(db_session):
    client = TestClient(app)
    resp = client.get("/api/market-intelligence/research-queries")
    assert resp.status_code == 200
    body = resp.json()
    assert "plan_date" in body
    categories = {q["category"] for q in body["queries"]}
    assert "bestseller_tracking" in categories
    for q in body["queries"]:
        assert q["query"]
        assert q["reason"]


def test_refresh_requires_serpapi_key(db_session, monkeypatch):
    from app.config import get_settings

    monkeypatch.delenv("SERPAPI_KEY", raising=False)
    get_settings.cache_clear()

    client = TestClient(app)
    resp = client.post("/api/market-intelligence/refresh")
    assert resp.status_code == 400
    assert "SERPAPI_KEY" in resp.json()["detail"]
    get_settings.cache_clear()


def test_refresh_persists_whatever_sources_actually_found(db_session, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("SERPAPI_KEY", "fake-key-for-test")
    get_settings.cache_clear()

    async def fake_refresh(session):
        from app.memory.market_signal_memory import record_signal

        record_signal(session, category="rising_trend", description="real finding", confidence=0.6, source="test")
        return ["placeholder"]  # only length is used by the route

    monkeypatch.setattr("app.api.routes.market_intelligence.refresh_real_market_signals", fake_refresh)

    client = TestClient(app)
    resp = client.post("/api/market-intelligence/refresh")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["description"] == "real finding"

    get_settings.cache_clear()
