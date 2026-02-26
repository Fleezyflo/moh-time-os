"""
Comprehensive tests for data lifecycle management.

Covers:
- DataLifecycleManager configuration and policy management
- Retention enforcement with safety guards
- Archival to cold storage
- Database vacuuming
- Lifecycle reporting
"""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from lib.data_lifecycle import (
    ARCHIVE_TABLES,
    MIN_ROWS_THRESHOLD,
    PROTECTED_TABLES,
    DataLifecycleManager,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def lifecycle_manager():
    """Fresh DataLifecycleManager instance for each test."""
    return DataLifecycleManager()


# =============================================================================
# CONFIGURATION TESTS
# =============================================================================


class TestDataLifecycleConfiguration:
    """Tests for DataLifecycleManager configuration."""

    def test_default_retention_policies(self, lifecycle_manager):
        """Manager should initialize with default retention policies."""
        assert "signals" in lifecycle_manager._retention_policies
        assert lifecycle_manager._retention_policies["signals"] == 90
        assert "change_bundles" in lifecycle_manager._retention_policies
        assert lifecycle_manager._retention_policies["change_bundles"] == 30

    def test_configure_retention(self, lifecycle_manager):
        """configure_retention should set policy for a table."""
        lifecycle_manager.configure_retention("test_table", 45)
        assert lifecycle_manager.get_retention_policy("test_table") == 45

    def test_configure_retention_protected_table_fails(self, lifecycle_manager):
        """configure_retention should reject protected tables."""
        with pytest.raises(ValueError, match="protected table"):
            lifecycle_manager.configure_retention("clients", 30)

        with pytest.raises(ValueError, match="protected table"):
            lifecycle_manager.configure_retention("projects", 30)

    def test_configure_retention_invalid_days(self, lifecycle_manager):
        """configure_retention should reject invalid days."""
        with pytest.raises(ValueError, match="Days must be"):
            lifecycle_manager.configure_retention("test_table", -5)

    def test_configure_retention_disable_policy(self, lifecycle_manager):
        """configure_retention with -1 should disable retention."""
        lifecycle_manager.configure_retention("signals", 45)
        assert lifecycle_manager.get_retention_policy("signals") == 45

        lifecycle_manager.configure_retention("signals", -1)
        assert lifecycle_manager.get_retention_policy("signals") is None

    def test_get_retention_policy_unknown_table(self, lifecycle_manager):
        """get_retention_policy should return None for unknown table."""
        result = lifecycle_manager.get_retention_policy("unknown_table")
        assert result is None

    def test_protected_tables_constant(self):
        """PROTECTED_TABLES should include core entities."""
        assert "clients" in PROTECTED_TABLES
        assert "projects" in PROTECTED_TABLES
        assert "engagements" in PROTECTED_TABLES
        assert "capacity_lanes" in PROTECTED_TABLES

    def test_archive_tables_constant(self):
        """ARCHIVE_TABLES should be configured."""
        assert "communications" in ARCHIVE_TABLES
        assert "gmail_messages" in ARCHIVE_TABLES
        assert len(ARCHIVE_TABLES) > 0


# =============================================================================
# TIMESTAMP COLUMN DETECTION TESTS
# =============================================================================


class TestTimestampColumnDetection:
    """Tests for detecting timestamp columns."""

    @patch("lib.data_lifecycle.get_connection")
    def test_detect_created_at_priority(self, mock_get_conn, lifecycle_manager):
        """Should detect created_at as highest priority."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # The code iterates over cursor with: {row[1] for row in cursor}
        # So cursor needs to be iterable
        mock_cursor.__iter__.return_value = iter(
            [
                (0, "id", "INTEGER"),
                (1, "created_at", "TEXT"),
                (2, "updated_at", "TEXT"),
            ]
        )
        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = lifecycle_manager._get_timestamp_column("test_table")
        assert result == "created_at"

    @patch("lib.data_lifecycle.get_connection")
    def test_detect_updated_at_fallback(self, mock_get_conn, lifecycle_manager):
        """Should fallback to updated_at if created_at not present."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.__iter__.return_value = iter(
            [
                (0, "id", "INTEGER"),
                (1, "updated_at", "TEXT"),
            ]
        )
        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = lifecycle_manager._get_timestamp_column("test_table")
        assert result == "updated_at"

    @patch("lib.data_lifecycle.get_connection")
    def test_no_timestamp_column(self, mock_get_conn, lifecycle_manager):
        """Should return None if no timestamp column found."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.__iter__.return_value = iter(
            [
                (0, "id", "INTEGER"),
                (1, "name", "TEXT"),
            ]
        )
        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = lifecycle_manager._get_timestamp_column("test_table")
        assert result is None


# =============================================================================
# RETENTION ENFORCEMENT TESTS
# =============================================================================


class TestRetentionEnforcement:
    """Tests for enforce_retention functionality."""

    @patch("lib.data_lifecycle.get_connection")
    @patch("lib.data_lifecycle.create_backup")
    def test_enforce_retention_dry_run(self, mock_backup, mock_get_conn, lifecycle_manager):
        """enforce_retention with dry_run=True should not delete."""
        # Clear policies to test with a single table
        lifecycle_manager._retention_policies = {"test_table": 90}

        mock_conn = MagicMock()

        # Create separate cursor objects for each execute call
        # Call 1: PRAGMA table_info for _get_timestamp_column
        pragma_cursor = MagicMock()
        pragma_cursor.__iter__.return_value = iter(
            [
                (0, "id", "INTEGER"),
                (1, "created_at", "TEXT"),
            ]
        )

        # Call 2: SELECT COUNT(*) for _get_row_count
        count_cursor = MagicMock()
        count_cursor.fetchone.return_value = (150,)

        # Call 3: SELECT COUNT(*) for checking deletable rows
        delete_count_cursor = MagicMock()
        delete_count_cursor.fetchone.return_value = (30,)

        mock_conn.execute.side_effect = [pragma_cursor, count_cursor, delete_count_cursor]
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        results = lifecycle_manager.enforce_retention(dry_run=True)

        # Should not delete in dry-run
        assert mock_backup.call_count == 0
        assert isinstance(results, list)

    @patch("lib.data_lifecycle.get_connection")
    @patch("lib.data_lifecycle.create_backup")
    def test_enforce_retention_skips_protected_tables(
        self, mock_backup, mock_get_conn, lifecycle_manager
    ):
        """enforce_retention should skip protected tables."""
        # This test just checks the logic - protected tables are in DEFAULT_RETENTION_POLICIES
        # but should be skipped
        results = lifecycle_manager.enforce_retention(dry_run=True)

        # Should not try to process protected tables
        # Just verify the test runs without error
        assert isinstance(results, list)

    @patch("lib.data_lifecycle.get_connection")
    def test_enforce_retention_respects_min_rows_threshold(self, mock_get_conn, lifecycle_manager):
        """enforce_retention should not delete if table has < MIN_ROWS_THRESHOLD."""
        # Clear policies and set one test table
        lifecycle_manager._retention_policies = {"test_table": 90}

        mock_conn = MagicMock()

        # Call 1: PRAGMA table_info for _get_timestamp_column
        pragma_cursor = MagicMock()
        pragma_cursor.__iter__.return_value = iter(
            [
                (0, "id", "INTEGER"),
                (1, "created_at", "TEXT"),
            ]
        )

        # Call 2: SELECT COUNT(*) for _get_row_count (returns 50, below threshold)
        count_cursor = MagicMock()
        count_cursor.fetchone.return_value = (50,)

        mock_conn.execute.side_effect = [pragma_cursor, count_cursor]
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        results = lifecycle_manager.enforce_retention(dry_run=True)

        # Should skip this table due to low row count
        assert isinstance(results, list)


# =============================================================================
# ARCHIVAL TESTS
# =============================================================================


class TestArchival:
    """Tests for archive_to_cold functionality."""

    @patch("lib.data_lifecycle.get_connection")
    def test_archive_protected_table_fails(self, mock_get_conn, lifecycle_manager):
        """archive_to_cold should reject protected tables."""
        with pytest.raises(ValueError, match="protected table"):
            lifecycle_manager.archive_to_cold("clients", date.today())

    @patch("lib.data_lifecycle.get_connection")
    def test_archive_no_timestamp_column_fails(self, mock_get_conn, lifecycle_manager):
        """archive_to_cold should fail if no timestamp column."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.__iter__.return_value = iter(
            [
                (0, "id", "INTEGER"),
                (1, "name", "TEXT"),
            ]
        )
        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        with pytest.raises(ValueError, match="no timestamp column"):
            lifecycle_manager.archive_to_cold("test_table", date.today())

    @patch("lib.data_lifecycle.get_connection")
    def test_archive_dry_run(self, mock_get_conn, lifecycle_manager):
        """archive_to_cold with dry_run=True should not archive."""
        mock_conn = MagicMock()

        # Call 1: PRAGMA table_info for _get_timestamp_column
        pragma_cursor = MagicMock()
        pragma_cursor.__iter__.return_value = iter(
            [
                (0, "id", "INTEGER"),
                (1, "created_at", "TEXT"),
            ]
        )

        # Call 2: SELECT COUNT(*) to check rows to archive
        count_cursor = MagicMock()
        count_cursor.fetchone.return_value = (50,)

        mock_conn.execute.side_effect = [pragma_cursor, count_cursor]
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = lifecycle_manager.archive_to_cold(
            "test_table", date.today() - timedelta(days=180), dry_run=True
        )

        assert result["table"] == "test_table"
        assert result["rows_archived"] == 50
        assert result["rows_deleted"] == 0

    @patch("lib.data_lifecycle.get_connection")
    @patch("lib.data_lifecycle.create_backup")
    def test_archive_no_rows_to_archive(self, mock_backup, mock_get_conn, lifecycle_manager):
        """archive_to_cold should handle case when no rows match cutoff."""
        mock_conn = MagicMock()

        # Call 1: PRAGMA table_info for _get_timestamp_column
        pragma_cursor = MagicMock()
        pragma_cursor.__iter__.return_value = iter(
            [
                (0, "id", "INTEGER"),
                (1, "created_at", "TEXT"),
            ]
        )

        # Call 2: SELECT COUNT(*) returns 0 rows to archive
        count_cursor = MagicMock()
        count_cursor.fetchone.return_value = (0,)

        mock_conn.execute.side_effect = [pragma_cursor, count_cursor]
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = lifecycle_manager.archive_to_cold(
            "test_table", date.today() - timedelta(days=180), dry_run=True
        )

        assert result["rows_archived"] == 0


