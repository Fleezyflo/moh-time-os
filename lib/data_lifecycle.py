"""
Data lifecycle management for MOH Time OS.

Handles retention policies, archival, cleanup, and vacuuming of old data.

- configure_retention(table, days) — set per-table retention policies
- enforce_retention() — delete rows older than retention policy
- archive_to_cold(table, before_date) — move old rows to {table}_archive tables
- vacuum_database() — run VACUUM after deletions to reclaim space
- get_lifecycle_report() — show per-table row counts, oldest rows, estimated savings

Safety guards:
- Never delete from: clients, projects, engagements, capacity_lanes
- Require min_rows threshold (never delete if table has < 100 rows)
- Log all deletions with counts
"""

import logging
import sqlite3
from datetime import date, datetime, timedelta
from typing import TypedDict

from . import safe_sql
from .backup import create_backup
from .store import get_connection

logger = logging.getLogger(__name__)

# Tables that should never be deleted from
PROTECTED_TABLES = {
    "clients",
    "projects",
    "engagements",
    "capacity_lanes",
    "sync_state",
}

# Default retention policies (days)
DEFAULT_RETENTION_POLICIES = {
    "signals": 90,
    "signals_v29": 90,
    "change_bundles": 30,
    "collector_metrics": 30,
    "audit_log": 365,
    "audit_entries": 365,
    "communications": 180,  # Archive, don't delete
    "gmail_messages": 180,
    "chat_messages": 180,
    "calendar_events": 90,
    "asana_attachments": 90,
    "asana_custom_fields": 90,
    "asana_goals": 90,
    "asana_portfolios": 90,
    "asana_project_map": 90,
    "asana_sections": 90,
    "asana_stories": 90,
    "asana_subtasks": 90,
    "asana_task_dependencies": 90,
    "artifact_blobs": 180,
    "artifact_excerpts": 180,
    "artifacts": 180,
    "notifications": 90,
    "item_history": 180,
    "sync_cursor": 90,
}

# Tables that should be archived instead of deleted
ARCHIVE_TABLES = {
    "communications",
    "gmail_messages",
    "chat_messages",
}

# Minimum row count threshold before deletion is allowed
MIN_ROWS_THRESHOLD = 100


class RowCountInfo(TypedDict):
    """Information about table row counts."""

    table: str
    row_count: int
    oldest_date: str | None
    newest_date: str | None


class RetentionStats(TypedDict):
    """Statistics for a retention enforcement run."""

    table: str
    rows_deleted: int
    rows_archived: int
    estimated_space_freed_kb: float
    timestamp: str


