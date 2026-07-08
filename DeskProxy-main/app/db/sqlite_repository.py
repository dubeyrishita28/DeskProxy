"""
SQLite persistence layer for DeskProxy Enterprise.

Responsibilities:
  - Initialise and migrate the schema on startup
  - Provide a thread-safe connection pool via a per-thread connection cache
  - Implement CRUD for cache entries and telemetry events

Raw sqlite3 is used intentionally (no ORM) so the schema stays explicit
and query behaviour is fully transparent.
"""

from __future__ import annotations

import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Generator, Optional

from app.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

_CACHE_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS cache_entries (
    entry_id        TEXT PRIMARY KEY,
    query_text      TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    result          TEXT NOT NULL,
    access_count    INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL,
    last_accessed_at TEXT NOT NULL,
    metadata        TEXT
);
"""

_TELEMETRY_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS telemetry_events (
    event_id        TEXT PRIMARY KEY,
    query_id        TEXT NOT NULL,
    original_query  TEXT NOT NULL,
    normalized_query TEXT NOT NULL,
    cache_hit       INTEGER NOT NULL,
    similarity_score REAL,
    latency_ms      REAL NOT NULL,
    result_length   INTEGER NOT NULL,
    recorded_at     TEXT NOT NULL
);
"""

_INDEXES_DDL = [
    "CREATE INDEX IF NOT EXISTS idx_cache_normalized ON cache_entries (normalized_text);",
    "CREATE INDEX IF NOT EXISTS idx_telemetry_recorded ON telemetry_events (recorded_at);",
    "CREATE INDEX IF NOT EXISTS idx_telemetry_cache_hit ON telemetry_events (cache_hit);",
]

# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

_local = threading.local()


def _get_connection() -> sqlite3.Connection:
    """Return a per-thread SQLite connection, creating it if needed."""
    if not hasattr(_local, "conn") or _local.conn is None:
        db_path = settings.sqlite_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            str(db_path),
            check_same_thread=False,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        _local.conn = conn
        logger.debug("Opened SQLite connection for thread %s", threading.current_thread().name)
    return _local.conn


@contextmanager
def _db() -> Generator[sqlite3.Connection, None, None]:
    conn = _get_connection()
    try:
        yield conn
        conn.commit()
    except sqlite3.Error as exc:
        conn.rollback()
        logger.error("SQLite error – rolling back: %s", exc, exc_info=True)
        raise


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------

def initialise_schema() -> None:
    """Create tables and indexes if they do not already exist."""
    with _db() as conn:
        conn.execute(_CACHE_TABLE_DDL)
        conn.execute(_TELEMETRY_TABLE_DDL)
        for ddl in _INDEXES_DDL:
            conn.execute(ddl)
    logger.info("SQLite schema initialised at %s", settings.sqlite_path)


def check_connectivity() -> bool:
    """Return True if the database is reachable and consistent."""
    try:
        with _db() as conn:
            conn.execute("SELECT 1").fetchone()
        return True
    except Exception:
        logger.exception("SQLite connectivity check failed")
        return False


# ---------------------------------------------------------------------------
# Cache entry repository
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def insert_cache_entry(
    query_text: str,
    normalized_text: str,
    result: str,
    metadata_json: Optional[str] = None,
) -> str:
    """Persist a new cache entry and return its entry_id."""
    entry_id = str(uuid.uuid4())
    now = _now_iso()
    with _db() as conn:
        conn.execute(
            """
            INSERT INTO cache_entries
                (entry_id, query_text, normalized_text, result, access_count,
                 created_at, last_accessed_at, metadata)
            VALUES (?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (entry_id, query_text, normalized_text, result, now, now, metadata_json),
        )
    logger.debug("Cache entry created: %s", entry_id)
    return entry_id


def update_cache_entry_access(entry_id: str) -> None:
    """Increment access count and refresh last_accessed_at."""
    with _db() as conn:
        conn.execute(
            """
            UPDATE cache_entries
            SET access_count = access_count + 1,
                last_accessed_at = ?
            WHERE entry_id = ?
            """,
            (_now_iso(), entry_id),
        )


def get_all_cache_entries() -> list[sqlite3.Row]:
    with _db() as conn:
        return conn.execute(
            """
            SELECT entry_id, query_text, result, access_count,
                   created_at, last_accessed_at, metadata
            FROM cache_entries
            ORDER BY last_accessed_at DESC
            """
        ).fetchall()


def delete_all_cache_entries() -> int:
    """Purge all cache entries and return the number of rows deleted."""
    with _db() as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM cache_entries")
        count: int = cursor.fetchone()[0]
        conn.execute("DELETE FROM cache_entries")
    logger.info("Purged %d cache entries", count)
    return count


# ---------------------------------------------------------------------------
# Telemetry repository
# ---------------------------------------------------------------------------

def insert_telemetry_event(
    query_id: str,
    original_query: str,
    normalized_query: str,
    cache_hit: bool,
    similarity_score: Optional[float],
    latency_ms: float,
    result_length: int,
) -> None:
    event_id = str(uuid.uuid4())
    with _db() as conn:
        conn.execute(
            """
            INSERT INTO telemetry_events
                (event_id, query_id, original_query, normalized_query,
                 cache_hit, similarity_score, latency_ms, result_length, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                query_id,
                original_query,
                normalized_query,
                int(cache_hit),
                similarity_score,
                latency_ms,
                result_length,
                _now_iso(),
            ),
        )


def fetch_telemetry_rows(limit: int = 10_000) -> list[sqlite3.Row]:
    with _db() as conn:
        return conn.execute(
            """
            SELECT cache_hit, similarity_score, latency_ms, recorded_at
            FROM telemetry_events
            ORDER BY recorded_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
