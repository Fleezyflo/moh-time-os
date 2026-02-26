"""
Intelligence Explainability — MOH TIME OS

Generates human-readable explanations of why intelligence outputs
(scores, signals, patterns, recommendations) were produced.

Brief 28 (IO), Task IO-2.1
"""

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ExplanationFactor:
    """One contributing factor to an intelligence output."""

    factor_type: str  # 'input' | 'weight' | 'threshold' | 'rule' | 'trend'
    description: str
    contribution: float  # How much this factor contributed (0.0 to 1.0)
    value: Any = None
    comparison: str | None = None  # e.g. "above threshold of 0.7"

    def to_dict(self) -> dict:
        return {
            "factor_type": self.factor_type,
            "description": self.description,
            "contribution": round(self.contribution, 4),
            "value": self.value,
            "comparison": self.comparison,
        }


@dataclass
class Explanation:
    """Complete explanation of an intelligence output."""

    output_type: str  # 'health_score' | 'signal' | 'pattern' | 'recommendation' | 'attention_level'
    output_value: Any
    summary: str
    factors: list[ExplanationFactor]
    confidence: float = 0.0
    data_quality_note: str | None = None

    def to_dict(self) -> dict:
        return {
            "output_type": self.output_type,
            "output_value": self.output_value,
            "summary": self.summary,
            "factors": [f.to_dict() for f in self.factors],
            "confidence": round(self.confidence, 4),
            "data_quality_note": self.data_quality_note,
        }


class IntelligenceExplainer:
    """Generates explanations for intelligence outputs."""

    def explain_health_score(
        self,
        entity_name: str,
        health_score: float,
        dimensions: list[dict[str, Any]],
        weights: dict[str, float],
    ) -> Explanation:
        """Explain how a health score was computed."""
        factors = []
        for dim in dimensions:
            dim_name = dim.get("dimension", "unknown")
            score = dim.get("score", 0)
            weight = weights.get(dim_name, 0.1)
            weighted = score * weight

            factors.append(
                ExplanationFactor(
                    factor_type="weight",
                    description=f"{dim_name} dimension: {score:.0f} × {weight:.0%} weight = {weighted:.1f}",
                    contribution=weight,
                    value=score,
                    comparison=f"trend: {dim.get('trend', 'unknown')}",
                )
            )

        summary = (
            f"{entity_name} health score is {health_score:.0f}. "
            f"Computed as weighted average of {len(dimensions)} dimensions."
        )

        return Explanation(
            output_type="health_score",
            output_value=health_score,
            summary=summary,
            factors=sorted(factors, key=lambda f: f.contribution, reverse=True),
            confidence=1.0,  # Health score is deterministic
        )

    def explain_signal(
        self,
        signal_type: str,
        severity: str,
        entity_name: str,
        trigger_value: Any,
        threshold: Any,
        contributing_data: list[dict[str, Any]] | None = None,
    ) -> Explanation:
        """Explain why a signal was raised."""
        factors = [
            ExplanationFactor(
                factor_type="threshold",
                description=f"Trigger value ({trigger_value}) crossed {severity} threshold ({threshold})",
                contribution=0.8,
                value=trigger_value,
                comparison=f"threshold: {threshold}",
            ),
        ]

        if contributing_data:
            for i, data in enumerate(contributing_data[:3]):
                factors.append(
                    ExplanationFactor(
                        factor_type="input",
                        description=data.get("description", f"Contributing factor {i + 1}"),
                        contribution=data.get("weight", 0.1),
                        value=data.get("value"),
                    )
                )

        summary = (
            f"{severity.upper()} signal '{signal_type}' raised for {entity_name}. "
            f"Value {trigger_value} exceeds {severity} threshold of {threshold}."
        )

        return Explanation(
            output_type="signal",
            output_value={"type": signal_type, "severity": severity},
            summary=summary,
            factors=factors,
        )

    def explain_attention_level(
        self,
        attention_level: str,
        entity_name: str,
        health_classification: str,
        active_signals: list[dict[str, Any]],
        compound_risks: list[dict[str, Any]],
    ) -> Explanation:
        """Explain why an entity has a particular attention level."""
        factors = []

        critical = [s for s in active_signals if s.get("severity") == "CRITICAL"]
        warning = [s for s in active_signals if s.get("severity") == "WARNING"]
        structural = [r for r in compound_risks if r.get("is_structural")]

        if critical:
            factors.append(
                ExplanationFactor(
                    factor_type="rule",
                    description=f"{len(critical)} CRITICAL signal(s) → URGENT attention",
                    contribution=1.0,
                    value=len(critical),
                )
            )
        if structural:
            factors.append(
                ExplanationFactor(
                    factor_type="rule",
                    description=f"{len(structural)} structural risk(s) → URGENT attention",
                    contribution=0.9,
                    value=len(structural),
                )
            )
        if health_classification == "critical":
            factors.append(
                ExplanationFactor(
                    factor_type="rule",
                    description="Health classification 'critical' → URGENT attention",
                    contribution=0.8,
                )
            )
        if warning:
            factors.append(
                ExplanationFactor(
                    factor_type="rule",
                    description=f"{len(warning)} WARNING signal(s) → ELEVATED attention",
                    contribution=0.6,
                    value=len(warning),
                )
            )
        if health_classification == "at_risk":
            factors.append(
                ExplanationFactor(
                    factor_type="rule",
                    description="Health classification 'at_risk' → ELEVATED attention",
                    contribution=0.5,
                )
            )

        if not factors:
            factors.append(
                ExplanationFactor(
                    factor_type="rule",
                    description="No active findings → STABLE attention",
                    contribution=0.0,
                )
            )

        summary = (
            f"{entity_name} attention level is {attention_level.upper()}. "
            f"Based on {len(active_signals)} signal(s) and {len(compound_risks)} risk(s)."
        )

        return Explanation(
            output_type="attention_level",
            output_value=attention_level,
            summary=summary,
            factors=factors,
        )

    def explain_recommendation(
        self,
        recommendation: str,
        triggering_conditions: list[str],
    ) -> Explanation:
        """Explain why a recommendation was generated."""
        factors = [
            ExplanationFactor(
                factor_type="rule",
                description=condition,
                contribution=1.0 / len(triggering_conditions) if triggering_conditions else 0,
            )
            for condition in triggering_conditions
        ]

        summary = f"Recommendation: {recommendation}"

        return Explanation(
            output_type="recommendation",
            output_value=recommendation,
            summary=summary,
            factors=factors,
        )
