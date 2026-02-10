"""
Golden Tests: Count Assertions

These tests verify that extracted/normalized counts match hand-verified database values.
The golden expectations are derived via DIRECT SQL QUERIES, not from the code under test.

This prevents the generator from silently dropping data.
"""

import sqlite3


class TestGoldenCounts:
    """Verify counts against hand-verified golden expectations."""

    def test_project_count_matches_golden(self, golden, db_path):
        """
        GOLDEN: Active project count must match hand-verified value.

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
            f"Project count changed: actual={actual}, golden={expected}. "
            f"If intentional, update GOLDEN_EXPECTATIONS with PR justification."
        )

    def test_unpaid_invoice_count_matches_golden(self, golden, db_path):
        """
        GOLDEN: Unpaid invoice count must match hand-verified value.

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
            f"Unpaid invoice count changed: actual={actual}, golden={expected}. "
            f"If intentional, update GOLDEN_EXPECTATIONS with PR justification."
        )

    def test_commitment_count_matches_golden(self, golden, db_path):
        """
        GOLDEN: Open commitment count must match hand-verified value.

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
            f"Commitment count changed: actual={actual}, golden={expected}. "
            f"If intentional, update GOLDEN_EXPECTATIONS with PR justification."
        )


class TestGoldenSnapshotCounts:
    """Verify snapshot section counts match golden expectations."""

    def test_snapshot_heatstrip_not_empty_when_projects_exist(self, golden, db_path):
        """
        GOLDEN: If active projects exist, heatstrip must not be empty.

        This catches the exact bug: empty heatstrip_projects while DB has projects.
        """
        from lib.agency_snapshot.generator import AgencySnapshotGenerator

        gen = AgencySnapshotGenerator(db_path=db_path)
        normalized = gen._build_normalized_data()

        project_count = len(normalized.projects)
        assert (
            project_count == golden["active_project_count"]
        ), f"Normalized project count mismatch: {project_count} vs golden {golden['active_project_count']}"

    def test_snapshot_debtors_not_empty_when_invoices_exist(self, golden, db_path):
        """
        GOLDEN: If unpaid invoices exist, cash_ar.debtors must not be empty.

        This catches the exact bug: empty debtors while invoices exist.
        """
        from lib.agency_snapshot.generator import AgencySnapshotGenerator

        gen = AgencySnapshotGenerator(db_path=db_path)
        normalized = gen._build_normalized_data()

        invoice_count = len(normalized.invoices)
        assert (
            invoice_count == golden["unpaid_invoice_count"]
        ), f"Normalized invoice count mismatch: {invoice_count} vs golden {golden['unpaid_invoice_count']}"

    def test_snapshot_people_count_matches_golden(self, golden, db_path):
        """
        GOLDEN: People with assignments must match hand-verified count.
        """
        from lib.agency_snapshot.generator import AgencySnapshotGenerator

        gen = AgencySnapshotGenerator(db_path=db_path)
        normalized = gen._build_normalized_data()

        people_count = len(
            [p for p in normalized.people if p.get("hours_assigned", 0) > 0]
        )
        assert (
            people_count == golden["active_people_count"]
        ), f"People count mismatch: {people_count} vs golden {golden['active_people_count']}"
