"""
Telemetry aggregation service.

Reads raw telemetry rows from SQLite and computes summary statistics.
Results are cached in-process with a TTL to avoid redundant database
scans on the hot path.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import numpy as np

from app.config import settings
from app.core.logging_config import get_logger
from app.db import sqlite_repository

logger = get_logger(__name__)


@dataclass
class _CachedSummary:
    data: dict
    expires_at: float


_analytics_cache: Optional[_CachedSummary] = None


def _invalidate_cache() -> None:
    global _analytics_cache
    _analytics_cache = None


def get_telemetry_summary() -> dict:
    """
    Return aggregated telemetry, using the in-memory cache when valid.
    """
    global _analytics_cache

    now = time.monotonic()
    if _analytics_cache is not None and now < _analytics_cache.expires_at:
        logger.debug("Analytics cache hit")
        return _analytics_cache.data

    logger.debug("Analytics cache miss – recomputing from SQLite")
    summary = _compute_summary()

    _analytics_cache = _CachedSummary(
        data=summary,
        expires_at=now + settings.analytics_cache_ttl_seconds,
    )
    return summary


def _compute_summary() -> dict:
    rows = sqlite_repository.fetch_telemetry_rows()

    total = len(rows)
    if total == 0:
        return {
            "total_queries": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "hit_rate_percent": 0.0,
            "average_latency_ms": 0.0,
            "p95_latency_ms": 0.0,
            "p99_latency_ms": 0.0,
            "average_similarity_score": 0.0,
            "window_start": None,
            "window_end": None,
        }

    hits = sum(1 for r in rows if r["cache_hit"])
    misses = total - hits

    latencies = np.array([r["latency_ms"] for r in rows], dtype=float)
    similarity_scores = np.array(
        [r["similarity_score"] for r in rows if r["similarity_score"] is not None],
        dtype=float,
    )

    timestamps = [r["recorded_at"] for r in rows]
    window_start = min(timestamps)
    window_end = max(timestamps)

    return {
        "total_queries": total,
        "cache_hits": hits,
        "cache_misses": misses,
        "hit_rate_percent": round(hits / total * 100, 2),
        "average_latency_ms": round(float(np.mean(latencies)), 3),
        "p95_latency_ms": round(float(np.percentile(latencies, 95)), 3),
        "p99_latency_ms": round(float(np.percentile(latencies, 99)), 3),
        "average_similarity_score": round(float(np.mean(similarity_scores)), 4) if len(similarity_scores) > 0 else 0.0,
        "window_start": window_start,
        "window_end": window_end,
    }


def record_event(
    query_id: str,
    original_query: str,
    normalized_query: str,
    cache_hit: bool,
    similarity_score: Optional[float],
    latency_ms: float,
    result_length: int,
) -> None:
    """Persist telemetry and invalidate the analytics cache."""
    try:
        sqlite_repository.insert_telemetry_event(
            query_id=query_id,
            original_query=original_query,
            normalized_query=normalized_query,
            cache_hit=cache_hit,
            similarity_score=similarity_score,
            latency_ms=latency_ms,
            result_length=result_length,
        )
        _invalidate_cache()
    except Exception as exc:
        # Telemetry must never crash the request path
        logger.warning("Failed to record telemetry event: %s", exc)
