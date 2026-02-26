"""
Audit Log System - Immutable audit trail for data governance actions.

Tracks all Subject Access Requests and data operations for compliance:
- SAR_CREATED: When a subject access request is created
- DATA_ACCESSED: When subject data is searched/accessed
- DATA_DELETED: When subject data is deleted (right to be forgotten)
- DATA_ANONYMIZED: When subject data is anonymized
- DATA_EXPORTED: When subject data is exported

Entries are immutable (cannot be deleted or modified after creation).
"""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    """Single immutable audit log entry."""

    id: str
    timestamp: str
    action: str  # SAR_CREATED, DATA_ACCESSED, DATA_DELETED, DATA_ANONYMIZED, DATA_EXPORTED
    actor: str  # User, system, or service name
    subject_identifier: str  # Email, name, or ID of data subject
    details: dict  # JSON-serializable dict with action-specific details
    ip_address: str | None = None


class AuditLog:
    """
    Immutable audit log for governance operations.

    Maintains complete audit trail of all data access and modification
    for compliance, forensics, and transparency.

    Storage: SQLite table governance_audit_log with no delete/update permissions.
    """

    def __init__(self, db_path: str | Path):
        """Initialize audit log with database connection."""
        self.db_path = Path(db_path)
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_schema(self):
        """Create audit log table if it doesn't exist."""
        try:
            conn = self._get_connection()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS governance_audit_log (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    subject_identifier TEXT NOT NULL,
                    details TEXT NOT NULL,
                    ip_address TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()
            conn.close()
            logger.info("Audit log schema initialized")
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error initializing audit log schema: {e}")
            raise

    def log(
        self,
        action: str,
        actor: str,
        subject: str,
        details: dict,
        ip_address: str | None = None,
    ) -> str:
        """
        Log an audit entry.

        Args:
            action: Action type (SAR_CREATED, DATA_ACCESSED, DATA_DELETED, etc)
            actor: Who performed the action
            subject: Data subject identifier (email, name, ID)
            details: Dict with action-specific details
            ip_address: Optional IP address of requester

        Returns:
            entry_id of the logged entry
        """
        try:
            import json
            import uuid

            entry_id = str(uuid.uuid4())
            timestamp = datetime.utcnow().isoformat()

            conn = self._get_connection()
            conn.execute(
                """
                INSERT INTO governance_audit_log (
                    id, timestamp, action, actor, subject_identifier, details, ip_address, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry_id,
                    timestamp,
                    action,
                    actor,
                    subject,
                    json.dumps(details),
                    ip_address,
                    timestamp,
                ),
            )
            conn.commit()
            conn.close()

            logger.info(
                f"Audit entry logged: id={entry_id}, action={action}, "
                f"actor={actor}, subject={subject}"
            )
            return entry_id

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error logging audit entry: {e}")
            raise

    def get_entries(
        self,
        subject: str | None = None,
        action: str | None = None,
        since: str | None = None,
    ) -> list[AuditEntry]:
        """
        Get audit entries matching filters.

        Args:
            subject: Filter by data subject identifier
            action: Filter by action type
            since: Filter by timestamp >= since (ISO format string)

        Returns:
            List of matching AuditEntry objects
        """
        try:
            import json

            conn = self._get_connection()

            sql = "SELECT * FROM governance_audit_log WHERE 1=1"
            params = []

            if subject:
                sql += " AND subject_identifier = ?"
                params.append(subject)

            if action:
                sql += " AND action = ?"
                params.append(action)

            if since:
                sql += " AND timestamp >= ?"
                params.append(since)

            sql += " ORDER BY timestamp DESC"

            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            conn.close()

            entries = []
            for row in rows:
                entries.append(
                    AuditEntry(
                        id=row["id"],
                        timestamp=row["timestamp"],
                        action=row["action"],
                        actor=row["actor"],
                        subject_identifier=row["subject_identifier"],
                        details=json.loads(row["details"]),
                        ip_address=row["ip_address"],
                    )
                )

            return entries

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error retrieving audit entries: {e}")
            raise

    def get_entry_count(self, action: str | None = None) -> int:
        """
        Get count of audit entries.

        Args:
            action: Optional filter by action type

        Returns:
            Count of matching entries
        """
        try:
            conn = self._get_connection()

            sql = "SELECT COUNT(*) as cnt FROM governance_audit_log WHERE 1=1"
            params = []

            if action:
                sql += " AND action = ?"
                params.append(action)

            cursor = conn.execute(sql, params)
            result = cursor.fetchone()
            conn.close()

            return result["cnt"] if result else 0

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error counting audit entries: {e}")
            raise
