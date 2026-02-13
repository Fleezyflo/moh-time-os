"""
Fixture Database Factory for Deterministic Golden Tests.

Creates a temp SQLite DB with schema matching the live DB + seeded data.
Golden tests MUST use this fixture, never the live data/moh_time_os.db.

Design:
- Schema is created inline (matches live DB structure)
- Seed data is from tests/fixtures/golden_seed.json (pinned, committed)
- All counts/values are deterministic and match GOLDEN_EXPECTATIONS
"""

import json
import sqlite3
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).parent.parent.parent
SEED_PATH = Path(__file__).parent / "golden_seed.json"

# Guard: Block access to live DB path
LIVE_DB_PATH = REPO_ROOT / "data" / "moh_time_os.db"


def guard_no_live_db(db_path: str | Path) -> None:
    """Fail loudly if tests try to access the live database."""
    resolved = Path(db_path).resolve()
    if resolved == LIVE_DB_PATH.resolve():
        raise RuntimeError(
            f"DETERMINISM VIOLATION: Test attempted to access live DB at {LIVE_DB_PATH}.\n"
            "Golden tests must use fixture DB only. See tests/fixtures/fixture_db.py."
        )


def load_seed_data() -> dict[str, Any]:
    """Load pinned seed data from golden_seed.json."""
    if not SEED_PATH.exists():
        raise FileNotFoundError(f"Seed data not found: {SEED_PATH}")
    return json.loads(SEED_PATH.read_text())


