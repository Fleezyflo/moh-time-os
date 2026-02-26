"""
Intelligence Audit Trail — MOH TIME OS

Records every intelligence computation for traceability.
Tracks what was computed, inputs used, outputs produced, and timing.

Brief 28 (IO), Task IO-1.1
"""

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    """A single audit trail entry."""

    id: str
    operation: str  # 'health_score' | 'signal_detect' | 'pattern_analyze' | 'correlation' | ...
    entity_type: str
    entity_id: str
    inputs_summary: dict[str, Any]
    outputs_summary: dict[str, Any]
    duration_ms: float
    created_at: str
    status: str = "success"  # 'success' | 'error' | 'partial'
    error_message: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "operation": self.operation,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "inputs_summary": self.inputs_summary,
            "outputs_summary": self.outputs_summary,
            "duration_ms": round(self.duration_ms, 2),
            "created_at": self.created_at,
            "status": self.status,
            "error_message": self.error_message,
        }


class AuditTrail:
    """Persistent audit trail for intelligence operations."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._ensure_table()

    def _ensure_table(self) -> None:
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS intelligence_audit (
                    id TEXT PRIMARY KEY,
                    operation TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    inputs_json TEXT DEFAULT '{}',
                    outputs_json TEXT DEFAULT '{}',
                    duration_ms REAL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    status TEXT DEFAULT 'success',
                    error_message TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_entity "
                "ON intelligence_audit(entity_type, entity_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_operation ON intelligence_audit(operation)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_time ON intelligence_audit(created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_status ON intelligence_audit(status)"
            )
            conn.commit()
        finally:
            conn.close()

    def record(
        self,
        operation: str,
        entity_type: str,
        entity_id: str,
        inputs_summary: dict[str, Any] | None = None,
        outputs_summary: dict[str, Any] | None = None,
        duration_ms: float = 0.0,
        status: str = "success",
        error_message: str | None = None,
    ) -> AuditEntry:
        """Record an audit trail entry."""
        entry = AuditEntry(
            id=str(uuid.uuid4()),
            operation=operation,
            entity_type=entity_type,
            entity_id=entity_id,
            inputs_summary=inputs_summary or {},
            outputs_summary=outputs_summary or {},
            duration_ms=duration_ms,
            created_at=datetime.now().isoformat(),
            status=status,
            error_message=error_message,
        )

        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """
                INSERT INTO intelligence_audit
                (id, operation, entity_type, entity_id, inputs_json, outputs_json,
                 duration_ms, created_at, status, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.id,
                    entry.operation,
                    entry.entity_type,
                    entry.entity_id,
                    json.dumps(entry.inputs_summary),
                    json.dumps(entry.outputs_summary),
                    entry.duration_ms,
                    entry.created_at,
                    entry.status,
                    entry.error_message,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return entry

    def get_entries(
        self,
        entity_type: str | None = None,
        entity_id: str | None = None,
        operation: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """Query audit trail entries with optional filters."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            conditions = []
            params = []

            if entity_type:
                conditions.append("entity_type = ?")
                params.append(entity_type)
            if entity_id:
                conditions.append("entity_id = ?")
                params.append(entity_id)
            if operation:
                conditions.append("operation = ?")
                params.append(operation)
            if status:
                conditions.append("status = ?")
                params.append(status)

            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            params.append(limit)

            rows = conn.execute(
                f"SELECT * FROM intelligence_audit {where} ORDER BY created_at DESC LIMIT ?",  # noqa: S608
                params,
            ).fetchall()

            return [self._row_to_entry(r) for r in rows]
        finally:
            conn.close()

    def get_error_entries(self, limit: int = 50) -> list[AuditEntry]:
        """Get recent error entries."""
        return self.get_entries(status="error", limit=limit)

    def get_performance_stats(
        self,
        operation: str | None = None,
    ) -> dict[str, Any]:
        """Get performance statistics for operations."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            if operation:
                rows = conn.execute(
                    """
                    SELECT operation, COUNT(*) as cnt,
                           AVG(duration_ms) as avg_ms,
                           MAX(duration_ms) as max_ms,
                           MIN(duration_ms) as min_ms,
                           SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors
                    FROM intelligence_audit
                    WHERE operation = ?
                    GROUP BY operation
                    """,
                    (operation,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT operation, COUNT(*) as cnt,
                           AVG(duration_ms) as avg_ms,
                           MAX(duration_ms) as max_ms,
                           MIN(duration_ms) as min_ms,
                           SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors
                    FROM intelligence_audit
                    GROUP BY operation
                    ORDER BY cnt DESC
                    """
                ).fetchall()

            stats = {}
            for row in rows:
                stats[row["operation"]] = {
                    "count": row["cnt"],
                    "avg_duration_ms": round(row["avg_ms"] or 0, 2),
                    "max_duration_ms": round(row["max_ms"] or 0, 2),
                    "min_duration_ms": round(row["min_ms"] or 0, 2),
                    "error_count": row["errors"],
                    "error_rate": round(row["errors"] / row["cnt"], 4) if row["cnt"] > 0 else 0,
                }
            return stats
        finally:
            conn.close()

    def _row_to_entry(self, row: sqlite3.Row) -> AuditEntry:
        return AuditEntry(
            id=row["id"],
            operation=row["operation"],
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            inputs_summary=json.loads(row["inputs_json"] or "{}"),
            outputs_summary=json.loads(row["outputs_json"] or "{}"),
            duration_ms=row["duration_ms"] or 0.0,
            created_at=row["created_at"],
            status=row["status"] or "success",
            error_message=row["error_message"],
        )
