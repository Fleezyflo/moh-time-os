"""
Golden Tests: AR Assertions

These tests verify AR calculations against hand-verified database values.
Cross-check: values computed two different ways must match.
"""

import sqlite3


class TestGoldenAR:
    """Verify AR calculations match golden expectations."""

    def test_total_ar_matches_golden(self, golden, db_path):
        """
        GOLDEN: Total valid AR must match hand-verified sum.

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
            f"Total AR changed: actual={actual:.2f}, golden={expected:.2f}. "
            f"If intentional, update GOLDEN_EXPECTATIONS with PR justification."
        )

    def test_ar_cross_check_invoice_sum_vs_debtor_sum(self, db_path):
        """
        GOLDEN CROSS-CHECK: AR computed from invoices must equal AR from debtors.

        This ensures the aggregation logic doesn't lose or duplicate amounts.
        """
        from lib.agency_snapshot.generator import AgencySnapshotGenerator

        gen = AgencySnapshotGenerator(db_path=db_path)
        normalized = gen._build_normalized_data()

        # Path 1: Sum from normalized invoices
        invoice_total = sum(inv.get("amount", 0) for inv in normalized.invoices)

        # Path 2: Sum from cash_ar section
        cash_ar = gen._build_cash_ar_minimal(normalized)
        debtor_total = sum(
            d.get("total_valid_ar", 0) for d in cash_ar.get("debtors", [])
        )

        # Both paths must agree
        assert (
            abs(invoice_total - debtor_total) < 0.01
        ), f"AR cross-check failed: invoices={invoice_total:.2f}, debtors={debtor_total:.2f}"

    def test_ar_tiles_match_debtors(self, db_path):
        """
        GOLDEN CROSS-CHECK: tiles.valid_ar must equal sum of debtors.
        """
        from lib.agency_snapshot.generator import AgencySnapshotGenerator

        gen = AgencySnapshotGenerator(db_path=db_path)
        normalized = gen._build_normalized_data()
        cash_ar = gen._build_cash_ar_minimal(normalized)

        # From tiles
        tiles_ar = sum(cash_ar.get("tiles", {}).get("valid_ar", {}).values())

        # From debtors
        debtors_ar = sum(d.get("total_valid_ar", 0) for d in cash_ar.get("debtors", []))

        assert (
            abs(tiles_ar - debtors_ar) < 0.01
        ), f"AR tiles/debtors mismatch: tiles={tiles_ar:.2f}, debtors={debtors_ar:.2f}"