# Schema DDL matching the actual live DB structure
FIXTURE_SCHEMA = """
-- Clients
CREATE TABLE IF NOT EXISTS clients (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_normalized TEXT NOT NULL,
    tier TEXT,
    type TEXT DEFAULT 'agency_client',
    relationship_health TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Brands
CREATE TABLE IF NOT EXISTS brands (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    client_id TEXT REFERENCES clients(id),
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Projects
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_normalized TEXT NOT NULL,
    client_id TEXT REFERENCES clients(id),
    brand_id TEXT,
    status TEXT DEFAULT 'active',
    health TEXT DEFAULT 'on_track',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Invoices
CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL DEFAULT 'fixture',
    external_id TEXT,
    client_id TEXT,
    client_name TEXT,
    amount REAL,
    currency TEXT DEFAULT 'AED',
    issue_date TEXT,
    due_date TEXT,
    status TEXT,
    aging_bucket TEXT,
    payment_date TEXT,
    source_id TEXT,
    total REAL,
    issued_at TEXT,
    due_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Issues (legacy)
CREATE TABLE IF NOT EXISTS issues (
    issue_id TEXT PRIMARY KEY,
    source_proposal_id TEXT NOT NULL,
    issue_type TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'open',
    primary_ref_type TEXT NOT NULL,
    primary_ref_id TEXT NOT NULL,
    scope_refs TEXT NOT NULL,
    headline TEXT NOT NULL,
    priority INTEGER NOT NULL,
    resolution_criteria TEXT NOT NULL,
    opened_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_activity_at TEXT NOT NULL DEFAULT (datetime('now')),
    closed_at TEXT,
    closed_reason TEXT,
    visibility TEXT NOT NULL DEFAULT 'tagged_only'
);
CREATE INDEX IF NOT EXISTS idx_issues_state ON issues(state);
CREATE INDEX IF NOT EXISTS idx_issues_priority ON issues(priority);

-- Issues v29 (current)
CREATE TABLE IF NOT EXISTS issues_v29 (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'detected',
    severity TEXT NOT NULL,
    client_id TEXT NOT NULL,
    brand_id TEXT,
    engagement_id TEXT,
    title TEXT NOT NULL,
    evidence TEXT,
    evidence_version TEXT DEFAULT 'v1',
    aggregation_key TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    snoozed_until TEXT,
    snoozed_by TEXT,
    snoozed_at TEXT,
    snooze_reason TEXT,
    tagged_by_user_id TEXT,
    tagged_at TEXT,
    assigned_to TEXT,
    assigned_at TEXT,
    assigned_by TEXT,
    suppressed INTEGER NOT NULL DEFAULT 0,
    suppressed_at TEXT,
    suppressed_by TEXT,
    escalated INTEGER NOT NULL DEFAULT 0,
    escalated_at TEXT,
    escalated_by TEXT,
    regression_watch_until TEXT,
    closed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_issues_v29_state ON issues_v29(state);
CREATE INDEX IF NOT EXISTS idx_issues_v29_client ON issues_v29(client_id);

-- Safety tables (required for triggers, but we skip triggers in test fixture)
CREATE TABLE IF NOT EXISTS write_context_v1 (
    id INTEGER PRIMARY KEY,
    request_id TEXT,
    actor TEXT,
    source TEXT,
    git_sha TEXT
);

CREATE TABLE IF NOT EXISTS maintenance_mode_v1 (
    id INTEGER PRIMARY KEY,
    flag INTEGER DEFAULT 0
);

-- Initialize maintenance mode for fixture (allows writes without context)
INSERT OR IGNORE INTO maintenance_mode_v1 (id, flag) VALUES (1, 1);

-- Inbox Items v29
CREATE TABLE IF NOT EXISTS inbox_items_v29 (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'proposed',
    severity TEXT NOT NULL,
    proposed_at TEXT NOT NULL,
    last_refreshed_at TEXT NOT NULL,
    read_at TEXT,
    resurfaced_at TEXT,
    resolved_at TEXT,
    snooze_until TEXT,
    snoozed_by TEXT,
    snoozed_at TEXT,
    snooze_reason TEXT,
    dismissed_by TEXT,
    dismissed_at TEXT,
    dismiss_reason TEXT,
    suppression_key TEXT,
    underlying_issue_id TEXT,
    underlying_signal_id TEXT,
    resolved_issue_id TEXT,
    title TEXT NOT NULL,
    client_id TEXT,
    brand_id TEXT,
    engagement_id TEXT,
    evidence TEXT,
    evidence_version TEXT DEFAULT 'v1',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_inbox_items_v29_state ON inbox_items_v29(state);
CREATE INDEX IF NOT EXISTS idx_inbox_items_v29_type ON inbox_items_v29(type);

-- Inbox Suppression Rules v29
CREATE TABLE IF NOT EXISTS inbox_suppression_rules_v29 (
    id TEXT PRIMARY KEY,
    suppression_key TEXT NOT NULL UNIQUE,
    item_type TEXT NOT NULL,
    scope_client_id TEXT,
    scope_engagement_id TEXT,
    scope_source TEXT,
    scope_rule TEXT,
    reason TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

-- Signals v29 (as table, not view, for fixture)
CREATE TABLE IF NOT EXISTS signals_v29 (
    id TEXT PRIMARY KEY,
    source TEXT,
    source_id TEXT,
    client_id TEXT,
    engagement_id TEXT,
    sentiment TEXT,
    signal_type TEXT,
    summary TEXT,
    observed_at TEXT,
    ingested_at TEXT,
    evidence TEXT,
    dismissed_at TEXT,
    dismissed_by TEXT,
    analysis_provider TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Signals (legacy, for view compatibility)
CREATE TABLE IF NOT EXISTS signals (
    signal_id TEXT PRIMARY KEY,
    detector_id TEXT,
    signal_type TEXT NOT NULL,
    entity_ref_type TEXT,
    entity_ref_id TEXT,
    value TEXT,
    detected_at TEXT,
    resolved_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Commitments
CREATE TABLE IF NOT EXISTS commitments (
    commitment_id TEXT PRIMARY KEY,
    scope_ref_type TEXT NOT NULL DEFAULT 'client',
    scope_ref_id TEXT NOT NULL,
    committed_by_type TEXT NOT NULL DEFAULT 'team',
    committed_by_id TEXT NOT NULL DEFAULT 'system',
    commitment_text TEXT NOT NULL,
    due_at TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- People
CREATE TABLE IF NOT EXISTS people (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_normalized TEXT NOT NULL,
    email TEXT,
    type TEXT DEFAULT 'internal',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Tasks
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL DEFAULT 'fixture',
    source_id TEXT,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    priority INTEGER DEFAULT 50,
    due_date TEXT,
    due_time TEXT,
    assignee TEXT,
    assignee_raw TEXT,
    assignee_id TEXT,
    project TEXT,
    project_id TEXT,
    client_id TEXT,
    brand_id TEXT,
    tags TEXT,
    dependencies TEXT,
    blockers TEXT,
    context TEXT,
    notes TEXT,
    description TEXT DEFAULT '',
    priority_reasons TEXT,
    project_link_status TEXT DEFAULT 'unlinked',
    client_link_status TEXT DEFAULT 'unlinked',
    completed_at TEXT,
    synced_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Communications
CREATE TABLE IF NOT EXISTS communications (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL DEFAULT 'fixture',
    thread_id TEXT,
    subject TEXT,
    received_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def create_fixture_db(db_path: str | Path = ":memory:") -> sqlite3.Connection:
    """
    Create a fixture database with schema + seeded data.

    Args:
        db_path: Path to DB file, or ":memory:" for in-memory DB.

    Returns:
        sqlite3.Connection to the initialized DB.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Apply schema
    conn.executescript(FIXTURE_SCHEMA)

    # Seed data
    seed = load_seed_data()
    _seed_tables(conn, seed)

    conn.commit()
    return conn


