"""
Priority Scoring — MOH TIME OS

Multi-criteria priority ranking for attention allocation.
Combines health scores, signals, trajectory, data quality, and
recency into a single prioritized queue.

Brief 23 (PS), Task PS-1.1

Designed for Molham's daily review: "what needs my attention first?"
"""

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# Priority weights — how much each factor contributes to final priority
DEFAULT_WEIGHTS = {
    "signal_severity": 0.30,  # Critical signals dominate
    "health_score_inverse": 0.25,  # Lower health = higher priority
    "trajectory_decline": 0.15,  # Declining entities need attention
    "staleness": 0.10,  # Not reviewed recently
    "revenue_weight": 0.10,  # Higher revenue = higher stakes
    "data_quality_penalty": 0.10,  # Low quality data = uncertain, needs check
}


@dataclass
class PriorityFactors:
    """Individual factors contributing to priority score."""

    signal_severity_score: float = 0.0
    health_inverse_score: float = 0.0
    trajectory_score: float = 0.0
    staleness_score: float = 0.0
    revenue_score: float = 0.0
    data_quality_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "signal_severity_score": round(self.signal_severity_score, 3),
            "health_inverse_score": round(self.health_inverse_score, 3),
            "trajectory_score": round(self.trajectory_score, 3),
            "staleness_score": round(self.staleness_score, 3),
            "revenue_score": round(self.revenue_score, 3),
            "data_quality_score": round(self.data_quality_score, 3),
        }


@dataclass
class PrioritizedEntity:
    """An entity with computed priority score and ranking."""

    entity_type: str
    entity_id: str
    entity_name: str = ""
    priority_score: float = 0.0
    priority_rank: int = 0
    urgency_level: str = "normal"  # critical | high | elevated | normal | low
    factors: PriorityFactors = field(default_factory=PriorityFactors)
    reason: str = ""
    health_score: float = 0.0
    active_signals: int = 0

    def to_dict(self) -> dict:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "priority_score": round(self.priority_score, 2),
            "priority_rank": self.priority_rank,
            "urgency_level": self.urgency_level,
            "factors": self.factors.to_dict(),
            "reason": self.reason,
            "health_score": self.health_score,
            "active_signals": self.active_signals,
        }


def classify_urgency(priority_score: float) -> str:
    """Classify urgency level from priority score (0-100)."""
    if priority_score >= 85:
        return "critical"
    if priority_score >= 70:
        return "high"
    if priority_score >= 50:
        return "elevated"
    if priority_score >= 30:
        return "normal"
    return "low"


def compute_signal_severity_score(
    critical_count: int,
    warning_count: int,
    watch_count: int = 0,
) -> float:
    """
    Score based on active signal severity (0-100).

    CRITICAL signals dominate: each adds 30 pts (capped at 100).
    WARNING: 15 pts each. WATCH: 5 pts each.
    """
    score = critical_count * 30 + warning_count * 15 + watch_count * 5
    return min(score, 100.0)


def compute_health_inverse_score(health_score: float) -> float:
    """
    Lower health = higher priority (0-100).

    health=0 → priority=100, health=100 → priority=0
    """
    return max(0.0, min(100.0, 100.0 - health_score))


def compute_trajectory_score(velocity: float) -> float:
    """
    Score declining trajectory (0-100).

    Negative velocity (declining) increases priority.
    Velocity of -10 or worse → 100.
    Positive velocity → 0.
    """
    if velocity >= 0:
        return 0.0
    # Map -10..0 → 100..0
    return min(100.0, abs(velocity) * 10)


def compute_staleness_score(days_since_review: int) -> float:
    """
    Score staleness from days since last review (0-100).

    0-3 days: 0 (recently reviewed)
    3-14 days: linear 0-50
    14-30 days: linear 50-80
    30+ days: 80-100
    """
    if days_since_review <= 3:
        return 0.0
    if days_since_review <= 14:
        return (days_since_review - 3) / 11.0 * 50.0
    if days_since_review <= 30:
        return 50.0 + (days_since_review - 14) / 16.0 * 30.0
    return min(100.0, 80.0 + (days_since_review - 30) / 30.0 * 20.0)


def compute_revenue_score(
    monthly_revenue: float,
    max_revenue: float = 50000.0,
) -> float:
    """
    Higher revenue = higher stakes = higher priority (0-100).

    Scaled relative to max_revenue.
    """
    if max_revenue <= 0:
        return 0.0
    return min(100.0, (monthly_revenue / max_revenue) * 100.0)


