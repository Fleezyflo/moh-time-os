"""
Resolution Queue - Surfaces entities needing manual resolution

Per MASTER_SPEC.md §5:
- Surfaces tasks with broken chains, unlinked projects
- Surfaces communications needing client identity
- Surfaces projects missing brand
- Surfaces invoices missing due_date or client
"""

import logging
import sqlite3
from typing import Any

from lib import paths

logger = logging.getLogger(__name__)


DB_PATH = paths.db_path()


class ResolutionQueue:
    """Manages resolution queue for manual intervention items."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def populate(self) -> dict[str, int]:
        """
        Populate resolution queue with items needing attention.
        Returns counts of items added by type.
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        counts = {}

        try:
            # Task: project unlinked
            cursor.execute("""
                INSERT INTO resolution_queue (entity_type, entity_id, issue_type, priority)
                SELECT 'task', id, 'project_unlinked',
                    CASE
                        WHEN due_date IS NOT NULL
                         AND date(due_date) IS NOT NULL
                         AND date(due_date) < date('now', '+7 days')
                        THEN 1 ELSE 2
                    END
                FROM tasks
                WHERE project_link_status = 'unlinked'
                AND NOT EXISTS (SELECT 1 FROM resolution_queue
                    WHERE entity_type = 'task' AND entity_id = tasks.id
                    AND issue_type = 'project_unlinked' AND resolved_at IS NULL)
            """)
            counts["task_project_unlinked"] = cursor.rowcount

            # Task: project partial (broken chain)
            cursor.execute("""
                INSERT INTO resolution_queue (entity_type, entity_id, issue_type, priority)
                SELECT 'task', id, 'chain_broken', 1
                FROM tasks
                WHERE project_link_status = 'partial'
                AND NOT EXISTS (SELECT 1 FROM resolution_queue
                    WHERE entity_type = 'task' AND entity_id = tasks.id
                    AND issue_type = 'chain_broken' AND resolved_at IS NULL)
            """)
            counts["task_chain_broken"] = cursor.rowcount

            # Task: project linked but client unlinked (sanity alarm)
            cursor.execute("""
                INSERT INTO resolution_queue (entity_type, entity_id, issue_type, priority)
                SELECT 'task', id, 'client_unlinked_unexpected', 1
                FROM tasks
                WHERE project_link_status = 'linked'
                AND client_link_status = 'unlinked'
                AND NOT EXISTS (SELECT 1 FROM resolution_queue
                    WHERE entity_type = 'task' AND entity_id = tasks.id
                    AND issue_type = 'client_unlinked_unexpected' AND resolved_at IS NULL)
            """)
            counts["task_client_unlinked_unexpected"] = cursor.rowcount

            # Project: missing brand (non-internal only)
            cursor.execute("""
                INSERT INTO resolution_queue (entity_type, entity_id, issue_type, priority)
                SELECT 'project', id, 'missing_brand', 1
                FROM projects
                WHERE is_internal = 0 AND brand_id IS NULL
                AND NOT EXISTS (SELECT 1 FROM resolution_queue
                    WHERE entity_type = 'project' AND entity_id = projects.id
                    AND issue_type = 'missing_brand' AND resolved_at IS NULL)
            """)
            counts["project_missing_brand"] = cursor.rowcount

            # Communication: unlinked with commitments
            cursor.execute("""
                INSERT INTO resolution_queue (entity_type, entity_id, issue_type, priority)
                SELECT 'communication', c.id, 'unlinked_with_commitments', 2
                FROM communications c
                WHERE c.link_status = 'unlinked'
                AND EXISTS (SELECT 1 FROM commitments cm WHERE cm.source_id = c.id)
                AND NOT EXISTS (SELECT 1 FROM resolution_queue
                    WHERE entity_type = 'communication' AND entity_id = c.id
                    AND issue_type = 'unlinked_with_commitments' AND resolved_at IS NULL)
            """)
            counts["communication_unlinked_with_commitments"] = cursor.rowcount

            # Invoice: missing due_date (AR only)
            cursor.execute("""
                INSERT INTO resolution_queue (entity_type, entity_id, issue_type, priority)
                SELECT 'invoice', id, 'missing_due_date', 2
                FROM invoices
                WHERE status IN ('sent', 'overdue')
                AND paid_date IS NULL
                AND due_date IS NULL
                AND NOT EXISTS (SELECT 1 FROM resolution_queue
                    WHERE entity_type = 'invoice' AND entity_id = invoices.id
                    AND issue_type = 'missing_due_date' AND resolved_at IS NULL)
            """)
            counts["invoice_missing_due_date"] = cursor.rowcount

            # Invoice: missing client (AR only)
            cursor.execute("""
                INSERT INTO resolution_queue (entity_type, entity_id, issue_type, priority)
                SELECT 'invoice', id, 'missing_client', 2
                FROM invoices
                WHERE status IN ('sent', 'overdue')
                AND paid_date IS NULL
                AND client_id IS NULL
                AND NOT EXISTS (SELECT 1 FROM resolution_queue
                    WHERE entity_type = 'invoice' AND entity_id = invoices.id
                    AND issue_type = 'missing_client' AND resolved_at IS NULL)
            """)
            counts["invoice_missing_client"] = cursor.rowcount

            conn.commit()
            return counts

        finally:
            conn.close()

    def get_pending(self, limit: int = 100) -> list[dict]:
        """Get pending resolution items, ordered by priority then age."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, entity_type, entity_id, issue_type, priority,
                       context, created_at, expires_at
                FROM resolution_queue
                WHERE resolved_at IS NULL
                ORDER BY priority ASC, created_at ASC
                LIMIT ?
            """,
                [limit],
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_by_priority(self, priority: int) -> list[dict]:
        """Get pending items of specific priority."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, entity_type, entity_id, issue_type, priority,
                       context, created_at, expires_at
                FROM resolution_queue
                WHERE resolved_at IS NULL AND priority = ?
                ORDER BY created_at ASC
            """,
                [priority],
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def resolve(self, item_id: str, resolved_by: str, action: str) -> bool:
        """Mark an item as resolved."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE resolution_queue
                SET resolved_at = datetime('now'),
                    resolved_by = ?,
                    resolution_action = ?
                WHERE id = ? AND resolved_at IS NULL
            """,
                [resolved_by, action, item_id],
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_summary(self) -> dict[str, Any]:
        """Get summary of queue state."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            # Count by issue_type
            cursor.execute("""
                SELECT issue_type, priority, COUNT(*) as count
                FROM resolution_queue
                WHERE resolved_at IS NULL
                GROUP BY issue_type, priority
                ORDER BY priority, issue_type
            """)
            by_type = {}
            for row in cursor.fetchall():
                key = f"P{row['priority']}_{row['issue_type']}"
                by_type[key] = row["count"]

            # Total counts
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN priority = 1 THEN 1 ELSE 0 END) as p1,
                    SUM(CASE WHEN priority = 2 THEN 1 ELSE 0 END) as p2
                FROM resolution_queue
                WHERE resolved_at IS NULL
            """)
            totals = dict(cursor.fetchone())

            return {
                "total": totals["total"] or 0,
                "p1": totals["p1"] or 0,
                "p2": totals["p2"] or 0,
                "by_type": by_type,
            }
        finally:
            conn.close()

    def clear_resolved(self, days_old: int = 30) -> int:
        """Remove resolved items older than N days."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM resolution_queue
                WHERE resolved_at IS NOT NULL
                AND resolved_at < datetime('now', ? || ' days')
            """,
                [f"-{days_old}"],
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()


def populate_queue() -> dict[str, int]:
    """Convenience function to populate queue."""
    queue = ResolutionQueue()
    return queue.populate()


def get_queue_summary() -> dict[str, Any]:
    """Convenience function to get queue summary."""
    queue = ResolutionQueue()
    return queue.get_summary()


if __name__ == "__main__":
    logger.info("Populating resolution queue...")
    counts = populate_queue()
    logger.info(f"Items added: {counts}")
    logger.info("\nQueue summary:")
    summary = get_queue_summary()
    logger.info(f"  Total: {summary['total']}")
    logger.info(f"  P1: {summary['p1']}")
    logger.info(f"  P2: {summary['p2']}")
    if summary["by_type"]:
        logger.info("  By type:")
        for k, v in summary["by_type"].items():
            logger.info(f"    {k}: {v}")
