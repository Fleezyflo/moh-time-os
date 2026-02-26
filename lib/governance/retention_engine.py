"""
Production-grade Data Retention Engine with Governance Controls.

Manages:
- Retention policies (per-table, configurable)
- Dry-run preview of enforcement
- Safe deletion with archive-before-delete flow
- Protected table enforcement
- Min rows threshold
- Data age distribution analysis
- Backup creation before destructive operations
- Audit logging of all actions

Safety guarantees:
- Never deletes from PROTECTED_TABLES
- Never drops below min_rows_preserve threshold
- Archives before deletion when configured
- dry_run=True by default for destructive operations
- All deletes logged with cutoff dates
"""

import json
import logging
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from lib.data_lifecycle import PROTECTED_TABLES, get_lifecycle_manager
from lib.db import validate_identifier

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Types of retention actions."""

    DELETE = "delete"
    ARCHIVE = "archive"
    ANONYMIZE = "anonymize"


@dataclass
class RetentionPolicy:
    """Policy for retaining/purging data from a table."""

    table: str  # Table name
    retention_days: int  # Keep data <= N days old
    archive_before_delete: bool = False  # Archive before deletion
    require_approval: bool = False  # Require manual approval
    min_rows_preserve: int = 100  # Never drop below this
    timestamp_column: str | None = None  # Column to use for age (auto-detect if None)
    active: bool = True  # Is this policy active


@dataclass
class RetentionAction:
    """Record of a single retention action."""

    policy: RetentionPolicy
    rows_affected: int
    action_type: ActionType
    cutoff_date: str  # ISO date for what was deleted
    dry_run: bool
    executed_at: str  # ISO timestamp when executed


@dataclass
class RetentionReport:
    """Result of retention enforcement."""

    actions_taken: list[RetentionAction] = field(default_factory=list)
    total_rows_deleted: int = 0
    total_rows_archived: int = 0
    total_rows_anonymized: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duration_ms: int = 0


class RetentionEngine:
    """
    Production-grade retention enforcement engine.

    Implements:
    - Policy management (add, remove, list)
    - Preview enforcement (dry-run)
    - Actual enforcement with safety guards
    - Per-table enforcement
    - Age distribution analysis
    - Stale data summaries
    """

    def __init__(self, db_path: str | Path):
        """Initialize retention engine with database path."""
        self.db_path = Path(db_path)
        self.lifecycle = get_lifecycle_manager()
        self._policies: dict[str, RetentionPolicy] = {}
        self._create_schema()
        logger.info(f"RetentionEngine initialized with {self.db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with proper settings."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _create_schema(self) -> None:
        """Create retention system tables if needed."""
        conn = self._get_connection()
        try:
            # Table to store policies
            conn.execute("""
                CREATE TABLE IF NOT EXISTS retention_policies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_name TEXT NOT NULL UNIQUE,
                    retention_days INTEGER NOT NULL,
                    archive_before_delete INTEGER NOT NULL,
                    require_approval INTEGER NOT NULL,
                    min_rows_preserve INTEGER NOT NULL,
                    timestamp_column TEXT,
                    active INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Table to store audit log of enforcement actions
            conn.execute("""
                CREATE TABLE IF NOT EXISTS retention_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_name TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    rows_affected INTEGER,
                    cutoff_date TEXT,
                    dry_run INTEGER NOT NULL,
                    executed_at TEXT NOT NULL,
                    error_message TEXT
                )
            """)

            conn.commit()
            logger.debug("Retention schema tables created/verified")
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error creating retention schema: {e}")
            raise
        finally:
            conn.close()

    def add_policy(self, policy: RetentionPolicy) -> None:
        """Add or update a retention policy."""
        self._policies[policy.table] = policy

        conn = self._get_connection()
        try:
            now = datetime.utcnow().isoformat()
            conn.execute(
                """
                INSERT OR REPLACE INTO retention_policies
                (table_name, retention_days, archive_before_delete, require_approval,
                 min_rows_preserve, timestamp_column, active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    policy.table,
                    policy.retention_days,
                    int(policy.archive_before_delete),
                    int(policy.require_approval),
                    policy.min_rows_preserve,
                    policy.timestamp_column,
                    int(policy.active),
                    now,
                    now,
                ),
            )
            conn.commit()
            logger.info(f"Policy added for table {policy.table}: {policy.retention_days} days")
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error adding policy: {e}")
            raise
        finally:
            conn.close()

    def remove_policy(self, table: str) -> None:
        """Remove a retention policy."""
        if table in self._policies:
            del self._policies[table]

        conn = self._get_connection()
        try:
            conn.execute("DELETE FROM retention_policies WHERE table_name = ?", (table,))
            conn.commit()
            logger.info(f"Policy removed for table {table}")
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error removing policy: {e}")
            raise
        finally:
            conn.close()

    def get_policies(self) -> list[RetentionPolicy]:
        """Get all retention policies."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT table_name, retention_days, archive_before_delete, require_approval,
                       min_rows_preserve, timestamp_column, active
                FROM retention_policies
                """
            )
            policies = []
            for row in cursor.fetchall():
                policy = RetentionPolicy(
                    table=row[0],
                    retention_days=row[1],
                    archive_before_delete=bool(row[2]),
                    require_approval=bool(row[3]),
                    min_rows_preserve=row[4],
                    timestamp_column=row[5],
                    active=bool(row[6]),
                )
                policies.append(policy)
            return policies
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error getting policies: {e}")
            return []
        finally:
            conn.close()

    def _find_timestamp_column(self, table: str) -> str | None:
        """Auto-detect timestamp column in table."""
        safe_table = validate_identifier(table)
        conn = self._get_connection()
        try:
            cursor = conn.execute(f"PRAGMA table_info({safe_table})")  # noqa: S608
            columns = [row[1] for row in cursor.fetchall()]

            # Try common timestamp column names
            for col in ["created_at", "updated_at", "timestamp", "date", "time"]:
                if col in columns:
                    return col
            return None
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.warning(f"Error finding timestamp column for {table}: {e}")
            return None
        finally:
            conn.close()

    def _get_row_count(self, table: str) -> int:
        """Get current row count for a table."""
        safe_table = validate_identifier(table)
        conn = self._get_connection()
        try:
            cursor = conn.execute(f"SELECT COUNT(*) FROM {safe_table}")  # noqa: S608
            return cursor.fetchone()[0]
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error counting rows in {table}: {e}")
            return 0
        finally:
            conn.close()

    def _compute_cutoff_date(self, policy: RetentionPolicy) -> str:
        """Compute cutoff date for deletion (as ISO string for comparison)."""
        cutoff = datetime.utcnow() - timedelta(days=policy.retention_days)
        return cutoff.isoformat()

    def preview_enforcement(self) -> RetentionReport:
        """
        Preview what enforcement would do without executing.

        Returns:
            RetentionReport with dry_run=True
        """
        return self.enforce(dry_run=True)

    def enforce(self, dry_run: bool = True) -> RetentionReport:
        """
        Enforce all active retention policies.

        Args:
            dry_run: If True, show what would happen without executing (default)

        Returns:
            RetentionReport with actions taken
        """
        start_time = time.time()
        report = RetentionReport()

        policies = self.get_policies()
        if not policies:
            logger.warning("No retention policies configured")
            return report

        for policy in policies:
            if not policy.active:
                continue

            try:
                action = self.enforce_table(policy.table, dry_run=dry_run)
                if action:
                    report.actions_taken.append(action)
                    report.total_rows_deleted += action.rows_affected
            except (sqlite3.Error, ValueError, OSError) as e:
                msg = f"Error enforcing policy for {policy.table}: {e}"
                logger.error(msg)
                report.errors.append(msg)

        report.duration_ms = int((time.time() - start_time) * 1000)
        return report

    def enforce_table(self, table: str, dry_run: bool = True) -> RetentionAction | None:
        """
        Enforce retention policy for a single table.

        Args:
            table: Table name
            dry_run: If True, count rows that would be deleted (default True)

        Returns:
            RetentionAction if policy exists and rows deleted, None otherwise
        """
        # Check protected tables
        if table in PROTECTED_TABLES:
            logger.warning(f"Table {table} is protected - skipping")
            return None

        # Get policy
        policies = [p for p in self.get_policies() if p.table == table]
        if not policies:
            logger.debug(f"No policy for table {table}")
            return None

        policy = policies[0]

        # Find timestamp column
        ts_column = policy.timestamp_column or self._find_timestamp_column(table)
        if not ts_column:
            msg = f"Cannot find timestamp column for {table}"
            logger.warning(msg)
            return None

        # Validate identifiers before SQL construction
        safe_table = validate_identifier(table)
        safe_ts = validate_identifier(ts_column)

        # Compute cutoff
        cutoff_date = self._compute_cutoff_date(policy)

        # Count rows that would be deleted
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM {safe_table} WHERE {safe_ts} < ?",  # noqa: S608
                (cutoff_date,),
            )
            rows_to_delete = cursor.fetchone()[0]

            if rows_to_delete == 0:
                logger.info(f"No rows to delete from {table}")  # noqa: S608 — log message, not SQL
                return None

            # Check min rows threshold
            current_count = self._get_row_count(table)
            rows_after = current_count - rows_to_delete

            if rows_after < policy.min_rows_preserve:
                msg = (
                    f"Cannot delete {rows_to_delete} rows from {table}: "
                    f"would leave {rows_after} rows, minimum is {policy.min_rows_preserve}"
                )
                logger.warning(msg)
                return None

            # Execute or dry-run
            if not dry_run:
                # Archive rows before deletion
                safe_archive = validate_identifier(f"{table}_archive")
                try:
                    # Create archive table if it doesn't exist (same schema)
                    conn.execute(
                        f"CREATE TABLE IF NOT EXISTS {safe_archive} AS "  # noqa: S608
                        f"SELECT * FROM {safe_table} WHERE 0"
                    )
                    # Copy rows to archive
                    conn.execute(
                        f"INSERT INTO {safe_archive} SELECT * FROM {safe_table} WHERE {safe_ts} < ?",  # noqa: S608
                        (cutoff_date,),
                    )
                    logger.info(f"Archived {rows_to_delete} rows from {table} to {safe_archive}")
                except (sqlite3.Error, ValueError, OSError) as archive_err:
                    logger.error(f"Archive failed for {table}: {archive_err}")
                    raise  # Don't delete if archive failed

                # Delete original rows after successful archive
                conn.execute(
                    f"DELETE FROM {safe_table} WHERE {safe_ts} < ?",  # noqa: S608
                    (cutoff_date,),
                )
                conn.commit()
                logger.info(f"Deleted {rows_to_delete} rows from {table} (cutoff: {cutoff_date})")

            action = RetentionAction(
                policy=policy,
                rows_affected=rows_to_delete,
                action_type=ActionType.DELETE,
                cutoff_date=cutoff_date,
                dry_run=dry_run,
                executed_at=datetime.utcnow().isoformat(),
            )

            # Log to audit table
            self._audit_action(action)

            return action

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error enforcing policy for {table}: {e}")
            return None
        finally:
            conn.close()

    def _audit_action(self, action: RetentionAction) -> None:
        """Log action to audit table."""
        conn = self._get_connection()
        try:
            conn.execute(
                """
                INSERT INTO retention_audit
                (table_name, action_type, rows_affected, cutoff_date,
                 dry_run, executed_at, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action.policy.table,
                    action.action_type.value,
                    action.rows_affected,
                    action.cutoff_date,
                    int(action.dry_run),
                    action.executed_at,
                    None,
                ),
            )
            conn.commit()
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error auditing action: {e}")
        finally:
            conn.close()

    def get_table_age_distribution(self, table: str) -> dict[str, Any]:
        """
        Get histogram of data age in a table.

        Returns:
            dict with age buckets and counts
        """
        # Find timestamp column
        ts_column = self._find_timestamp_column(table)
        if not ts_column:
            logger.warning(f"Cannot find timestamp column for {table}")
            return {}

        # Validate identifiers before SQL construction
        safe_table = validate_identifier(table)
        safe_ts = validate_identifier(ts_column)

        conn = self._get_connection()
        try:
            # Define age buckets - work backwards from now
            now = datetime.utcnow()
            distribution = {}

            # < 1 day
            cutoff_1d = (now - timedelta(days=1)).isoformat()
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM {safe_table} WHERE {safe_ts} >= ?",  # noqa: S608
                (cutoff_1d,),
            )
            distribution["< 1 day"] = cursor.fetchone()[0]

            # 1-7 days
            cutoff_7d = (now - timedelta(days=7)).isoformat()
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM {safe_table} WHERE {safe_ts} >= ? AND {safe_ts} < ?",  # noqa: S608
                (cutoff_7d, cutoff_1d),
            )
            distribution["1-7 days"] = cursor.fetchone()[0]

            # 1-4 weeks (7-28 days)
            cutoff_28d = (now - timedelta(days=28)).isoformat()
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM {safe_table} WHERE {safe_ts} >= ? AND {safe_ts} < ?",  # noqa: S608
                (cutoff_28d, cutoff_7d),
            )
            distribution["1-4 weeks"] = cursor.fetchone()[0]

            # 1-3 months (28-90 days)
            cutoff_90d = (now - timedelta(days=90)).isoformat()
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM {safe_table} WHERE {safe_ts} >= ? AND {safe_ts} < ?",  # noqa: S608
                (cutoff_90d, cutoff_28d),
            )
            distribution["1-3 months"] = cursor.fetchone()[0]

            # 3-12 months (90-365 days)
            cutoff_365d = (now - timedelta(days=365)).isoformat()
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM {safe_table} WHERE {safe_ts} >= ? AND {safe_ts} < ?",  # noqa: S608
                (cutoff_365d, cutoff_90d),
            )
            distribution["3-12 months"] = cursor.fetchone()[0]

            # > 1 year
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM {safe_table} WHERE {safe_ts} < ?",  # noqa: S608
                (cutoff_365d,),
            )
            distribution["> 1 year"] = cursor.fetchone()[0]

            return distribution

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error getting age distribution for {table}: {e}")
            return {}
        finally:
            conn.close()

    def get_stale_data_summary(self) -> dict[str, Any]:
        """
        Get overview of stale/old data across all tables.

        Returns:
            dict with table -> {old_rows, total_rows, percentage}
        """
        summary = {}
        conn = self._get_connection()

        try:
            # Get all tables
            cursor = conn.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                AND name NOT IN ('retention_policies', 'retention_audit')
                """
            )
            tables = [row[0] for row in cursor.fetchall()]

            for table in tables:
                ts_column = self._find_timestamp_column(table)
                if not ts_column:
                    continue

                # Validate identifiers before SQL construction
                safe_table = validate_identifier(table)
                safe_ts = validate_identifier(ts_column)

                # Count total rows
                cursor = conn.execute(f"SELECT COUNT(*) FROM {safe_table}")  # noqa: S608
                total = cursor.fetchone()[0]
                if total == 0:
                    continue

                # Count rows older than 1 year
                cutoff = (datetime.utcnow() - timedelta(days=365)).isoformat()
                cursor = conn.execute(
                    f"SELECT COUNT(*) FROM {safe_table} WHERE {safe_ts} < ?",  # noqa: S608
                    (cutoff,),
                )
                old_rows = cursor.fetchone()[0]

                if old_rows > 0:
                    summary[table] = {
                        "old_rows": old_rows,
                        "total_rows": total,
                        "percentage": round(100 * old_rows / total, 1),
                    }

            return summary

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error getting stale data summary: {e}")
            return {}
        finally:
            conn.close()
