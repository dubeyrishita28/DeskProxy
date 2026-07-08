"""
GET /cache/entries  and  DELETE /cache  endpoints.
"""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, HTTPException, status

from app.core.logging_config import get_logger
from app.db import sqlite_repository, vector_search_repository
from app.models.schemas import CacheEntry, CacheListResponse, DeleteCacheResponse

logger = get_logger(__name__)
router = APIRouter(tags=["Cache"])


@router.get(
    "/cache/entries",
    response_model=CacheListResponse,
    summary="List all cache entries",
)
def list_cache_entries() -> CacheListResponse:
    try:
        rows = sqlite_repository.get_all_cache_entries()
        entries: list[CacheEntry] = []
        for row in rows:
            metadata = None
            if row["metadata"]:
                try:
                    metadata = json.loads(row["metadata"])
                except (json.JSONDecodeError, TypeError):
                    metadata = None

            entries.append(
                CacheEntry(
                    entry_id=row["entry_id"],
                    query_text=row["query_text"],
                    result=row["result"],
                    access_count=row["access_count"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    last_accessed_at=datetime.fromisoformat(row["last_accessed_at"]),
                    metadata=metadata,
                )
            )
        return CacheListResponse(total=len(entries), entries=entries)
    except Exception as exc:
        logger.exception("Failed to list cache entries")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve cache entries.",
        ) from exc


@router.delete(
    "/cache",
    response_model=DeleteCacheResponse,
    summary="Purge all cache entries",
    description="Removes all entries from both the SQLite store and the ChromaDB vector index.",
)
def purge_cache() -> DeleteCacheResponse:
    try:
        sqlite_count = sqlite_repository.delete_all_cache_entries()
        vector_search_repository.delete_all_embeddings()
        logger.info("Cache purged: %d entries removed", sqlite_count)
        return DeleteCacheResponse(
            message="Cache purged successfully.",
            deleted_count=sqlite_count,
        )
    except Exception as exc:
        logger.exception("Failed to purge cache")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cache purge failed.",
        ) from exc
