"""
Data Freshness Tracker — MOH TIME OS

Tracks when data was last collected/updated for each entity and source.
Computes freshness scores and identifies stale data sources.

Brief 27 (DQ), Task DQ-1.1
"""

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Freshness thresholds (hours) — how old data can be before quality degrades
DEFAULT_FRESHNESS_THRESHOLDS = {
    "harvest": 48,  # Time data: 2 days
    "email": 24,  # Email data: 1 day
    "project_mgmt": 72,  # PM tool data: 3 days
    "financial": 168,  # Financial data: 7 days
    "default": 72,  # Default: 3 days
}


@dataclass
class FreshnessRecord:
    """Freshness state for one entity + source pair."""

    entity_type: str
    entity_id: str
    source: str  # 'harvest' | 'email' | 'project_mgmt' | 'financial' | etc.
    last_collected_at: str
    hours_since_collection: float
    freshness_score: float  # 1.0 = fresh, 0.0 = completely stale
    is_stale: bool
    threshold_hours: float

    def to_dict(self) -> dict:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "source": self.source,
            "last_collected_at": self.last_collected_at,
            "hours_since_collection": round(self.hours_since_collection, 1),
            "freshness_score": round(self.freshness_score, 4),
            "is_stale": self.is_stale,
            "threshold_hours": self.threshold_hours,
        }


@dataclass
class EntityFreshness:
    """Aggregated freshness across all sources for an entity."""

    entity_type: str
    entity_id: str
    overall_freshness: float  # Min of all source freshness scores
    sources: list[FreshnessRecord]
    stale_sources: list[str]
    freshest_source: str | None = None
    stalest_source: str | None = None

    def to_dict(self) -> dict:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "overall_freshness": round(self.overall_freshness, 4),
            "sources": [s.to_dict() for s in self.sources],
            "stale_sources": self.stale_sources,
            "freshest_source": self.freshest_source,
            "stalest_source": self.stalest_source,
        }


def compute_freshness_score(hours_since: float, threshold_hours: float) -> float:
    """
    Compute freshness score (0.0 to 1.0).

    Score of 1.0 means data was just collected.
    Score decays linearly to 0.0 at 2x the threshold.
    """
    if hours_since <= 0:
        return 1.0
    if hours_since >= threshold_hours * 2:
        return 0.0
    # Linear decay from 1.0 to 0.0 over 2x threshold
    return max(0.0, 1.0 - (hours_since / (threshold_hours * 2)))


