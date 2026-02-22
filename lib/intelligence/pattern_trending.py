"""
Pattern Trending — MOH TIME OS

Classifies pattern direction (new, persistent, resolving, worsening)
by analyzing pattern_snapshots table from Brief 17. Determines whether
patterns are emerging, stable, fading, or deteriorating.

Brief 18 (ID), Task ID-5.1
"""

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, stdev
from typing import Dict, List, Literal, Optional

logger = logging.getLogger(__name__)


@dataclass
class PatternCycleSnapshot:
    """Single cycle snapshot of a pattern."""

    pattern_key: str
    pattern_type: str
    cycle_index: int
    entity_count: int
    evidence_strength: float  # 0.0 to 1.0
    is_present: bool


@dataclass
class PatternTrendAnalysis:
    """Analysis of pattern trend across cycles."""

    pattern_key: str
    pattern_type: str
    current_direction: str  # 'new' | 'persistent' | 'resolving' | 'worsening'
    cycle_presence_history: list[bool]  # [current, -1, -2, -3, -4, -5]
    current_entity_count: int
    avg_entity_count_last_5: float
    current_evidence_strength: float
    avg_evidence_strength_last_5: float
    cycles_present_in_last_5: int

    def to_dict(self) -> dict:
        return {
            "pattern_key": self.pattern_key,
            "pattern_type": self.pattern_type,
            "current_direction": self.current_direction,
            "cycle_presence_history": self.cycle_presence_history,
            "current_entity_count": self.current_entity_count,
            "avg_entity_count_last_5": round(self.avg_entity_count_last_5, 2),
            "current_evidence_strength": round(self.current_evidence_strength, 4),
            "avg_evidence_strength_last_5": round(self.avg_evidence_strength_last_5, 4),
            "cycles_present_in_last_5": self.cycles_present_in_last_5,
        }


