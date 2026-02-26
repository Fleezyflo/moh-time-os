"""
Attention Tracking — MOH TIME OS

Tracks what Molham pays attention to, measures attention debt,
and identifies neglected entities requiring review.

Brief 30 (AT), Task AT-1.1

Complements entity_memory.py with explicit attention economics:
budget, debt, and investment tracking.
"""

import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Attention budget: expected reviews per entity type per week
WEEKLY_ATTENTION_BUDGET = {
    "client": 2,  # Review each client ~2x/week
    "project": 3,  # Review each project ~3x/week
    "person": 1,  # Review each person ~1x/week
}

# Attention debt thresholds
DEBT_LEVELS = {
    "healthy": 0,  # On track
    "minor": 1,  # 1 missed review cycle
    "moderate": 2,  # 2 missed review cycles
    "severe": 4,  # 4+ missed review cycles
}


@dataclass
class AttentionEvent:
    """A recorded attention event."""

    id: str
    entity_type: str
    entity_id: str
    event_type: str  # review | check_in | deep_dive | quick_glance
    duration_minutes: float = 0.0
    notes: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "event_type": self.event_type,
            "duration_minutes": self.duration_minutes,
            "notes": self.notes,
            "created_at": self.created_at,
        }


@dataclass
class AttentionDebt:
    """Attention debt for a single entity."""

    entity_type: str
    entity_id: str
    expected_reviews_per_week: int
    actual_reviews_last_week: int
    debt_weeks: int  # how many weeks behind
    debt_level: str  # healthy | minor | moderate | severe
    last_attention_at: str | None = None
    days_since_attention: int = 0

    def to_dict(self) -> dict:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "expected_reviews_per_week": self.expected_reviews_per_week,
            "actual_reviews_last_week": self.actual_reviews_last_week,
            "debt_weeks": self.debt_weeks,
            "debt_level": self.debt_level,
            "last_attention_at": self.last_attention_at,
            "days_since_attention": self.days_since_attention,
        }


@dataclass
class AttentionSummary:
    """Portfolio-level attention summary."""

    total_entities: int = 0
    entities_with_debt: int = 0
    total_attention_minutes_week: float = 0.0
    avg_attention_per_entity: float = 0.0
    most_attended: list[dict[str, Any]] = field(default_factory=list)
    most_neglected: list[dict[str, Any]] = field(default_factory=list)
    debt_distribution: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "total_entities": self.total_entities,
            "entities_with_debt": self.entities_with_debt,
            "total_attention_minutes_week": round(self.total_attention_minutes_week, 1),
            "avg_attention_per_entity": round(self.avg_attention_per_entity, 1),
            "most_attended": self.most_attended,
            "most_neglected": self.most_neglected,
            "debt_distribution": self.debt_distribution,
        }


def classify_debt_level(debt_weeks: int) -> str:
    """Classify attention debt level from missed weeks."""
    if debt_weeks >= DEBT_LEVELS["severe"]:
        return "severe"
    if debt_weeks >= DEBT_LEVELS["moderate"]:
        return "moderate"
    if debt_weeks >= DEBT_LEVELS["minor"]:
        return "minor"
    return "healthy"


