"""
Predictive Intelligence — MOH TIME OS

Forecasting, early warning detection, and proactive recommendations.
Uses historical patterns to predict future entity states and surface
issues before they become critical.

Brief 24 (PI), Task PI-1.1
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class EarlyWarning:
    """An early warning about a potential future issue."""

    entity_type: str
    entity_id: str
    warning_type: str  # health_decline | churn_risk | capacity_crunch | revenue_drop
    description: str
    probability: float  # 0-1
    time_horizon_days: int  # how soon
    current_indicators: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "warning_type": self.warning_type,
            "description": self.description,
            "probability": round(self.probability, 2),
            "time_horizon_days": self.time_horizon_days,
            "current_indicators": self.current_indicators,
            "recommended_actions": self.recommended_actions,
        }


@dataclass
class HealthForecast:
    """Projected health score with confidence bounds."""

    entity_type: str
    entity_id: str
    current_score: float
    projected_score: float
    projected_days: int
    confidence: float
    lower_bound: float
    upper_bound: float
    trend: str  # improving | stable | declining

    def to_dict(self) -> dict:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "current_score": round(self.current_score, 1),
            "projected_score": round(self.projected_score, 1),
            "projected_days": self.projected_days,
            "confidence": round(self.confidence, 2),
            "lower_bound": round(self.lower_bound, 1),
            "upper_bound": round(self.upper_bound, 1),
            "trend": self.trend,
        }


@dataclass
class ProactiveRecommendation:
    """A proactive recommendation based on predicted future state."""

    entity_type: str
    entity_id: str
    recommendation: str
    urgency: str  # immediate | soon | planned
    basis: str  # why this recommendation
    expected_impact: str
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "recommendation": self.recommendation,
            "urgency": self.urgency,
            "basis": self.basis,
            "expected_impact": self.expected_impact,
            "confidence": round(self.confidence, 2),
        }


def linear_forecast(
    values: list[float],
    periods_ahead: int = 1,
) -> tuple[float, float, float]:
    """
    Simple linear forecast with confidence bounds.

    Returns (projected, lower_bound, upper_bound).
    """
    if len(values) < 2:
        v = values[0] if values else 50.0
        return v, v - 10, v + 10

    n = len(values)
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n

    ss_xx = sum((i - x_mean) ** 2 for i in range(n))
    ss_xy = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))

    if abs(ss_xx) < 1e-10:
        return y_mean, y_mean - 10, y_mean + 10

    slope = ss_xy / ss_xx
    intercept = y_mean - slope * x_mean

    projected = slope * (n - 1 + periods_ahead) + intercept

    # Residual standard error
    residuals = [values[i] - (slope * i + intercept) for i in range(n)]
    sse = sum(r * r for r in residuals)
    se = math.sqrt(sse / max(1, n - 2)) if n > 2 else 5.0

    margin = 1.96 * se  # ~95% CI
    return projected, projected - margin, projected + margin


def detect_decline_pattern(
    scores: list[float],
    threshold: float = -2.0,
) -> bool:
    """Detect if scores show a consistent decline pattern."""
    if len(scores) < 3:
        return False

    deltas = [scores[i] - scores[i - 1] for i in range(1, len(scores))]
    avg_delta = sum(deltas) / len(deltas)
    decline_count = sum(1 for d in deltas if d < 0)

    return avg_delta < threshold and decline_count > len(deltas) * 0.6


def estimate_churn_probability(
    health_score: float,
    trend_velocity: float,
    days_since_contact: int,
    signal_count: int,
) -> float:
    """
    Estimate churn probability from multiple indicators.

    Returns probability 0-1.
    """
    # Health factor: low health increases risk
    health_factor = max(0, (50 - health_score) / 50.0) if health_score < 50 else 0.0

    # Trend factor: declining trend increases risk
    trend_factor = min(1.0, max(0, -trend_velocity / 10.0))

    # Contact factor: no recent contact increases risk
    contact_factor = min(1.0, max(0, (days_since_contact - 14) / 30.0))

    # Signal factor: more signals = more risk
    signal_factor = min(1.0, signal_count * 0.15)

    # Weighted combination
    probability = (
        health_factor * 0.35 + trend_factor * 0.25 + contact_factor * 0.20 + signal_factor * 0.20
    )
    return min(1.0, max(0.0, probability))


class PredictiveIntelligence:
    """Forecasting, early warnings, and proactive recommendations."""

    def __init__(self) -> None:
        pass

    def forecast_health(
        self,
        entity_type: str,
        entity_id: str,
        historical_scores: list[float],
        periods_ahead: int = 7,
    ) -> HealthForecast:
        """Forecast entity health score."""
        current = historical_scores[-1] if historical_scores else 50.0
        projected, lower, upper = linear_forecast(historical_scores, periods_ahead)

        # Clamp to valid range
        projected = max(0, min(100, projected))
        lower = max(0, min(100, lower))
        upper = max(0, min(100, upper))

        # Confidence based on data and consistency
        n = len(historical_scores)
        confidence = min(0.9, n * 0.1)

        if projected > current + 3:
            trend = "improving"
        elif projected < current - 3:
            trend = "declining"
        else:
            trend = "stable"

        return HealthForecast(
            entity_type=entity_type,
            entity_id=entity_id,
            current_score=current,
            projected_score=projected,
            projected_days=periods_ahead,
            confidence=confidence,
            lower_bound=lower,
            upper_bound=upper,
            trend=trend,
        )

    def generate_early_warnings(
        self,
        entity_type: str,
        entity_id: str,
        health_scores: list[float] | None = None,
        trend_velocity: float = 0.0,
        days_since_contact: int = 0,
        signal_count: int = 0,
        monthly_revenue: float = 0.0,
        revenue_trend: str = "stable",
    ) -> list[EarlyWarning]:
        """Generate early warnings for an entity."""
        warnings = []
        scores = health_scores or []
        current_health = scores[-1] if scores else 50.0

        # Health decline warning
        if detect_decline_pattern(scores):
            forecast = self.forecast_health(entity_type, entity_id, scores)
            warnings.append(
                EarlyWarning(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    warning_type="health_decline",
                    description=(
                        f"Health score declining from {current_health:.0f} "
                        f"toward {forecast.projected_score:.0f}"
                    ),
                    probability=0.7 if len(scores) >= 5 else 0.5,
                    time_horizon_days=14,
                    current_indicators=["consistent score decline"],
                    recommended_actions=["review entity health", "check for root causes"],
                )
            )

        # Churn risk
        churn_prob = estimate_churn_probability(
            current_health,
            trend_velocity,
            days_since_contact,
            signal_count,
        )
        if churn_prob >= 0.3:
            indicators = []
            if current_health < 50:
                indicators.append(f"low health ({current_health:.0f})")
            if trend_velocity < -3:
                indicators.append("declining trajectory")
            if days_since_contact > 14:
                indicators.append(f"no contact for {days_since_contact}d")
            if signal_count > 0:
                indicators.append(f"{signal_count} active signals")

            warnings.append(
                EarlyWarning(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    warning_type="churn_risk",
                    description=f"Elevated churn risk ({churn_prob:.0%})",
                    probability=churn_prob,
                    time_horizon_days=30,
                    current_indicators=indicators,
                    recommended_actions=[
                        "schedule check-in",
                        "review recent delivery quality",
                    ],
                )
            )

        # Revenue decline
        if revenue_trend == "declining" and monthly_revenue > 5000:
            warnings.append(
                EarlyWarning(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    warning_type="revenue_drop",
                    description=f"Revenue declining (current: {monthly_revenue:,.0f} AED)",
                    probability=0.6,
                    time_horizon_days=60,
                    current_indicators=["declining revenue trend"],
                    recommended_actions=["upsell opportunity review", "client strategy session"],
                )
            )

        return warnings

    def generate_recommendations(
        self,
        entity_type: str,
        entity_id: str,
        warnings: list[EarlyWarning],
        health_score: float = 50.0,
        days_since_review: int = 0,
    ) -> list[ProactiveRecommendation]:
        """Generate proactive recommendations from warnings and state."""
        recs = []

        for w in warnings:
            if w.warning_type == "churn_risk" and w.probability >= 0.5:
                recs.append(
                    ProactiveRecommendation(
                        entity_type=entity_type,
                        entity_id=entity_id,
                        recommendation="Schedule urgent client retention meeting",
                        urgency="immediate",
                        basis=f"Churn probability at {w.probability:.0%}",
                        expected_impact="Reduce churn risk through direct engagement",
                        confidence=w.probability,
                    )
                )
            elif w.warning_type == "health_decline":
                recs.append(
                    ProactiveRecommendation(
                        entity_type=entity_type,
                        entity_id=entity_id,
                        recommendation="Investigate root cause of health decline",
                        urgency="soon",
                        basis=w.description,
                        expected_impact="Early intervention before score drops further",
                        confidence=w.probability,
                    )
                )
            elif w.warning_type == "revenue_drop":
                recs.append(
                    ProactiveRecommendation(
                        entity_type=entity_type,
                        entity_id=entity_id,
                        recommendation="Review scope and identify upsell opportunities",
                        urgency="planned",
                        basis=w.description,
                        expected_impact="Stabilize or grow revenue",
                        confidence=w.probability,
                    )
                )

        # Staleness recommendation
        if days_since_review > 21 and health_score < 60:
            recs.append(
                ProactiveRecommendation(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    recommendation="Overdue for review — schedule assessment",
                    urgency="soon",
                    basis=f"Not reviewed in {days_since_review} days with health at {health_score:.0f}",
                    expected_impact="Prevent further undetected deterioration",
                    confidence=0.8,
                )
            )

        return recs
