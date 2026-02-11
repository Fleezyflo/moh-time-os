"""
Test fixtures for deterministic testing.

This module provides:
- fixture_db: Creates temp SQLite databases with pinned seed data
- golden_seed.json: Pinned data that defines golden expectations
"""

from .fixture_db import create_fixture_db, get_fixture_db_path, guard_no_live_db

__all__ = ["create_fixture_db", "get_fixture_db_path", "guard_no_live_db"]