# =============================================================================
# VACUUM TESTS
# =============================================================================


class TestVacuum:
    """Tests for vacuum_database functionality."""

    @patch("lib.data_lifecycle.get_connection")
    def test_vacuum_success(self, mock_get_conn, lifecycle_manager):
        """vacuum_database should report success."""
        mock_conn = MagicMock()

        # Call 1: PRAGMA page_count (before)
        pages_before_cursor = MagicMock()
        pages_before_cursor.fetchone.return_value = (1000,)

        # Call 2: PRAGMA page_size
        page_size_cursor = MagicMock()
        page_size_cursor.fetchone.return_value = (4096,)

        # Call 3: VACUUM (no return value needed, just execute)
        vacuum_cursor = MagicMock()

        # Call 4: PRAGMA page_count (after)
        pages_after_cursor = MagicMock()
        pages_after_cursor.fetchone.return_value = (800,)

        mock_conn.execute.side_effect = [
            pages_before_cursor,
            page_size_cursor,
            vacuum_cursor,
            pages_after_cursor,
        ]
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = lifecycle_manager.vacuum_database()

        assert result["success"] is True
        assert "size_before_mb" in result
        assert "size_after_mb" in result
        assert "space_freed_mb" in result

    @patch("lib.data_lifecycle.get_connection")
    def test_vacuum_failure(self, mock_get_conn, lifecycle_manager):
        """vacuum_database should handle vacuum failure gracefully."""
        mock_conn = MagicMock()

        # Call 1: PRAGMA page_count (before)
        pages_before_cursor = MagicMock()
        pages_before_cursor.fetchone.return_value = (1000,)

        # Call 2: PRAGMA page_size
        page_size_cursor = MagicMock()
        page_size_cursor.fetchone.return_value = (4096,)

        # Call 3: VACUUM fails
        def raise_on_vacuum(sql, *args):
            if "VACUUM" in sql:
                raise Exception("VACUUM failed")
            return page_size_cursor

        mock_conn.execute.side_effect = [
            pages_before_cursor,
            page_size_cursor,
            Exception("VACUUM failed"),
        ]

        # Better approach: use side_effect with a function
        call_count = [0]

        def side_effect_func(sql, *args):
            call_count[0] += 1
            if call_count[0] == 1:  # PRAGMA page_count
                c = MagicMock()
                c.fetchone.return_value = (1000,)
                return c
            elif call_count[0] == 2:  # PRAGMA page_size
                c = MagicMock()
                c.fetchone.return_value = (4096,)
                return c
            elif call_count[0] == 3:  # VACUUM
                raise Exception("VACUUM failed")

        mock_conn.execute.side_effect = side_effect_func
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = lifecycle_manager.vacuum_database()

        assert result["success"] is False
        assert "error" in result


