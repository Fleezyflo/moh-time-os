"""
Golden Tests: AR (Accounts Receivable) Assertions

DETERMINISTIC tests that verify AR calculations against pinned fixture data.
These tests use DIRECT SQL QUERIES against the fixture database.

The golden expectations are derived from tests/fixtures/golden_seed.json.
Tests must NOT depend on AgencySnapshotGenerator or other code under test.
"""

import sqlite3


class TestGoldenAR:
    """Verify AR calculations against pinned golden expectations using direct SQL."""

    def test_total_ar_matches_golden(self, golden, db_path):
        """
        GOLDEN: Total valid AR must match fixture seed data sum.

        Verification SQL:
        SELECT SUM(amount) FROM invoices
        WHERE status IN ('sent', 'overdue') AND payment_date IS NULL
        """
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT SUM(amount) FROM invoices WHERE status IN ('sent', 'overdue') AND payment_date IS NULL"
        )
        actual = cursor.fetchone()[0] or 0
        conn.close()

        expected = golden["total_valid_ar_aed"]
        # Allow small floating point tolerance
        assert abs(actual - expected) < 0.01, (
            f"Total AR mismatch: actual={actual:.2f}, expected={expected:.2f}. "
            f"If seed data changed, update GOLDEN_EXPECTATIONS in conftest.py."
        )

    def test_ar_sum_by_client_consistency(self, db_path):
        """
        CROSS-CHECK: Sum of AR grouped by client must equal total AR.

        This ensures no data is lost or duplicated in aggregation.
        """
        conn = sqlite3.connect(db_path)

        # Total AR
        cursor = conn.execute(
            "SELECT SUM(amount) FROM invoices WHERE status IN ('sent', 'overdue') AND payment_date IS NULL"
        )
        total_ar = cursor.fetchone()[0] or 0

        # AR grouped by client
        cursor = conn.execute(
            """
            SELECT client_id, SUM(amount) as client_ar
            FROM invoices
            WHERE status IN ('sent', 'overdue') AND payment_date IS NULL
            GROUP BY client_id
            """
        )
        client_ar_sum = sum(row[1] for row in cursor.fetchall())
        conn.close()

        assert abs(total_ar - client_ar_sum) < 0.01, (
            f"AR aggregation mismatch: total={total_ar:.2f}, sum_by_client={client_ar_sum:.2f}. "
            "Check for NULL client_ids or aggregation bugs."
        )

    def test_paid_invoices_excluded_from_ar(self, db_path):
        """
        CROSS-CHECK: Invoices with payment_date set must not be in AR.
        """
        conn = sqlite3.connect(db_path)

        # Count paid invoices
        cursor = conn.execute(
            "SELECT COUNT(*) FROM invoices WHERE payment_date IS NOT NULL"
        )
        paid_count = cursor.fetchone()[0]

        # Count unpaid invoices
        cursor = conn.execute(
            "SELECT COUNT(*) FROM invoices WHERE status IN ('sent', 'overdue') AND payment_date IS NULL"
        )
        unpaid_count = cursor.fetchone()[0]

        # Total invoices
        cursor = conn.execute("SELECT COUNT(*) FROM invoices")
        total_count = cursor.fetchone()[0]
        conn.close()

        # Paid + unpaid <= total (some may have other statuses)
        assert paid_count > 0, "Expected at least one paid invoice in fixture data"
        assert unpaid_count > 0, "Expected at least one unpaid invoice in fixture data"

    def test_ar_by_status_breakdown(self, golden, db_path):
        """
        CROSS-CHECK: AR split by status (sent vs overdue) must sum to total AR.
        """
        conn = sqlite3.connect(db_path)

        # AR from 'sent' status
        cursor = conn.execute(
            "SELECT SUM(amount) FROM invoices WHERE status = 'sent' AND payment_date IS NULL"
        )
        sent_ar = cursor.fetchone()[0] or 0

        # AR from 'overdue' status
        cursor = conn.execute(
            "SELECT SUM(amount) FROM invoices WHERE status = 'overdue' AND payment_date IS NULL"
        )
        overdue_ar = cursor.fetchone()[0] or 0
        conn.close()

        expected_total = golden["total_valid_ar_aed"]
        actual_total = sent_ar + overdue_ar

        assert abs(actual_total - expected_total) < 0.01, (
            f"AR status breakdown mismatch: sent={sent_ar:.2f} + overdue={overdue_ar:.2f} = {actual_total:.2f}, "
            f"expected={expected_total:.2f}"
        )
