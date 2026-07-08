"""
Compatibility shim — the canonical settings live in app.config.

This module re-exports ApplicationSettings and settings so that any
tooling expecting app.core.config still works without modification.
"""
from app.config import ApplicationSettings, settings  # noqa: F401

__all__ = ["ApplicationSettings", "settings"]
