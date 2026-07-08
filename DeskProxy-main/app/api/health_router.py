"""
GET /health  endpoint.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi import APIRouter

from app.config import settings
from app.core.logging_config import get_logger
from app.db import sqlite_repository, vector_search_repository
from app.models.schemas import HealthResponse
from app.services.semantic_embedding_service import is_model_loaded

logger = get_logger(__name__)
router = APIRouter(tags=["Health"])

_startup_time = time.monotonic()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health check",
)
def health_check() -> HealthResponse:
    sqlite_ok = sqlite_repository.check_connectivity()
    chroma_ok = vector_search_repository.check_connectivity()
    uptime = time.monotonic() - _startup_time

    overall = "healthy" if sqlite_ok and chroma_ok and is_model_loaded() else "degraded"

    return HealthResponse(
        status=overall,
        version=settings.api_version,
        embedding_model=settings.embedding_model_name,
        sqlite_ok=sqlite_ok,
        chroma_ok=chroma_ok,
        uptime_seconds=round(uptime, 2),
        timestamp=datetime.now(timezone.utc),
    )
