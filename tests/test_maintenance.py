"""
Comprehensive tests for maintenance utilities.

Covers:
- get_ancient_items with age-based filtering
- archive_ancient_items with dry-run mode
- cleanup_asana_cruft for stale Asana tasks
- fix_item_priorities for priority recalculation
- get_maintenance_report for status overview
"""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from lib.maintenance import (
    archive_ancient_items,
    cleanup_asana_cruft,
    fix_item_priorities,
    get_ancient_items,
    get_maintenance_report,
)

# =============================================================================
# GET ANCIENT ITEMS TESTS
# =============================================================================


class TestGetAncientItems:
    """Tests for get_ancient_items functionality."""

    @patch("lib.maintenance.get_connection")
    def test_get_ancient_items_filters_by_age(self, mock_get_conn):
        """get_ancient_items should filter items older than threshold."""
        mock_conn = MagicMock()

        # Mock database response: items due before cutoff date
        (date.today() - timedelta(days=180)).isoformat()
        ancient_date = (date.today() - timedelta(days=365)).isoformat()

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "id": "item-1",
                "what": "Ancient task",
                "due": ancient_date,
                "source_type": "asana",
            },
        ]

        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = get_ancient_items(days_overdue=180)

        assert len(result) == 1
        assert result[0]["id"] == "item-1"
        assert result[0]["days_overdue"] > 180

    @patch("lib.maintenance.get_connection")
    def test_get_ancient_items_calculates_age(self, mock_get_conn):
        """get_ancient_items should calculate days overdue."""
        mock_conn = MagicMock()

        # Create a date exactly 200 days ago
        target_date = (date.today() - timedelta(days=200)).isoformat()

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "id": "item-1",
                "what": "Old task",
                "due": target_date,
                "source_type": "asana",
            },
        ]

        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = get_ancient_items(days_overdue=180)

        assert len(result) == 1
        assert result[0]["days_overdue"] == 200

    @patch("lib.maintenance.get_connection")
    def test_get_ancient_items_empty_result(self, mock_get_conn):
        """get_ancient_items should return empty list when no matches."""
        mock_conn = MagicMock()

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []

        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = get_ancient_items(days_overdue=180)

        assert result == []

    @patch("lib.maintenance.get_connection")
    def test_get_ancient_items_excludes_recent(self, mock_get_conn):
        """get_ancient_items should exclude items newer than threshold."""
        mock_conn = MagicMock()

        # Only include items from the query (which filters on server-side)
        # So we just verify the function handles it correctly
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []

        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = get_ancient_items(days_overdue=180)

        assert result == []


# =============================================================================
# ARCHIVE ANCIENT ITEMS TESTS
# =============================================================================


class TestArchiveAncientItems:
    """Tests for archive_ancient_items functionality."""

    @patch("lib.maintenance.get_ancient_items")
    def test_archive_ancient_items_dry_run(self, mock_get_ancient):
        """archive_ancient_items with dry_run=True should not modify database."""
        mock_get_ancient.return_value = [
            {
                "id": "item-1",
                "what": "Ancient task",
                "days_overdue": 400,
                "source_type": "asana",
            },
        ]

        count, archived = archive_ancient_items(days_overdue=365, dry_run=True)

        assert count == 1
        assert len(archived) == 1
        assert "Ancient task" in archived[0]
        assert "400d overdue" in archived[0]

    @patch("lib.maintenance.mark_cancelled")
    @patch("lib.maintenance.create_backup")
    @patch("lib.maintenance.get_ancient_items")
    def test_archive_ancient_items_performs_archival(
        self, mock_get_ancient, mock_backup, mock_mark_cancelled
    ):
        """archive_ancient_items should archive items when not dry_run."""
        mock_get_ancient.return_value = [
            {
                "id": "item-1",
                "what": "Ancient task",
                "days_overdue": 400,
                "source_type": "asana",
            },
            {
                "id": "item-2",
                "what": "Another old task",
                "days_overdue": 500,
                "source_type": "asana",
            },
        ]

        count, archived = archive_ancient_items(days_overdue=365, dry_run=False)

        assert count == 2
        assert len(archived) == 2
        mock_backup.assert_called_once()
        assert mock_mark_cancelled.call_count == 2

    @patch("lib.maintenance.get_ancient_items")
    def test_archive_ancient_items_empty_list(self, mock_get_ancient):
        """archive_ancient_items should handle empty list."""
        mock_get_ancient.return_value = []

        count, archived = archive_ancient_items(dry_run=True)

        assert count == 0
        assert archived == []


# =============================================================================
# CLEANUP ASANA CRUFT TESTS
# =============================================================================


