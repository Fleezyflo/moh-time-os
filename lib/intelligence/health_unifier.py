"""
Health Unifier — Single source of truth for entity health scores.

Designates scorecard.py as the authoritative health computation.
Other systems (health_calculator.py, agency_snapshot) read through this
interface instead of computing their own scores.

The score_history table (v30 migration) stores one row per entity per day:
- composite_score: weighted health score (0-100)
- dimensions_json: full dimension breakdown as JSON
- data_completeness: how complete was the data (0-1)

This module:
1. Reads from score_history
2. Provides typed HealthScore results
3. Offers fallback to live scorecard computation when no history exists
"""

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from lib import paths

logger = logging.getLogger(__name__)


@dataclass
class HealthScore:
    """Unified health score for any entity."""

    entity_type: str
    entity_id: str
    composite_score: float
    dimensions: dict  # Full dimension breakdown
    data_completeness: float
    recorded_at: str
    classification: str = ""  # 'excellent' | 'good' | 'fair' | 'poor' | 'critical'

    def to_dict(self) -> dict:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "composite_score": round(self.composite_score, 1),
            "dimensions": self.dimensions,
            "data_completeness": round(self.data_completeness, 2),
            "recorded_at": self.recorded_at,
            "classification": self.classification,
        }


def classify_score(score: float) -> str:
    """Map numeric score to health classification."""
    if score >= 80:
        return "excellent"
    if score >= 65:
        return "good"
    if score >= 50:
        return "fair"
    if score >= 35:
        return "poor"
    return "critical"


