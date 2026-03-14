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

from lib import schema_engine

REPO_ROOT = Path(__file__).parent.parent.parent
SEED_PATH = Path(__file__).parent / "golden_seed.json"

# Guard: Block access to live DB path
# Use string to avoid triggering Path.resolve() which calls os.lstat
LIVE_DB_PATH = REPO_ROOT / "data" / "moh_time_os.db"
_LIVE_DB_STR = str(LIVE_DB_PATH)


def guard_no_live_db(db_path: str | Path) -> None:
    """Fail loudly if tests try to access the live database."""
    # Compare as strings to avoid Path.resolve() which triggers os.lstat
    path_str = str(db_path)
    # Match various forms of live DB path
    if (
        "data/moh_time_os.db" in path_str
        or ".moh_time_os/data/moh_time_os.db" in path_str
        or path_str == _LIVE_DB_STR
    ):
        raise RuntimeError(
            f"DETERMINISM VIOLATION: Test attempted to access live DB at {db_path}.\n"
            "Golden tests must use fixture DB only. See tests/fixtures/fixture_db.py."
        )


def load_seed_data() -> dict[str, Any]:
    """Load pinned seed data from golden_seed.json."""
    if not SEED_PATH.exists():
        raise FileNotFoundError(f"Seed data not found: {SEED_PATH}")
    return json.loads(SEED_PATH.read_text())


# Cross-entity views are now canonical in lib/schema.py VIEWS dict.
# schema_engine.create_fresh() creates them automatically.


def create_fixture_db(db_path: str | Path = ":memory:") -> sqlite3.Connection:
    """
    Create a fixture database with schema + seeded data.

    Schema comes from schema_engine.create_fresh() — the same single source
    of truth used by lib/db.py for the live database.  Views and seed data
    are fixture-specific.

    Args:
        db_path: Path to DB file, or ":memory:" for in-memory DB.

    Returns:
        sqlite3.Connection to the initialized DB.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Phase 1: Create all tables + indexes from the single source of truth
    schema_engine.create_fresh(conn)

    # Phase 2: Enable maintenance mode (allows writes without write_context)
    conn.execute("INSERT OR IGNORE INTO maintenance_mode_v1 (id, flag) VALUES (1, 1)")

    # Phase 3: Views are now created by schema_engine.create_fresh() via schema.VIEWS

    # Phase 4: Seed data
    seed = load_seed_data()
    _seed_tables(conn, seed)

    conn.commit()
    return conn


def _seed_tables(conn: sqlite3.Connection, seed: dict[str, Any]) -> None:
    """Insert seed data into tables."""

    # Build person ID -> name lookup for task assignee resolution
    person_id_to_name = {person["id"]: person["name"] for person in seed.get("people", [])}

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
                client.get("health_status", "good"),
            ),
        )

    # Brands
    for brand in seed.get("brands", []):
        conn.execute(
            """
            INSERT INTO brands (id, client_id, name)
            VALUES (?, ?, ?)
            """,
            (brand["id"], brand["client_id"], brand["name"]),
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
                project.get("health_status", "on_track"),
            ),
        )

    # Invoices
    for invoice in seed.get("invoices", []):
        pay_date = invoice.get("payment_date")
        conn.execute(
            """
            INSERT INTO invoices
                (id, client_id, amount, currency, status,
                 paid_date, payment_date, due_date, issue_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                invoice["id"],
                invoice["client_id"],
                invoice["amount"],
                invoice.get("currency", "AED"),
                invoice["status"],
                pay_date,
                pay_date,
                invoice.get("due_date"),
                invoice.get("issue_date"),
            ),
        )

    # Commitments
    for commitment in seed.get("commitments", []):
        conn.execute(
            """
            INSERT INTO commitments
                (id, source_type, source_id, text, type,
                 client_id, status, deadline)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                commitment["id"],
                "communication",
                commitment.get("client_id", "unknown"),
                commitment["description"],
                "delivery",
                commitment.get("client_id"),
                commitment["status"],
                commitment.get("due_date"),
            ),
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
                "internal" if person.get("person_type") == "team" else "external",
            ),
        )

    # Tasks
    # Note: assignee column stores the person's NAME (for v_person_load_profile view
    # which matches LOWER(t.assignee) = LOWER(ppl.name)), while assignee_id stores the ID
    for task in seed.get("tasks", []):
        assignee_id = task.get("assignee_id")
        assignee_name = person_id_to_name.get(assignee_id) if assignee_id else None
        conn.execute(
            """
            INSERT INTO tasks (id, title, status, assignee, assignee_id, project_id, client_id, due_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task["id"],
                task["title"],
                task.get("status", "pending"),
                assignee_name,  # assignee column stores the NAME for view matching
                assignee_id,
                task.get("project_id"),
                task.get("client_id"),
                task.get("due_date"),
            ),
        )

    # Communications
    for comm in seed.get("communications", []):
        conn.execute(
            """
            INSERT INTO communications (id, subject, received_at)
            VALUES (?, ?, ?)
            """,
            (comm["id"], comm.get("subject", ""), comm.get("received_at")),
        )

    # Artifacts (for communication-client links)
    for artifact in seed.get("artifacts", []):
        conn.execute(
            """
            INSERT INTO artifacts (artifact_id, type, source, occurred_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                artifact["artifact_id"],
                artifact["type"],
                artifact.get("source"),
                artifact.get("occurred_at"),
            ),
        )

    # Entity Links (for cross-entity relationships)
    for link in seed.get("entity_links", []):
        conn.execute(
            """
            INSERT INTO entity_links (from_artifact_id, to_entity_type, to_entity_id, confidence, method)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                link["from_artifact_id"],
                link["to_entity_type"],
                link["to_entity_id"],
                link.get("confidence", 1.0),
                link.get("method", "fixture"),
            ),
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