def _seed_tables(conn: sqlite3.Connection, seed: dict[str, Any]) -> None:
    """Insert seed data into tables."""

    # Clients
    for client in seed.get("clients", []):
        conn.execute(
            """
            INSERT INTO clients (id, name, name_normalized, tier, relationship_health)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                client["id"],
                client["name"],
                client["name"].lower(),
                client.get("tier", "B"),
                client.get("health_status", "good")
            )
        )

    # Brands
    for brand in seed.get("brands", []):
        conn.execute(
            """
            INSERT INTO brands (id, client_id, name)
            VALUES (?, ?, ?)
            """,
            (brand["id"], brand["client_id"], brand["name"])
        )

    # Projects
    for project in seed.get("projects", []):
        conn.execute(
            """
            INSERT INTO projects (id, name, name_normalized, client_id, brand_id, status, health)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project["id"],
                project["name"],
                project["name"].lower(),
                project["client_id"],
                project["brand_id"],
                project.get("status", "active"),
                project.get("health_status", "on_track")
            )
        )

    # Invoices
    for invoice in seed.get("invoices", []):
        conn.execute(
            """
            INSERT INTO invoices (id, client_id, amount, currency, status, payment_date, due_date, issue_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                invoice["id"],
                invoice["client_id"],
                invoice["amount"],
                invoice.get("currency", "AED"),
                invoice["status"],
                invoice.get("payment_date"),
                invoice.get("due_date"),
                invoice.get("issue_date")
            )
        )

    # Commitments
    for commitment in seed.get("commitments", []):
        conn.execute(
            """
            INSERT INTO commitments (commitment_id, scope_ref_type, scope_ref_id, committed_by_type, committed_by_id, commitment_text, status, due_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                commitment["id"],
                "client",
                commitment.get("client_id", "unknown"),
                "team",
                "system",
                commitment["description"],
                commitment["status"],
                commitment.get("due_date")
            )
        )

    # People
    for person in seed.get("people", []):
        conn.execute(
            """
            INSERT INTO people (id, name, name_normalized, email, type)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                person["id"],
                person["name"],
                person["name"].lower(),
                person.get("email"),
                "internal" if person.get("person_type") == "team" else "external"
            )
        )

    # Tasks
    for task in seed.get("tasks", []):
        conn.execute(
            """
            INSERT INTO tasks (id, title, status, assignee, assignee_id, project_id, client_id, due_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task["id"],
                task["title"],
                task.get("status", "pending"),
                task.get("assignee_id"),  # assignee column stores the ID
                task.get("assignee_id"),
                task.get("project_id"),
                task.get("client_id"),
                task.get("due_date")
            )
        )

    # Communications
    for comm in seed.get("communications", []):
        conn.execute(
            """
            INSERT INTO communications (id, subject, received_at)
            VALUES (?, ?, ?)
            """,
            (
                comm["id"],
                comm.get("subject", ""),
                comm.get("received_at")
            )
        )


def get_fixture_db_path(tmp_path: Path) -> Path:
    """
    Create a fixture DB file in the given tmp_path.

    Use this with pytest's tmp_path fixture:
        db_path = get_fixture_db_path(tmp_path)
    """
    db_path = tmp_path / "fixture_golden.db"
    conn = create_fixture_db(db_path)
    conn.close()
    return db_path