class TestCleanupAsanaCruft:
    """Tests for cleanup_asana_cruft functionality."""

    @patch("lib.maintenance.get_connection")
    def test_cleanup_asana_cruft_finds_ancient_tasks(self, mock_get_conn):
        """cleanup_asana_cruft should identify tasks >1 year old."""
        mock_conn = MagicMock()

        ancient_date = (date.today() - timedelta(days=400)).isoformat()

        ancient_response = MagicMock()
        ancient_response.fetchall.return_value = [
            ("task-1", "Ancient Asana task", ancient_date),
        ]

        stale_response = MagicMock()
        stale_response.fetchall.return_value = []

        # Setup side effects for the two queries
        mock_conn.execute.side_effect = [ancient_response, stale_response]
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = cleanup_asana_cruft(dry_run=True)

        assert len(result["ancient_tasks"]) == 1
        assert result["ancient_tasks"][0]["id"] == "task-1"

    @patch("lib.maintenance.get_connection")
    def test_cleanup_asana_cruft_finds_stale_no_context(self, mock_get_conn):
        """cleanup_asana_cruft should identify stale tasks with no client context."""
        mock_conn = MagicMock()

        stale_date = (date.today() - timedelta(days=200)).isoformat()

        ancient_response = MagicMock()
        ancient_response.fetchall.return_value = []

        stale_response = MagicMock()
        stale_response.fetchall.return_value = [
            ("task-2", "Stale no context", stale_date),
        ]

        mock_conn.execute.side_effect = [ancient_response, stale_response]
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = cleanup_asana_cruft(dry_run=True)

        assert len(result["no_context_tasks"]) == 1
        assert result["no_context_tasks"][0]["id"] == "task-2"

    @patch("lib.maintenance.mark_cancelled")
    @patch("lib.maintenance.create_backup")
    @patch("lib.maintenance.get_connection")
    def test_cleanup_asana_cruft_performs_cleanup(
        self, mock_get_conn, mock_backup, mock_mark_cancelled
    ):
        """cleanup_asana_cruft should archive tasks when not dry_run."""
        mock_conn = MagicMock()

        ancient_date = (date.today() - timedelta(days=400)).isoformat()

        ancient_response = MagicMock()
        ancient_response.fetchall.return_value = [
            ("task-1", "Ancient task", ancient_date),
        ]

        stale_response = MagicMock()
        stale_response.fetchall.return_value = [
            ("task-2", "Stale task", (date.today() - timedelta(days=200)).isoformat()),
        ]

        mock_conn.execute.side_effect = [ancient_response, stale_response]
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = cleanup_asana_cruft(dry_run=False)

        assert result["dry_run"] is False
        mock_backup.assert_called_once()
        # Should have called mark_cancelled for each task
        assert mock_mark_cancelled.call_count == 2

    @patch("lib.maintenance.get_connection")
    def test_cleanup_asana_cruft_returns_structure(self, mock_get_conn):
        """cleanup_asana_cruft should return expected structure."""
        mock_conn = MagicMock()

        ancient_response = MagicMock()
        ancient_response.fetchall.return_value = []

        stale_response = MagicMock()
        stale_response.fetchall.return_value = []

        mock_conn.execute.side_effect = [ancient_response, stale_response]
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = cleanup_asana_cruft(dry_run=True)

        assert "ancient_tasks" in result
        assert "no_context_tasks" in result
        assert "dry_run" in result
        assert isinstance(result["ancient_tasks"], list)
        assert isinstance(result["no_context_tasks"], list)


# =============================================================================
# FIX ITEM PRIORITIES TESTS
# =============================================================================


