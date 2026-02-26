"""
Subject Access & Right-to-be-Forgotten System - GDPR/privacy compliance.

Implements:
- Subject Access Requests (SAR) for GDPR Article 15 (data access)
- Right to be Forgotten (RTBF) for GDPR Article 17 (data deletion)
- Rectification for GDPR Article 16 (data correction)
- Data Portability for GDPR Article 20

Features:
- Search for all data related to a subject (email, name, client_id)
- Export subject's data in portable format
- Delete subject's data (with audit trail)
- Anonymize instead of delete (for data retention)
- Audit trail of all operations
- Protected table handling (system tables skipped during deletion)
- Dry-run mode for destructive operations
"""

import json
import logging
import os
import re
import sqlite3
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

from lib.data_lifecycle import get_lifecycle_manager
from lib.db import validate_identifier
from lib.governance.anonymizer import Anonymizer
from lib.governance.audit_log import AuditLog

logger = logging.getLogger(__name__)


class RequestType(Enum):
    """Types of subject access requests."""

    ACCESS = "access"
    DELETION = "deletion"
    RECTIFICATION = "rectification"
    PORTABILITY = "portability"


class RequestStatus(Enum):
    """Status of subject access request."""

    PENDING = "pending"
    PROCESSING = "processing"
    FULFILLED = "fulfilled"
    DENIED = "denied"


@dataclass
class SubjectAccessRequest:
    """Subject Access Request tracking."""

    request_id: str
    subject_identifier: str  # Email, name, or ID
    request_type: str  # ACCESS, DELETION, RECTIFICATION, PORTABILITY
    requested_at: str
    fulfilled_at: str | None = None
    status: str = "pending"  # pending, processing, fulfilled, denied
    requested_by: str = "system"
    reason: str | None = None


@dataclass
class SubjectDataReport:
    """Report of data found for a subject."""

    subject_identifier: str
    tables_searched: list[str]
    tables_with_data: list[str]
    total_records: int
    data_by_table: dict = field(default_factory=dict)  # {table: [records]}
    generated_at: str = ""


@dataclass
class DeletionResult:
    """Result of deletion or anonymization operation."""

    subject_identifier: str
    tables_affected: list[str]
    rows_deleted: int
    rows_anonymized: int
    tables_skipped: dict = field(default_factory=dict)  # {table: reason}
    completed_at: str = ""
    audit_log: list[str] = field(default_factory=list)  # List of audit entry IDs