def compute_data_quality_score(quality_multiplier: float) -> float:
    """
    Low data quality → higher priority (needs review) (0-100).

    quality=1.0 → 0 (no concern)
    quality=0.0 → 100 (very uncertain data)
    """
    return max(0.0, min(100.0, (1.0 - quality_multiplier) * 100.0))


class PriorityScorer:
    """Multi-criteria priority ranking for attention allocation."""

    def __init__(
        self,
        weights: dict[str, float] | None = None,
    ) -> None:
        self.weights = weights or DEFAULT_WEIGHTS.copy()

    def score_entity(
        self,
        entity_type: str,
        entity_id: str,
        entity_name: str = "",
        health_score: float = 50.0,
        critical_signals: int = 0,
        warning_signals: int = 0,
        watch_signals: int = 0,
        trajectory_velocity: float = 0.0,
        days_since_review: int = 0,
        monthly_revenue: float = 0.0,
        max_revenue: float = 50000.0,
        data_quality: float = 1.0,
    ) -> PrioritizedEntity:
        """Score a single entity's priority."""
        factors = PriorityFactors(
            signal_severity_score=compute_signal_severity_score(
                critical_signals, warning_signals, watch_signals
            ),
            health_inverse_score=compute_health_inverse_score(health_score),
            trajectory_score=compute_trajectory_score(trajectory_velocity),
            staleness_score=compute_staleness_score(days_since_review),
            revenue_score=compute_revenue_score(monthly_revenue, max_revenue),
            data_quality_score=compute_data_quality_score(data_quality),
        )

        # Weighted sum
        priority = (
            factors.signal_severity_score * self.weights.get("signal_severity", 0.3)
            + factors.health_inverse_score * self.weights.get("health_score_inverse", 0.25)
            + factors.trajectory_score * self.weights.get("trajectory_decline", 0.15)
            + factors.staleness_score * self.weights.get("staleness", 0.1)
            + factors.revenue_score * self.weights.get("revenue_weight", 0.1)
            + factors.data_quality_score * self.weights.get("data_quality_penalty", 0.1)
        )

        # Build reason string from top factors
        reason_parts = []
        factor_scores = [
            (factors.signal_severity_score, "active signals"),
            (factors.health_inverse_score, "low health score"),
            (factors.trajectory_score, "declining trajectory"),
            (factors.staleness_score, "not reviewed recently"),
            (factors.revenue_score, "high revenue stake"),
            (factors.data_quality_score, "uncertain data quality"),
        ]
        factor_scores.sort(key=lambda x: x[0], reverse=True)
        for score, label in factor_scores[:2]:
            if score > 20:
                reason_parts.append(label)

        return PrioritizedEntity(
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            priority_score=round(priority, 2),
            urgency_level=classify_urgency(priority),
            factors=factors,
            reason="; ".join(reason_parts) if reason_parts else "no urgent factors",
            health_score=health_score,
            active_signals=critical_signals + warning_signals + watch_signals,
        )

    def rank_entities(
        self,
        entities: list[dict[str, Any]],
    ) -> list[PrioritizedEntity]:
        """
        Score and rank a batch of entities.

        Each entity dict should have keys matching score_entity params:
        entity_type, entity_id, entity_name, health_score,
        critical_signals, warning_signals, etc.
        """
        scored = []
        for e in entities:
            result = self.score_entity(**e)
            scored.append(result)

        # Sort by priority descending
        scored.sort(key=lambda x: x.priority_score, reverse=True)

        # Assign ranks
        for i, entity in enumerate(scored):
            entity.priority_rank = i + 1

        return scored

    def get_attention_queue(
        self,
        entities: list[dict[str, Any]],
        max_items: int = 10,
        min_urgency: str = "normal",
    ) -> list[PrioritizedEntity]:
        """
        Get the top-N entities requiring attention.

        Filters to entities at or above min_urgency level.
        """
        urgency_order = ["critical", "high", "elevated", "normal", "low"]
        min_idx = urgency_order.index(min_urgency) if min_urgency in urgency_order else 3

        ranked = self.rank_entities(entities)
        filtered = [e for e in ranked if urgency_order.index(e.urgency_level) <= min_idx]
        return filtered[:max_items]

    def get_priority_distribution(
        self,
        entities: list[dict[str, Any]],
    ) -> dict[str, int]:
        """Get distribution of urgency levels."""
        ranked = self.rank_entities(entities)
        dist: dict[str, int] = {
            "critical": 0,
            "high": 0,
            "elevated": 0,
            "normal": 0,
            "low": 0,
        }
        for e in ranked:
            dist[e.urgency_level] = dist.get(e.urgency_level, 0) + 1
        return dist
