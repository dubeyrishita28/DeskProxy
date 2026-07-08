"""
Unit / integration tests for the SQLite repository layer.

Uses a temporary database path via monkeypatching so tests
are fully isolated and never touch the real data directory.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# Patch the settings before any app import resolves the DB path
@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setenv("BASE_DIR", str(tmp_path))
    # Reload settings and repository with fresh state
    import importlib
    import app.config as cfg_mod
    import app.db.sqlite_repository as repo_mod

    # Reset thread-local connection so the new path is used
    if hasattr(repo_mod._local, "conn") and repo_mod._local.conn:
        try:
            repo_mod._local.conn.close()
        except Exception:
            pass
        repo_mod._local.conn = None

    # Reinitialise settings with new base dir
    importlib.reload(cfg_mod)
    importlib.reload(repo_mod)
    repo_mod.initialise_schema()
    yield
    if hasattr(repo_mod._local, "conn") and repo_mod._local.conn:
        try:
            repo_mod._local.conn.close()
        except Exception:
            pass
        repo_mod._local.conn = None


class TestSchemaInitialisation:
    def test_schema_initialises_without_error(self):
        from app.db.sqlite_repository import initialise_schema
        initialise_schema()  # idempotent

    def test_connectivity_check_passes(self):
        from app.db.sqlite_repository import check_connectivity
        assert check_connectivity() is True


class TestCacheEntryRepository:
    def test_insert_returns_uuid(self):
        from app.db.sqlite_repository import insert_cache_entry
        entry_id = insert_cache_entry("show revenue", "show revenue", "Revenue is $4M")
        assert isinstance(entry_id, str)
        assert len(entry_id) == 36  # UUID4 format

    def test_fetch_all_returns_inserted_entry(self):
        from app.db.sqlite_repository import insert_cache_entry, get_all_cache_entries
        insert_cache_entry("headcount report", "headcount report", "847 FTEs")
        rows = get_all_cache_entries()
        queries = [r["query_text"] for r in rows]
        assert "headcount report" in queries

    def test_update_access_increments_count(self):
        from app.db.sqlite_repository import insert_cache_entry, get_all_cache_entries, update_cache_entry_access
        eid = insert_cache_entry("kpi summary", "key performance indicator summary", "3 KPIs")
        update_cache_entry_access(eid)
        rows = get_all_cache_entries()
        row = next(r for r in rows if r["entry_id"] == eid)
        assert row["access_count"] == 2

    def test_delete_all_removes_entries(self):
        from app.db.sqlite_repository import insert_cache_entry, delete_all_cache_entries, get_all_cache_entries
        insert_cache_entry("q1 revenue", "first quarter revenue", "Result A")
        insert_cache_entry("q2 revenue", "second quarter revenue", "Result B")
        count = delete_all_cache_entries()
        assert count == 2
        assert get_all_cache_entries() == []

    def test_metadata_json_roundtrip(self):
        import json
        from app.db.sqlite_repository import insert_cache_entry, get_all_cache_entries
        meta = json.dumps({"user": "alice", "dept": "finance"})
        eid = insert_cache_entry("budget vs actuals", "budget actuals", "Under budget", meta)
        rows = get_all_cache_entries()
        row = next(r for r in rows if r["entry_id"] == eid)
        assert json.loads(row["metadata"])["user"] == "alice"


class TestTelemetryRepository:
    def test_insert_and_fetch_telemetry(self):
        from app.db.sqlite_repository import insert_telemetry_event, fetch_telemetry_rows
        insert_telemetry_event(
            query_id="qid-001",
            original_query="show me revenue",
            normalized_query="show revenue",
            cache_hit=True,
            similarity_score=0.91,
            latency_ms=45.2,
            result_length=320,
        )
        rows = fetch_telemetry_rows()
        assert len(rows) == 1
        assert rows[0]["cache_hit"] == 1
        assert abs(rows[0]["similarity_score"] - 0.91) < 1e-6

    def test_miss_event_has_none_similarity(self):
        from app.db.sqlite_repository import insert_telemetry_event, fetch_telemetry_rows
        insert_telemetry_event(
            query_id="qid-002",
            original_query="opex breakdown",
            normalized_query="operating expenditure breakdown",
            cache_hit=False,
            similarity_score=None,
            latency_ms=210.5,
            result_length=150,
        )
        rows = fetch_telemetry_rows()
        miss = next(r for r in rows if r["cache_hit"] == 0)
        assert miss["similarity_score"] is None