class PatternTrendAnalyzer:
    """Analyzes pattern direction from cycle-by-cycle snapshots."""

    def __init__(self, db_path: Path, lookback_cycles: int = 5):
        """
        Initialize analyzer.

        Args:
            db_path: Path to SQLite database.
            lookback_cycles: Number of past cycles to consider (default 5).
        """
        self.db_path = db_path
        self.lookback_cycles = lookback_cycles

    def analyze_pattern_trend(
        self,
        pattern_key: str,
        snapshots: list[PatternCycleSnapshot],
    ) -> PatternTrendAnalysis:
        """
        Classify pattern direction based on cycle history.

        Args:
            pattern_key: Unique pattern identifier.
            snapshots: Ordered snapshots [current, -1, -2, ...].

        Returns:
            PatternTrendAnalysis with direction and metrics.
        """
        if not snapshots:
            return PatternTrendAnalysis(
                pattern_key=pattern_key,
                pattern_type="unknown",
                current_direction="new",
                cycle_presence_history=[],
                current_entity_count=0,
                avg_entity_count_last_5=0.0,
                current_evidence_strength=0.0,
                avg_evidence_strength_last_5=0.0,
                cycles_present_in_last_5=0,
            )

        # Build presence history (most recent first)
        presence = [s.is_present for s in snapshots]

        # Current snapshot
        current = snapshots[0]
        past = snapshots[1 : self.lookback_cycles + 1]

        # Past metrics
        past_entity_counts = [s.entity_count for s in past if s.is_present]
        past_strengths = [s.evidence_strength for s in past if s.is_present]

        avg_entity = mean(past_entity_counts) if past_entity_counts else 0.0
        avg_strength = mean(past_strengths) if past_strengths else 0.0

        past_presence = [s.is_present for s in past]
        cycles_present = sum(1 for p in past_presence if p)

        direction = self._classify_direction(
            presence_history=presence,
            current_entity_count=current.entity_count,
            avg_entity_count_last_5=avg_entity,
            current_evidence_strength=current.evidence_strength,
            avg_evidence_strength_last_5=avg_strength,
        )

        return PatternTrendAnalysis(
            pattern_key=pattern_key,
            pattern_type=current.pattern_type,
            current_direction=direction,
            cycle_presence_history=presence[: self.lookback_cycles + 1],
            current_entity_count=current.entity_count,
            avg_entity_count_last_5=avg_entity,
            current_evidence_strength=current.evidence_strength,
            avg_evidence_strength_last_5=avg_strength,
            cycles_present_in_last_5=cycles_present,
        )

    def get_entity_pattern_trends(
        self,
        entity_type: str,
        entity_id: str,
    ) -> dict[str, PatternTrendAnalysis]:
        """
        Get pattern trends for all active patterns of an entity.

        Returns dict mapping pattern_key -> PatternTrendAnalysis.
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            # Get distinct pattern keys for this entity
            keys = conn.execute(
                """
                SELECT DISTINCT pattern_id as pattern_key
                FROM pattern_snapshots
                WHERE entities_json LIKE ?
                ORDER BY pattern_id
                """,
                (f"%{entity_id}%",),
            ).fetchall()

            results = {}
            for key_row in keys:
                pk = key_row["pattern_key"]
                snapshots = self._load_snapshots_for_pattern(conn, pk)
                if snapshots:
                    results[pk] = self.analyze_pattern_trend(pk, snapshots)

            return results
        finally:
            conn.close()

    def get_patterns_by_direction(
        self,
        direction: str,
        entity_type: str | None = None,
    ) -> list[PatternTrendAnalysis]:
        """
        Get all patterns matching a direction filter.

        Useful for portfolio-wide alerts:
        - direction='worsening' → emerging problems
        - direction='new' → early warning patterns
        - direction='resolving' → positive indicators
        """
        all_trends = self.refresh_all_pattern_trends()
        matching = []
        for trend in all_trends.values():
            if trend.current_direction == direction:
                matching.append(trend)
        return matching

    def refresh_all_pattern_trends(self) -> dict[str, PatternTrendAnalysis]:
        """
        Refresh pattern direction for all patterns.

        Returns dict: pattern_key -> PatternTrendAnalysis.
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            # Get all distinct pattern keys
            keys = conn.execute(
                """
                SELECT DISTINCT pattern_id as pattern_key
                FROM pattern_snapshots
                ORDER BY pattern_id
                """
            ).fetchall()

            results = {}
            for key_row in keys:
                pk = key_row["pattern_key"]
                snapshots = self._load_snapshots_for_pattern(conn, pk)
                if snapshots:
                    results[pk] = self.analyze_pattern_trend(pk, snapshots)
            return results
        finally:
            conn.close()

    def _load_snapshots_for_pattern(
        self,
        conn: sqlite3.Connection,
        pattern_key: str,
    ) -> list[PatternCycleSnapshot]:
        """Load snapshots for a pattern ordered by cycle (most recent first)."""
        rows = conn.execute(
            """
            SELECT pattern_id, pattern_type, cycle_id,
                   COALESCE(json_array_length(entities_json), 0) as entity_count,
                   COALESCE(CAST(json_extract(evidence_json, '$.confidence') AS REAL), 0.5) as evidence_strength
            FROM pattern_snapshots
            WHERE pattern_id = ?
            ORDER BY detected_at DESC
            LIMIT ?
            """,
            (pattern_key, self.lookback_cycles + 1),
        ).fetchall()

        snapshots = []
        for i, row in enumerate(rows):
            snapshots.append(
                PatternCycleSnapshot(
                    pattern_key=row["pattern_id"],
                    pattern_type=row["pattern_type"] or "unknown",
                    cycle_index=i,
                    entity_count=row["entity_count"],
                    evidence_strength=row["evidence_strength"],
                    is_present=True,  # if it's in snapshots, it was detected
                )
            )
        return snapshots

    def _classify_direction(
        self,
        presence_history: list[bool],
        current_entity_count: int,
        avg_entity_count_last_5: float,
        current_evidence_strength: float,
        avg_evidence_strength_last_5: float,
    ) -> str:
        """
        Classify direction based on presence history and metrics.

        - Not in current cycle → 'resolving' (if was in 3+ of last 5)
        - In current only, not in past → 'new'
        - In current + 3+ past → check for 'worsening' or 'persistent'
        """
        if not presence_history:
            return "new"

        in_current = presence_history[0]
        past = presence_history[1:]
        past_present_count = sum(1 for p in past if p)

        if not in_current:
            # Not in current cycle
            if past_present_count >= 3:
                return "resolving"
            return "resolving"  # Even fewer appearances, still resolving

        # In current cycle
        if past_present_count < 1:
            return "new"

        if past_present_count >= 3:
            # Check worsening
            if self._is_worsening(
                current_entity_count,
                avg_entity_count_last_5,
                current_evidence_strength,
                avg_evidence_strength_last_5,
            ):
                return "worsening"
            return "persistent"

        # Present in current + 1-2 past cycles
        if self._is_worsening(
            current_entity_count,
            avg_entity_count_last_5,
            current_evidence_strength,
            avg_evidence_strength_last_5,
        ):
            return "worsening"

        return "new"  # Only appeared recently

    def _is_worsening(
        self,
        current_entity_count: int,
        avg_entity_count: float,
        current_strength: float,
        avg_strength: float,
        threshold: float = 1.2,
    ) -> bool:
        """
        Determine if pattern is worsening based on metrics.

        Returns True if current metrics exceed historical average by
        more than 20%.
        """
        entity_worsening = (
            avg_entity_count > 0 and current_entity_count > avg_entity_count * threshold
        )
        strength_worsening = avg_strength > 0 and current_strength > avg_strength * threshold
        return entity_worsening or strength_worsening