class SubjectAccessManager:
    """
    Manages subject access requests and right-to-be-forgotten operations.

    Handles:
    - Creating and tracking SARs
    - Searching for all data related to a subject
    - Exporting subject data
    - Deleting subject data (with audit)
    - Anonymizing instead of deletion
    - Protected table handling
    """

    def __init__(self, db_path: str | Path):
        """Initialize manager with database path."""
        self.db_path = Path(db_path)
        self.lifecycle = get_lifecycle_manager()
        self.anonymizer = Anonymizer()
        self.audit_log = AuditLog(db_path)
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_schema(self):
        """Create required tables if they don't exist."""
        try:
            conn = self._get_connection()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS subject_access_requests (
                    request_id TEXT PRIMARY KEY,
                    subject_identifier TEXT NOT NULL,
                    request_type TEXT NOT NULL,
                    requested_at TEXT NOT NULL,
                    fulfilled_at TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    requested_by TEXT NOT NULL DEFAULT 'system',
                    reason TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()
            conn.close()
            logger.info("Subject access request schema initialized")
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error initializing subject access schema: {e}")
            raise

    def create_request(
        self,
        subject_identifier: str,
        request_type: str,
        requested_by: str = "system",
        reason: str | None = None,
    ) -> str:
        """
        Create a new subject access request.

        Args:
            subject_identifier: Email, name, or ID of data subject
            request_type: ACCESS, DELETION, RECTIFICATION, or PORTABILITY
            requested_by: User or system that made request
            reason: Optional reason for request

        Returns:
            request_id
        """
        try:
            request_id = str(uuid.uuid4())
            timestamp = datetime.utcnow().isoformat()

            conn = self._get_connection()
            conn.execute(
                """
                INSERT INTO subject_access_requests (
                    request_id, subject_identifier, request_type,
                    requested_at, status, requested_by, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    subject_identifier,
                    request_type,
                    timestamp,
                    "pending",
                    requested_by,
                    reason,
                    timestamp,
                ),
            )
            conn.commit()
            conn.close()

            # Log in audit trail
            self.audit_log.log(
                action="SAR_CREATED",
                actor=requested_by,
                subject=subject_identifier,
                details={
                    "request_id": request_id,
                    "request_type": request_type,
                    "reason": reason,
                },
            )

            logger.info(
                f"Created SAR: request_id={request_id}, "
                f"subject={subject_identifier}, type={request_type}"
            )
            return request_id

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error creating subject access request: {e}")
            raise

    def _find_identifier_columns(self, table: str) -> list[str]:
        """
        Find columns that might contain subject identifiers.

        Looks for email, name, and client_id patterns.
        """
        try:
            safe_table = validate_identifier(table)
            conn = self._get_connection()
            cursor = conn.execute(f"PRAGMA table_info({safe_table})")  # noqa: S608
            columns = cursor.fetchall()
            conn.close()

            identifier_cols = []
            for col in columns:
                col_name = col[1].lower()
                # Match email, name, id patterns
                if any(
                    pattern in col_name
                    for pattern in ["email", "address", "name", "client_id", "person_id"]
                ):
                    identifier_cols.append(col[1])

            return identifier_cols

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error finding identifier columns in {table}: {e}")
            return []

    def _search_table(self, table: str, subject_identifier: str) -> list[dict]:
        """
        Search table for records matching subject identifier.

        Uses email pattern matching, name matching, and ID matching.
        """
        try:
            identifier_cols = self._find_identifier_columns(table)

            if not identifier_cols:
                return []

            safe_table = validate_identifier(table)
            conn = self._get_connection()

            # Build WHERE clause for matching any identifier column
            where_conditions = []
            params = []

            for col in identifier_cols:
                safe_col = validate_identifier(col)
                # Email match
                if "email" in col.lower():
                    where_conditions.append(f'"{safe_col}" = ?')
                    params.append(subject_identifier)
                # Name match (case-insensitive)
                elif "name" in col.lower():
                    where_conditions.append(f'LOWER("{safe_col}") = LOWER(?)')
                    params.append(subject_identifier)
                # ID match
                elif "id" in col.lower():
                    where_conditions.append(f'"{safe_col}" = ?')
                    params.append(subject_identifier)

            if not where_conditions:
                conn.close()
                return []

            where_clause = " OR ".join(where_conditions)
            sql = f"SELECT * FROM {safe_table} WHERE {where_clause}"  # noqa: S608

            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            conn.close()

            # Convert rows to dicts
            return [dict(row) for row in rows]

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error searching table {table}: {e}")
            return []

    def find_subject_data(self, subject_identifier: str) -> SubjectDataReport:
        """
        Find all data related to a subject across all tables.

        Searches:
        - Email columns (exact match)
        - Name columns (case-insensitive match)
        - Client ID columns (exact match)

        Returns:
            SubjectDataReport with all matching records
        """
        try:
            conn = self._get_connection()
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            all_tables = [row[0] for row in cursor.fetchall()]
            conn.close()

            # Filter to known tables (skip sqlite internals)
            all_tables = [
                t
                for t in all_tables
                if not t.startswith("sqlite_")
                and t not in ["governance_audit_log", "subject_access_requests"]
            ]

            data_by_table = {}
            tables_with_data = []
            total_records = 0

            for table in all_tables:
                try:
                    records = self._search_table(table, subject_identifier)
                    if records:
                        data_by_table[table] = records
                        tables_with_data.append(table)
                        total_records += len(records)
                except (sqlite3.Error, ValueError, OSError) as e:
                    logger.warning(f"Error searching {table}: {e}")
                    continue

            timestamp = datetime.utcnow().isoformat()

            # Log data access
            self.audit_log.log(
                action="DATA_ACCESSED",
                actor="system",
                subject=subject_identifier,
                details={
                    "tables_searched": len(all_tables),
                    "tables_with_data": len(tables_with_data),
                    "total_records": total_records,
                },
            )

            return SubjectDataReport(
                subject_identifier=subject_identifier,
                tables_searched=all_tables,
                tables_with_data=tables_with_data,
                total_records=total_records,
                data_by_table=data_by_table,
                generated_at=timestamp,
            )

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error finding subject data: {e}")
            raise

    def export_subject_data(
        self,
        subject_identifier: str,
        format: str = "json",
    ) -> str:
        """
        Export all subject data to a file.

        Args:
            subject_identifier: Subject to export
            format: json, csv, or jsonl

        Returns:
            Path to exported file
        """
        try:
            report = self.find_subject_data(subject_identifier)

            # Generate filename
            safe_subject = re.sub(r"[^\w\-@.]", "_", subject_identifier)
            filename = f"subject_data_{safe_subject}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{format}"
            file_path = os.path.join(tempfile.gettempdir(), filename)

            if format == "json":
                with open(file_path, "w") as f:
                    json.dump(
                        {
                            "subject": subject_identifier,
                            "exported_at": report.generated_at,
                            "tables": report.data_by_table,
                        },
                        f,
                        indent=2,
                        default=str,
                    )
            else:
                logger.error(f"Unsupported export format: {format}")
                raise ValueError(f"Unsupported format: {format}")

            # Log export
            self.audit_log.log(
                action="DATA_EXPORTED",
                actor="system",
                subject=subject_identifier,
                details={
                    "format": format,
                    "file_path": file_path,
                    "record_count": report.total_records,
                },
            )

            logger.info(f"Exported subject data to {file_path}")
            return file_path

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error exporting subject data: {e}")
            raise

    def _get_identifier_value(self, row: dict, table: str) -> str | None:
        """
        Extract the identifier value from a row that matches subject.

        Used to match which identifier was found in deletion queries.
        """
        identifier_cols = self._find_identifier_columns(table)
        for col in identifier_cols:
            if col in row and row[col]:
                return row[col]
        return None

    def delete_subject_data(
        self,
        subject_identifier: str,
        dry_run: bool = True,
    ) -> DeletionResult:
        """
        Delete all data for a subject (right to be forgotten).

        GDPR Article 17 - Right to be Forgotten.

        Args:
            subject_identifier: Subject to delete
            dry_run: If True, only report what would be deleted (default True)

        Returns:
            DeletionResult with deletion details and audit trail
        """
        try:
            report = self.find_subject_data(subject_identifier)
            tables_affected = []
            rows_deleted = 0
            tables_skipped = {}
            audit_entries = []
            timestamp = datetime.utcnow().isoformat()

            for table in report.tables_with_data:
                # Skip protected tables
                if self.lifecycle.is_protected(table):
                    tables_skipped[table] = "Protected system table"
                    continue

                identifier_cols = self._find_identifier_columns(table)
                if not identifier_cols:
                    tables_skipped[table] = "No identifier columns found"
                    continue

                # Build DELETE query with proper parameter binding
                safe_table = validate_identifier(table)
                where_conditions = []
                params = []

                for col in identifier_cols:
                    safe_col = validate_identifier(col)
                    if "email" in col.lower():
                        where_conditions.append(f'"{safe_col}" = ?')
                        params.append(subject_identifier)
                    elif "name" in col.lower():
                        where_conditions.append(f'LOWER("{safe_col}") = LOWER(?)')
                        params.append(subject_identifier)
                    elif "id" in col.lower():
                        where_conditions.append(f'"{safe_col}" = ?')
                        params.append(subject_identifier)

                where_clause = " OR ".join(where_conditions)

                if not dry_run:
                    # Execute delete
                    conn = self._get_connection()
                    conn.execute(
                        f"DELETE FROM {safe_table} WHERE {where_clause}",  # noqa: S608
                        params,
                    )
                    deleted = conn.total_changes
                    conn.commit()
                    conn.close()

                    rows_deleted += deleted
                    tables_affected.append(table)

                    # Log deletion
                    entry_id = self.audit_log.log(
                        action="DATA_DELETED",
                        actor="system",
                        subject=subject_identifier,
                        details={
                            "table": table,
                            "rows_deleted": deleted,
                        },
                    )
                    audit_entries.append(entry_id)
                else:
                    # Count rows that would be deleted
                    conn = self._get_connection()
                    cursor = conn.execute(
                        f"SELECT COUNT(*) as cnt FROM {safe_table} WHERE {where_clause}",  # noqa: S608
                        params,
                    )
                    count = cursor.fetchone()["cnt"]
                    conn.close()

                    if count > 0:
                        rows_deleted += count
                        tables_affected.append(table)

            logger.info(
                f"Subject deletion: subject={subject_identifier}, "
                f"rows_deleted={rows_deleted}, tables_affected={len(tables_affected)}"
            )

            return DeletionResult(
                subject_identifier=subject_identifier,
                tables_affected=tables_affected,
                rows_deleted=rows_deleted,
                rows_anonymized=0,
                tables_skipped=tables_skipped,
                completed_at=timestamp,
                audit_log=audit_entries,
            )

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error deleting subject data: {e}")
            raise

    def anonymize_subject_data(
        self,
        subject_identifier: str,
        dry_run: bool = True,
    ) -> DeletionResult:
        """
        Anonymize all data for a subject instead of deleting.

        Useful for data retention while removing PII.

        Args:
            subject_identifier: Subject to anonymize
            dry_run: If True, only report what would be anonymized (default True)

        Returns:
            DeletionResult with anonymization details
        """
        try:
            report = self.find_subject_data(subject_identifier)
            tables_affected = []
            rows_anonymized = 0
            tables_skipped = {}
            audit_entries = []
            timestamp = datetime.utcnow().isoformat()

            for table in report.tables_with_data:
                # Skip protected tables
                if self.lifecycle.is_protected(table):
                    tables_skipped[table] = "Protected system table"
                    continue

                records = report.data_by_table.get(table, [])
                if not records:
                    continue

                table_rows_anonymized = 0

                for record in records:
                    # Anonymize each PII field
                    pii_columns = self.lifecycle.get_pii_columns(table)

                    if not dry_run:
                        # Build UPDATE query for this record
                        safe_table = validate_identifier(table)
                        updates = []
                        params = []

                        for col, value in record.items():
                            if col in pii_columns and value:
                                safe_col = validate_identifier(col)
                                anon_value = self.anonymizer.anonymize_value(value, "text")
                                updates.append(f'"{safe_col}" = ?')
                                params.append(anon_value)

                        if updates:
                            # Find primary key (usually 'id')
                            pk_col = None
                            for col in record.keys():
                                if col in ["id", "pk", f"{table[:-1]}_id"]:
                                    pk_col = col
                                    break

                            if pk_col and pk_col in record:
                                safe_pk = validate_identifier(pk_col)
                                params.append(record[pk_col])
                                update_clause = ", ".join(updates)
                                conn = self._get_connection()
                                conn.execute(
                                    f'UPDATE {safe_table} SET {update_clause} WHERE "{safe_pk}" = ?',  # noqa: S608
                                    params,
                                )
                                conn.commit()
                                conn.close()
                                rows_anonymized += 1
                                table_rows_anonymized += 1
                    else:
                        # In dry-run, count anonymizable rows
                        rows_anonymized += 1
                        table_rows_anonymized += 1

                if table_rows_anonymized > 0:
                    tables_affected.append(table)
                    if not dry_run:
                        # Log anonymization
                        entry_id = self.audit_log.log(
                            action="DATA_ANONYMIZED",
                            actor="system",
                            subject=subject_identifier,
                            details={
                                "table": table,
                                "rows_anonymized": table_rows_anonymized,
                            },
                        )
                        audit_entries.append(entry_id)

            logger.info(
                f"Subject anonymization: subject={subject_identifier}, "
                f"rows_anonymized={rows_anonymized}, tables_affected={len(tables_affected)}"
            )

            return DeletionResult(
                subject_identifier=subject_identifier,
                tables_affected=tables_affected,
                rows_deleted=0,
                rows_anonymized=rows_anonymized,
                tables_skipped=tables_skipped,
                completed_at=timestamp,
                audit_log=audit_entries,
            )

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error anonymizing subject data: {e}")
            raise

    def get_request_status(self, request_id: str) -> SubjectAccessRequest | None:
        """Get status of a specific subject access request."""
        try:
            conn = self._get_connection()
            cursor = conn.execute(
                "SELECT * FROM subject_access_requests WHERE request_id = ?",
                (request_id,),
            )
            row = cursor.fetchone()
            conn.close()

            if not row:
                return None

            return SubjectAccessRequest(
                request_id=row["request_id"],
                subject_identifier=row["subject_identifier"],
                request_type=row["request_type"],
                requested_at=row["requested_at"],
                fulfilled_at=row["fulfilled_at"],
                status=row["status"],
                requested_by=row["requested_by"],
                reason=row["reason"],
            )

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error getting request status: {e}")
            raise

    def list_requests(self, status: str | None = None) -> list[SubjectAccessRequest]:
        """
        List all subject access requests.

        Args:
            status: Optional filter by status (pending, processing, fulfilled, denied)

        Returns:
            List of SubjectAccessRequest objects
        """
        try:
            conn = self._get_connection()

            sql = "SELECT * FROM subject_access_requests WHERE 1=1"
            params = []

            if status:
                sql += " AND status = ?"
                params.append(status)

            sql += " ORDER BY requested_at DESC"

            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            conn.close()

            requests = []
            for row in rows:
                requests.append(
                    SubjectAccessRequest(
                        request_id=row["request_id"],
                        subject_identifier=row["subject_identifier"],
                        request_type=row["request_type"],
                        requested_at=row["requested_at"],
                        fulfilled_at=row["fulfilled_at"],
                        status=row["status"],
                        requested_by=row["requested_by"],
                        reason=row["reason"],
                    )
                )

            return requests

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error listing requests: {e}")
            raise
