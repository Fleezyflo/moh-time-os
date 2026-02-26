"""
Decision Journal — MOH TIME OS

Persistent log of every decision made through the system.
Records decision type, entity, action taken, context, and outcomes.

Brief 22 (SM), Task SM-1.1
"""

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Decision:
    """A recorded decision."""

    id: str
    decision_type: str  # 'signal_dismiss' | 'signal_escalate' | 'signal_acknowledge' | ...
    entity_type: str
    entity_id: str
    action_taken: str  # What was done
    context_snapshot: dict[str, Any]  # State at time of decision
    outcome: str | None = None  # Filled later
    outcome_score: float | None = None  # 0.0 to 1.0
    created_at: str = ""
    source: str = "system"  # 'system' | 'user' | 'automation'

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "decision_type": self.decision_type,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "action_taken": self.action_taken,
            "context_snapshot": self.context_snapshot,
            "outcome": self.outcome,
            "outcome_score": self.outcome_score,
            "created_at": self.created_at,
            "source": self.source,
        }


class DecisionJournal:
    """Persistent decision log with query capabilities."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._ensure_table()

    def _ensure_table(self) -> None:
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS decision_log (
                    id TEXT PRIMARY KEY,
                    decision_type TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    action_taken TEXT NOT NULL,
                    context_json TEXT DEFAULT '{}',
                    outcome TEXT,
                    outcome_score REAL,
                    created_at TEXT NOT NULL,
                    source TEXT DEFAULT 'system'
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_decision_entity "
                "ON decision_log(entity_type, entity_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_decision_type ON decision_log(decision_type)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_decision_time ON decision_log(created_at)")
            conn.commit()
        finally:
            conn.close()

    def record(
        self,
        decision_type: str,
        entity_type: str,
        entity_id: str,
        action_taken: str,
        context_snapshot: dict[str, Any] | None = None,
        source: str = "system",
    ) -> Decision:
        """Record a new decision."""
        decision = Decision(
            id=str(uuid.uuid4()),
            decision_type=decision_type,
            entity_type=entity_type,
            entity_id=entity_id,
            action_taken=action_taken,
            context_snapshot=context_snapshot or {},
            created_at=datetime.now().isoformat(),
            source=source,
        )

        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """
                INSERT INTO decision_log
                (id, decision_type, entity_type, entity_id, action_taken,
                 context_json, created_at, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision.id,
                    decision.decision_type,
                    decision.entity_type,
                    decision.entity_id,
                    decision.action_taken,
                    json.dumps(decision.context_snapshot),
                    decision.created_at,
                    decision.source,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return decision

    def record_outcome(
        self,
        decision_id: str,
        outcome: str,
        outcome_score: float | None = None,
    ) -> None:
        """Update a decision with its outcome."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """
                UPDATE decision_log
                SET outcome = ?, outcome_score = ?
                WHERE id = ?
                """,
                (outcome, outcome_score, decision_id),
            )
            conn.commit()
        finally:
            conn.close()

    def get_decisions_for_entity(
        self,
        entity_type: str,
        entity_id: str,
        limit: int = 50,
    ) -> list[Decision]:
        """Get decisions for a specific entity."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT * FROM decision_log
                WHERE entity_type = ? AND entity_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (entity_type, entity_id, limit),
            ).fetchall()
            return [self._row_to_decision(r) for r in rows]
        finally:
            conn.close()

    def get_decisions_by_type(
        self,
        decision_type: str,
        limit: int = 100,
    ) -> list[Decision]:
        """Get all decisions of a given type."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT * FROM decision_log
                WHERE decision_type = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (decision_type, limit),
            ).fetchall()
            return [self._row_to_decision(r) for r in rows]
        finally:
            conn.close()

    def get_action_distribution(
        self,
        entity_type: str | None = None,
        days_back: int = 30,
    ) -> dict[str, int]:
        """Get distribution of action types over the last N days."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            cutoff = datetime.now().isoformat()[:10]
            if entity_type:
                rows = conn.execute(
                    """
                    SELECT decision_type, COUNT(*) as cnt
                    FROM decision_log
                    WHERE entity_type = ?
                    AND created_at >= date(?, '-' || ? || ' days')
                    GROUP BY decision_type
                    ORDER BY cnt DESC
                    """,
                    (entity_type, cutoff, days_back),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT decision_type, COUNT(*) as cnt
                    FROM decision_log
                    WHERE created_at >= date(?, '-' || ? || ' days')
                    GROUP BY decision_type
                    ORDER BY cnt DESC
                    """,
                    (cutoff, days_back),
                ).fetchall()
            return {row["decision_type"]: row["cnt"] for row in rows}
        finally:
            conn.close()

    def get_effectiveness_report(self) -> dict[str, Any]:
        """Analyze decision outcomes for effectiveness."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            total = conn.execute("SELECT COUNT(*) as cnt FROM decision_log").fetchone()["cnt"]

            with_outcome = conn.execute(
                "SELECT COUNT(*) as cnt FROM decision_log WHERE outcome IS NOT NULL"
            ).fetchone()["cnt"]

            avg_score = conn.execute(
                "SELECT AVG(outcome_score) as avg FROM decision_log WHERE outcome_score IS NOT NULL"
            ).fetchone()["avg"]

            by_type = conn.execute(
                """
                SELECT decision_type,
                       COUNT(*) as cnt,
                       AVG(outcome_score) as avg_score
                FROM decision_log
                WHERE outcome_score IS NOT NULL
                GROUP BY decision_type
                """
            ).fetchall()

            return {
                "total_decisions": total,
                "with_outcome": with_outcome,
                "outcome_rate": with_outcome / total if total > 0 else 0.0,
                "avg_outcome_score": avg_score or 0.0,
                "by_type": {
                    row["decision_type"]: {
                        "count": row["cnt"],
                        "avg_score": round(row["avg_score"], 4) if row["avg_score"] else 0.0,
                    }
                    for row in by_type
                },
            }
        finally:
            conn.close()

    def _row_to_decision(self, row: sqlite3.Row) -> Decision:
        return Decision(
            id=row["id"],
            decision_type=row["decision_type"],
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            action_taken=row["action_taken"],
            context_snapshot=json.loads(row["context_json"] or "{}"),
            outcome=row["outcome"],
            outcome_score=row["outcome_score"],
            created_at=row["created_at"],
            source=row["source"],
        )
