"""
Cache orchestration service — the core request pipeline.

For every incoming query this service:
  1. Normalises the raw text via QueryProcessingService
  2. Embeds the normalised text via SemanticEmbeddingService
  3. Searches ChromaDB for a semantically similar cached result
  4. On a hit  → returns the cached result and updates access metadata
  5. On a miss → executes the simulated cloud workload, stores the new
                 entry in both SQLite and ChromaDB, and returns the result
  6. Records a telemetry event regardless of hit/miss outcome
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.config import settings
from app.core.logging_config import get_logger
from app.db import sqlite_repository, vector_search_repository
from app.models.schemas import QueryRequest, QueryResponse
from app.services import (
    cloud_execution_simulator,
    query_processing_service,
    semantic_embedding_service,
    telemetry_aggregator,
)

logger = get_logger(__name__)


def process_query(request: QueryRequest) -> QueryResponse:
    """
    Execute the full semantic-cache lookup pipeline and return a response.

    This is the single entry point called by the API layer.
    """
    pipeline_start = time.perf_counter()
    query_id = str(uuid.uuid4())

    # ------------------------------------------------------------------
    # 1. Normalise
    # ------------------------------------------------------------------
    normalized = query_processing_service.normalize_query(request.query)
    logger.info(
        "Query received (id=%s) original=%r normalized=%r",
        query_id,
        request.query,
        normalized,
    )

    # ------------------------------------------------------------------
    # 2. Embed
    # ------------------------------------------------------------------
    try:
        embedding = semantic_embedding_service.get_embedding(normalized)
    except Exception as exc:
        logger.error("Embedding generation failed for query_id=%s: %s", query_id, exc, exc_info=True)
        raise RuntimeError("Embedding service unavailable") from exc

    # ------------------------------------------------------------------
    # 3. Semantic cache lookup
    # ------------------------------------------------------------------
    cache_hit = False
    similarity_score: Optional[float] = None
    matched_query: Optional[str] = None
    result: str

    try:
        candidates = vector_search_repository.query_similar(
            embedding=embedding,
            n_results=settings.max_cache_results,
        )
    except Exception as exc:
        logger.error("Vector search failed for query_id=%s: %s", query_id, exc, exc_info=True)
        candidates = []

    for candidate in candidates:
        score = candidate["similarity"]
        if score >= settings.similarity_threshold:
            cache_hit = True
            similarity_score = score
            matched_query = candidate["query_text"]
            entry_id = candidate["entry_id"]

            logger.info(
                "Cache HIT (id=%s, similarity=%.4f, matched=%r)",
                query_id, score, matched_query,
            )

            # Fetch the stored result from SQLite
            rows = sqlite_repository.get_all_cache_entries()
            row_map = {str(r["entry_id"]): r for r in rows}
            if entry_id in row_map:
                result = row_map[entry_id]["result"]
                sqlite_repository.update_cache_entry_access(entry_id)
            else:
                # Vector index ahead of SQLite (edge case) — treat as miss
                logger.warning(
                    "Vector entry %s not found in SQLite, treating as cache miss", entry_id
                )
                cache_hit = False
                similarity_score = None
                matched_query = None

            break

    # ------------------------------------------------------------------
    # 4. Cache miss → cloud execution + storage
    # ------------------------------------------------------------------
    if not cache_hit:
        logger.info("Cache MISS (id=%s)", query_id)

        result, _cloud_latency_ms = cloud_execution_simulator.execute_cloud_query(
            request.query
        )

        metadata_json: Optional[str] = (
            json.dumps(request.metadata) if request.metadata else None
        )

        try:
            entry_id = sqlite_repository.insert_cache_entry(
                query_text=request.query,
                normalized_text=normalized,
                result=result,
                metadata_json=metadata_json,
            )
            vector_search_repository.upsert_embedding(
                entry_id=entry_id,
                embedding=embedding,
                query_text=request.query,
                normalized_text=normalized,
            )
            logger.info("Stored new cache entry (id=%s, entry_id=%s)", query_id, entry_id)
        except Exception as exc:
            logger.error(
                "Failed to persist cache entry for query_id=%s: %s", query_id, exc, exc_info=True
            )
            # Continue — the caller still gets the result, just uncached

    # ------------------------------------------------------------------
    # 5. Compute total latency and record telemetry
    # ------------------------------------------------------------------
    elapsed_ms = (time.perf_counter() - pipeline_start) * 1000.0

    telemetry_aggregator.record_event(
        query_id=query_id,
        original_query=request.query,
        normalized_query=normalized,
        cache_hit=cache_hit,
        similarity_score=similarity_score,
        latency_ms=elapsed_ms,
        result_length=len(result),
    )

    return QueryResponse(
        query_id=query_id,
        original_query=request.query,
        normalized_query=normalized,
        cache_hit=cache_hit,
        similarity_score=similarity_score,
        matched_query=matched_query,
        result=result,
        latency_ms=round(elapsed_ms, 3),
        timestamp=datetime.now(timezone.utc),
    )
