"""Database connection and schema management for MOH Time OS v2."""

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from lib import paths, safe_sql

log = logging.getLogger("moh_time_os")

DB_PATH = paths.db_path()

SCHEMA = """
-- Clients
CREATE TABLE IF NOT EXISTS clients (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    tier TEXT CHECK (tier IN ('A', 'B', 'C')),
    type TEXT,

    financial_annual_value REAL,
    financial_ar_outstanding REAL,
    financial_ar_aging TEXT,
    financial_payment_pattern TEXT,

    relationship_health TEXT CHECK (relationship_health IN
        ('excellent', 'good', 'fair', 'poor', 'critical')),
    relationship_trend TEXT CHECK (relationship_trend IN
        ('improving', 'stable', 'declining')),
    relationship_last_interaction TEXT,
    relationship_notes TEXT,

    contacts_json TEXT,
    active_projects_json TEXT,

    xero_contact_id TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- People
CREATE TABLE IF NOT EXISTS people (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,

    type TEXT CHECK (type IN ('internal', 'external')),
    company TEXT,
    client_id TEXT REFERENCES clients(id),
    role TEXT,
    department TEXT,

    relationship_trust TEXT CHECK (relationship_trust IN
        ('high', 'medium', 'low', 'unknown')),
    relationship_style TEXT,
    relationship_responsiveness TEXT,
    relationship_notes TEXT,

    reliability_rate REAL,
    reliability_notes TEXT,

    last_interaction TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Projects
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    client_id TEXT REFERENCES clients(id),

    status TEXT CHECK (status IN
        ('discovery', 'active', 'delivery', 'on_hold', 'completed', 'cancelled')),
    health TEXT CHECK (health IN
        ('on_track', 'at_risk', 'blocked', 'late')),

    start_date TEXT,
    target_end_date TEXT,

    value REAL,
    stakes TEXT,
    description TEXT,

    milestones_json TEXT,
    blockers_json TEXT,
    team_json TEXT,

    asana_project_id TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Items
CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY,
    what TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('open', 'waiting', 'done', 'cancelled')),

    owner TEXT NOT NULL,
    owner_id TEXT REFERENCES people(id),
    counterparty TEXT,
    counterparty_id TEXT REFERENCES people(id),

    due TEXT,
    waiting_since TEXT,

    client_id TEXT REFERENCES clients(id),
    project_id TEXT REFERENCES projects(id),
    context_snapshot_json TEXT,
    stakes TEXT,
    history_context TEXT,

    source_type TEXT,
    source_ref TEXT,
    captured_at TEXT NOT NULL,

    resolution_outcome TEXT,
    resolution_notes TEXT,
    resolved_at TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Item History (append-only audit log)
CREATE TABLE IF NOT EXISTS item_history (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES items(id),
    timestamp TEXT NOT NULL,
    change TEXT NOT NULL,
    changed_by TEXT NOT NULL
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_clients_tier ON clients(tier);
CREATE INDEX IF NOT EXISTS idx_clients_health ON clients(relationship_health);
CREATE INDEX IF NOT EXISTS idx_clients_xero ON clients(xero_contact_id);

CREATE INDEX IF NOT EXISTS idx_people_type ON people(type);
CREATE INDEX IF NOT EXISTS idx_people_client ON people(client_id);
CREATE INDEX IF NOT EXISTS idx_people_email ON people(email);

CREATE INDEX IF NOT EXISTS idx_projects_client ON projects(client_id);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_health ON projects(health);
CREATE INDEX IF NOT EXISTS idx_projects_asana ON projects(asana_project_id);

CREATE INDEX IF NOT EXISTS idx_items_status ON items(status);
CREATE INDEX IF NOT EXISTS idx_items_due ON items(due);
CREATE INDEX IF NOT EXISTS idx_items_client ON items(client_id);
CREATE INDEX IF NOT EXISTS idx_items_project ON items(project_id);
CREATE INDEX IF NOT EXISTS idx_items_owner ON items(owner);

CREATE INDEX IF NOT EXISTS idx_history_item ON item_history(item_id);
"""


def init_db() -> None:
    """Initialize database with schema. Safe to call multiple times."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with get_connection() as conn:
        conn.executescript(SCHEMA)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")

    log.info(f"Database initialized at {DB_PATH}")


@contextmanager
def get_connection():
    """Get database connection with auto-commit/rollback."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
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


def now_iso() -> str:
    """Current UTC time in ISO format."""
    return datetime.utcnow().isoformat() + "Z"


def db_exists() -> bool:
    """Check if database file exists."""
    return DB_PATH.exists()


def table_counts() -> dict:
    """Get row counts for all tables."""
    if not db_exists():
        return {}

    with get_connection() as conn:
        tables = ["clients", "people", "projects", "items", "item_history"]
        counts = {}
        for table in tables:
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
