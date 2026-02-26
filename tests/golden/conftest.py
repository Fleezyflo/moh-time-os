"""
Golden Test Configuration - DETERMINISTIC FIXTURE-BASED

Golden tests use a fixture database with pinned seed data, NOT the live database.
This ensures CI determinism and removes dependency on external systems.

Seed data: tests/fixtures/golden_seed.json
Fixture factory: tests/fixtures/fixture_db.py

GOLDEN EXPECTATIONS must match the seeded fixture data exactly.
Any change to seed data requires updating these expectations.
"""

from pathlib import Path

import pytest

from tests.fixtures.fixture_db import get_fixture_db_path

# Block access to live DB
LIVE_DB_PATH = Path(__file__).parent.parent.parent / "data" / "moh_time_os.db"

# =============================================================================
# GOLDEN EXPECTATIONS - DERIVED FROM tests/fixtures/golden_seed.json
# =============================================================================
# These values are deterministic because they come from pinned seed data.
# If you change golden_seed.json, update these values to match.

GOLDEN_EXPECTATIONS = {
    # Fixture: 5 projects with status in (execution, kickoff, delivery) - none completed/cancelled/archived
    "active_project_count": 5,
    # Fixture: 3 invoices with status in (sent, overdue) and payment_date IS NULL
    # inv-001: sent, no payment
    # inv-002: overdue, no payment
    # inv-003: sent, no payment
    # inv-004: paid (excluded)
    "unpaid_invoice_count": 3,
    # Fixture: sum of amounts for unpaid invoices = 5000 + 7500 + 2500 = 15000.00
    "total_valid_ar_aed": 15000.00,
    # Fixture: 4 commitments with status NOT IN (fulfilled, closed)
    # commit-001: open
    # commit-002: pending
    # commit-003: open
    # commit-004: in_progress
    # commit-005: fulfilled (excluded)
    "open_commitment_count": 4,
    # Fixture: 3 clients
    "client_count": 3,
    # Fixture: 3 distinct assignees with active tasks (status NOT IN done, completed, archived)
    # person-001, person-002, person-003 all have in_progress tasks
    "active_people_count": 3,
    # Fixture: 5 communications with received_at set
    "communication_count": 5,
}


@pytest.fixture
def golden():
    """Return golden expectations dict."""
    return GOLDEN_EXPECTATIONS


@pytest.fixture
def db_path(tmp_path):
    """
    Return path to a DETERMINISTIC fixture database.

    This fixture creates a fresh temp DB with pinned seed data for each test.
    Tests MUST NOT access the live data/moh_time_os.db.
    """
    return get_fixture_db_path(tmp_path)


@pytest.fixture(autouse=True)
def block_live_db_access(monkeypatch):
    """
    Guard that fails tests if they try to access the live database.

    This ensures golden tests remain deterministic and don't depend on
    user-local data or external system state.
    """
    import sqlite3

    original_connect = sqlite3.connect

    def guarded_connect(database, *args, **kwargs):
        if isinstance(database, str | Path):
            db_str = str(database)
            if "moh_time_os.db" in db_str and "fixture" not in db_str:
                # Allow if it's clearly a test/fixture path
                resolved = Path(database).resolve() if Path(database).exists() else None
                if resolved and resolved == LIVE_DB_PATH.resolve():
                    raise RuntimeError(
                        f"DETERMINISM VIOLATION: Test attempted to access live DB.\n"
                        f"Path: {database}\n"
                        "Golden tests must use fixture DB only."
                    )
        return original_connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", guarded_connect)
