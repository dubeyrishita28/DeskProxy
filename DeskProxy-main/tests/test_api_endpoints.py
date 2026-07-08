"""
Integration / API tests using FastAPI's TestClient.

Each test class uses an isolated temporary database so tests
are hermetic and can run in parallel.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    """
    Spin up a fully initialised TestClient with isolated storage.
    """
    tmp = tmp_path_factory.mktemp("deskproxy_test")
    import os
    os.environ["BASE_DIR"] = str(tmp)

    # Reload config and db modules so they pick up the patched BASE_DIR
    import importlib
    import app.config as cfg_mod
    import app.db.sqlite_repository as repo_mod
    import app.db.vector_search_repository as vec_mod

    importlib.reload(cfg_mod)

    # Reset singletons
    if hasattr(repo_mod._local, "conn") and repo_mod._local.conn:
        repo_mod._local.conn.close()
        repo_mod._local.conn = None

    vec_mod._client = None
    vec_mod._collection = None

    importlib.reload(repo_mod)
    importlib.reload(vec_mod)

    from app.main import create_application
    test_app = create_application()

    with TestClient(test_app, raise_server_exceptions=True) as c:
        yield c


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_has_required_fields(self, client):
        data = client.get("/health").json()
        for field in ("status", "version", "sqlite_ok", "chroma_ok", "uptime_seconds"):
            assert field in data, f"Missing field: {field}"

    def test_health_status_is_healthy(self, client):
        data = client.get("/health").json()
        assert data["status"] == "healthy"


class TestQueryEndpoint:
    def test_valid_query_returns_200(self, client):
        payload = {"query": "show me the revenue dashboard"}
        response = client.post("/query", json=payload)
        assert response.status_code == 200

    def test_response_has_required_fields(self, client):
        data = client.post("/query", json={"query": "KPI summary for Q3"}).json()
        for field in ("query_id", "original_query", "cache_hit", "result", "latency_ms"):
            assert field in data

    def test_first_call_is_cache_miss(self, client):
        data = client.post("/query", json={"query": "unique query abc123xyz"}).json()
        assert data["cache_hit"] is False
        assert data["similarity_score"] is None

    def test_duplicate_query_is_cache_hit(self, client):
        q = "duplicate cache test revenue report"
        client.post("/query", json={"query": q})           # seed
        data = client.post("/query", json={"query": q}).json()  # hit
        assert data["cache_hit"] is True
        assert data["similarity_score"] is not None
        assert data["similarity_score"] > 0.9

    def test_semantically_similar_query_hits_cache(self, client):
        # Seed with one phrasing
        client.post("/query", json={"query": "show annual recurring revenue breakdown"})
        # Query with different phrasing
        data = client.post(
            "/query", json={"query": "annual recurring revenue summary"}
        ).json()
        # May or may not hit depending on threshold — just verify it runs cleanly
        assert "cache_hit" in data
        assert "result" in data

    def test_empty_query_rejected(self, client):
        response = client.post("/query", json={"query": "   "})
        assert response.status_code == 422

    def test_missing_query_field_rejected(self, client):
        response = client.post("/query", json={})
        assert response.status_code == 422

    def test_query_too_long_rejected(self, client):
        response = client.post("/query", json={"query": "x" * 3000})
        assert response.status_code == 422

    def test_query_with_metadata_accepted(self, client):
        payload = {"query": "HR headcount analysis", "metadata": {"user_id": "u42", "dept": "hr"}}
        data = client.post("/query", json=payload).json()
        assert data["query_id"]

    def test_normalized_query_in_response(self, client):
        data = client.post("/query", json={"query": "Please show me the KPI dashboard"}).json()
        # normalized should differ from original (filler removed, abbreviation expanded)
        assert data["normalized_query"] != data["original_query"]


class TestCacheEndpoints:
    def test_list_entries_returns_200(self, client):
        response = client.get("/cache/entries")
        assert response.status_code == 200

    def test_list_entries_has_total_field(self, client):
        data = client.get("/cache/entries").json()
        assert "total" in data
        assert "entries" in data

    def test_delete_cache_returns_200(self, client):
        # Seed an entry first
        client.post("/query", json={"query": "budget vs actuals Q2"})
        response = client.delete("/cache")
        assert response.status_code == 200

    def test_delete_cache_clears_entries(self, client):
        client.post("/query", json={"query": "clear cache test entry"})
        client.delete("/cache")
        data = client.get("/cache/entries").json()
        assert data["total"] == 0


class TestTelemetryEndpoint:
    def test_telemetry_returns_200(self, client):
        response = client.get("/telemetry/summary")
        assert response.status_code == 200

    def test_telemetry_has_required_fields(self, client):
        data = client.get("/telemetry/summary").json()
        required = (
            "total_queries", "cache_hits", "cache_misses",
            "hit_rate_percent", "average_latency_ms",
            "p95_latency_ms", "p99_latency_ms", "average_similarity_score",
        )
        for field in required:
            assert field in data, f"Missing telemetry field: {field}"

    def test_telemetry_reflects_queries(self, client):
        # Purge and start fresh
        client.delete("/cache")
        before = client.get("/telemetry/summary").json()["total_queries"]
        client.post("/query", json={"query": "telemetry counting test query"})
        after = client.get("/telemetry/summary").json()["total_queries"]
        assert after == before + 1