class AttentionTracker:
    """Tracks attention investment and computes attention debt."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._ensure_table()

    def _ensure_table(self) -> None:
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS attention_events (
                    id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    duration_minutes REAL DEFAULT 0,
                    notes TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_attention_entity "
                "ON attention_events(entity_type, entity_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_attention_time ON attention_events(created_at)"
            )
            conn.commit()
        finally:
            conn.close()

    def record_attention(
        self,
        entity_type: str,
        entity_id: str,
        event_type: str = "review",
        duration_minutes: float = 0.0,
        notes: str = "",
    ) -> AttentionEvent:
        """Record an attention event."""
        event = AttentionEvent(
            id=str(uuid.uuid4()),
            entity_type=entity_type,
            entity_id=entity_id,
            event_type=event_type,
            duration_minutes=duration_minutes,
            notes=notes,
            created_at=datetime.now().isoformat(),
        )
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """
                INSERT INTO attention_events
                (id, entity_type, entity_id, event_type, duration_minutes, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.entity_type,
                    event.entity_id,
                    event.event_type,
                    event.duration_minutes,
                    event.notes,
                    event.created_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return event

    def get_attention_debt(
        self,
        entity_type: str,
        entity_id: str,
    ) -> AttentionDebt:
        """Compute attention debt for an entity."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            week_ago = (datetime.now() - timedelta(days=7)).isoformat()

            # Count reviews in last week
            row = conn.execute(
                """
                SELECT COUNT(*) as cnt, MAX(created_at) as latest
                FROM attention_events
                WHERE entity_type = ? AND entity_id = ?
                AND created_at >= ?
                """,
                (entity_type, entity_id, week_ago),
            ).fetchone()

            actual_reviews = row["cnt"] if row else 0
            latest = row["latest"] if row else None

            # Get last attention ever
            if not latest:
                last_row = conn.execute(
                    """
                    SELECT MAX(created_at) as latest
                    FROM attention_events
                    WHERE entity_type = ? AND entity_id = ?
                    """,
                    (entity_type, entity_id),
                ).fetchone()
                latest = last_row["latest"] if last_row else None

            expected = WEEKLY_ATTENTION_BUDGET.get(entity_type, 1)
            max(0, expected - actual_reviews)

            # Compute weeks behind
            days_since = 999
            if latest:
                try:
                    latest_dt = datetime.fromisoformat(latest)
                    days_since = (datetime.now() - latest_dt).days
                except (ValueError, TypeError):
                    pass

            debt_weeks = max(0, days_since // 7)

            return AttentionDebt(
                entity_type=entity_type,
                entity_id=entity_id,
                expected_reviews_per_week=expected,
                actual_reviews_last_week=actual_reviews,
                debt_weeks=debt_weeks,
                debt_level=classify_debt_level(debt_weeks),
                last_attention_at=latest,
                days_since_attention=days_since,
            )
        finally:
            conn.close()

    def get_attention_summary(
        self,
        entity_type: str | None = None,
        days_back: int = 7,
    ) -> AttentionSummary:
        """Get summary of attention allocation."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()

            # Build query
            if entity_type:
                rows = conn.execute(
                    """
                    SELECT entity_type, entity_id,
                           COUNT(*) as review_count,
                           SUM(duration_minutes) as total_minutes,
                           MAX(created_at) as latest
                    FROM attention_events
                    WHERE entity_type = ? AND created_at >= ?
                    GROUP BY entity_type, entity_id
                    ORDER BY total_minutes DESC
                    """,
                    (entity_type, cutoff),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT entity_type, entity_id,
                           COUNT(*) as review_count,
                           SUM(duration_minutes) as total_minutes,
                           MAX(created_at) as latest
                    FROM attention_events
                    WHERE created_at >= ?
                    GROUP BY entity_type, entity_id
                    ORDER BY total_minutes DESC
                    """,
                    (cutoff,),
                ).fetchall()

            entities_data = [dict(r) for r in rows]
            total_entities = len(entities_data)
            total_minutes = sum(e["total_minutes"] or 0 for e in entities_data)

            # Most attended (top 5)
            most_attended = [
                {
                    "entity": f"{e['entity_type']}:{e['entity_id']}",
                    "minutes": e["total_minutes"],
                    "reviews": e["review_count"],
                }
                for e in entities_data[:5]
            ]

            # Most neglected (bottom 5 by reviews)
            by_reviews = sorted(entities_data, key=lambda x: x["review_count"])
            most_neglected = [
                {
                    "entity": f"{e['entity_type']}:{e['entity_id']}",
                    "minutes": e["total_minutes"],
                    "reviews": e["review_count"],
                }
                for e in by_reviews[:5]
            ]

            # Debt distribution
            debt_dist: dict[str, int] = {"healthy": 0, "minor": 0, "moderate": 0, "severe": 0}
            entities_with_debt = 0
            for e in entities_data:
                debt = self.get_attention_debt(e["entity_type"], e["entity_id"])
                debt_dist[debt.debt_level] = debt_dist.get(debt.debt_level, 0) + 1
                if debt.debt_level != "healthy":
                    entities_with_debt += 1

            return AttentionSummary(
                total_entities=total_entities,
                entities_with_debt=entities_with_debt,
                total_attention_minutes_week=total_minutes,
                avg_attention_per_entity=(
                    total_minutes / total_entities if total_entities > 0 else 0.0
                ),
                most_attended=most_attended,
                most_neglected=most_neglected,
                debt_distribution=debt_dist,
            )
        finally:
            conn.close()

    def get_neglected_entities(
        self,
        entity_type: str,
        known_entity_ids: list[str],
        days_threshold: int = 14,
    ) -> list[AttentionDebt]:
        """Find entities that haven't received attention recently."""
        neglected = []
        for eid in known_entity_ids:
            debt = self.get_attention_debt(entity_type, eid)
            if debt.days_since_attention >= days_threshold:
                neglected.append(debt)

        return sorted(neglected, key=lambda d: d.days_since_attention, reverse=True)
