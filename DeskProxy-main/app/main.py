"""
DeskProxy Enterprise – FastAPI application entry point.

Startup sequence:
  1. Configure structured logging
  2. Ensure data directories exist
  3. Initialise SQLite schema
  4. Initialise ChromaDB collection
  5. Load and warm-up the embedding model
  6. Register API routers

Shutdown sequence:
  1. Log graceful shutdown signal
"""

from __future__ import annotations

import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import ensure_directories, settings
from app.core.logging_config import configure_logging
from app.db import sqlite_repository, vector_search_repository
from app.services.semantic_embedding_service import initialise_model

# Configure logging first so every subsequent log call is formatted correctly
configure_logging(level=settings.log_level, use_json=settings.log_json)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("DeskProxy Enterprise starting up (version=%s)", settings.api_version)

    try:
        ensure_directories()
        logger.info("Runtime directories verified")

        sqlite_repository.initialise_schema()

        vector_search_repository.initialise_collection()

        initialise_model()

        logger.info("DeskProxy Enterprise is ready to serve requests")
    except Exception as exc:
        logger.critical("Startup failed: %s", exc, exc_info=True)
        raise

    yield  # application is live

    logger.info("DeskProxy Enterprise shutting down gracefully")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_application() -> FastAPI:
    application = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        description=settings.api_description,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    from app.api.query_router import router as query_router
    from app.api.cache_router import router as cache_router
    from app.api.telemetry_router import router as telemetry_router
    from app.api.health_router import router as health_router

    application.include_router(query_router)
    application.include_router(cache_router)
    application.include_router(telemetry_router)
    application.include_router(health_router)

    return application


app = create_application()
