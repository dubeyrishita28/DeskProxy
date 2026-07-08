"""
Application configuration – single source of truth for all settings.

Every path, threshold, model name, and tuneable parameter lives here.
Values are driven by environment variables with sensible defaults so the
application works out-of-the-box while remaining fully configurable in
production.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _env_float(key: str, default: float) -> float:
    try:
        return float(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


def _env_bool(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes"}


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ApplicationSettings:
    """Immutable settings object populated once at startup."""

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------
    base_dir: Path = field(
        default_factory=lambda: Path(_env("BASE_DIR", str(Path(__file__).parent.parent)))
    )

    @property
    def data_dir(self) -> Path:
        return self.base_dir / _env("DATA_DIR_NAME", "data")

    @property
    def sqlite_path(self) -> Path:
        return self.data_dir / _env("SQLITE_FILENAME", "deskproxy.db")

    @property
    def chroma_persist_dir(self) -> Path:
        return self.data_dir / _env("CHROMA_DIR_NAME", "chroma")

    @property
    def log_dir(self) -> Path:
        return self.base_dir / _env("LOG_DIR_NAME", "logs")

    # ------------------------------------------------------------------
    # Embedding / semantic search
    # ------------------------------------------------------------------
    embedding_model_name: str = field(
        default_factory=lambda: _env("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    )
    similarity_threshold: float = field(
        default_factory=lambda: _env_float("SIMILARITY_THRESHOLD", 0.72)
    )
    chroma_collection_name: str = field(
        default_factory=lambda: _env("CHROMA_COLLECTION", "deskproxy_cache")
    )
    max_cache_results: int = field(
        default_factory=lambda: _env_int("MAX_CACHE_RESULTS", 5)
    )

    # ------------------------------------------------------------------
    # Analytics cache
    # ------------------------------------------------------------------
    analytics_cache_ttl_seconds: int = field(
        default_factory=lambda: _env_int("ANALYTICS_CACHE_TTL", 300)
    )

    # ------------------------------------------------------------------
    # Cloud simulation
    # ------------------------------------------------------------------
    cloud_min_latency_ms: int = field(
        default_factory=lambda: _env_int("CLOUD_MIN_LATENCY_MS", 80)
    )
    cloud_max_latency_ms: int = field(
        default_factory=lambda: _env_int("CLOUD_MAX_LATENCY_MS", 350)
    )

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------
    api_title: str = field(
        default_factory=lambda: _env("API_TITLE", "DeskProxy Enterprise")
    )
    api_version: str = field(
        default_factory=lambda: _env("API_VERSION", "2.0.0")
    )
    api_description: str = field(
        default_factory=lambda: _env(
            "API_DESCRIPTION",
            "Semantic query cache with telemetry and analytics for enterprise deployments.",
        )
    )

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    log_level: str = field(
        default_factory=lambda: _env("LOG_LEVEL", "INFO").upper()
    )
    log_json: bool = field(
        default_factory=lambda: _env_bool("LOG_JSON", False)
    )


# ---------------------------------------------------------------------------
# Module-level singleton – import this everywhere
# ---------------------------------------------------------------------------

settings = ApplicationSettings()


def ensure_directories() -> None:
    """Create all required runtime directories if they do not exist."""
    for directory in (
        settings.data_dir,
        settings.chroma_persist_dir,
        settings.log_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)
