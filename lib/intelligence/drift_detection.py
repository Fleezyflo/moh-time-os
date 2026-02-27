"""
Intelligence Drift Detection — MOH TIME OS

Detects when intelligence outputs diverge significantly from historical
baselines, indicating either genuine changes or data/model issues.

Brief 28 (IO), Task IO-3.1
"""

import logging
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from math import sqrt
from pathlib import Path
from typing import Any

from lib import safe_sql

logger = logging.getLogger(__name__)


@dataclass
class DriftAlert:
    """A detected drift event."""

    id: str
    metric_name: str  # 'health_score' | 'signal_count' | 'pattern_count' | etc.
    entity_type: str
    entity_id: str
    current_value: float
    baseline_mean: float
    baseline_stddev: float
    deviation_sigma: float  # How many std devs from baseline
    direction: str  # 'up' | 'down'
    severity: str  # 'minor' | 'moderate' | 'major'
    detected_at: str
    explanation: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "metric_name": self.metric_name,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "current_value": round(self.current_value, 2),
            "baseline_mean": round(self.baseline_mean, 2),
            "baseline_stddev": round(self.baseline_stddev, 2),
            "deviation_sigma": round(self.deviation_sigma, 2),
            "direction": self.direction,
            "severity": self.severity,
            "detected_at": self.detected_at,
            "explanation": self.explanation,
        }


# Drift severity thresholds (in std deviations)
DRIFT_THRESHOLDS = {
    "minor": 1.5,
    "moderate": 2.5,
    "major": 3.5,
}


def classify_drift_severity(sigma: float) -> str | None:
    """Classify drift severity based on standard deviations."""
    abs_sigma = abs(sigma)
    if abs_sigma >= DRIFT_THRESHOLDS["major"]:
        return "major"
    if abs_sigma >= DRIFT_THRESHOLDS["moderate"]:
        return "moderate"
    if abs_sigma >= DRIFT_THRESHOLDS["minor"]:
        return "minor"
    return None  # No significant drift


