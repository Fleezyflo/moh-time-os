"""
Scheduled Retention Enforcement with Run History and Locking.

Features:
- Configurable schedule (daily, weekly, monthly)
- Run history tracking in SQLite
- Lock mechanism to prevent concurrent runs
- Last run details retrieval
- Next run time calculation
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Any

from lib.governance.retention_engine import RetentionEngine, RetentionReport

logger = logging.getLogger(__name__)


class RetentionScheduler:
    """
    Manages scheduled execution of retention enforcement.

    Supports:
    - daily: Run every 24 hours
    - weekly: Run every 7 days
    - monthly: Run every 30 days
    """

    VALID_SCHEDULES = {"daily", "weekly", "monthly"}

    def __init__(self, engine: RetentionEngine, schedule: str = "daily"):
        """
        Initialize scheduler.

        Args:
            engine: RetentionEngine instance
            schedule: One of 'daily', 'weekly', 'monthly'
        """
        if schedule not in self.VALID_SCHEDULES:
            raise ValueError(f"Invalid schedule: {schedule}")

        self.engine = engine
        self.schedule = schedule
        self.db_path = engine.db_path
        self._create_schema()
        logger.info(f"RetentionScheduler initialized with {schedule} schedule")

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _create_schema(self) -> None:
        """Create scheduler tables."""
        conn = self._get_connection()
        try:
            # Table for run history
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS retention_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    schedule TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    status TEXT NOT NULL,
                    total_rows_deleted INTEGER,
                    total_rows_archived INTEGER,
                    total_rows_anonymized INTEGER,
                    error_count INTEGER,
                    warning_count INTEGER,
                    duration_ms INTEGER,
                    dry_run INTEGER NOT NULL
                )
                """
            )

            # Table for locking
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS retention_locks (
                    lock_key TEXT PRIMARY KEY,
                    acquired_at TEXT NOT NULL,
                    released_at TEXT
                )
                """
            )

            conn.commit()
            logger.debug("Scheduler schema tables created/verified")
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error creating scheduler schema: {e}")
            raise
        finally:
            conn.close()

    def should_run(self) -> bool:
        """
        Check if retention should run now.

        Returns:
            True if enough time has passed since last run
        """
        last_run = self.get_last_run()
        if last_run is None:
            logger.info("No previous run found - should run")
            return True

        completed_at = last_run.get("completed_at")
        if not completed_at:
            logger.warning("Last run did not complete - should run")
            return True

        last_dt = datetime.fromisoformat(completed_at)
        now = datetime.utcnow()

        # Calculate required interval
        if self.schedule == "daily":
            interval = timedelta(days=1)
        elif self.schedule == "weekly":
            interval = timedelta(days=7)
        elif self.schedule == "monthly":
            interval = timedelta(days=30)
        else:
            interval = timedelta(days=1)

        next_run = last_dt + interval
        should_run = now >= next_run

        logger.debug(f"Last run: {last_dt}, next eligible: {next_run}, should run: {should_run}")

        return should_run

    def get_next_run(self) -> datetime:
        """
        Calculate next scheduled run time.

        Returns:
            datetime of next run
        """
        last_run = self.get_last_run()
        if last_run is None:
            return datetime.utcnow()

        completed_at = last_run.get("completed_at")
        if not completed_at:
            return datetime.utcnow()

        last_dt = datetime.fromisoformat(completed_at)

        if self.schedule == "daily":
            interval = timedelta(days=1)
        elif self.schedule == "weekly":
            interval = timedelta(days=7)
        elif self.schedule == "monthly":
            interval = timedelta(days=30)
        else:
            interval = timedelta(days=1)

        return last_dt + interval

    def get_last_run(self) -> dict[str, Any] | None:
        """
        Get details of last retention run.

        Returns:
            dict with run details or None if no runs
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT id, schedule, started_at, completed_at, status,
                       total_rows_deleted, total_rows_archived,
                       total_rows_anonymized, error_count, warning_count,
                       duration_ms, dry_run
                FROM retention_runs
                WHERE schedule = ?
                ORDER BY started_at DESC
                LIMIT 1
                """,
                (self.schedule,),
            )
            row = cursor.fetchone()

            if not row:
                return None

            return {
                "id": row[0],
                "schedule": row[1],
                "started_at": row[2],
                "completed_at": row[3],
                "status": row[4],
                "total_rows_deleted": row[5],
                "total_rows_archived": row[6],
                "total_rows_anonymized": row[7],
                "error_count": row[8],
                "warning_count": row[9],
                "duration_ms": row[10],
                "dry_run": bool(row[11]),
            }

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error getting last run: {e}")
            return None
        finally:
            conn.close()

    def _acquire_lock(self) -> bool:
        """
        Acquire lock to prevent concurrent runs.

        Returns:
            True if lock acquired, False if already locked
        """
        conn = self._get_connection()
        try:
            lock_key = f"retention_{self.schedule}"
            now = datetime.utcnow().isoformat()

            # Check if lock already exists and not released
            cursor = conn.execute(
                """
                SELECT released_at FROM retention_locks
                WHERE lock_key = ? AND released_at IS NULL
                """,
                (lock_key,),
            )

            if cursor.fetchone():
                logger.warning(f"Lock already held for {lock_key}")
                return False

            # Try to acquire lock (insert or replace)
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO retention_locks (lock_key, acquired_at, released_at)
                    VALUES (?, ?, NULL)
                    """,
                    (lock_key, now),
                )
                conn.commit()
                logger.debug(f"Lock acquired: {lock_key}")
                return True
            except (sqlite3.Error, ValueError, OSError) as e:
                logger.warning(f"Failed to acquire lock for {lock_key}: {e}")
                return False

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error acquiring lock: {e}")
            return False
        finally:
            conn.close()

    def _release_lock(self) -> None:
        """Release execution lock."""
        conn = self._get_connection()
        try:
            lock_key = f"retention_{self.schedule}"
            now = datetime.utcnow().isoformat()

            conn.execute(
                """
                UPDATE retention_locks
                SET released_at = ?
                WHERE lock_key = ? AND released_at IS NULL
                """,
                (now, lock_key),
            )
            conn.commit()
            logger.debug(f"Lock released: {lock_key}")

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error releasing lock: {e}")
        finally:
            conn.close()

    def run(self, dry_run: bool = False) -> RetentionReport:
        """
        Execute scheduled retention enforcement.

        Args:
            dry_run: If True, preview without executing (default False)

        Returns:
            RetentionReport with results
        """
        # Try to acquire lock
        if not self._acquire_lock():
            logger.warning("Could not acquire lock - skipping run")
            return RetentionReport(errors=["Could not acquire execution lock"])

        started_at = datetime.utcnow()
        started_at_iso = started_at.isoformat()

        try:
            # Run enforcement
            report = self.engine.enforce(dry_run=dry_run)

            # Record run
            completed_at = datetime.utcnow().isoformat()
            status = "success" if not report.errors else "partial_failure"

            conn = self._get_connection()
            try:
                conn.execute(
                    """
                    INSERT INTO retention_runs
                    (schedule, started_at, completed_at, status,
                     total_rows_deleted, total_rows_archived, total_rows_anonymized,
                     error_count, warning_count, duration_ms, dry_run)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.schedule,
                        started_at_iso,
                        completed_at,
                        status,
                        report.total_rows_deleted,
                        report.total_rows_archived,
                        report.total_rows_anonymized,
                        len(report.errors),
                        len(report.warnings),
                        report.duration_ms,
                        int(dry_run),
                    ),
                )
                conn.commit()
                logger.info(
                    f"Run recorded: {status}, "
                    f"deleted={report.total_rows_deleted}, "
                    f"errors={len(report.errors)}"
                )
            except (sqlite3.Error, ValueError, OSError) as e:
                logger.error(f"Error recording run: {e}")
            finally:
                conn.close()

            return report

        finally:
            self._release_lock()
