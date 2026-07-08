"""
ChromaDB vector search repository.

Responsibilities:
  - Initialise and persist the ChromaDB collection
  - Store embedding vectors with metadata
  - Execute approximate nearest-neighbour queries
  - Convert cosine distance to a [0, 1] similarity score

ChromaDB's default metric is cosine distance, where distance = 1 − similarity.
The conversion is:  similarity = 1 - distance
"""

from __future__ import annotations

from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Singleton collection handle
# ---------------------------------------------------------------------------

_client: Optional[chromadb.ClientAPI] = None
_collection: Optional[chromadb.Collection] = None


def _get_collection() -> chromadb.Collection:
    global _client, _collection
    if _collection is not None:
        return _collection

    persist_dir = str(settings.chroma_persist_dir)
    settings.chroma_persist_dir.mkdir(parents=True, exist_ok=True)

    _client = chromadb.PersistentClient(
        path=persist_dir,
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    _collection = _client.get_or_create_collection(
        name=settings.chroma_collection_name,
        metadata={"hnsw:space": "cosine"},
    )
    logger.info(
        "ChromaDB collection '%s' ready at %s (documents: %d)",
        settings.chroma_collection_name,
        persist_dir,
        _collection.count(),
    )
    return _collection


def initialise_collection() -> None:
    """Eagerly initialise the collection so errors surface at startup."""
    _get_collection()


def check_connectivity() -> bool:
    try:
        col = _get_collection()
        col.count()
        return True
    except Exception:
        logger.exception("ChromaDB connectivity check failed")
        return False


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def upsert_embedding(
    entry_id: str,
    embedding: list[float],
    query_text: str,
    normalized_text: str,
) -> None:
    """Store or update a vector for the given cache entry."""
    col = _get_collection()
    col.upsert(
        ids=[entry_id],
        embeddings=[embedding],
        metadatas=[{"query_text": query_text, "normalized_text": normalized_text}],
        documents=[normalized_text],
    )
    logger.debug("Upserted embedding for entry %s", entry_id)


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def query_similar(
    embedding: list[float],
    n_results: int = 5,
) -> list[dict]:
    """
    Return up to n_results similar entries sorted by similarity (descending).

    Each returned dict contains:
      - entry_id (str)
      - similarity (float, 0–1)
      - query_text (str)
      - normalized_text (str)
    """
    col = _get_collection()
    total = col.count()
    if total == 0:
        return []

    safe_n = min(n_results, total)
    results = col.query(
        query_embeddings=[embedding],
        n_results=safe_n,
        include=["metadatas", "distances"],
    )

    hits: list[dict] = []
    ids = results.get("ids", [[]])[0]
    distances = results.get("distances", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    for entry_id, distance, meta in zip(ids, distances, metadatas):
        similarity = max(0.0, 1.0 - float(distance))
        hits.append(
            {
                "entry_id": entry_id,
                "similarity": round(similarity, 6),
                "query_text": meta.get("query_text", ""),
                "normalized_text": meta.get("normalized_text", ""),
            }
        )

    hits.sort(key=lambda h: h["similarity"], reverse=True)
    return hits


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def delete_all_embeddings() -> int:
    """Remove every vector from the collection.  Returns count deleted."""
    col = _get_collection()
    count = col.count()
    if count > 0:
        all_ids = col.get(include=[])["ids"]
        col.delete(ids=all_ids)
        logger.info("Deleted %d vectors from ChromaDB", count)
    return count
