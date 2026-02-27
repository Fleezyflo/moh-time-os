"""
Centralized Database Access for MOH TIME OS.

Single source of truth for:
- DB path resolution
- Connection factory
- Schema convergence (delegated to schema_engine)
- Startup validation

ALL code must use this module for DB access. No direct sqlite3.connect() elsewhere.

Schema is declared in lib/schema.  Convergence logic lives in lib/schema_engine.
This module wires them together and provides the public API that the rest of
the codebase calls.
"""

import logging
import re
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from lib import paths, safe_sql, schema, schema_engine

logger = logging.getLogger(__name__)

# ============================================================
# SQL IDENTIFIER VALIDATION
# ============================================================

_SAFE_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def validate_identifier(name: str) -> str:
    """Validate that *name* is a safe SQL identifier (table or column name).

    Returns the name unchanged if valid; raises ``ValueError`` otherwise.
    This prevents SQL injection via dynamic identifier interpolation.
    """
    if not _SAFE_IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return name


# ============================================================
# DB PATH RESOLUTION
# ============================================================


def get_db_path() -> Path:
    """
    Get the canonical DB path. ALL code must use this.

    Resolution order:
    1. MOH_TIME_OS_DB env var (explicit override)
    2. ~/.moh_time_os/data/moh_time_os.db (default via paths.db_path())
    """
    return paths.db_path()


def get_db_path_str() -> str:
    """Get DB path as string for sqlite3.connect()."""
    return str(get_db_path())


# ============================================================
# CONNECTION FACTORY
# ============================================================


@contextmanager
def get_connection(
    row_factory: bool = True,
) -> Generator[sqlite3.Connection, None, None]:
    """
    Get a database connection with proper setup.

    Usage:
        with get_connection() as conn:
            conn.execute(...)
    """
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    if row_factory:
        conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ============================================================
# SCHEMA INTROSPECTION
# ============================================================


def get_table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """Get existing column names for a table."""
    validate_identifier(table)
    try:
        cursor = conn.execute(safe_sql.pragma_table_info(table))
        return {row[1] for row in cursor.fetchall()}
    except sqlite3.OperationalError:
        return set()


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    """Check if a table exists."""
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cursor.fetchone() is not None


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Get current schema version from PRAGMA user_version."""
    cursor = conn.execute("PRAGMA user_version")
    return cursor.fetchone()[0]


def set_schema_version(conn: sqlite3.Connection, version: int):
    """Set schema version via PRAGMA user_version."""
    if not isinstance(version, int) or version < 0:
        raise ValueError(f"Invalid schema version: {version!r}")
    conn.execute(safe_sql.pragma_user_version_set(version))


# ============================================================
# SCHEMA CONVERGENCE — delegates to schema_engine
# ============================================================


def run_migrations(conn: sqlite3.Connection) -> dict:
    """
    Converge the database schema to match lib/schema declarations.

    Delegates entirely to schema_engine.converge() which:
      1. Creates missing tables
      2. Adds missing columns to existing tables
      3. Creates missing indexes (skipping views)
      4. Runs idempotent data migrations
      5. Sets PRAGMA user_version

    Returns a results dict for logging.
    """
    previous_version = get_schema_version(conn)
    results = schema_engine.converge(conn)
    results["previous_version"] = previous_version
    return results


# ============================================================
# STARTUP ENTRY POINT
# ============================================================

_migrations_run = False


def run_startup_migrations() -> dict:
    """
    Run schema convergence at startup. Safe to call multiple times.
    Logs comprehensive startup info.
    """
    global _migrations_run  # noqa: PLW0603

    db_path = get_db_path()

    # Log startup info
    logger.info("=" * 50)
    logger.info("MOH TIME OS Database Startup")
    logger.info("=" * 50)
    logger.info("Resolved DB path: %s", db_path)
    logger.info("DB exists: %s", db_path.exists())
    logger.info("Target SCHEMA_VERSION: %s", schema.SCHEMA_VERSION)

    # Ensure parent directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with get_connection() as conn:
        version_before = get_schema_version(conn)
        logger.info("Current user_version: %s", version_before)

        if version_before >= schema.SCHEMA_VERSION and _migrations_run:
            logger.info("Schema already converged, skipping")
            return {"status": "skipped", "version": version_before}

        # Run convergence
        results = run_migrations(conn)

        # Log what happened
        if results.get("tables_created"):
            logger.info("Tables created: %s", results["tables_created"])
        if results.get("columns_added"):
            logger.info("Columns added: %s", results["columns_added"])
        if results.get("indexes_created"):
            logger.info("Indexes created: %d", len(results["indexes_created"]))
        if results.get("data_migrations_run"):
            logger.info("Data migrations: %s", results["data_migrations_run"])
        if results.get("skipped_views"):
            logger.info("Skipped views: %s", results["skipped_views"])
        if results.get("errors"):
            logger.warning("Convergence errors: %s", results["errors"])

        if (
            not results.get("tables_created")
            and not results.get("columns_added")
            and not results.get("indexes_created")
        ):
            logger.info("No changes needed, schema up to date")

        # Confirm critical tables present
        for critical in (
            "clients",
            "tasks",
            "communications",
            "projects",
            "invoices",
            "inbox_items_v29",
        ):
            if table_exists(conn, critical):
                logger.info("OK %s present", critical)
            else:
                logger.error("MISSING %s", critical)

        logger.info("Final user_version: %s", results.get("schema_version"))
        logger.info("=" * 50)

        _migrations_run = True
        return results


def ensure_migrations():
    """Ensure schema has converged. Called by StateStore and other entry points."""
    global _migrations_run  # noqa: PLW0603
    if not _migrations_run:
        run_startup_migrations()
        _migrations_run = True


# ============================================================
# DEBUG INFO
# ============================================================


def get_db_info() -> dict:
    """
    Get detailed DB info for /api/debug/db endpoint.

    Returns dict with path, exists, size, version, table schemas.
    """
    db_path = get_db_path()
    info = {
        "resolved_db_path": str(db_path),
        "exists": db_path.exists(),
        "file_size": None,
        "sqlite_version": sqlite3.sqlite_version,
        "user_version": None,
        "target_schema_version": schema.SCHEMA_VERSION,
        "tables": {},
    }

    if db_path.exists():
        info["file_size"] = db_path.stat().st_size

        with get_connection() as conn:
            info["user_version"] = get_schema_version(conn)

            # Get columns for core tables
            for table in [
                "tasks",
                "communications",
                "events",
                "invoices",
                "projects",
                "people",
            ]:
                if table_exists(conn, table):
                    info["tables"][table] = sorted(get_table_columns(conn, table))
                else:
                    info["tables"][table] = None  # Table doesn't exist

    return info
