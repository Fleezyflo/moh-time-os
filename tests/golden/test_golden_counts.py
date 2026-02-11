"""
Golden Tests: Count Assertions

DETERMINISTIC tests that verify counts against pinned fixture data.
These tests use DIRECT SQL QUERIES against the fixture database.

The golden expectations are derived from tests/fixtures/golden_seed.json.
Tests must NOT depend on AgencySnapshotGenerator or other code under test.
"""

import sqlite3


class TestGoldenCounts:
    """Verify counts against pinned golden expectations using direct SQL."""

    def test_project_count_matches_golden(self, golden, db_path):
        """
        GOLDEN: Active project count must match fixture seed data.

        Verification SQL:
        SELECT COUNT(*) FROM projects WHERE status NOT IN ('completed', 'cancelled', 'archived')
        """
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM projects WHERE status NOT IN ('completed', 'cancelled', 'archived')"
        )
        actual = cursor.fetchone()[0]
        conn.close()

        expected = golden["active_project_count"]
        assert actual == expected, (
            f"Project count mismatch: actual={actual}, expected={expected}. "
            f"If seed data changed, update GOLDEN_EXPECTATIONS in conftest.py."
        )

    def test_unpaid_invoice_count_matches_golden(self, golden, db_path):
        """
        GOLDEN: Unpaid invoice count must match fixture seed data.

        Verification SQL:
        SELECT COUNT(*) FROM invoices WHERE status IN ('sent', 'overdue') AND payment_date IS NULL
        """
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM invoices WHERE status IN ('sent', 'overdue') AND payment_date IS NULL"
        )
        actual = cursor.fetchone()[0]
        conn.close()

        expected = golden["unpaid_invoice_count"]
        assert actual == expected, (
            f"Unpaid invoice count mismatch: actual={actual}, expected={expected}. "
            f"If seed data changed, update GOLDEN_EXPECTATIONS in conftest.py."
        )

    def test_commitment_count_matches_golden(self, golden, db_path):
        """
        GOLDEN: Open commitment count must match fixture seed data.

        Verification SQL:
        SELECT COUNT(*) FROM commitments WHERE status NOT IN ('fulfilled', 'closed')
        """
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM commitments WHERE status NOT IN ('fulfilled', 'closed')"
        )
        actual = cursor.fetchone()[0]
        conn.close()

        expected = golden["open_commitment_count"]
        assert actual == expected, (
            f"Commitment count mismatch: actual={actual}, expected={expected}. "
            f"If seed data changed, update GOLDEN_EXPECTATIONS in conftest.py."
        )

    def test_communication_count_matches_golden(self, golden, db_path):
        """
        GOLDEN: Communication count must match fixture seed data.

        Verification SQL:
        SELECT COUNT(*) FROM communications WHERE received_at IS NOT NULL OR created_at IS NOT NULL
        """
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM communications WHERE received_at IS NOT NULL OR created_at IS NOT NULL"
        )
        actual = cursor.fetchone()[0]
        conn.close()

        expected = golden["communication_count"]
        assert actual == expected, (
            f"Communication count mismatch: actual={actual}, expected={expected}. "
            f"If seed data changed, update GOLDEN_EXPECTATIONS in conftest.py."
        )

    def test_client_count_matches_golden(self, golden, db_path):
        """
        GOLDEN: Client count must match fixture seed data.

        Verification SQL:
        SELECT COUNT(*) FROM clients
        """
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT COUNT(*) FROM clients")
        actual = cursor.fetchone()[0]
        conn.close()

        expected = golden["client_count"]
        assert actual == expected, (
            f"Client count mismatch: actual={actual}, expected={expected}. "
            f"If seed data changed, update GOLDEN_EXPECTATIONS in conftest.py."
        )

    def test_active_people_count_matches_golden(self, golden, db_path):
        """
        GOLDEN: Active people (with non-done tasks) must match fixture seed data.

        Verification SQL:
        SELECT COUNT(DISTINCT assignee) FROM tasks
        WHERE assignee IS NOT NULL AND status NOT IN ('done', 'completed', 'archived')
        """
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            """
            SELECT COUNT(DISTINCT assignee) FROM tasks
            WHERE assignee IS NOT NULL AND status NOT IN ('done', 'completed', 'archived')
            """
        )
        actual = cursor.fetchone()[0]
        conn.close()

        expected = golden["active_people_count"]
        assert actual == expected, (
            f"Active people count mismatch: actual={actual}, expected={expected}. "
            f"If seed data changed, update GOLDEN_EXPECTATIONS in conftest.py."
        )
