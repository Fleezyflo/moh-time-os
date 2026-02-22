"""
Behavioral Pattern Learning — MOH TIME OS

Analyzes decision journal data to identify recurring behavioral patterns,
generate context hints, and compute action effectiveness metrics.

Brief 22 (SM), Task SM-4.1
"""

import logging
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class BehavioralPattern:
    """A discovered pattern in decision-making behavior."""

    pattern_type: (
        str  # 'frequent_action' | 'entity_preference' | 'timing_pattern' | 'escalation_pattern'
    )
    description: str
    frequency: int
    confidence: float  # 0.0 to 1.0
    entity_type: str | None = None
    entity_id: str | None = None
    supporting_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "pattern_type": self.pattern_type,
            "description": self.description,
            "frequency": self.frequency,
            "confidence": round(self.confidence, 4),
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "supporting_data": self.supporting_data,
        }


@dataclass
class ContextHint:
    """A contextual hint derived from past decisions."""

    hint_type: str  # 'past_action' | 'similar_entity' | 'timing' | 'effectiveness'
    message: str
    relevance: float  # 0.0 to 1.0
    source_decision_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "hint_type": self.hint_type,
            "message": self.message,
            "relevance": round(self.relevance, 4),
            "source_decisions": len(self.source_decision_ids),
        }


@dataclass
class ActionEffectiveness:
    """Effectiveness metrics for a decision type / action combination."""

    decision_type: str
    action_taken: str
    total_uses: int
    outcomes_recorded: int
    avg_outcome_score: float
    success_rate: float  # % of outcomes with score >= 0.6
    avg_days_to_outcome: float

    def to_dict(self) -> dict:
        return {
            "decision_type": self.decision_type,
            "action_taken": self.action_taken,
            "total_uses": self.total_uses,
            "outcomes_recorded": self.outcomes_recorded,
            "avg_outcome_score": round(self.avg_outcome_score, 4),
            "success_rate": round(self.success_rate, 4),
            "avg_days_to_outcome": round(self.avg_days_to_outcome, 1),
        }


