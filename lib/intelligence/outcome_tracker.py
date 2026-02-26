"""
Signal Outcome Tracking — MOH TIME OS

Records what happens when signals clear, enabling retrospective
analysis of intelligence effectiveness. Classifies resolution type:
- natural: condition improved on its own
- addressed: action was taken
- expired: threshold no longer met
- unknown: unclear resolution

Brief 18 (ID), Task ID-4.1
"""

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SignalOutcome:
    """Record of what happened when a signal cleared."""

    id: str
    signal_key: str
    entity_type: str
    entity_id: str
    signal_type: str
    detected_at: str
    cleared_at: str
    duration_days: float
    health_before: float | None
    health_after: float | None
    health_improved: bool
    actions_taken: list[str] | None
    resolution_type: str  # 'natural' | 'addressed' | 'expired' | 'unknown'
    created_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "signal_key": self.signal_key,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "signal_type": self.signal_type,
            "detected_at": self.detected_at,
            "cleared_at": self.cleared_at,
            "duration_days": round(self.duration_days, 2),
            "health_before": self.health_before,
            "health_after": self.health_after,
            "health_improved": self.health_improved,
            "actions_taken": self.actions_taken,
            "resolution_type": self.resolution_type,
            "created_at": self.created_at,
        }


class OutcomeTracker:
    """Records and analyzes signal outcomes for intelligence effectiveness."""

    def __init__(self, db_path: Path):
        """
        Initialize with database path.

        Args:
            db_path: Path to SQLite database.
        """
        self.db_path = db_path
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Create signal_outcomes table if it doesn't exist."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS signal_outcomes (
                    id TEXT PRIMARY KEY,
                    signal_key TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    detected_at TEXT NOT NULL,
                    cleared_at TEXT NOT NULL,
                    duration_days REAL NOT NULL,
                    health_before REAL,
                    health_after REAL,
                    health_improved INTEGER,
                    actions_taken TEXT,
                    resolution_type TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            # Create indexes if not exist
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_signal_outcomes_entity "
                "ON signal_outcomes(entity_type, entity_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_signal_outcomes_type "
                "ON signal_outcomes(signal_type, resolution_type)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_signal_outcomes_time "
                "ON signal_outcomes(cleared_at DESC)"
            )
            conn.commit()
        finally:
            conn.close()

    def record_outcome(
        self,
        signal_key: str,
        entity_type: str,
        entity_id: str,
        signal_type: str,
        detected_at: datetime,
        cleared_at: datetime,
        health_before: float | None = None,
        health_after: float | None = None,
        actions_taken: list[str] | None = None,
    ) -> SignalOutcome:
        """
        Record a signal outcome when it clears.

        Automatically determines resolution_type based on health changes
        and actions taken.
        """
        duration_days = (cleared_at - detected_at).total_seconds() / 86400.0
        improved = (
            health_after is not None and health_before is not None and health_after > health_before
        )
        resolution = self._determine_resolution_type(health_before, health_after, actions_taken)

        outcome = SignalOutcome(
            id=str(uuid.uuid4()),
            signal_key=signal_key,
            entity_type=entity_type,
            entity_id=entity_id,
            signal_type=signal_type,
            detected_at=detected_at.isoformat(),
            cleared_at=cleared_at.isoformat(),
            duration_days=duration_days,
            health_before=health_before,
            health_after=health_after,
            health_improved=improved,
            actions_taken=actions_taken,
            resolution_type=resolution,
            created_at=datetime.now().isoformat(),
        )

        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """
                INSERT INTO signal_outcomes (
                    id, signal_key, entity_type, entity_id, signal_type,
                    detected_at, cleared_at, duration_days,
                    health_before, health_after, health_improved,
                    actions_taken, resolution_type, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    outcome.id,
                    outcome.signal_key,
                    outcome.entity_type,
                    outcome.entity_id,
                    outcome.signal_type,
                    outcome.detected_at,
                    outcome.cleared_at,
                    outcome.duration_days,
                    outcome.health_before,
                    outcome.health_after,
                    1 if outcome.health_improved else 0,
                    json.dumps(outcome.actions_taken) if outcome.actions_taken else None,
                    outcome.resolution_type,
                    outcome.created_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return outcome

    def get_outcomes_for_entity(
        self,
        entity_type: str,
        entity_id: str,
        days: int = 90,
        limit: int = 100,
    ) -> list[SignalOutcome]:
        """Retrieve outcomes for an entity in past N days."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT * FROM signal_outcomes
                WHERE entity_type = ? AND entity_id = ?
                  AND cleared_at >= date('now', ?)
                ORDER BY cleared_at DESC
                LIMIT ?
                """,
                (entity_type, entity_id, f"-{days} days", limit),
            ).fetchall()
            return [self._row_to_outcome(r) for r in rows]
        finally:
            conn.close()

    def get_outcomes_by_type(
        self,
        signal_type: str,
        days: int = 90,
        limit: int = 100,
    ) -> list[SignalOutcome]:
        """Retrieve outcomes for a signal type across all entities."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT * FROM signal_outcomes
                WHERE signal_type = ?
                  AND cleared_at >= date('now', ?)
                ORDER BY cleared_at DESC
                LIMIT ?
                """,
                (signal_type, f"-{days} days", limit),
            ).fetchall()
            return [self._row_to_outcome(r) for r in rows]
        finally:
            conn.close()

    def get_outcomes_by_resolution(
        self,
        resolution_type: str,
        days: int = 90,
        limit: int = 100,
    ) -> list[SignalOutcome]:
        """Get outcomes filtered by how they were resolved."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT * FROM signal_outcomes
                WHERE resolution_type = ?
                  AND cleared_at >= date('now', ?)
                ORDER BY cleared_at DESC
                LIMIT ?
                """,
                (resolution_type, f"-{days} days", limit),
            ).fetchall()
            return [self._row_to_outcome(r) for r in rows]
        finally:
            conn.close()

    def get_effectiveness_metrics(self, days: int = 90) -> dict:
        """
        Aggregate metrics on signal resolution.

        Returns breakdown by resolution type, improvement rate,
        and per-signal-type metrics.
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT * FROM signal_outcomes
                WHERE cleared_at >= date('now', ?)
                """,
                (f"-{days} days",),
            ).fetchall()

            if not rows:
                return {
                    "total_outcomes": 0,
                    "avg_duration_days": 0.0,
                    "resolution_type_breakdown": {
                        "natural": 0,
                        "addressed": 0,
                        "expired": 0,
                        "unknown": 0,
                    },
                    "improvement_rate": 0.0,
                    "action_success_rate": 0.0,
                    "by_signal_type": {},
                }

            total = len(rows)
            durations = [r["duration_days"] for r in rows]
            avg_duration = sum(durations) / total

            # Resolution type breakdown
            breakdown = {"natural": 0, "addressed": 0, "expired": 0, "unknown": 0}
            for r in rows:
                rt = r["resolution_type"]
                if rt in breakdown:
                    breakdown[rt] += 1

            # Improvement rate
            improved = sum(1 for r in rows if r["health_improved"])
            improvement_rate = improved / total

            # Action success rate (among 'addressed', fraction with health_improved)
            addressed = [r for r in rows if r["resolution_type"] == "addressed"]
            if addressed:
                action_success = sum(1 for r in addressed if r["health_improved"])
                action_success_rate = action_success / len(addressed)
            else:
                action_success_rate = 0.0

            # By signal type
            by_type: dict = {}
            for r in rows:
                st = r["signal_type"]
                if st not in by_type:
                    by_type[st] = {
                        "count": 0,
                        "avg_duration": 0.0,
                        "improved_count": 0,
                        "durations": [],
                    }
                by_type[st]["count"] += 1
                by_type[st]["durations"].append(r["duration_days"])
                if r["health_improved"]:
                    by_type[st]["improved_count"] += 1

            for st in by_type:
                d = by_type[st]["durations"]
                by_type[st]["avg_duration"] = sum(d) / len(d) if d else 0.0
                del by_type[st]["durations"]

            return {
                "total_outcomes": total,
                "avg_duration_days": round(avg_duration, 2),
                "resolution_type_breakdown": breakdown,
                "improvement_rate": round(improvement_rate, 4),
                "action_success_rate": round(action_success_rate, 4),
                "by_signal_type": by_type,
            }
        finally:
            conn.close()

    def _determine_resolution_type(
        self,
        health_before: float | None,
        health_after: float | None,
        actions_taken: list[str] | None,
    ) -> str:
        """Classify how signal was resolved."""
        has_health_data = health_before is not None and health_after is not None
        has_actions = actions_taken is not None and len(actions_taken) > 0

        if has_health_data and health_after > health_before:
            if has_actions:
                return "addressed"
            return "natural"
        if has_actions:
            return "addressed"
        if has_health_data and health_after <= health_before:
            return "expired"
        return "unknown"

    def _row_to_outcome(self, row: sqlite3.Row) -> SignalOutcome:
        """Convert a database row to SignalOutcome."""
        actions_raw = row["actions_taken"]
        actions = json.loads(actions_raw) if actions_raw else None

        return SignalOutcome(
            id=row["id"],
            signal_key=row["signal_key"],
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            signal_type=row["signal_type"],
            detected_at=row["detected_at"],
            cleared_at=row["cleared_at"],
            duration_days=row["duration_days"],
            health_before=row["health_before"],
            health_after=row["health_after"],
            health_improved=bool(row["health_improved"]),
            actions_taken=actions,
            resolution_type=row["resolution_type"],
            created_at=row["created_at"],
        )
