"""
Entity Memory — MOH TIME OS

Tracks interaction history and attention levels for entities.
Provides a combined timeline of decisions, signal changes, and reviews.

Brief 22 (SM), Task SM-2.1
"""

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class EntityInteraction:
    """A single recorded interaction with an entity."""

    id: str
    entity_type: str
    entity_id: str
    interaction_type: str  # 'review' | 'action' | 'escalation' | 'check_in' | 'note'
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    source: str = "system"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "interaction_type": self.interaction_type,
            "summary": self.summary,
            "details": self.details,
            "created_at": self.created_at,
            "source": self.source,
        }


@dataclass
class EntityMemoryState:
    """Aggregated memory state for an entity."""

    entity_type: str
    entity_id: str
    review_count: int = 0
    action_count: int = 0
    escalation_count: int = 0
    last_review_at: str | None = None
    last_action_at: str | None = None
    attention_level: str = "normal"  # 'high' | 'normal' | 'low' | 'stale'
    days_since_last_interaction: int = 0

    def to_dict(self) -> dict:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "review_count": self.review_count,
            "action_count": self.action_count,
            "escalation_count": self.escalation_count,
            "last_review_at": self.last_review_at,
            "last_action_at": self.last_action_at,
            "attention_level": self.attention_level,
            "days_since_last_interaction": self.days_since_last_interaction,
        }


# Attention thresholds (days since last interaction)
_ATTENTION_THRESHOLDS = {
    "high": 3,  # interacted within 3 days
    "normal": 14,  # interacted within 14 days
    "low": 30,  # interacted within 30 days
    "stale": 999,  # 30+ days without interaction
}


def classify_attention(days_since: int) -> str:
    """Classify attention level based on days since last interaction."""
    if days_since <= _ATTENTION_THRESHOLDS["high"]:
        return "high"
    if days_since <= _ATTENTION_THRESHOLDS["normal"]:
        return "normal"
    if days_since <= _ATTENTION_THRESHOLDS["low"]:
        return "low"
    return "stale"


