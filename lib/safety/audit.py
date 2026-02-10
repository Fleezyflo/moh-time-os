"""
Audit Logging

Provides append-only audit trail for all DB writes.
Triggered automatically via SQLite triggers.
"""

import sqlite3
from dataclasses import dataclass
from typing import Any


@dataclass
class AuditEntry:
    """A single audit log entry."""

    id: str
    at: str
    actor: str
    request_id: str
    source: str
    git_sha: str
    table_name: str
    op: str
    row_id: str
    before_json: str | None
    after_json: str | None


class AuditLogger:
    """
    Query and analyze the audit log.

    The log is written by SQLite triggers; this class provides query access.
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_changes_for_row(
        self, table_name: str, row_id: str, limit: int = 100
    ) -> list[AuditEntry]:
        """Get all changes for a specific row."""
        cursor = self.conn.execute(
            """
            SELECT id, at, actor, request_id, source, git_sha, table_name, op, row_id, before_json, after_json
            FROM db_write_audit_v1
            WHERE table_name = ? AND row_id = ?
            ORDER BY at DESC
            LIMIT ?
        """,
            (table_name, row_id, limit),
        )

        return [AuditEntry(*row) for row in cursor.fetchall()]

    def get_changes_by_actor(self, actor: str, limit: int = 100) -> list[AuditEntry]:
        """Get all changes made by a specific actor."""
        cursor = self.conn.execute(
            """
            SELECT id, at, actor, request_id, source, git_sha, table_name, op, row_id, before_json, after_json
            FROM db_write_audit_v1
            WHERE actor = ?
            ORDER BY at DESC
            LIMIT ?
        """,
            (actor, limit),
        )

        return [AuditEntry(*row) for row in cursor.fetchall()]

    def get_changes_by_request(self, request_id: str) -> list[AuditEntry]:
        """Get all changes in a specific request."""
        cursor = self.conn.execute(
            """
            SELECT id, at, actor, request_id, source, git_sha, table_name, op, row_id, before_json, after_json
            FROM db_write_audit_v1
            WHERE request_id = ?
            ORDER BY at ASC
        """,
            (request_id,),
        )

        return [AuditEntry(*row) for row in cursor.fetchall()]

    def get_changes_in_window(
        self,
        table_name: str,
        start_at: str,
        end_at: str,
        limit: int = 1000,
    ) -> list[AuditEntry]:
        """Get all changes to a table in a time window."""
        cursor = self.conn.execute(
            """
            SELECT id, at, actor, request_id, source, git_sha, table_name, op, row_id, before_json, after_json
            FROM db_write_audit_v1
            WHERE table_name = ? AND at >= ? AND at <= ?
            ORDER BY at DESC
            LIMIT ?
        """,
            (table_name, start_at, end_at, limit),
        )

        return [AuditEntry(*row) for row in cursor.fetchall()]

    def count_changes_in_window(
        self,
        table_name: str,
        start_at: str,
        end_at: str,
    ) -> dict[str, int]:
        """
        Count changes to a table in a time window, grouped by actor.

        Returns dict of actor -> count.
        Useful for detecting bulk/mystery writes.
        """
        cursor = self.conn.execute(
            """
            SELECT actor, COUNT(*) as count
            FROM db_write_audit_v1
            WHERE table_name = ? AND at >= ? AND at <= ?
            GROUP BY actor
            ORDER BY count DESC
        """,
            (table_name, start_at, end_at),
        )

        return {row[0]: row[1] for row in cursor.fetchall()}

    def get_mystery_writes(
        self,
        table_name: str,
        threshold: int = 10,
        window_seconds: int = 1,
    ) -> list[dict[str, Any]]:
        """
        Detect writes that affected many rows in a short window.

        Returns list of suspicious write clusters.
        """
        # Find requests that touched > threshold rows
        cursor = self.conn.execute(
            """
            SELECT request_id, actor, source, MIN(at) as start_at, MAX(at) as end_at, COUNT(*) as row_count
            FROM db_write_audit_v1
            WHERE table_name = ?
            GROUP BY request_id
            HAVING COUNT(*) > ?
            ORDER BY row_count DESC
        """,
            (table_name, threshold),
        )

        return [
            {
                "request_id": row[0],
                "actor": row[1],
                "source": row[2],
                "start_at": row[3],
                "end_at": row[4],
                "row_count": row[5],
            }
            for row in cursor.fetchall()
        ]


def query_who_changed(conn: sqlite3.Connection, table_name: str, row_id: str) -> str:
    """
    Quick answer to "who changed this row?"

    Returns a human-readable summary.
    """
    logger = AuditLogger(conn)
    entries = logger.get_changes_for_row(table_name, row_id, limit=10)

    if not entries:
        return f"No audit entries found for {table_name}.{row_id}"

    lines = [f"Audit trail for {table_name}.{row_id}:"]
    for e in entries:
        lines.append(
            f"  {e.at} | {e.op} by {e.actor} (source={e.source}, request={e.request_id[:16]}...)"
        )

    return "\n".join(lines)
