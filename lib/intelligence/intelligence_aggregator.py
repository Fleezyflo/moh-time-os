"""
Intelligence Aggregator — MOH TIME OS

Cross-entity intelligence synthesis: cascading risk analysis,
portfolio-level roll-ups, and unified intelligence views.

Brief 26 (IA), Task IA-1.1

Aggregates outputs from scoring, signals, trajectory, and cost
modules into actionable portfolio-level intelligence.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class EntityIntelligenceSummary:
    """Condensed intelligence for a single entity."""

    entity_type: str
    entity_id: str
    entity_name: str = ""
    health_score: float = 0.0
    health_classification: str = "unknown"
    active_signal_count: int = 0
    critical_signal_count: int = 0
    warning_signal_count: int = 0
    trend_direction: str = "stable"  # rising | stable | declining | volatile
    trajectory_velocity: float = 0.0
    cost_efficiency: float = 0.0
    data_quality: float = 1.0
    top_risks: list[str] = field(default_factory=list)
    top_opportunities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "health_score": self.health_score,
            "health_classification": self.health_classification,
            "active_signal_count": self.active_signal_count,
            "critical_signal_count": self.critical_signal_count,
            "warning_signal_count": self.warning_signal_count,
            "trend_direction": self.trend_direction,
            "trajectory_velocity": self.trajectory_velocity,
            "cost_efficiency": self.cost_efficiency,
            "data_quality": self.data_quality,
            "top_risks": self.top_risks,
            "top_opportunities": self.top_opportunities,
        }


@dataclass
class CascadingRisk:
    """A risk that propagates across entities."""

    risk_id: str
    description: str
    source_entity_type: str
    source_entity_id: str
    affected_entities: list[dict[str, str]]  # [{entity_type, entity_id, impact}]
    severity: str  # critical | high | medium | low
    cascade_depth: int = 1
    estimated_impact: str = ""

    def to_dict(self) -> dict:
        return {
            "risk_id": self.risk_id,
            "description": self.description,
            "source_entity_type": self.source_entity_type,
            "source_entity_id": self.source_entity_id,
            "affected_entities": self.affected_entities,
            "severity": self.severity,
            "cascade_depth": self.cascade_depth,
            "estimated_impact": self.estimated_impact,
        }


@dataclass
class PortfolioRollup:
    """Portfolio-level aggregated intelligence."""

    generated_at: str = ""
    total_clients: int = 0
    total_projects: int = 0
    total_persons: int = 0
    avg_client_health: float = 0.0
    avg_project_health: float = 0.0
    health_distribution: dict[str, int] = field(default_factory=dict)
    total_active_signals: int = 0
    total_critical_signals: int = 0
    cascading_risks: list[CascadingRisk] = field(default_factory=list)
    entities_declining: int = 0
    entities_rising: int = 0
    portfolio_trend: str = "stable"
    attention_required: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "total_clients": self.total_clients,
            "total_projects": self.total_projects,
            "total_persons": self.total_persons,
            "avg_client_health": round(self.avg_client_health, 1),
            "avg_project_health": round(self.avg_project_health, 1),
            "health_distribution": self.health_distribution,
            "total_active_signals": self.total_active_signals,
            "total_critical_signals": self.total_critical_signals,
            "cascading_risks": [r.to_dict() for r in self.cascading_risks],
            "entities_declining": self.entities_declining,
            "entities_rising": self.entities_rising,
            "portfolio_trend": self.portfolio_trend,
            "attention_required": self.attention_required,
        }


def classify_health(score: float) -> str:
    """Classify health score into category."""
    if score >= 80:
        return "excellent"
    if score >= 65:
        return "good"
    if score >= 50:
        return "fair"
    if score >= 35:
        return "poor"
    return "critical"


def determine_trend(velocities: list[float]) -> str:
    """Determine trend from velocity values."""
    if not velocities:
        return "stable"
    avg_vel = sum(velocities) / len(velocities)
    if avg_vel > 2.0:
        return "rising"
    if avg_vel < -2.0:
        return "declining"
    # Check volatility
    if len(velocities) >= 3:
        spread = max(velocities) - min(velocities)
        if spread > 10.0:
            return "volatile"
    return "stable"


class IntelligenceAggregator:
    """Synthesizes cross-entity intelligence into unified views."""

    def __init__(self) -> None:
        pass

    def build_entity_summary(
        self,
        entity_type: str,
        entity_id: str,
        entity_name: str = "",
        health_score: float = 0.0,
        signals: list[dict[str, Any]] | None = None,
        trajectory_velocity: float = 0.0,
        cost_efficiency: float = 0.0,
        data_quality: float = 1.0,
    ) -> EntityIntelligenceSummary:
        """Build a condensed intelligence summary for an entity."""
        signals = signals or []

        critical = sum(1 for s in signals if s.get("severity") == "CRITICAL")
        warnings = sum(1 for s in signals if s.get("severity") == "WARNING")

        # Extract top risks from critical/warning signals
        top_risks = []
        for s in signals:
            if s.get("severity") in ("CRITICAL", "WARNING"):
                risk_text = s.get("evidence_text", s.get("signal_id", "unknown risk"))
                top_risks.append(risk_text)

        # Determine trend from velocity
        if trajectory_velocity > 2.0:
            trend = "rising"
        elif trajectory_velocity < -2.0:
            trend = "declining"
        else:
            trend = "stable"

        return EntityIntelligenceSummary(
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            health_score=health_score,
            health_classification=classify_health(health_score),
            active_signal_count=len(signals),
            critical_signal_count=critical,
            warning_signal_count=warnings,
            trend_direction=trend,
            trajectory_velocity=trajectory_velocity,
            cost_efficiency=cost_efficiency,
            data_quality=data_quality,
            top_risks=top_risks[:5],
        )

    def detect_cascading_risks(
        self,
        entity_summaries: list[EntityIntelligenceSummary],
        entity_relationships: list[dict[str, str]] | None = None,
    ) -> list[CascadingRisk]:
        """
        Detect risks that cascade across related entities.

        entity_relationships: [{source_type, source_id, target_type, target_id, relationship}]
        """
        relationships = entity_relationships or []
        cascading = []
        risk_counter = 0

        # Build lookup: entity_key -> summary
        by_key = {}
        for s in entity_summaries:
            key = f"{s.entity_type}:{s.entity_id}"
            by_key[key] = s

        # Find entities with critical signals
        critical_entities = [s for s in entity_summaries if s.critical_signal_count > 0]

        for entity in critical_entities:
            source_key = f"{entity.entity_type}:{entity.entity_id}"
            affected = []

            for rel in relationships:
                rel_source = f"{rel['source_type']}:{rel['source_id']}"
                rel_target = f"{rel['target_type']}:{rel['target_id']}"

                # If critical entity is source, target is affected
                if rel_source == source_key:
                    target = by_key.get(rel_target)
                    impact = "direct"
                    if target and target.health_score < 50:
                        impact = "compounding"
                    affected.append(
                        {
                            "entity_type": rel["target_type"],
                            "entity_id": rel["target_id"],
                            "impact": impact,
                        }
                    )
                # If critical entity is target, source may cascade too
                elif rel_target == source_key:
                    affected.append(
                        {
                            "entity_type": rel["source_type"],
                            "entity_id": rel["source_id"],
                            "impact": "upstream",
                        }
                    )

            if affected:
                risk_counter += 1
                severity = "critical" if entity.critical_signal_count >= 2 else "high"
                cascading.append(
                    CascadingRisk(
                        risk_id=f"cascade_{risk_counter}",
                        description=(
                            f"{entity.entity_type} {entity.entity_id} has "
                            f"{entity.critical_signal_count} critical signals "
                            f"affecting {len(affected)} related entities"
                        ),
                        source_entity_type=entity.entity_type,
                        source_entity_id=entity.entity_id,
                        affected_entities=affected,
                        severity=severity,
                        cascade_depth=1,
                        estimated_impact=f"{len(affected)} entities at risk",
                    )
                )

        return cascading

    def build_portfolio_rollup(
        self,
        entity_summaries: list[EntityIntelligenceSummary],
        cascading_risks: list[CascadingRisk] | None = None,
    ) -> PortfolioRollup:
        """Build portfolio-level aggregated intelligence."""
        cascading_risks = cascading_risks or []

        clients = [s for s in entity_summaries if s.entity_type == "client"]
        projects = [s for s in entity_summaries if s.entity_type == "project"]
        persons = [s for s in entity_summaries if s.entity_type == "person"]

        # Health averages
        avg_client = sum(c.health_score for c in clients) / len(clients) if clients else 0.0
        avg_project = sum(p.health_score for p in projects) / len(projects) if projects else 0.0

        # Health distribution
        distribution: dict[str, int] = {
            "excellent": 0,
            "good": 0,
            "fair": 0,
            "poor": 0,
            "critical": 0,
        }
        for s in entity_summaries:
            cat = classify_health(s.health_score)
            distribution[cat] = distribution.get(cat, 0) + 1

        # Signal totals
        total_signals = sum(s.active_signal_count for s in entity_summaries)
        total_critical = sum(s.critical_signal_count for s in entity_summaries)

        # Trend counts
        declining = sum(1 for s in entity_summaries if s.trend_direction == "declining")
        rising = sum(1 for s in entity_summaries if s.trend_direction == "rising")

        # Portfolio trend
        if declining > len(entity_summaries) * 0.3:
            portfolio_trend = "declining"
        elif rising > len(entity_summaries) * 0.3:
            portfolio_trend = "rising"
        else:
            portfolio_trend = "stable"

        # Attention required: entities with critical signals or poor/critical health
        attention = []
        for s in entity_summaries:
            if s.critical_signal_count > 0 or s.health_classification in ("poor", "critical"):
                attention.append(f"{s.entity_type}:{s.entity_id}")

        return PortfolioRollup(
            generated_at=datetime.now().isoformat(),
            total_clients=len(clients),
            total_projects=len(projects),
            total_persons=len(persons),
            avg_client_health=avg_client,
            avg_project_health=avg_project,
            health_distribution=distribution,
            total_active_signals=total_signals,
            total_critical_signals=total_critical,
            cascading_risks=cascading_risks,
            entities_declining=declining,
            entities_rising=rising,
            portfolio_trend=portfolio_trend,
            attention_required=attention,
        )

    def compare_periods(
        self,
        current: list[EntityIntelligenceSummary],
        previous: list[EntityIntelligenceSummary],
    ) -> dict[str, Any]:
        """Compare intelligence between two periods."""
        curr_by_key = {f"{s.entity_type}:{s.entity_id}": s for s in current}
        prev_by_key = {f"{s.entity_type}:{s.entity_id}": s for s in previous}

        improved = []
        degraded = []
        new_entities = []
        removed_entities = []

        for key, curr_s in curr_by_key.items():
            if key in prev_by_key:
                prev_s = prev_by_key[key]
                delta = curr_s.health_score - prev_s.health_score
                if delta > 5:
                    improved.append(
                        {
                            "entity": key,
                            "delta": round(delta, 1),
                            "from": prev_s.health_classification,
                            "to": curr_s.health_classification,
                        }
                    )
                elif delta < -5:
                    degraded.append(
                        {
                            "entity": key,
                            "delta": round(delta, 1),
                            "from": prev_s.health_classification,
                            "to": curr_s.health_classification,
                        }
                    )
            else:
                new_entities.append(key)

        for key in prev_by_key:
            if key not in curr_by_key:
                removed_entities.append(key)

        curr_avg = sum(s.health_score for s in current) / len(current) if current else 0
        prev_avg = sum(s.health_score for s in previous) / len(previous) if previous else 0

        return {
            "portfolio_health_delta": round(curr_avg - prev_avg, 1),
            "improved_count": len(improved),
            "degraded_count": len(degraded),
            "improved": sorted(improved, key=lambda x: x["delta"], reverse=True),
            "degraded": sorted(degraded, key=lambda x: x["delta"]),
            "new_entities": new_entities,
            "removed_entities": removed_entities,
        }
