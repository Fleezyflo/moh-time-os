"""Database connection and schema management for MOH Time OS v2."""

import logging
import sqlite3
from contextlib import contextmanager

from lib import paths, safe_sql
from lib.clock import now_iso

log = logging.getLogger("moh_time_os")


def _db_path():
    """Resolve DB path at call time to respect env overrides (MOH_TIME_OS_DB)."""
    return paths.db_path()


def init_db() -> None:
    """Initialize database with schema. Safe to call multiple times.

    Delegates to schema_engine.converge() which reads lib/schema.py TABLES
    as the single source of truth. The legacy SCHEMA constant was removed
    in v24 — all table definitions now live in lib/schema.py.
    """
    from lib import schema_engine

    db = _db_path()
    db.parent.mkdir(parents=True, exist_ok=True)

    with get_connection() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        schema_engine.converge(conn)

    log.info(f"Database initialized at {db}")


@contextmanager
def get_connection():
    """Get database connection with auto-commit/rollback."""
    conn = sqlite3.connect(_db_path(), timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except (sqlite3.Error, ValueError, OSError) as e:
        conn.rollback()
        log.error(f"Database error: {e}")
        raise
    finally:
        conn.close()


def now_iso() -> str:  # noqa: F811
    """Current UTC time in canonical ISO format (24-char, 3-digit ms, Z suffix).

    Delegates to lib.clock.now_iso() which is the single source of truth.
    Kept here for backward compatibility — new code should import from lib.clock.
    """
    from lib.clock import now_iso as _now_iso

    return _now_iso()


def db_exists() -> bool:
    """Check if database file exists."""
    return _db_path().exists()


def table_counts() -> dict:
    """Get row counts for all tables."""
    if not db_exists():
        return {}

    from lib.schema import TABLES

    with get_connection() as conn:
        counts = {}
        for table in TABLES:
            try:
                sql = safe_sql.select_count_bare(table)
                count = conn.execute(sql).fetchone()[0]
                counts[table] = count
            except sqlite3.OperationalError:
                counts[table] = 0
        return counts


def integrity_check() -> tuple[bool, str]:
    """Run SQLite integrity check. Returns (ok, message)."""
    if not db_exists():
        return False, "Database does not exist"

    try:
        with get_connection() as conn:
            result = conn.execute("PRAGMA integrity_check").fetchone()[0]
            return result == "ok", result
    except (sqlite3.Error, ValueError, OSError) as e:
        return False, str(e)


def checkpoint_wal() -> None:
    """Checkpoint WAL to main database file."""
    if not db_exists():
        return

    with get_connection() as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