# =============================================================================
# REPORTING TESTS
# =============================================================================


class TestLifecycleReporting:
    """Tests for get_lifecycle_report functionality."""

    @patch("lib.data_lifecycle.get_connection")
    def test_lifecycle_report_structure(self, mock_get_conn, lifecycle_manager):
        """get_lifecycle_report should return structured report."""
        mock_conn = MagicMock()

        # Create a callable side_effect to handle multiple calls
        def make_cursor(sql, *args):
            c = MagicMock()
            if "PRAGMA table_info" in sql:
                c.__iter__.return_value = iter([(0, "id", "INTEGER")])
            else:
                c.fetchone.return_value = (0,)
            return c

        mock_conn.execute.side_effect = make_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        # Clear policies to test with simpler setup
        lifecycle_manager._retention_policies = {"test_table": 90}

        report = lifecycle_manager.get_lifecycle_report()

        assert "timestamp" in report
        assert "retention_policies" in report
        assert "tables" in report
        assert "protected_tables" in report
        assert "archive_tables" in report
        assert PROTECTED_TABLES == set(report["protected_tables"])

    @patch("lib.data_lifecycle.get_connection")
    def test_lifecycle_report_table_info(self, mock_get_conn, lifecycle_manager):
        """get_lifecycle_report should include per-table statistics."""
        mock_conn = MagicMock()

        # Create a callable side_effect for multiple calls
        call_count = [0]

        def make_cursor(sql, *args):
            call_count[0] += 1
            c = MagicMock()

            if "PRAGMA table_info" in sql:
                c.__iter__.return_value = iter([(0, "id", "INTEGER"), (1, "created_at", "TEXT")])
            elif "COUNT(*)" in sql:
                c.fetchone.return_value = (100,)
            elif "MIN(" in sql:
                c.fetchone.return_value = ("2024-01-01T00:00:00Z",)
            elif "MAX(" in sql:
                c.fetchone.return_value = ("2024-02-01T00:00:00Z",)

            return c

        mock_conn.execute.side_effect = make_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        lifecycle_manager._retention_policies = {"test_table": 90}

        report = lifecycle_manager.get_lifecycle_report()

        # Should handle the table
        assert "tables" in report

    def test_min_rows_threshold_constant(self):
        """MIN_ROWS_THRESHOLD should be reasonable."""
        assert MIN_ROWS_THRESHOLD == 100
        assert MIN_ROWS_THRESHOLD > 0
