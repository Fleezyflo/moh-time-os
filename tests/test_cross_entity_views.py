"""
Cross-Entity Views Tests — Task 2.3

Tests for the cross-entity SQL views created to enable operational intelligence queries.
Uses fixture DB (not live DB) for deterministic testing.
"""

import sqlite3
from pathlib import Path

import pytest


@pytest.fixture
def db_conn(integration_db_path):
    """Get a read-only database connection to fixture DB."""
    conn = sqlite3.connect(f"file:{integration_db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


class TestViewsExist:
    """Test that all cross-entity views exist and are queryable."""

    EXPECTED_VIEWS = [
        "v_task_with_client",
        "v_client_operational_profile",
        "v_project_operational_state",
        "v_person_load_profile",
        "v_communication_client_link",
        "v_invoice_client_project",
    ]

    def test_all_views_exist(self, db_conn):
        """All expected views exist in the database."""
        cursor = db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='view' AND name LIKE 'v_%'"
        )
        actual_views = {row["name"] for row in cursor.fetchall()}

        for view in self.EXPECTED_VIEWS:
            assert view in actual_views, f"View {view} not found"

    @pytest.mark.parametrize("view_name", EXPECTED_VIEWS)
    def test_view_is_queryable(self, db_conn, view_name):
        """Each view can be queried without errors."""
        cursor = db_conn.execute(f"SELECT COUNT(*) as cnt FROM {view_name}")
        result = cursor.fetchone()
        assert result["cnt"] >= 0, f"View {view_name} returned invalid count"


