"""
Pydantic request/response models for the DeskProxy Enterprise API.

Every external-facing contract is defined here.  Internal data classes
live alongside their owning modules to avoid polluting this file.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    """Payload for POST /query."""

    query: str = Field(..., min_length=1, max_length=2048, description="Natural language query to resolve.")
    metadata: Optional[dict[str, Any]] = Field(default=None, description="Arbitrary client-supplied metadata stored with the cache entry.")

    @field_validator("query")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("query must not be blank")
        return stripped


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class QueryResponse(BaseModel):
    """Response payload for POST /query."""

    query_id: str
    original_query: str
    normalized_query: str
    cache_hit: bool
    similarity_score: Optional[float] = None
    matched_query: Optional[str] = None
    result: str
    latency_ms: float
    timestamp: datetime


class CacheEntry(BaseModel):
    """Single entry returned by GET /cache/entries."""

    entry_id: str
    query_text: str
    result: str
    access_count: int
    created_at: datetime
    last_accessed_at: datetime
    metadata: Optional[dict[str, Any]] = None


class CacheListResponse(BaseModel):
    total: int
    entries: list[CacheEntry]


class TelemetrySummary(BaseModel):
    """Aggregated telemetry for GET /telemetry/summary."""

    total_queries: int
    cache_hits: int
    cache_misses: int
    hit_rate_percent: float
    average_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    average_similarity_score: float
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None


class HealthResponse(BaseModel):
    """Response payload for GET /health."""

    status: str
    version: str
    embedding_model: str
    sqlite_ok: bool
    chroma_ok: bool
    uptime_seconds: float
    timestamp: datetime


class DeleteCacheResponse(BaseModel):
    message: str
    deleted_count: int