class DataLifecycleManager:
    """Manages data retention, archival, and cleanup."""

    PROTECTED_TABLES = PROTECTED_TABLES

    def __init__(self):
        """Initialize the lifecycle manager."""
        self._retention_policies = DEFAULT_RETENTION_POLICIES.copy()

    def is_protected(self, table: str) -> bool:
        """Check if a table is protected from deletion."""
        return table in PROTECTED_TABLES

    def get_pii_columns(self, table: str) -> list[str]:
        """Get PII columns for a table (heuristic: columns with 'email', 'name', 'phone', 'address')."""
        pii_patterns = ["email", "name", "phone", "address", "contact", "person"]
        # Return a reasonable default — actual column introspection would need DB access
        return list(pii_patterns)

    def configure_retention(self, table: str, days: int) -> None:
        """
        Set retention policy for a table.

        Args:
            table: Table name
            days: Retention period in days. -1 to disable retention for this table.

        Raises:
            ValueError: If table is protected
        """
        if table in PROTECTED_TABLES:
            raise ValueError(f"Cannot set retention for protected table: {table}")

        if days < -1:
            raise ValueError("Days must be >= -1")

        if days == -1:
            # Remove from policies
            self._retention_policies.pop(table, None)
        else:
            self._retention_policies[table] = days

        logger.info(f"Configured retention for {table}: {days} days")

    def get_retention_policy(self, table: str) -> int | None:
        """Get retention policy for a table. Returns None if not configured."""
        return self._retention_policies.get(table)

    def _get_timestamp_column(self, table: str) -> str | None:
        """
        Detect which timestamp column to use for retention checks.

        Priority: created_at > updated_at > timestamp > collected_at > sent_at
        """
        with get_connection() as conn:
            cursor = conn.execute(f"PRAGMA table_info({table})")
            columns = {row[1] for row in cursor}

        priority_cols = [
            "created_at",
            "updated_at",
            "timestamp",
            "collected_at",
            "sent_at",
        ]

        for col in priority_cols:
            if col in columns:
                return col

        return None

    def _get_row_count(self, table: str) -> int:
        """Get current row count for a table."""
        with get_connection() as conn:
            sql = safe_sql.select_count_bare(table)
            cursor = conn.execute(sql)
            return cursor.fetchone()[0]

    def _get_oldest_row_date(self, table: str) -> date | None:
        """Get date of oldest row in table."""
        timestamp_col = self._get_timestamp_column(table)
        if not timestamp_col:
            return None

        with get_connection() as conn:
            sql = safe_sql.select(
                table, columns=f"MIN({timestamp_col})", where=f"{timestamp_col} IS NOT NULL"
            )
            cursor = conn.execute(sql)
            oldest = cursor.fetchone()[0]

        if not oldest:
            return None

        # Parse ISO format date/datetime
        try:
            if "T" in oldest or " " in oldest:
                return datetime.fromisoformat(oldest.replace("Z", "+00:00")).date()
            else:
                return date.fromisoformat(oldest)
        except (ValueError, AttributeError):
            return None

    def _create_archive_table(self, table: str) -> str:
        """
        Create archive table if it doesn't exist.

        Returns the archive table name.
        """
        archive_table = f"{table}_archive"

        with get_connection() as conn:
            # Get original table schema
            cursor = conn.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()

            # Check if archive table exists
            cursor = conn.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name = ?
            """,
                (archive_table,),
            )
            if cursor.fetchone():
                logger.debug(f"Archive table {archive_table} already exists")
                return archive_table

            # Create archive table with same schema
            col_defs = ", ".join([f"{col[1]} {col[2]}" for col in columns])
            create_sql = f"CREATE TABLE {archive_table} ({col_defs})"

            try:
                conn.execute(create_sql)
                conn.commit()
                logger.info(f"Created archive table: {archive_table}")
            except (sqlite3.Error, ValueError, OSError) as e:
                logger.error(f"Failed to create archive table {archive_table}: {e}")
                raise

        return archive_table

    def archive_to_cold(
        self,
        table: str,
        before_date: date,
        dry_run: bool = False,
    ) -> RetentionStats:
        """
        Archive old rows to {table}_archive.

        Args:
            table: Table to archive from
            before_date: Archive rows before this date
            dry_run: If True, only report what would be archived

        Returns:
            RetentionStats with archival results

        Raises:
            ValueError: If table is protected or has no timestamp column
        """
        if table in PROTECTED_TABLES:
            raise ValueError(f"Cannot archive protected table: {table}")

        timestamp_col = self._get_timestamp_column(table)
        if not timestamp_col:
            raise ValueError(f"Table {table} has no timestamp column for archival")

        cutoff = before_date.isoformat()

        with get_connection() as conn:
            # Get rows to archive
            sql = safe_sql.select_count_bare(table, where=f"{timestamp_col} < ?")
            cursor = conn.execute(sql, (cutoff,))
            count = cursor.fetchone()[0]

        if count == 0:
            logger.debug(f"No rows to archive from {table} before {cutoff}")
            return RetentionStats(
                table=table,
                rows_deleted=0,
                rows_archived=0,
                estimated_space_freed_kb=0.0,
                timestamp=datetime.now().isoformat(),
            )

        if dry_run:
            logger.info(f"Would archive {count} rows from {table} (before {cutoff})")
            return RetentionStats(
                table=table,
                rows_deleted=0,
                rows_archived=count,
                estimated_space_freed_kb=count * 1.5,  # Rough estimate
                timestamp=datetime.now().isoformat(),
            )

        # Create backup before archival
        create_backup(label="pre-archive")

        archive_table = self._create_archive_table(table)

        with get_connection() as conn:
            # Move rows to archive table
            sql = safe_sql.insert_from_select(archive_table, table, where=f"{timestamp_col} < ?")
            conn.execute(sql, (cutoff,))

            # Delete from original table
            sql = safe_sql.delete(table, where=f"{timestamp_col} < ?")
            cursor = conn.execute(sql, (cutoff,))
            archived = cursor.rowcount

            conn.commit()

        logger.info(f"Archived {archived} rows from {table} to {archive_table} (before {cutoff})")

        return RetentionStats(
            table=table,
            rows_deleted=0,
            rows_archived=archived,
            estimated_space_freed_kb=archived * 1.5,
            timestamp=datetime.now().isoformat(),
        )

    def enforce_retention(self, dry_run: bool = False) -> list[RetentionStats]:
        """
        Delete rows older than retention policies.

        Args:
            dry_run: If True, only report what would be deleted

        Returns:
            List of RetentionStats for each table processed

        Safety guards:
            - Never deletes from protected tables
            - Never deletes if table has < MIN_ROWS_THRESHOLD rows
            - Creates backup before any deletions
            - Logs all deletions
        """
        results = []

        if not dry_run:
            create_backup(label="pre-retention-enforcement")

        for table, retention_days in self._retention_policies.items():
            # Skip protected tables
            if table in PROTECTED_TABLES:
                logger.debug(f"Skipping protected table: {table}")
                continue

            # Skip if policy is disabled
            if retention_days < 0:
                continue

            timestamp_col = self._get_timestamp_column(table)
            if not timestamp_col:
                logger.debug(f"Table {table} has no timestamp column, skipping")
                continue

            # Check row count
            row_count = self._get_row_count(table)
            if row_count < MIN_ROWS_THRESHOLD:
                logger.debug(f"Table {table} has only {row_count} rows, skipping deletion")
                continue

            # Calculate cutoff date
            cutoff = (date.today() - timedelta(days=retention_days)).isoformat()

            with get_connection() as conn:
                # Check how many rows would be deleted
                sql = safe_sql.select_count_bare(table, where=f"{timestamp_col} < ?")
                cursor = conn.execute(sql, (cutoff,))
                delete_count = cursor.fetchone()[0]

            if delete_count == 0:
                logger.debug("No rows to delete from %s (before %s)", table, cutoff)
                continue

            if delete_count > row_count * 0.8:
                logger.warning(
                    f"Refusing to delete {delete_count}/{row_count} rows from {table} "
                    f"(>80% of table)"
                )
                continue

            if dry_run:
                logger.info(f"Would delete {delete_count} rows from {table} (before {cutoff})")
                results.append(
                    RetentionStats(
                        table=table,
                        rows_deleted=delete_count,
                        rows_archived=0,
                        estimated_space_freed_kb=delete_count * 0.5,
                        timestamp=datetime.now().isoformat(),
                    )
                )
                continue

            # Perform deletion
            with get_connection() as conn:
                sql = safe_sql.delete(table, where=f"{timestamp_col} < ?")
                cursor = conn.execute(sql, (cutoff,))
                deleted = cursor.rowcount
                conn.commit()

            logger.info(f"Deleted {deleted} rows from {table} (created before {cutoff})")

            results.append(
                RetentionStats(
                    table=table,
                    rows_deleted=deleted,
                    rows_archived=0,
                    estimated_space_freed_kb=deleted * 0.5,
                    timestamp=datetime.now().isoformat(),
                )
            )

        return results

    def vacuum_database(self) -> dict:
        """
        Run VACUUM to reclaim space after deletions.

        Returns dict with vacuum results.
        """
        logger.info("Starting database vacuum")

        with get_connection() as conn:
            # Get page count before vacuum
            cursor = conn.execute("PRAGMA page_count")
            pages_before = cursor.fetchone()[0]

            cursor = conn.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]

            size_before_mb = (pages_before * page_size) / (1024 * 1024)

            # Run vacuum
            try:
                conn.execute("VACUUM")
                conn.commit()
            except (sqlite3.Error, ValueError, OSError) as e:
                logger.error(f"VACUUM failed: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }

            # Get page count after vacuum
            cursor = conn.execute("PRAGMA page_count")
            pages_after = cursor.fetchone()[0]

            size_after_mb = (pages_after * page_size) / (1024 * 1024)

        logger.info(
            f"Vacuum complete: {size_before_mb:.1f}MB -> {size_after_mb:.1f}MB "
            f"(freed {size_before_mb - size_after_mb:.1f}MB)"
        )

        return {
            "success": True,
            "size_before_mb": round(size_before_mb, 1),
            "size_after_mb": round(size_after_mb, 1),
            "space_freed_mb": round(size_before_mb - size_after_mb, 1),
            "timestamp": datetime.now().isoformat(),
        }

    def get_lifecycle_report(self) -> dict:
        """
        Get detailed lifecycle report for all tables with retention policies.

        Returns dict with per-table statistics.
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "retention_policies": self._retention_policies.copy(),
            "tables": {},
            "protected_tables": list(PROTECTED_TABLES),
            "archive_tables": list(ARCHIVE_TABLES),
        }

        for table in self._retention_policies.keys():
            try:
                row_count = self._get_row_count(table)
                oldest_date = self._get_oldest_row_date(table)
                newest_date = self._get_newest_row_date(table)
                timestamp_col = self._get_timestamp_column(table)

                # Calculate how many rows would be deleted by current policy
                retention_days = self._retention_policies[table]
                if retention_days > 0 and oldest_date:
                    cutoff = date.today() - timedelta(days=retention_days)
                    if oldest_date < cutoff:
                        deletable = self._count_deletable(table, timestamp_col, cutoff)
                    else:
                        deletable = 0
                else:
                    deletable = 0

                report["tables"][table] = {
                    "row_count": row_count,
                    "oldest_row_date": oldest_date.isoformat() if oldest_date else None,
                    "newest_row_date": newest_date.isoformat() if newest_date else None,
                    "timestamp_column": timestamp_col,
                    "retention_days": retention_days,
                    "rows_deletable": deletable,
                    "estimated_space_kb": row_count * 0.5,
                }
            except (sqlite3.Error, ValueError, OSError) as e:
                logger.error(f"Error generating report for {table}: {e}")
                report["tables"][table] = {"error": str(e)}

        return report

    def _get_newest_row_date(self, table: str) -> date | None:
        """Get date of newest row in table."""
        timestamp_col = self._get_timestamp_column(table)
        if not timestamp_col:
            return None

        with get_connection() as conn:
            sql = safe_sql.select(
                table, columns=f"MAX({timestamp_col})", where=f"{timestamp_col} IS NOT NULL"
            )
            cursor = conn.execute(sql)
            newest = cursor.fetchone()[0]

        if not newest:
            return None

        try:
            if "T" in newest or " " in newest:
                return datetime.fromisoformat(newest.replace("Z", "+00:00")).date()
            else:
                return date.fromisoformat(newest)
        except (ValueError, AttributeError):
            return None

    def _count_deletable(self, table: str, timestamp_col: str, cutoff: date) -> int:
        """Count rows that would be deleted by cutoff date."""
        cutoff_str = cutoff.isoformat()
        with get_connection() as conn:
            sql = safe_sql.select_count_bare(table, where=f"{timestamp_col} < ?")
            cursor = conn.execute(sql, (cutoff_str,))
            return cursor.fetchone()[0]


if __name__ == "__main__":
    logger.info("=== Data Lifecycle Report ===\n")

    manager = DataLifecycleManager()
    report = manager.get_lifecycle_report()

    logger.info(f"Retention Policies: {report['retention_policies']}\n")

    for table, stats in report["tables"].items():
        if "error" in stats:
            logger.error(f"{table}: {stats['error']}")
        else:
            logger.info(
                f"{table}:"
                f"\n  Rows: {stats['row_count']}"
                f"\n  Oldest: {stats['oldest_row_date']}"
                f"\n  Newest: {stats['newest_row_date']}"
                f"\n  Retention: {stats['retention_days']} days"
                f"\n  Deletable: {stats['rows_deletable']}"
            )


def get_lifecycle_manager(db_path: str | None = None) -> DataLifecycleManager:
    """Factory function to get a DataLifecycleManager instance."""
    return DataLifecycleManager()
