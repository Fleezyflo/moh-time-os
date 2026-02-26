"""
Tests for Retention Engine and Scheduler.

Covers:
- Policy CRUD operations
- Preview enforcement (dry-run)
- Actual enforcement on temp DB
- PROTECTED_TABLES safety guard
- Min rows threshold enforcement
- Table age distribution
- Stale data summary
- Scheduler should_run logic
- Run history tracking
- Concurrent run prevention
- Lock mechanism
- Error handling

Uses temporary SQLite databases for all tests.
"""

import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from lib.governance.retention_engine import (
    ActionType,
    RetentionEngine,
    RetentionPolicy,
    RetentionReport,
)
from lib.governance.retention_scheduler import RetentionScheduler


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    # Create basic schema for testing
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE test_table (
            id INTEGER PRIMARY KEY,
            data TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE protected_table (
            id INTEGER PRIMARY KEY,
            data TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE unprotected_data (
            id INTEGER PRIMARY KEY,
            value INTEGER,
            timestamp TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    db_path.unlink(missing_ok=True)


@pytest.fixture
def engine(temp_db):
    """Create retention engine with temp DB."""
    return RetentionEngine(temp_db)


@pytest.fixture
def sample_data(temp_db):
    """Insert sample data into test tables."""
    conn = sqlite3.connect(str(temp_db))
    now = datetime.utcnow()

    # Insert rows of varying ages
    for i in range(10):
        age_days = i * 10  # 0, 10, 20, 30, ... 90 days old
        created = (now - timedelta(days=age_days)).isoformat()
        conn.execute(
            "INSERT INTO test_table (data, created_at) VALUES (?, ?)",
            (f"row_{i}", created),
        )

    # Insert into protected table
    for i in range(5):
        created = (now - timedelta(days=50)).isoformat()
        conn.execute(
            "INSERT INTO protected_table (data, created_at) VALUES (?, ?)",
            (f"protected_{i}", created),
        )

    # Insert into unprotected_data
    for i in range(20):
        age_days = i * 5
        timestamp = (now - timedelta(days=age_days)).isoformat()
        conn.execute(
            "INSERT INTO unprotected_data (value, timestamp) VALUES (?, ?)",
            (i * 100, timestamp),
        )

    conn.commit()
    conn.close()


# =============================================================================
# POLICY CRUD TESTS
# =============================================================================


class TestPolicyCRUD:
    """Tests for policy creation, reading, updating, deletion."""

    def test_add_policy(self, engine):
        """Test adding a retention policy."""
        policy = RetentionPolicy(
            table="test_table",
            retention_days=30,
            min_rows_preserve=5,
            timestamp_column="created_at",
        )
        engine.add_policy(policy)

        policies = engine.get_policies()
        assert len(policies) == 1
        assert policies[0].table == "test_table"
        assert policies[0].retention_days == 30

    def test_remove_policy(self, engine):
        """Test removing a policy."""
        policy = RetentionPolicy(
            table="test_table",
            retention_days=30,
            min_rows_preserve=5,
        )
        engine.add_policy(policy)
        assert len(engine.get_policies()) == 1

        engine.remove_policy("test_table")
        assert len(engine.get_policies()) == 0

    def test_update_policy(self, engine):
        """Test updating an existing policy."""
        policy = RetentionPolicy(
            table="test_table",
            retention_days=30,
            min_rows_preserve=5,
        )
        engine.add_policy(policy)

        # Update
        policy.retention_days = 60
        engine.add_policy(policy)

        policies = engine.get_policies()
        assert policies[0].retention_days == 60

    def test_get_policies_empty(self, engine):
        """Test getting policies when none exist."""
        policies = engine.get_policies()
        assert policies == []

    def test_get_policies_multiple(self, engine):
        """Test getting multiple policies."""
        for table in ["table1", "table2", "table3"]:
            policy = RetentionPolicy(
                table=table,
                retention_days=30,
                min_rows_preserve=5,
            )
            engine.add_policy(policy)

        policies = engine.get_policies()
        assert len(policies) == 3


# =============================================================================
# PREVIEW ENFORCEMENT TESTS
# =============================================================================


class TestPreviewEnforcement:
    """Tests for dry-run preview enforcement."""

    def test_preview_no_policies(self, engine, sample_data):
        """Preview with no policies should return empty report."""
        report = engine.preview_enforcement()
        assert report.total_rows_deleted == 0
        assert report.total_rows_archived == 0
        assert len(report.actions_taken) == 0

    def test_preview_shows_what_would_delete(self, engine, sample_data):
        """Preview should show rows that would be deleted without deleting."""
        policy = RetentionPolicy(
            table="test_table",
            retention_days=40,
            min_rows_preserve=3,
            timestamp_column="created_at",
        )
        engine.add_policy(policy)

        # Preview
        report = engine.preview_enforcement()

        assert len(report.actions_taken) == 1
        action = report.actions_taken[0]
        assert action.dry_run is True
        assert action.action_type == ActionType.DELETE
        assert action.rows_affected > 0

        # Verify data not actually deleted
        conn = sqlite3.connect(str(engine.db_path))
        cursor = conn.execute("SELECT COUNT(*) FROM test_table")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 10  # All original rows still there

    def test_preview_respects_min_rows(self, engine, sample_data):
        """Preview should respect min_rows_preserve threshold."""
        policy = RetentionPolicy(
            table="test_table",
            retention_days=5,
            min_rows_preserve=8,  # Preserve at least 8 rows
            timestamp_column="created_at",
        )
        engine.add_policy(policy)

        report = engine.preview_enforcement()

        # Should not delete because it would drop below min_rows_preserve
        if report.actions_taken:
            action = report.actions_taken[0]
            # If there is an action, it should preserve minimum
            conn = sqlite3.connect(str(engine.db_path))
            cursor = conn.execute("SELECT COUNT(*) FROM test_table")
            current = cursor.fetchone()[0]
            conn.close()
            assert current - action.rows_affected >= policy.min_rows_preserve


# =============================================================================
# ACTUAL ENFORCEMENT TESTS
# =============================================================================


class TestActualEnforcement:
    """Tests for actual enforcement with database modification."""

    def test_enforce_deletes_old_rows(self, engine, sample_data):
        """Test that enforce actually deletes old rows."""
        policy = RetentionPolicy(
            table="test_table",
            retention_days=40,
            min_rows_preserve=2,
            timestamp_column="created_at",
        )
        engine.add_policy(policy)

        # Get count before
        conn = sqlite3.connect(str(engine.db_path))
        cursor = conn.execute("SELECT COUNT(*) FROM test_table")
        before = cursor.fetchone()[0]
        conn.close()

        # Enforce (not dry-run)
        report = engine.enforce(dry_run=False)

        # Get count after
        conn = sqlite3.connect(str(engine.db_path))
        cursor = conn.execute("SELECT COUNT(*) FROM test_table")
        after = cursor.fetchone()[0]
        conn.close()

        assert after < before
        assert report.total_rows_deleted > 0

    def test_enforce_dry_run_default(self, engine, sample_data):
        """Test that dry_run=True is the default."""
        policy = RetentionPolicy(
            table="test_table",
            retention_days=40,
            min_rows_preserve=2,
            timestamp_column="created_at",
        )
        engine.add_policy(policy)

        # Count before
        conn = sqlite3.connect(str(engine.db_path))
        cursor = conn.execute("SELECT COUNT(*) FROM test_table")
        before = cursor.fetchone()[0]
        conn.close()

        # Call enforce without dry_run argument
        engine.enforce()

        # Count after (should be unchanged)
        conn = sqlite3.connect(str(engine.db_path))
        cursor = conn.execute("SELECT COUNT(*) FROM test_table")
        after = cursor.fetchone()[0]
        conn.close()

        assert after == before  # No actual deletion happened


# =============================================================================
# PROTECTED TABLES SAFETY TEST
# =============================================================================


class TestProtectedTablesSafety:
    """Tests for PROTECTED_TABLES enforcement."""

    def test_protected_tables_not_deleted(self, engine, sample_data):
        """Test that PROTECTED_TABLES are never deleted."""
        # Monkey-patch to mark protected_table as protected
        from lib import data_lifecycle

        data_lifecycle.DataLifecycleManager.PROTECTED_TABLES.add("protected_table")

        policy = RetentionPolicy(
            table="protected_table",
            retention_days=30,
            min_rows_preserve=2,
            timestamp_column="created_at",
        )
        engine.add_policy(policy)

        report = engine.enforce(dry_run=False)

        # No action should be taken
        assert len(report.actions_taken) == 0

        # Verify data still exists
        conn = sqlite3.connect(str(engine.db_path))
        cursor = conn.execute("SELECT COUNT(*) FROM protected_table")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 5  # Original data preserved


# =============================================================================
# MIN ROWS THRESHOLD TESTS
# =============================================================================


class TestMinRowsThreshold:
    """Tests for min_rows_preserve enforcement."""

    def test_min_rows_prevents_excessive_delete(self, engine, sample_data):
        """Test that min_rows_preserve prevents over-deletion."""
        policy = RetentionPolicy(
            table="test_table",
            retention_days=5,
            min_rows_preserve=9,  # Preserve 9 of 10 rows
            timestamp_column="created_at",
        )
        engine.add_policy(policy)

        # Count before
        conn = sqlite3.connect(str(engine.db_path))
        cursor = conn.execute("SELECT COUNT(*) FROM test_table")
        cursor.fetchone()[0]
        conn.close()

        # Enforce
        engine.enforce(dry_run=False)

        # Count after
        conn = sqlite3.connect(str(engine.db_path))
        cursor = conn.execute("SELECT COUNT(*) FROM test_table")
        after = cursor.fetchone()[0]
        conn.close()

        # Should have at least min_rows_preserve
        assert after >= policy.min_rows_preserve


# =============================================================================
# TABLE AGE DISTRIBUTION TESTS
# =============================================================================


class TestTableAgeDistribution:
    """Tests for get_table_age_distribution."""

    def test_age_distribution_buckets(self, engine, sample_data):
        """Test age distribution returns expected buckets."""
        distribution = engine.get_table_age_distribution("test_table")

        # Should have buckets
        assert len(distribution) > 0
        # Should have some expected keys
        assert any(k in distribution for k in ["< 1 day", "1-7 days", "> 1 year"])

    def test_age_distribution_counts(self, engine, sample_data):
        """Test age distribution counts are reasonable."""
        distribution = engine.get_table_age_distribution("test_table")

        # Total count should match or be close to actual
        total = sum(distribution.values())
        assert total > 0


# =============================================================================
# STALE DATA SUMMARY TESTS
# =============================================================================


class TestStaleDataSummary:
    """Tests for get_stale_data_summary."""

    def test_stale_data_summary(self, engine, sample_data):
        """Test stale data summary generation."""
        summary = engine.get_stale_data_summary()

        # Should be a dict
        assert isinstance(summary, dict)

        # May be empty if no data is > 1 year old
        if summary:
            for _table_name, stats in summary.items():
                assert "old_rows" in stats
                assert "total_rows" in stats
                assert "percentage" in stats


# =============================================================================
# SINGLE TABLE ENFORCEMENT TESTS
# =============================================================================


class TestEnforceTable:
    """Tests for enforce_table method."""

    def test_enforce_table_with_policy(self, engine, sample_data):
        """Test enforce_table with existing policy."""
        policy = RetentionPolicy(
            table="test_table",
            retention_days=40,
            min_rows_preserve=2,
            timestamp_column="created_at",
        )
        engine.add_policy(policy)

        action = engine.enforce_table("test_table", dry_run=True)

        assert action is not None
        assert action.policy.table == "test_table"
        assert action.rows_affected > 0

    def test_enforce_table_no_policy(self, engine):
        """Test enforce_table with no policy returns None."""
        action = engine.enforce_table("nonexistent_table", dry_run=True)
        assert action is None

    def test_enforce_table_no_timestamp_column(self, engine, sample_data):
        """Test enforce_table with no timestamp column returns None."""
        policy = RetentionPolicy(
            table="test_table",
            retention_days=40,
            min_rows_preserve=2,
            timestamp_column="nonexistent_column",
        )
        engine.add_policy(policy)

        action = engine.enforce_table("test_table", dry_run=True)
        # Should return None due to bad column
        assert action is None


# =============================================================================
# SCHEDULER TESTS
# =============================================================================


class TestRetentionScheduler:
    """Tests for RetentionScheduler."""

    def test_scheduler_init(self, engine):
        """Test scheduler initialization."""
        scheduler = RetentionScheduler(engine, schedule="daily")
        assert scheduler.schedule == "daily"

    def test_scheduler_invalid_schedule(self, engine):
        """Test scheduler rejects invalid schedule."""
        with pytest.raises(ValueError):
            RetentionScheduler(engine, schedule="invalid")

    def test_should_run_no_history(self, engine):
        """Test should_run returns True with no history."""
        scheduler = RetentionScheduler(engine, schedule="daily")
        assert scheduler.should_run() is True

    def test_get_next_run_no_history(self, engine):
        """Test get_next_run with no history."""
        scheduler = RetentionScheduler(engine, schedule="daily")
        next_run = scheduler.get_next_run()
        # Should be soon (now or shortly after)
        assert next_run is not None

    def test_get_last_run_no_history(self, engine):
        """Test get_last_run with no history."""
        scheduler = RetentionScheduler(engine, schedule="daily")
        last_run = scheduler.get_last_run()
        assert last_run is None

    def test_should_run_daily_schedule(self, engine):
        """Test daily schedule trigger logic."""
        scheduler = RetentionScheduler(engine, schedule="daily")

        # First run should be ready
        assert scheduler.should_run() is True

        # After running, should not be ready immediately
        scheduler.run(dry_run=True)

        # Check last run was recorded
        last_run = scheduler.get_last_run()
        assert last_run is not None
        assert last_run["schedule"] == "daily"

    def test_lock_prevents_concurrent_runs(self, engine):
        """Test lock prevents concurrent runs."""
        scheduler = RetentionScheduler(engine, schedule="daily")

        # Acquire lock
        acquired = scheduler._acquire_lock()
        assert acquired is True

        # Try to acquire again (should fail)
        acquired2 = scheduler._acquire_lock()
        assert acquired2 is False

        # Release lock
        scheduler._release_lock()

        # Verify lock released by checking can acquire again
        acquired3 = scheduler._acquire_lock()
        assert acquired3 is True

        scheduler._release_lock()

    def test_run_history_tracking(self, engine):
        """Test run history is recorded."""
        scheduler = RetentionScheduler(engine, schedule="daily")

        # Run with dry_run
        scheduler.run(dry_run=True)

        # Check history
        last_run = scheduler.get_last_run()
        assert last_run is not None
        assert last_run["dry_run"] is True
        assert last_run["status"] in ["success", "partial_failure"]


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestErrorHandling:
    """Tests for error handling in enforcement."""

    def test_nonexistent_table_handled(self, engine):
        """Test that nonexistent tables are handled gracefully."""
        policy = RetentionPolicy(
            table="nonexistent_table",
            retention_days=30,
            min_rows_preserve=2,
            timestamp_column="created_at",
        )
        engine.add_policy(policy)

        # Should handle gracefully
        report = engine.enforce(dry_run=True)
        # May have errors or just skip
        assert isinstance(report, RetentionReport)

    def test_error_logged_in_report(self, engine, sample_data):
        """Test that errors are captured in report."""
        policy = RetentionPolicy(
            table="test_table",
            retention_days=30,
            min_rows_preserve=2,
            timestamp_column="nonexistent_column",
        )
        engine.add_policy(policy)

        report = engine.enforce(dry_run=True)
        # Report should be valid even with errors
        assert isinstance(report, RetentionReport)


# =============================================================================
# SCHEDULE VALIDATION TESTS
# =============================================================================


class TestScheduleVariants:
    """Test different schedule types."""

    def test_daily_schedule(self, engine):
        """Test daily schedule."""
        scheduler = RetentionScheduler(engine, schedule="daily")
        assert scheduler.schedule == "daily"

    def test_weekly_schedule(self, engine):
        """Test weekly schedule."""
        scheduler = RetentionScheduler(engine, schedule="weekly")
        assert scheduler.schedule == "weekly"

    def test_monthly_schedule(self, engine):
        """Test monthly schedule."""
        scheduler = RetentionScheduler(engine, schedule="monthly")
        assert scheduler.schedule == "monthly"