class BehavioralPatternAnalyzer:
    """
    Analyzes decision journal data to find behavioral patterns
    and generate context hints.

    Reads from the decision_log table (created by DecisionJournal).
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def discover_patterns(
        self,
        days_back: int = 90,
        min_frequency: int = 3,
    ) -> list[BehavioralPattern]:
        """
        Analyze decision journal to discover recurring patterns.

        Returns patterns sorted by confidence (highest first).
        """
        patterns = []
        patterns.extend(self._find_frequent_actions(days_back, min_frequency))
        patterns.extend(self._find_entity_preferences(days_back, min_frequency))
        patterns.extend(self._find_escalation_patterns(days_back, min_frequency))

        patterns.sort(key=lambda p: p.confidence, reverse=True)
        return patterns

    def _find_frequent_actions(self, days_back: int, min_frequency: int) -> list[BehavioralPattern]:
        """Find frequently taken actions by decision type."""
        conn = self._connect()
        try:
            cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()
            rows = conn.execute(
                """
                SELECT decision_type, action_taken, COUNT(*) as cnt
                FROM decision_log
                WHERE created_at >= ?
                GROUP BY decision_type, action_taken
                HAVING COUNT(*) >= ?
                ORDER BY cnt DESC
                """,
                (cutoff, min_frequency),
            ).fetchall()

            # Get total decisions per type for confidence
            totals = {}
            for row in conn.execute(
                """
                SELECT decision_type, COUNT(*) as cnt
                FROM decision_log
                WHERE created_at >= ?
                GROUP BY decision_type
                """,
                (cutoff,),
            ).fetchall():
                totals[row["decision_type"]] = row["cnt"]

            patterns = []
            for row in rows:
                dtype = row["decision_type"]
                total = totals.get(dtype, 1)
                confidence = row["cnt"] / total if total > 0 else 0.0

                patterns.append(
                    BehavioralPattern(
                        pattern_type="frequent_action",
                        description=(
                            f"When facing '{dtype}', action '{row['action_taken']}' "
                            f"is chosen {row['cnt']} times ({confidence:.0%} of cases)"
                        ),
                        frequency=row["cnt"],
                        confidence=confidence,
                        supporting_data={
                            "decision_type": dtype,
                            "action_taken": row["action_taken"],
                            "total_for_type": total,
                        },
                    )
                )
            return patterns
        finally:
            conn.close()

    def _find_entity_preferences(
        self, days_back: int, min_frequency: int
    ) -> list[BehavioralPattern]:
        """Find entities that receive disproportionate attention."""
        conn = self._connect()
        try:
            cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()
            rows = conn.execute(
                """
                SELECT entity_type, entity_id, COUNT(*) as cnt
                FROM decision_log
                WHERE created_at >= ?
                GROUP BY entity_type, entity_id
                HAVING COUNT(*) >= ?
                ORDER BY cnt DESC
                LIMIT 10
                """,
                (cutoff, min_frequency),
            ).fetchall()

            total_decisions = conn.execute(
                "SELECT COUNT(*) as cnt FROM decision_log WHERE created_at >= ?",
                (cutoff,),
            ).fetchone()["cnt"]

            patterns = []
            for row in rows:
                share = row["cnt"] / total_decisions if total_decisions > 0 else 0.0
                if share > 0.1:  # Entity gets >10% of decisions
                    patterns.append(
                        BehavioralPattern(
                            pattern_type="entity_preference",
                            description=(
                                f"{row['entity_type']} '{row['entity_id']}' receives "
                                f"{share:.0%} of decisions ({row['cnt']}/{total_decisions})"
                            ),
                            frequency=row["cnt"],
                            confidence=share,
                            entity_type=row["entity_type"],
                            entity_id=row["entity_id"],
                            supporting_data={
                                "total_decisions": total_decisions,
                                "entity_share": round(share, 4),
                            },
                        )
                    )
            return patterns
        finally:
            conn.close()

    def _find_escalation_patterns(
        self, days_back: int, min_frequency: int
    ) -> list[BehavioralPattern]:
        """Find entities/types with recurring escalations."""
        conn = self._connect()
        try:
            cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()
            rows = conn.execute(
                """
                SELECT entity_type, entity_id, COUNT(*) as cnt
                FROM decision_log
                WHERE created_at >= ?
                AND decision_type LIKE '%escalat%'
                GROUP BY entity_type, entity_id
                HAVING COUNT(*) >= ?
                ORDER BY cnt DESC
                """,
                (cutoff, min_frequency),
            ).fetchall()

            patterns = []
            for row in rows:
                patterns.append(
                    BehavioralPattern(
                        pattern_type="escalation_pattern",
                        description=(
                            f"{row['entity_type']} '{row['entity_id']}' escalated "
                            f"{row['cnt']} times in {days_back} days"
                        ),
                        frequency=row["cnt"],
                        confidence=min(1.0, row["cnt"] / 10),  # Scale to 10 escalations = 1.0
                        entity_type=row["entity_type"],
                        entity_id=row["entity_id"],
                    )
                )
            return patterns
        finally:
            conn.close()

    def generate_context_hints(
        self,
        entity_type: str,
        entity_id: str,
        decision_type: str | None = None,
        limit: int = 5,
    ) -> list[ContextHint]:
        """
        Generate context hints for an upcoming decision about an entity.

        Hints are based on:
        - Past decisions for this entity
        - Action effectiveness data
        - Similar entity patterns
        """
        hints = []
        hints.extend(self._hints_from_past_decisions(entity_type, entity_id, decision_type))
        hints.extend(self._hints_from_effectiveness(decision_type))

        hints.sort(key=lambda h: h.relevance, reverse=True)
        return hints[:limit]

    def _hints_from_past_decisions(
        self,
        entity_type: str,
        entity_id: str,
        decision_type: str | None,
    ) -> list[ContextHint]:
        """Generate hints from past decisions for this entity."""
        conn = self._connect()
        try:
            if decision_type:
                rows = conn.execute(
                    """
                    SELECT id, decision_type, action_taken, outcome, outcome_score, created_at
                    FROM decision_log
                    WHERE entity_type = ? AND entity_id = ?
                    AND decision_type = ?
                    ORDER BY created_at DESC
                    LIMIT 10
                    """,
                    (entity_type, entity_id, decision_type),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, decision_type, action_taken, outcome, outcome_score, created_at
                    FROM decision_log
                    WHERE entity_type = ? AND entity_id = ?
                    ORDER BY created_at DESC
                    LIMIT 10
                    """,
                    (entity_type, entity_id),
                ).fetchall()

            if not rows:
                return [
                    ContextHint(
                        hint_type="past_action",
                        message=f"No prior decisions recorded for this {entity_type}",
                        relevance=0.3,
                    )
                ]

            hints = []
            # Most recent action
            latest = rows[0]
            hints.append(
                ContextHint(
                    hint_type="past_action",
                    message=(
                        f"Last action for this {entity_type}: "
                        f"'{latest['action_taken']}' ({latest['decision_type']}) "
                        f"on {latest['created_at'][:10]}"
                    ),
                    relevance=0.8,
                    source_decision_ids=[latest["id"]],
                )
            )

            # Action with best outcome
            scored = [r for r in rows if r["outcome_score"] is not None]
            if scored:
                best = max(scored, key=lambda r: r["outcome_score"])
                hints.append(
                    ContextHint(
                        hint_type="effectiveness",
                        message=(
                            f"Best past outcome: '{best['action_taken']}' "
                            f"(score {best['outcome_score']:.2f})"
                        ),
                        relevance=0.7,
                        source_decision_ids=[best["id"]],
                    )
                )

            return hints
        finally:
            conn.close()

    def _hints_from_effectiveness(
        self,
        decision_type: str | None,
    ) -> list[ContextHint]:
        """Generate hints from overall action effectiveness."""
        if not decision_type:
            return []

        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT action_taken,
                       COUNT(*) as total,
                       AVG(outcome_score) as avg_score,
                       SUM(CASE WHEN outcome_score >= 0.6 THEN 1 ELSE 0 END) as successes
                FROM decision_log
                WHERE decision_type = ?
                AND outcome_score IS NOT NULL
                GROUP BY action_taken
                HAVING COUNT(*) >= 2
                ORDER BY avg_score DESC
                LIMIT 3
                """,
                (decision_type,),
            ).fetchall()

            hints = []
            for row in rows:
                success_rate = row["successes"] / row["total"] if row["total"] > 0 else 0
                hints.append(
                    ContextHint(
                        hint_type="effectiveness",
                        message=(
                            f"For '{decision_type}': action '{row['action_taken']}' "
                            f"has {success_rate:.0%} success rate "
                            f"(avg score {row['avg_score']:.2f}, n={row['total']})"
                        ),
                        relevance=0.6,
                    )
                )
            return hints
        finally:
            conn.close()

    def get_action_effectiveness(
        self,
        decision_type: str | None = None,
        days_back: int = 90,
    ) -> list[ActionEffectiveness]:
        """
        Compute effectiveness metrics for each action type.

        Returns sorted by success_rate descending.
        """
        conn = self._connect()
        try:
            cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()

            if decision_type:
                rows = conn.execute(
                    """
                    SELECT decision_type, action_taken,
                           COUNT(*) as total,
                           SUM(CASE WHEN outcome IS NOT NULL THEN 1 ELSE 0 END) as with_outcome,
                           AVG(CASE WHEN outcome_score IS NOT NULL THEN outcome_score END) as avg_score,
                           SUM(CASE WHEN outcome_score >= 0.6 THEN 1 ELSE 0 END) as successes
                    FROM decision_log
                    WHERE decision_type = ?
                    AND created_at >= ?
                    GROUP BY decision_type, action_taken
                    ORDER BY avg_score DESC
                    """,
                    (decision_type, cutoff),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT decision_type, action_taken,
                           COUNT(*) as total,
                           SUM(CASE WHEN outcome IS NOT NULL THEN 1 ELSE 0 END) as with_outcome,
                           AVG(CASE WHEN outcome_score IS NOT NULL THEN outcome_score END) as avg_score,
                           SUM(CASE WHEN outcome_score >= 0.6 THEN 1 ELSE 0 END) as successes
                    FROM decision_log
                    WHERE created_at >= ?
                    GROUP BY decision_type, action_taken
                    ORDER BY avg_score DESC
                    """,
                    (cutoff,),
                ).fetchall()

            results = []
            for row in rows:
                with_outcome = row["with_outcome"] or 0
                success_rate = row["successes"] / with_outcome if with_outcome > 0 else 0.0
                results.append(
                    ActionEffectiveness(
                        decision_type=row["decision_type"],
                        action_taken=row["action_taken"],
                        total_uses=row["total"],
                        outcomes_recorded=with_outcome,
                        avg_outcome_score=row["avg_score"] or 0.0,
                        success_rate=success_rate,
                        avg_days_to_outcome=0.0,  # Would need timestamp diff; omitting for now
                    )
                )

            results.sort(key=lambda r: r.success_rate, reverse=True)
            return results
        finally:
            conn.close()

    def get_decision_distribution(
        self,
        days_back: int = 30,
    ) -> dict[str, Any]:
        """Get distribution of decisions by type, action, and source."""
        conn = self._connect()
        try:
            cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()

            by_type = conn.execute(
                """
                SELECT decision_type, COUNT(*) as cnt
                FROM decision_log
                WHERE created_at >= ?
                GROUP BY decision_type
                ORDER BY cnt DESC
                """,
                (cutoff,),
            ).fetchall()

            by_source = conn.execute(
                """
                SELECT source, COUNT(*) as cnt
                FROM decision_log
                WHERE created_at >= ?
                GROUP BY source
                ORDER BY cnt DESC
                """,
                (cutoff,),
            ).fetchall()

            total = conn.execute(
                "SELECT COUNT(*) as cnt FROM decision_log WHERE created_at >= ?",
                (cutoff,),
            ).fetchone()["cnt"]

            return {
                "period_days": days_back,
                "total_decisions": total,
                "by_type": {row["decision_type"]: row["cnt"] for row in by_type},
                "by_source": {row["source"]: row["cnt"] for row in by_source},
            }
        finally:
            conn.close()