class DriftDetector:
    """Detects drift in intelligence metrics."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        conn = sqlite3.connect(str(self.db_path))
        try:
            # Baseline statistics for metrics
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS drift_baselines (
                    metric_name TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    mean_value REAL NOT NULL,
                    stddev_value REAL NOT NULL,
                    sample_count INTEGER NOT NULL,
                    last_updated TEXT NOT NULL,
                    PRIMARY KEY (metric_name, entity_type, entity_id)
                )
                """
            )
            # Detected drift alerts
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS drift_alerts (
                    id TEXT PRIMARY KEY,
                    metric_name TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    current_value REAL NOT NULL,
                    baseline_mean REAL NOT NULL,
                    baseline_stddev REAL NOT NULL,
                    deviation_sigma REAL NOT NULL,
                    direction TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    detected_at TEXT NOT NULL,
                    explanation TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_drift_time ON drift_alerts(detected_at)")
            conn.commit()
        finally:
            conn.close()

    def update_baseline(
        self,
        metric_name: str,
        entity_type: str,
        entity_id: str,
        values: list[float],
    ) -> None:
        """Update baseline statistics from a list of historical values."""
        if len(values) < 2:
            return

        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
        stddev = sqrt(variance) if variance > 0 else 0.001  # Avoid zero division

        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """
                INSERT INTO drift_baselines (metric_name, entity_type, entity_id,
                    mean_value, stddev_value, sample_count, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(metric_name, entity_type, entity_id)
                DO UPDATE SET mean_value = excluded.mean_value,
                             stddev_value = excluded.stddev_value,
                             sample_count = excluded.sample_count,
                             last_updated = excluded.last_updated
                """,
                (
                    metric_name,
                    entity_type,
                    entity_id,
                    mean,
                    stddev,
                    len(values),
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def check_drift(
        self,
        metric_name: str,
        entity_type: str,
        entity_id: str,
        current_value: float,
    ) -> DriftAlert | None:
        """
        Check if current value has drifted from baseline.

        Returns DriftAlert if drift detected, None otherwise.
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                """
                SELECT mean_value, stddev_value, sample_count
                FROM drift_baselines
                WHERE metric_name = ? AND entity_type = ? AND entity_id = ?
                """,
                (metric_name, entity_type, entity_id),
            ).fetchone()

            if row is None:
                return None  # No baseline yet

            mean = row["mean_value"]
            stddev = row["stddev_value"]
            if stddev == 0:
                stddev = 0.001

            sigma = (current_value - mean) / stddev
            severity = classify_drift_severity(sigma)

            if severity is None:
                return None

            direction = "up" if sigma > 0 else "down"
            explanation = (
                f"{metric_name} for {entity_type}/{entity_id} is {current_value:.2f}, "
                f"which is {abs(sigma):.1f} std devs {direction} from baseline "
                f"(mean={mean:.2f}, stddev={stddev:.2f}, n={row['sample_count']})"
            )

            alert = DriftAlert(
                id=str(uuid.uuid4()),
                metric_name=metric_name,
                entity_type=entity_type,
                entity_id=entity_id,
                current_value=current_value,
                baseline_mean=mean,
                baseline_stddev=stddev,
                deviation_sigma=sigma,
                direction=direction,
                severity=severity,
                detected_at=datetime.now().isoformat(),
                explanation=explanation,
            )

            # Persist alert
            conn.execute(
                """
                INSERT INTO drift_alerts
                (id, metric_name, entity_type, entity_id, current_value,
                 baseline_mean, baseline_stddev, deviation_sigma,
                 direction, severity, detected_at, explanation)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert.id,
                    alert.metric_name,
                    alert.entity_type,
                    alert.entity_id,
                    alert.current_value,
                    alert.baseline_mean,
                    alert.baseline_stddev,
                    alert.deviation_sigma,
                    alert.direction,
                    alert.severity,
                    alert.detected_at,
                    alert.explanation,
                ),
            )
            conn.commit()

            return alert
        finally:
            conn.close()

    def get_recent_alerts(
        self,
        entity_type: str | None = None,
        severity: str | None = None,
        limit: int = 50,
    ) -> list[DriftAlert]:
        """Get recent drift alerts."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            conditions = []
            params = []
            if entity_type:
                conditions.append("entity_type = ?")
                params.append(entity_type)
            if severity:
                conditions.append("severity = ?")
                params.append(severity)

            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            params.append(limit)

            sql = safe_sql.select(
                "drift_alerts",
                where=where if where else None,
                order_by="detected_at DESC",
                suffix="LIMIT ?",
            )
            rows = conn.execute(sql, params).fetchall()

            return [self._row_to_alert(r) for r in rows]
        finally:
            conn.close()

    def get_drift_summary(self) -> dict[str, Any]:
        """Get summary of drift detection activity."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            total = conn.execute("SELECT COUNT(*) as cnt FROM drift_alerts").fetchone()["cnt"]
            by_severity = conn.execute(
                "SELECT severity, COUNT(*) as cnt FROM drift_alerts GROUP BY severity"
            ).fetchall()
            by_metric = conn.execute(
                "SELECT metric_name, COUNT(*) as cnt FROM drift_alerts GROUP BY metric_name ORDER BY cnt DESC"
            ).fetchall()
            baselines = conn.execute("SELECT COUNT(*) as cnt FROM drift_baselines").fetchone()[
                "cnt"
            ]

            return {
                "total_alerts": total,
                "baselines_tracked": baselines,
                "by_severity": {row["severity"]: row["cnt"] for row in by_severity},
                "by_metric": {row["metric_name"]: row["cnt"] for row in by_metric},
            }
        finally:
            conn.close()

    def _row_to_alert(self, row: sqlite3.Row) -> DriftAlert:
        return DriftAlert(
            id=row["id"],
            metric_name=row["metric_name"],
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            current_value=row["current_value"],
            baseline_mean=row["baseline_mean"],
            baseline_stddev=row["baseline_stddev"],
            deviation_sigma=row["deviation_sigma"],
            direction=row["direction"],
            severity=row["severity"],
            detected_at=row["detected_at"],
            explanation=row["explanation"],
        )
