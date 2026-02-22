"""
Entity Intelligence Profiles — MOH TIME OS

Unified EntityIntelligenceProfile synthesizing all intelligence
dimensions (health, signals, patterns, costs, risks, narrative)
for a single entity.

Brief 18 (ID), Task ID-3.1
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional

from lib.intelligence.narrative import NarrativeBuilder

logger = logging.getLogger(__name__)


class AttentionLevel(Enum):
    """Entity attention priority level."""

    URGENT = "urgent"
    ELEVATED = "elevated"
    NORMAL = "normal"
    STABLE = "stable"


@dataclass
class ScoreDimension:
    """One dimension of entity health."""

    dimension: str  # 'delivery' | 'communication' | 'financial' | 'engagement' | 'structural'
    score: float  # 0.0 to 100.0
    trend: str  # 'improving' | 'stable' | 'declining'

    def to_dict(self) -> dict:
        return {
            "dimension": self.dimension,
            "score": round(self.score, 2),
            "trend": self.trend,
        }


@dataclass
class SignalSnapshot:
    """Current state of one active signal."""

    signal_key: str
    signal_type: str
    severity: str  # 'CRITICAL' | 'WARNING' | 'WATCH'
    detected_at: str
    latest_value: float

    def to_dict(self) -> dict:
        return {
            "signal_key": self.signal_key,
            "signal_type": self.signal_type,
            "severity": self.severity,
            "detected_at": self.detected_at,
            "latest_value": self.latest_value,
        }


@dataclass
class ProfilePatternSnapshot:
    """Current state of one active pattern."""

    pattern_key: str
    pattern_type: str
    direction: str  # 'new' | 'persistent' | 'resolving' | 'worsening'
    entity_count: int
    confidence: float

    def to_dict(self) -> dict:
        return {
            "pattern_key": self.pattern_key,
            "pattern_type": self.pattern_type,
            "direction": self.direction,
            "entity_count": self.entity_count,
            "confidence": round(self.confidence, 4),
        }


@dataclass
class ProfileCompoundRisk:
    """Cross-domain risk from correlation of signals."""

    correlation_id: str
    title: str
    signals: list[str]
    severity: str
    confidence: float
    is_structural: bool

    def to_dict(self) -> dict:
        return {
            "correlation_id": self.correlation_id,
            "title": self.title,
            "signals": self.signals,
            "severity": self.severity,
            "confidence": round(self.confidence, 4),
            "is_structural": self.is_structural,
        }


@dataclass
class CostProfile:
    """Cost-to-serve and profitability metrics."""

    effort_score: float
    profitability_band: str
    estimated_cost_per_month: float
    cost_drivers: list[str]

    def to_dict(self) -> dict:
        return {
            "effort_score": round(self.effort_score, 2),
            "profitability_band": self.profitability_band,
            "estimated_cost_per_month": round(self.estimated_cost_per_month, 2),
            "cost_drivers": self.cost_drivers,
        }


@dataclass
class EntityIntelligenceProfile:
    """Complete intelligence view of an entity."""

    # Identity
    entity_type: str
    entity_id: str
    entity_name: str

    # Health
    health_score: float
    health_classification: str
    score_dimensions: list[ScoreDimension]

    # Signals
    active_signals: list[SignalSnapshot]
    signal_trend: str

    # Patterns
    active_patterns: list[ProfilePatternSnapshot]
    pattern_direction: str

    # Trajectory
    trajectory_direction: str
    projected_score_30d: float
    confidence_band: tuple

    # Costs
    cost_profile: CostProfile

    # Cross-domain risks
    compound_risks: list[ProfileCompoundRisk] = field(default_factory=list)
    cross_domain_issues: list[str] = field(default_factory=list)

    # Narrative
    narrative: str = ""
    attention_level: AttentionLevel = AttentionLevel.STABLE
    recommended_actions: list[str] = field(default_factory=list)

    # Metadata
    as_of: str = ""
    next_review_date: str | None = None

    def to_dict(self) -> dict:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "health_score": round(self.health_score, 2),
            "health_classification": self.health_classification,
            "score_dimensions": [d.to_dict() for d in self.score_dimensions],
            "active_signals": [s.to_dict() for s in self.active_signals],
            "signal_trend": self.signal_trend,
            "active_patterns": [p.to_dict() for p in self.active_patterns],
            "pattern_direction": self.pattern_direction,
            "trajectory_direction": self.trajectory_direction,
            "projected_score_30d": round(self.projected_score_30d, 2),
            "confidence_band": (
                round(self.confidence_band[0], 2),
                round(self.confidence_band[1], 2),
            ),
            "cost_profile": self.cost_profile.to_dict(),
            "compound_risks": [r.to_dict() for r in self.compound_risks],
            "cross_domain_issues": self.cross_domain_issues,
            "narrative": self.narrative,
            "attention_level": self.attention_level.value,
            "recommended_actions": self.recommended_actions,
            "as_of": self.as_of,
            "next_review_date": self.next_review_date,
        }


# ===========================================================================
# Health classification and attention logic
# ===========================================================================

# Dimension weights by entity type
DIMENSION_WEIGHTS = {
    "client": {
        "delivery": 0.30,
        "communication": 0.25,
        "financial": 0.25,
        "engagement": 0.20,
    },
    "project": {
        "delivery": 0.40,
        "communication": 0.20,
        "financial": 0.20,
        "engagement": 0.20,
    },
    "person": {
        "delivery": 0.35,
        "communication": 0.25,
        "engagement": 0.25,
        "financial": 0.15,
    },
}

SEVERITY_INT = {"CRITICAL": 3, "WARNING": 2, "WATCH": 1}


def classify_health(score: float) -> str:
    """Map health score to classification."""
    if score >= 90:
        return "thriving"
    if score >= 70:
        return "healthy"
    if score >= 50:
        return "at_risk"
    return "critical"


def compute_health_score(
    dimensions: list[ScoreDimension],
    entity_type: str,
) -> float:
    """Weighted average of score dimensions."""
    weights = DIMENSION_WEIGHTS.get(entity_type, DIMENSION_WEIGHTS["client"])
    total_weight = 0.0
    weighted_sum = 0.0
    for dim in dimensions:
        w = weights.get(dim.dimension, 0.1)
        weighted_sum += dim.score * w
        total_weight += w
    if total_weight == 0:
        return 0.0
    return weighted_sum / total_weight


def compute_signal_trend(
    current_signals: list[SignalSnapshot],
    previous_signals: list[SignalSnapshot] | None = None,
) -> str:
    """Compare active signals between current and previous cycle."""
    if previous_signals is None:
        previous_signals = []

    count_change = len(current_signals) - len(previous_signals)

    current_sev = sum(SEVERITY_INT.get(s.severity, 1) for s in current_signals)
    prev_sev = sum(SEVERITY_INT.get(s.severity, 1) for s in previous_signals)
    severity_change = current_sev - prev_sev

    if severity_change > 0 or count_change > 2:
        return "deteriorating"
    if severity_change < 0 or count_change < -2:
        return "improving"
    return "stable"


def compute_pattern_direction(
    patterns: list[ProfilePatternSnapshot],
) -> str:
    """Aggregate individual pattern directions into entity-level assessment."""
    worsening = sum(1 for p in patterns if p.direction == "worsening")
    resolving = sum(1 for p in patterns if p.direction == "resolving")

    if worsening > resolving:
        return "destabilizing"
    if resolving > worsening:
        return "stabilizing"
    return "neutral"


def determine_attention_level(
    signals: list[SignalSnapshot],
    compound_risks: list[ProfileCompoundRisk],
    health_classification: str,
) -> AttentionLevel:
    """
    Priority order (first match wins):
    1. Any CRITICAL signal → URGENT
    2. Any structural compound risk → URGENT
    3. health_classification == 'critical' → URGENT
    4. Any WARNING signal → ELEVATED
    5. health_classification == 'at_risk' → ELEVATED
    6. Any WATCH signal → NORMAL
    7. No active findings → STABLE
    """
    if any(s.severity == "CRITICAL" for s in signals):
        return AttentionLevel.URGENT
    if any(r.is_structural for r in compound_risks):
        return AttentionLevel.URGENT
    if health_classification == "critical":
        return AttentionLevel.URGENT
    if any(s.severity == "WARNING" for s in signals):
        return AttentionLevel.ELEVATED
    if health_classification == "at_risk":
        return AttentionLevel.ELEVATED
    if any(s.severity == "WATCH" for s in signals):
        return AttentionLevel.NORMAL
    return AttentionLevel.STABLE


def compute_next_review(attention_level: AttentionLevel, as_of: datetime) -> datetime:
    """Compute next review date based on attention level."""
    intervals = {
        AttentionLevel.URGENT: timedelta(days=1),
        AttentionLevel.ELEVATED: timedelta(days=7),
        AttentionLevel.NORMAL: timedelta(days=30),
        AttentionLevel.STABLE: timedelta(days=90),
    }
    return as_of + intervals.get(attention_level, timedelta(days=30))


def build_entity_profile(
    entity_type: str,
    entity_id: str,
    entity_name: str,
    score_dimensions: list[ScoreDimension],
    active_signals: list[SignalSnapshot],
    previous_signals: list[SignalSnapshot] | None,
    active_patterns: list[ProfilePatternSnapshot],
    compound_risks: list[ProfileCompoundRisk],
    cost_profile: CostProfile,
    trajectory_direction: str = "stable",
    projected_score_30d: float | None = None,
    confidence_band: tuple | None = None,
    cross_domain_issues: list[str] | None = None,
    as_of: datetime | None = None,
) -> EntityIntelligenceProfile:
    """
    Assemble complete EntityIntelligenceProfile from all intelligence sources.

    Performance target: < 500ms per entity.
    """
    if as_of is None:
        as_of = datetime.now()

    # Health
    health_score = compute_health_score(score_dimensions, entity_type)
    health_class = classify_health(health_score)

    # Signal trend
    signal_trend = compute_signal_trend(active_signals, previous_signals)

    # Pattern direction
    pattern_dir = compute_pattern_direction(active_patterns)

    # Trajectory defaults
    if projected_score_30d is None:
        projected_score_30d = health_score  # flat projection
    if confidence_band is None:
        confidence_band = (
            max(0, projected_score_30d - 10),
            min(100, projected_score_30d + 10),
        )

    # Attention
    attention = determine_attention_level(active_signals, compound_risks, health_class)

    # Next review
    review_date = compute_next_review(attention, as_of)

    # Narrative
    builder = NarrativeBuilder()

    narrative = builder.build_narrative(
        entity_type=entity_type,
        entity_name=entity_name,
        health_score=health_score,
        health_classification=health_class,
        active_signals=[
            {"signal_type": s.signal_type, "severity": s.severity} for s in active_signals
        ],
        active_patterns=[
            {"pattern_type": p.pattern_type, "direction": p.direction} for p in active_patterns
        ],
        compound_risks=[
            {"title": r.title, "severity": r.severity, "confidence": r.confidence}
            for r in compound_risks
        ],
        cost_profile=cost_profile.to_dict(),
        trajectory_direction=trajectory_direction,
        projected_score_30d=projected_score_30d,
    )

    actions = builder.build_action_recommendations(
        health_classification=health_class,
        attention_level=attention.value,
        active_signals=[
            {"signal_type": s.signal_type, "severity": s.severity} for s in active_signals
        ],
        compound_risks=[{"title": r.title, "severity": r.severity} for r in compound_risks],
        cost_profile=cost_profile.to_dict(),
        trajectory_direction=trajectory_direction,
    )

    return EntityIntelligenceProfile(
        entity_type=entity_type,
        entity_id=entity_id,
        entity_name=entity_name,
        health_score=health_score,
        health_classification=health_class,
        score_dimensions=score_dimensions,
        active_signals=active_signals,
        signal_trend=signal_trend,
        active_patterns=active_patterns,
        pattern_direction=pattern_dir,
        trajectory_direction=trajectory_direction,
        projected_score_30d=projected_score_30d,
        confidence_band=confidence_band,
        cost_profile=cost_profile,
        compound_risks=compound_risks,
        cross_domain_issues=cross_domain_issues or [],
        narrative=narrative,
        attention_level=attention,
        recommended_actions=actions,
        as_of=as_of.isoformat(),
        next_review_date=review_date.isoformat(),
    )
