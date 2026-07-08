"""
Semantic embedding service.

Wraps SentenceTransformers to:
  - Load the configured model exactly once at startup
  - Expose an in-process embedding cache (query → vector)
  - Generate normalised float list vectors suitable for ChromaDB

Model: all-MiniLM-L6-v2  (384-dim, cosine similarity optimised)
"""

from __future__ import annotations

import threading
from functools import lru_cache
from typing import Optional

from app.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# SentenceTransformers is imported lazily so the application can start
# and respond to /health even if the model download is slow.
_model = None
_model_lock = threading.Lock()


def _load_model():
    """Load the SentenceTransformer model (thread-safe, idempotent)."""
    global _model
    if _model is not None:
        return _model

    with _model_lock:
        if _model is not None:  # double-check after acquiring lock
            return _model

        from sentence_transformers import SentenceTransformer  # noqa: PLC0415

        model_name = settings.embedding_model_name
        logger.info("Loading embedding model: %s", model_name)
        try:
            _model = SentenceTransformer(model_name)
            logger.info("Embedding model loaded successfully")
        except Exception as exc:
            logger.error("Failed to load embedding model '%s': %s", model_name, exc, exc_info=True)
            raise RuntimeError(f"Embedding model load failure: {exc}") from exc

    return _model


def initialise_model() -> None:
    """Eagerly warm up the model so the first query is not penalised."""
    _load_model()
    # Warm-up inference to force ONNX / Torch compilation
    _embed_text("warmup deskproxy enterprise semantic cache")
    logger.info("Embedding model warm-up complete")


def is_model_loaded() -> bool:
    return _model is not None


@lru_cache(maxsize=8192)
def _embed_text(text: str) -> tuple[float, ...]:
    """
    Compute and cache the embedding vector for *text*.

    Returns a tuple (hashable, so lru_cache works) rather than a list.
    """
    model = _load_model()
    vector = model.encode(text, normalize_embeddings=True, show_progress_bar=False)
    return tuple(float(v) for v in vector)


def get_embedding(text: str) -> list[float]:
    """Return the embedding vector for *text* as a plain list of floats."""
    if not text:
        raise ValueError("Cannot embed empty text")
    return list(_embed_text(text))


def get_embedding_cache_stats() -> dict:
    info = _embed_text.cache_info()
    return {
        "hits": info.hits,
        "misses": info.misses,
        "maxsize": info.maxsize,
        "currsize": info.currsize,
    }
