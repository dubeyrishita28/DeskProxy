"""
POST /query endpoint.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.core.logging_config import get_logger
from app.models.schemas import QueryRequest, QueryResponse
from app.services.cache_orchestration_service import process_query

logger = get_logger(__name__)
router = APIRouter(tags=["Query"])


@router.post(
    "/query",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit a semantic query",
    description=(
        "Normalises the query, performs a semantic cache lookup, and returns "
        "the cached result (hit) or a freshly executed cloud result (miss)."
    ),
)
def submit_query(request: QueryRequest) -> QueryResponse:
    try:
        return process_query(request)
    except RuntimeError as exc:
        logger.error("Query processing error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error processing query")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again.",
        ) from exc
