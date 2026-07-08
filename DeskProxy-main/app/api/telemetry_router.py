"""
GET /telemetry/summary  endpoint.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, status

from app.core.logging_config import get_logger
from app.models.schemas import TelemetrySummary
from app.services.telemetry_aggregator import get_telemetry_summary

logger = get_logger(__name__)
router = APIRouter(tags=["Telemetry"])


@router.get(
    "/telemetry/summary",
    response_model=TelemetrySummary,
    summary="Aggregated telemetry statistics",
    description=(
        "Returns hit rate, latency percentiles, and average similarity score. "
        "Results are cached in-process and refreshed automatically."
    ),
)
def telemetry_summary() -> TelemetrySummary:
    try:
        data = get_telemetry_summary()

        def _parse_dt(val) -> datetime | None:
            if not val:
                return None
            if isinstance(val, datetime):
                return val
            try:
                return datetime.fromisoformat(str(val))
            except (ValueError, TypeError):
                return None

        return TelemetrySummary(
            total_queries=data["total_queries"],
            cache_hits=data["cache_hits"],
            cache_misses=data["cache_misses"],
            hit_rate_percent=data["hit_rate_percent"],
            average_latency_ms=data["average_latency_ms"],
            p95_latency_ms=data["p95_latency_ms"],
            p99_latency_ms=data["p99_latency_ms"],
            average_similarity_score=data["average_similarity_score"],
            window_start=_parse_dt(data.get("window_start")),
            window_end=_parse_dt(data.get("window_end")),
        )
    except Exception as exc:
        logger.exception("Failed to compute telemetry summary")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Telemetry aggregation failed.",
        ) from exc