class TestTaskWithClientView:
    """Tests for v_task_with_client view."""

    def test_returns_data(self, db_conn):
        """View returns task data."""
        cursor = db_conn.execute("SELECT COUNT(*) as cnt FROM v_task_with_client")
        assert cursor.fetchone()["cnt"] > 0

    def test_has_expected_columns(self, db_conn):
        """View has all expected columns."""
        cursor = db_conn.execute("SELECT * FROM v_task_with_client LIMIT 1")
        row = cursor.fetchone()
        assert row is not None

        expected_cols = ["task_id", "task_title", "project_id", "client_id", "client_name"]
        for col in expected_cols:
            assert col in row.keys(), f"Missing column: {col}"

    def test_client_linkage_rate(self, db_conn):
        """At least 50% of tasks should be linked to a client (via project)."""
        cursor = db_conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN client_id IS NOT NULL THEN 1 ELSE 0 END) as with_client
            FROM v_task_with_client
        """)
        row = cursor.fetchone()
        linkage_rate = row["with_client"] / row["total"] if row["total"] > 0 else 0
        assert linkage_rate >= 0.5, f"Client linkage rate too low: {linkage_rate:.1%}"


class TestClientOperationalProfileView:
    """Tests for v_client_operational_profile view."""

    def test_returns_data(self, db_conn):
        """View returns client data."""
        cursor = db_conn.execute("SELECT COUNT(*) as cnt FROM v_client_operational_profile")
        assert cursor.fetchone()["cnt"] > 0

    def test_has_financial_metrics(self, db_conn):
        """View has financial metrics columns."""
        cursor = db_conn.execute("SELECT * FROM v_client_operational_profile LIMIT 1")
        row = cursor.fetchone()

        financial_cols = ["total_invoiced", "total_paid", "total_outstanding"]
        for col in financial_cols:
            assert col in row.keys(), f"Missing financial column: {col}"

    def test_financial_metrics_non_negative(self, db_conn):
        """Financial metrics should be non-negative."""
        cursor = db_conn.execute("""
            SELECT MIN(total_invoiced) as min_inv, MIN(total_paid) as min_paid
            FROM v_client_operational_profile
        """)
        row = cursor.fetchone()
        assert row["min_inv"] >= 0, "total_invoiced has negative values"
        assert row["min_paid"] >= 0, "total_paid has negative values"


class TestProjectOperationalStateView:
    """Tests for v_project_operational_state view."""

    def test_returns_data(self, db_conn):
        """View returns project data."""
        cursor = db_conn.execute("SELECT COUNT(*) as cnt FROM v_project_operational_state")
        assert cursor.fetchone()["cnt"] > 0

    def test_completion_rate_in_range(self, db_conn):
        """Completion rate should be between 0 and 100."""
        cursor = db_conn.execute("""
            SELECT MIN(completion_rate_pct) as min_rate, MAX(completion_rate_pct) as max_rate
            FROM v_project_operational_state
        """)
        row = cursor.fetchone()
        assert row["min_rate"] >= 0, "completion_rate_pct below 0"
        assert row["max_rate"] <= 100, "completion_rate_pct above 100"

    def test_task_counts_consistent(self, db_conn):
        """open_tasks + completed_tasks should equal total_tasks."""
        cursor = db_conn.execute("""
            SELECT COUNT(*) as inconsistent
            FROM v_project_operational_state
            WHERE open_tasks + completed_tasks != total_tasks
        """)
        assert cursor.fetchone()["inconsistent"] == 0


class TestPersonLoadProfileView:
    """Tests for v_person_load_profile view."""

    def test_returns_data(self, db_conn):
        """View returns person data."""
        cursor = db_conn.execute("SELECT COUNT(*) as cnt FROM v_person_load_profile")
        assert cursor.fetchone()["cnt"] > 0

    def test_has_email_column(self, db_conn):
        """View has person_email column."""
        cursor = db_conn.execute("SELECT person_email FROM v_person_load_profile LIMIT 1")
        row = cursor.fetchone()
        assert "person_email" in row.keys()


class TestCommunicationClientLinkView:
    """Tests for v_communication_client_link view."""

    def test_returns_data(self, db_conn):
        """View returns communication-client links."""
        cursor = db_conn.execute("SELECT COUNT(*) as cnt FROM v_communication_client_link")
        assert cursor.fetchone()["cnt"] > 0

    def test_artifact_types_present(self, db_conn):
        """View contains expected artifact types."""
        cursor = db_conn.execute(
            "SELECT DISTINCT artifact_type FROM v_communication_client_link"
        )
        types = {row["artifact_type"] for row in cursor.fetchall()}
        assert "message" in types, "No message artifacts linked to clients"

    def test_confidence_in_range(self, db_conn):
        """Link confidence should be between 0 and 1."""
        cursor = db_conn.execute("""
            SELECT MIN(confidence) as min_conf, MAX(confidence) as max_conf
            FROM v_communication_client_link
        """)
        row = cursor.fetchone()
        assert row["min_conf"] >= 0, "confidence below 0"
        assert row["max_conf"] <= 1, "confidence above 1"


class TestInvoiceClientProjectView:
    """Tests for v_invoice_client_project view."""

    def test_returns_data(self, db_conn):
        """View returns invoice data."""
        cursor = db_conn.execute("SELECT COUNT(*) as cnt FROM v_invoice_client_project")
        assert cursor.fetchone()["cnt"] > 0

    def test_has_client_linkage(self, db_conn):
        """Most invoices should be linked to clients."""
        cursor = db_conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN client_id IS NOT NULL THEN 1 ELSE 0 END) as with_client
            FROM v_invoice_client_project
        """)
        row = cursor.fetchone()
        linkage_rate = row["with_client"] / row["total"] if row["total"] > 0 else 0
        assert linkage_rate >= 0.9, f"Invoice-client linkage too low: {linkage_rate:.1%}"

    def test_amount_non_negative(self, db_conn):
        """Invoice amounts should be non-negative."""
        cursor = db_conn.execute("SELECT MIN(amount) as min_amt FROM v_invoice_client_project")
        assert cursor.fetchone()["min_amt"] >= 0


class TestCrossViewIntegration:
    """Tests that verify views work together for cross-entity queries."""

    def test_client_task_count_matches(self, db_conn):
        """Client task counts should match between views."""
        # Get task counts per client from v_task_with_client
        cursor = db_conn.execute("""
            SELECT client_id, COUNT(*) as task_count
            FROM v_task_with_client
            WHERE client_id IS NOT NULL
            GROUP BY client_id
            LIMIT 5
        """)

        for row in cursor.fetchall():
            # Verify against v_client_operational_profile
            check = db_conn.execute("""
                SELECT total_tasks FROM v_client_operational_profile
                WHERE client_id = ?
            """, (row["client_id"],))
            profile = check.fetchone()
            if profile:
                assert profile["total_tasks"] == row["task_count"], \
                    f"Task count mismatch for client {row['client_id']}"