class HealthUnifier:
    """
    Unified health score provider.

    Reads from score_history (written by scorecard.py / score recording system).
    Falls back to live scorecard computation if no history exists.
    """

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or paths.db_path()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def get_latest_health(self, entity_type: str, entity_id: str) -> HealthScore | None:
        """
        Get the most recent health score for an entity.

        Returns the latest score from score_history. If none exists,
        falls back to live scorecard computation.
        """
        conn = self._connect()
        try:
            row = conn.execute(
                """SELECT * FROM score_history
                   WHERE entity_type = ? AND entity_id = ?
                   ORDER BY recorded_at DESC LIMIT 1""",
                (entity_type, entity_id),
            ).fetchone()

            if row:
                return self._row_to_health(row)

            # Fallback: compute live from scorecard
            return self._compute_live(entity_type, entity_id)

        except sqlite3.OperationalError as e:
            logger.warning("score_history query failed: %s", e)
            return self._compute_live(entity_type, entity_id)
        finally:
            conn.close()

    def get_health_at_time(
        self, entity_type: str, entity_id: str, at_date: str
    ) -> HealthScore | None:
        """Get health score closest to a specific date."""
        conn = self._connect()
        try:
            row = conn.execute(
                """SELECT * FROM score_history
                   WHERE entity_type = ? AND entity_id = ?
                     AND recorded_date <= ?
                   ORDER BY recorded_date DESC LIMIT 1""",
                (entity_type, entity_id, at_date),
            ).fetchone()

            return self._row_to_health(row) if row else None
        finally:
            conn.close()

    def get_health_trend(
        self, entity_type: str, entity_id: str, days: int = 30
    ) -> list[HealthScore]:
        """Get health scores over time, ordered chronologically."""
        conn = self._connect()
        try:
            since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            rows = conn.execute(
                """SELECT * FROM score_history
                   WHERE entity_type = ? AND entity_id = ?
                     AND recorded_date >= ?
                   ORDER BY recorded_date ASC""",
                (entity_type, entity_id, since),
            ).fetchall()

            return [self._row_to_health(row) for row in rows]
        finally:
            conn.close()

    def get_all_latest_health(self, entity_type: str) -> list[HealthScore]:
        """Get the latest health score for all entities of a type."""
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT sh.* FROM score_history sh
                   INNER JOIN (
                       SELECT entity_type, entity_id, MAX(recorded_at) as max_at
                       FROM score_history
                       WHERE entity_type = ?
                       GROUP BY entity_type, entity_id
                   ) latest ON sh.entity_type = latest.entity_type
                       AND sh.entity_id = latest.entity_id
                       AND sh.recorded_at = latest.max_at""",
                (entity_type,),
            ).fetchall()

            return [self._row_to_health(row) for row in rows]
        finally:
            conn.close()

    def record_health(
        self,
        entity_type: str,
        entity_id: str,
        composite_score: float,
        dimensions: dict,
        data_completeness: float = 1.0,
    ) -> None:
        """
        Record a health score to score_history.

        Uses INSERT OR REPLACE with (entity_type, entity_id, recorded_date) uniqueness.
        """
        conn = self._connect()
        try:
            now = datetime.now()
            conn.execute(
                """INSERT OR REPLACE INTO score_history
                   (entity_type, entity_id, composite_score,
                    dimensions_json, data_completeness,
                    recorded_at, recorded_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    entity_type,
                    entity_id,
                    composite_score,
                    json.dumps(dimensions),
                    data_completeness,
                    now.isoformat(),
                    now.strftime("%Y-%m-%d"),
                ),
            )
            conn.commit()
        except sqlite3.Error as e:
            logger.error(
                "Failed to record health for %s/%s: %s",
                entity_type,
                entity_id,
                e,
            )
            raise
        finally:
            conn.close()

    def _compute_live(self, entity_type: str, entity_id: str) -> HealthScore | None:
        """Fallback: compute score live using scorecard.py."""
        try:
            if entity_type == "client":
                from lib.intelligence.scorecard import score_client

                result = score_client(entity_id, self.db_path)
                if not result or result.get("composite_score") is None:
                    return None

                return HealthScore(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    composite_score=result["composite_score"],
                    dimensions=result.get("dimensions", {}),
                    data_completeness=result.get("data_completeness", 0.0),
                    recorded_at=result.get("scored_at", datetime.now().isoformat()),
                    classification=classify_score(result["composite_score"]),
                )

            elif entity_type == "project":
                from lib.intelligence.scorecard import score_project

                result = score_project(entity_id, self.db_path)
                if not result or result.get("composite_score") is None:
                    return None

                return HealthScore(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    composite_score=result["composite_score"],
                    dimensions=result.get("dimensions", {}),
                    data_completeness=result.get("data_completeness", 0.0),
                    recorded_at=result.get("scored_at", datetime.now().isoformat()),
                    classification=classify_score(result["composite_score"]),
                )

            elif entity_type == "person":
                from lib.intelligence.scorecard import score_person

                result = score_person(entity_id, self.db_path)
                if not result or result.get("composite_score") is None:
                    return None

                return HealthScore(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    composite_score=result["composite_score"],
                    dimensions=result.get("dimensions", {}),
                    data_completeness=result.get("data_completeness", 0.0),
                    recorded_at=result.get("scored_at", datetime.now().isoformat()),
                    classification=classify_score(result["composite_score"]),
                )

            logger.warning("Unsupported entity type for live scoring: %s", entity_type)
            return None

        except Exception as e:
            logger.warning("Live scoring failed for %s/%s: %s", entity_type, entity_id, e)
            return None

    @staticmethod
    def _row_to_health(row: sqlite3.Row) -> HealthScore:
        d = dict(row)
        dims = {}
        if d.get("dimensions_json"):
            try:
                dims = json.loads(d["dimensions_json"])
            except (json.JSONDecodeError, TypeError):
                pass

        score = d.get("composite_score", 0.0)
        return HealthScore(
            entity_type=d["entity_type"],
            entity_id=d["entity_id"],
            composite_score=score,
            dimensions=dims,
            data_completeness=d.get("data_completeness", 0.0),
            recorded_at=d.get("recorded_at", ""),
            classification=classify_score(score),
        )