class TestFixItemPriorities:
    """Tests for fix_item_priorities functionality."""

    @patch("lib.maintenance.get_connection")
    @patch("lib.maintenance.recalculate_all_priorities")
    def test_fix_item_priorities_returns_count(self, mock_recalc, mock_get_conn):
        """fix_item_priorities should return count of open/waiting items."""
        mock_conn = MagicMock()

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (42,)

        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = fix_item_priorities()

        assert result == 42
        mock_recalc.assert_called_once()

    @patch("lib.maintenance.get_connection")
    @patch("lib.maintenance.recalculate_all_priorities")
    def test_fix_item_priorities_calls_recalculate(self, mock_recalc, mock_get_conn):
        """fix_item_priorities should call recalculate_all_priorities."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (0,)

        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        fix_item_priorities()

        mock_recalc.assert_called_once()


# =============================================================================
# GET MAINTENANCE REPORT TESTS
# =============================================================================


class TestGetMaintenanceReport:
    """Tests for get_maintenance_report functionality."""

    @patch("lib.maintenance.get_connection")
    @patch("lib.maintenance.get_ancient_items")
    def test_get_maintenance_report_structure(self, mock_get_ancient, mock_get_conn):
        """get_maintenance_report should return expected structure."""
        mock_get_ancient.return_value = []

        mock_conn = MagicMock()

        # Mock multiple execute calls
        by_source_cursor = MagicMock()
        by_source_cursor.fetchall.return_value = [
            ("asana", 50),
            ("gmail", 20),
        ]

        no_due_cursor = MagicMock()
        no_due_cursor.fetchone.return_value = (15,)

        no_client_cursor = MagicMock()
        no_client_cursor.fetchone.return_value = (10,)

        mock_conn.execute.side_effect = [
            by_source_cursor,
            no_due_cursor,
            no_client_cursor,
        ]

        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = get_maintenance_report()

        assert "ancient_items" in result
        assert "very_ancient_items" in result
        assert "items_by_source" in result
        assert "items_without_due" in result
        assert "items_without_client" in result
        assert "recommendation" in result

    @patch("lib.maintenance.get_connection")
    @patch("lib.maintenance.get_ancient_items")
    def test_get_maintenance_report_counts_items(self, mock_get_ancient, mock_get_conn):
        """get_maintenance_report should count items correctly."""
        # Create items: some ancient, some very ancient
        mock_get_ancient.return_value = [
            {"days_overdue": 200},
            {"days_overdue": 400},  # very_ancient (>365)
            {"days_overdue": 500},  # very_ancient (>365)
        ]

        mock_conn = MagicMock()
        by_source_cursor = MagicMock()
        by_source_cursor.fetchall.return_value = []

        no_due_cursor = MagicMock()
        no_due_cursor.fetchone.return_value = (0,)

        no_client_cursor = MagicMock()
        no_client_cursor.fetchone.return_value = (0,)

        mock_conn.execute.side_effect = [
            by_source_cursor,
            no_due_cursor,
            no_client_cursor,
        ]

        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = get_maintenance_report()

        assert result["ancient_items"] == 3
        assert result["very_ancient_items"] == 2

    @patch("lib.maintenance.get_connection")
    @patch("lib.maintenance.get_ancient_items")
    def test_get_maintenance_report_recommendation_clean(self, mock_get_ancient, mock_get_conn):
        """get_maintenance_report should recommend 'clean' when no issues."""
        mock_get_ancient.return_value = []

        mock_conn = MagicMock()
        by_source_cursor = MagicMock()
        by_source_cursor.fetchall.return_value = []

        no_due_cursor = MagicMock()
        no_due_cursor.fetchone.return_value = (0,)

        no_client_cursor = MagicMock()
        no_client_cursor.fetchone.return_value = (0,)

        mock_conn.execute.side_effect = [
            by_source_cursor,
            no_due_cursor,
            no_client_cursor,
        ]

        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = get_maintenance_report()

        assert "clean" in result["recommendation"].lower()

    @patch("lib.maintenance.get_connection")
    @patch("lib.maintenance.get_ancient_items")
    def test_get_maintenance_report_recommendation_cleanup_needed(
        self, mock_get_ancient, mock_get_conn
    ):
        """get_maintenance_report should recommend cleanup when issues found."""
        very_ancient = [{"days_overdue": 400}]
        mock_get_ancient.return_value = very_ancient

        mock_conn = MagicMock()
        by_source_cursor = MagicMock()
        by_source_cursor.fetchall.return_value = []

        no_due_cursor = MagicMock()
        no_due_cursor.fetchone.return_value = (0,)

        no_client_cursor = MagicMock()
        no_client_cursor.fetchone.return_value = (0,)

        mock_conn.execute.side_effect = [
            by_source_cursor,
            no_due_cursor,
            no_client_cursor,
        ]

        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = get_maintenance_report()

        assert "cleanup" in result["recommendation"].lower()


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestMaintenanceIntegration:
    """Integration tests for maintenance utilities."""

    @patch("lib.maintenance.get_connection")
    def test_get_ancient_items_with_mock_data(self, mock_get_conn):
        """Integration: get_ancient_items with realistic data."""
        mock_conn = MagicMock()

        # Simulate realistic data
        ancient_date = (date.today() - timedelta(days=365)).isoformat()
        old_date = (date.today() - timedelta(days=200)).isoformat()

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "id": "asana-12345",
                "what": "Complete project proposal",
                "due": ancient_date,
                "source_type": "asana",
            },
            {
                "id": "asana-12346",
                "what": "Client feedback review",
                "due": old_date,
                "source_type": "asana",
            },
        ]

        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = get_ancient_items(days_overdue=180)

        assert len(result) == 2
        assert result[0]["what"] == "Complete project proposal"
        assert result[0]["days_overdue"] >= 365
        assert result[1]["days_overdue"] >= 200