class EntityMemory:
    """Persistent entity interaction memory with timeline generation."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._ensure_table()

    def _ensure_table(self) -> None:
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS entity_interactions (
                    id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    interaction_type TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    details_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    source TEXT DEFAULT 'system'
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_interactions_entity "
                "ON entity_interactions(entity_type, entity_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_interactions_time "
                "ON entity_interactions(created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_interactions_type "
                "ON entity_interactions(interaction_type)"
            )
            conn.commit()
        finally:
            conn.close()

    def record_interaction(
        self,
        entity_type: str,
        entity_id: str,
        interaction_type: str,
        summary: str,
        details: dict[str, Any] | None = None,
        source: str = "system",
    ) -> EntityInteraction:
        """Record an interaction with an entity."""
        interaction = EntityInteraction(
            id=str(uuid.uuid4()),
            entity_type=entity_type,
            entity_id=entity_id,
            interaction_type=interaction_type,
            summary=summary,
            details=details or {},
            created_at=datetime.now().isoformat(),
            source=source,
        )

        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """
                INSERT INTO entity_interactions
                (id, entity_type, entity_id, interaction_type, summary,
                 details_json, created_at, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    interaction.id,
                    interaction.entity_type,
                    interaction.entity_id,
                    interaction.interaction_type,
                    interaction.summary,
                    json.dumps(interaction.details),
                    interaction.created_at,
                    interaction.source,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return interaction

    def get_memory_state(
        self,
        entity_type: str,
        entity_id: str,
    ) -> EntityMemoryState:
        """Get aggregated memory state for an entity."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            # Counts by type
            rows = conn.execute(
                """
                SELECT interaction_type, COUNT(*) as cnt,
                       MAX(created_at) as latest
                FROM entity_interactions
                WHERE entity_type = ? AND entity_id = ?
                GROUP BY interaction_type
                """,
                (entity_type, entity_id),
            ).fetchall()

            review_count = 0
            action_count = 0
            escalation_count = 0
            last_review_at = None
            last_action_at = None
            latest_any = None

            for row in rows:
                itype = row["interaction_type"]
                cnt = row["cnt"]
                latest = row["latest"]

                if itype == "review":
                    review_count = cnt
                    last_review_at = latest
                elif itype == "action":
                    action_count = cnt
                    last_action_at = latest
                elif itype == "escalation":
                    escalation_count = cnt

                if latest_any is None or (latest and latest > latest_any):
                    latest_any = latest

            # Days since last interaction
            days_since = 999
            if latest_any:
                try:
                    latest_dt = datetime.fromisoformat(latest_any)
                    days_since = (datetime.now() - latest_dt).days
                except (ValueError, TypeError):
                    pass

            attention = classify_attention(days_since)

            return EntityMemoryState(
                entity_type=entity_type,
                entity_id=entity_id,
                review_count=review_count,
                action_count=action_count,
                escalation_count=escalation_count,
                last_review_at=last_review_at,
                last_action_at=last_action_at,
                attention_level=attention,
                days_since_last_interaction=days_since,
            )
        finally:
            conn.close()

    def get_timeline(
        self,
        entity_type: str,
        entity_id: str,
        limit: int = 50,
        interaction_types: list[str] | None = None,
    ) -> list[EntityInteraction]:
        """Get interaction timeline for an entity."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            if interaction_types:
                placeholders = ",".join("?" for _ in interaction_types)
                rows = conn.execute(
                    f"""
                    SELECT * FROM entity_interactions
                    WHERE entity_type = ? AND entity_id = ?
                    AND interaction_type IN ({placeholders})
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,  # noqa: S608
                    (entity_type, entity_id, *interaction_types, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM entity_interactions
                    WHERE entity_type = ? AND entity_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (entity_type, entity_id, limit),
                ).fetchall()

            return [self._row_to_interaction(r) for r in rows]
        finally:
            conn.close()

    def get_stale_entities(
        self,
        entity_type: str,
        days_threshold: int = 30,
    ) -> list[EntityMemoryState]:
        """Find entities with no interaction in the last N days."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            cutoff = (datetime.now() - timedelta(days=days_threshold)).isoformat()
            rows = conn.execute(
                """
                SELECT entity_type, entity_id,
                       MAX(created_at) as latest
                FROM entity_interactions
                WHERE entity_type = ?
                GROUP BY entity_type, entity_id
                HAVING MAX(created_at) < ?
                ORDER BY latest ASC
                """,
                (entity_type, cutoff),
            ).fetchall()

            results = []
            for row in rows:
                state = self.get_memory_state(row["entity_type"], row["entity_id"])
                results.append(state)
            return results
        finally:
            conn.close()

    def get_interaction_summary(
        self,
        entity_type: str | None = None,
        days_back: int = 30,
    ) -> dict[str, Any]:
        """Get summary of interactions over the last N days."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()

            if entity_type:
                rows = conn.execute(
                    """
                    SELECT interaction_type, COUNT(*) as cnt
                    FROM entity_interactions
                    WHERE entity_type = ? AND created_at >= ?
                    GROUP BY interaction_type
                    ORDER BY cnt DESC
                    """,
                    (entity_type, cutoff),
                ).fetchall()
                total_row = conn.execute(
                    """
                    SELECT COUNT(DISTINCT entity_id) as cnt
                    FROM entity_interactions
                    WHERE entity_type = ? AND created_at >= ?
                    """,
                    (entity_type, cutoff),
                ).fetchone()
            else:
                rows = conn.execute(
                    """
                    SELECT interaction_type, COUNT(*) as cnt
                    FROM entity_interactions
                    WHERE created_at >= ?
                    GROUP BY interaction_type
                    ORDER BY cnt DESC
                    """,
                    (cutoff,),
                ).fetchall()
                total_row = conn.execute(
                    """
                    SELECT COUNT(DISTINCT entity_id) as cnt
                    FROM entity_interactions
                    WHERE created_at >= ?
                    """,
                    (cutoff,),
                ).fetchone()

            by_type = {row["interaction_type"]: row["cnt"] for row in rows}
            total_interactions = sum(by_type.values())
            unique_entities = total_row["cnt"] if total_row else 0

            return {
                "period_days": days_back,
                "total_interactions": total_interactions,
                "unique_entities": unique_entities,
                "by_type": by_type,
            }
        finally:
            conn.close()

    def _row_to_interaction(self, row: sqlite3.Row) -> EntityInteraction:
        return EntityInteraction(
            id=row["id"],
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            interaction_type=row["interaction_type"],
            summary=row["summary"],
            details=json.loads(row["details_json"] or "{}"),
            created_at=row["created_at"],
            source=row["source"],
        )
