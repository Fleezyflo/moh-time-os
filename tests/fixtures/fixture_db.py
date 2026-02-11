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
    client_id TEXT,
    client_name TEXT,
    amount REAL,
    currency TEXT DEFAULT 'AED',
    due_date TEXT,
    status TEXT,
    payment_date TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
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
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    assignee TEXT,
    assignee_id TEXT,
    project_id TEXT,
    due_date TEXT,
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
            INSERT INTO invoices (id, client_id, amount, currency, status, payment_date, due_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                invoice["id"],
                invoice["client_id"],
                invoice["amount"],
                invoice.get("currency", "AED"),
                invoice["status"],
                invoice.get("payment_date"),
                invoice.get("due_date")
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
            INSERT INTO tasks (id, title, status, assignee, assignee_id, project_id, due_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task["id"],
                task["title"],
                task.get("status", "pending"),
                task.get("assignee_id"),  # assignee column stores the ID
                task.get("assignee_id"),
                task.get("project_id"),
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