class DataFreshnessTracker:
    """Tracks and computes data freshness for entities."""

    def __init__(
        self,
        db_path: Path,
        thresholds: dict[str, float] | None = None,
    ):
        self.db_path = db_path
        self.thresholds = thresholds or DEFAULT_FRESHNESS_THRESHOLDS
        self._ensure_table()

    def _ensure_table(self) -> None:
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS data_freshness (
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    last_collected_at TEXT NOT NULL,
                    record_count INTEGER DEFAULT 0,
                    PRIMARY KEY (entity_type, entity_id, source)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_freshness_source ON data_freshness(source)"
            )
            conn.commit()
        finally:
            conn.close()

    def record_collection(
        self,
        entity_type: str,
        entity_id: str,
        source: str,
        collected_at: datetime | None = None,
        record_count: int = 1,
    ) -> None:
        """Record that data was collected for an entity from a source."""
        ts = (collected_at or datetime.now()).isoformat()
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """
                INSERT INTO data_freshness (entity_type, entity_id, source, last_collected_at, record_count)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(entity_type, entity_id, source)
                DO UPDATE SET last_collected_at = excluded.last_collected_at,
                             record_count = record_count + excluded.record_count
                """,
                (entity_type, entity_id, source, ts, record_count),
            )
            conn.commit()
        finally:
            conn.close()

    def get_freshness(
        self,
        entity_type: str,
        entity_id: str,
        source: str | None = None,
    ) -> list[FreshnessRecord]:
        """Get freshness records for an entity."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            if source:
                rows = conn.execute(
                    "SELECT * FROM data_freshness WHERE entity_type = ? AND entity_id = ? AND source = ?",
                    (entity_type, entity_id, source),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM data_freshness WHERE entity_type = ? AND entity_id = ?",
                    (entity_type, entity_id),
                ).fetchall()

            now = datetime.now()
            records = []
            for row in rows:
                try:
                    collected_dt = datetime.fromisoformat(row["last_collected_at"])
                except (ValueError, TypeError):
                    collected_dt = now

                hours_since = (now - collected_dt).total_seconds() / 3600
                threshold = self.thresholds.get(row["source"], self.thresholds.get("default", 72))
                score = compute_freshness_score(hours_since, threshold)

                records.append(
                    FreshnessRecord(
                        entity_type=row["entity_type"],
                        entity_id=row["entity_id"],
                        source=row["source"],
                        last_collected_at=row["last_collected_at"],
                        hours_since_collection=hours_since,
                        freshness_score=score,
                        is_stale=score < 0.3,
                        threshold_hours=threshold,
                    )
                )

            return records
        finally:
            conn.close()

    def get_entity_freshness(
        self,
        entity_type: str,
        entity_id: str,
    ) -> EntityFreshness:
        """Get aggregated freshness for an entity across all sources."""
        records = self.get_freshness(entity_type, entity_id)

        if not records:
            return EntityFreshness(
                entity_type=entity_type,
                entity_id=entity_id,
                overall_freshness=0.0,
                sources=[],
                stale_sources=[],
            )

        stale = [r.source for r in records if r.is_stale]
        freshest = max(records, key=lambda r: r.freshness_score)
        stalest = min(records, key=lambda r: r.freshness_score)
        overall = min(r.freshness_score for r in records)

        return EntityFreshness(
            entity_type=entity_type,
            entity_id=entity_id,
            overall_freshness=overall,
            sources=records,
            stale_sources=stale,
            freshest_source=freshest.source,
            stalest_source=stalest.source,
        )

    def get_stale_sources(
        self,
        entity_type: str | None = None,
    ) -> list[FreshnessRecord]:
        """Get all stale data sources across entities."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            if entity_type:
                rows = conn.execute(
                    "SELECT * FROM data_freshness WHERE entity_type = ?",
                    (entity_type,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM data_freshness").fetchall()

            now = datetime.now()
            stale = []
            for row in rows:
                try:
                    collected_dt = datetime.fromisoformat(row["last_collected_at"])
                except (ValueError, TypeError):
                    collected_dt = now

                hours_since = (now - collected_dt).total_seconds() / 3600
                threshold = self.thresholds.get(row["source"], self.thresholds.get("default", 72))
                score = compute_freshness_score(hours_since, threshold)

                if score < 0.3:
                    stale.append(
                        FreshnessRecord(
                            entity_type=row["entity_type"],
                            entity_id=row["entity_id"],
                            source=row["source"],
                            last_collected_at=row["last_collected_at"],
                            hours_since_collection=hours_since,
                            freshness_score=score,
                            is_stale=True,
                            threshold_hours=threshold,
                        )
                    )

            stale.sort(key=lambda r: r.freshness_score)
            return stale
        finally:
            conn.close()

    def get_freshness_dashboard(self) -> dict[str, Any]:
        """Get overall freshness dashboard across all entities."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT * FROM data_freshness").fetchall()

            now = datetime.now()
            total = 0
            stale_count = 0
            fresh_count = 0
            scores_by_source: dict[str, list[float]] = {}

            for row in rows:
                total += 1
                try:
                    collected_dt = datetime.fromisoformat(row["last_collected_at"])
                except (ValueError, TypeError):
                    collected_dt = now

                hours_since = (now - collected_dt).total_seconds() / 3600
                threshold = self.thresholds.get(row["source"], self.thresholds.get("default", 72))
                score = compute_freshness_score(hours_since, threshold)

                if score < 0.3:
                    stale_count += 1
                elif score > 0.7:
                    fresh_count += 1

                scores_by_source.setdefault(row["source"], []).append(score)

            avg_by_source = {
                src: round(sum(scores) / len(scores), 4) for src, scores in scores_by_source.items()
            }

            return {
                "total_tracked": total,
                "fresh_count": fresh_count,
                "stale_count": stale_count,
                "avg_freshness_by_source": avg_by_source,
                "overall_freshness": (
                    round(sum(sum(s) for s in scores_by_source.values()) / total, 4)
                    if total > 0
                    else 0.0
                ),
            }
        finally:
            conn.close()
