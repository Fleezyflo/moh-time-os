"""
Revenue Analytics — MOH TIME OS

Revenue trend analysis, profitability forecasting, client tier
classification, and financial health insights.

Brief 15 (BI), Task BI-1.1

Complements cost_to_serve.py and cost_proxies.py with revenue-side
analytics and forward-looking financial intelligence.
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# Client tier thresholds (monthly revenue, AED)
TIER_THRESHOLDS = {
    "platinum": 30000,
    "gold": 15000,
    "silver": 5000,
    "bronze": 0,
}


@dataclass
class RevenueTrend:
    """Revenue trend analysis for an entity."""

    entity_type: str
    entity_id: str
    entity_name: str = ""
    current_monthly: float = 0.0
    previous_monthly: float = 0.0
    monthly_change: float = 0.0
    monthly_change_pct: float = 0.0
    trailing_3m_avg: float = 0.0
    trailing_6m_avg: float = 0.0
    trend_direction: str = "stable"  # growing | stable | declining
    tier: str = "bronze"

    def to_dict(self) -> dict:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "current_monthly": round(self.current_monthly, 2),
            "previous_monthly": round(self.previous_monthly, 2),
            "monthly_change": round(self.monthly_change, 2),
            "monthly_change_pct": round(self.monthly_change_pct, 1),
            "trailing_3m_avg": round(self.trailing_3m_avg, 2),
            "trailing_6m_avg": round(self.trailing_6m_avg, 2),
            "trend_direction": self.trend_direction,
            "tier": self.tier,
        }


@dataclass
class ProfitabilityForecast:
    """Forward-looking profitability projection."""

    entity_id: str
    current_margin_pct: float = 0.0
    projected_margin_pct: float = 0.0
    revenue_projection: float = 0.0
    cost_projection: float = 0.0
    confidence: float = 0.0
    risk_factors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "current_margin_pct": round(self.current_margin_pct, 1),
            "projected_margin_pct": round(self.projected_margin_pct, 1),
            "revenue_projection": round(self.revenue_projection, 2),
            "cost_projection": round(self.cost_projection, 2),
            "confidence": round(self.confidence, 2),
            "risk_factors": self.risk_factors,
        }


@dataclass
class PortfolioFinancials:
    """Portfolio-level financial summary."""

    total_monthly_revenue: float = 0.0
    total_monthly_cost: float = 0.0
    portfolio_margin_pct: float = 0.0
    revenue_concentration_hhi: float = 0.0
    top_client_revenue_pct: float = 0.0
    tier_distribution: dict[str, int] = field(default_factory=dict)
    tier_revenue: dict[str, float] = field(default_factory=dict)
    at_risk_revenue: float = 0.0
    growing_revenue: float = 0.0

    def to_dict(self) -> dict:
        return {
            "total_monthly_revenue": round(self.total_monthly_revenue, 2),
            "total_monthly_cost": round(self.total_monthly_cost, 2),
            "portfolio_margin_pct": round(self.portfolio_margin_pct, 1),
            "revenue_concentration_hhi": round(self.revenue_concentration_hhi, 4),
            "top_client_revenue_pct": round(self.top_client_revenue_pct, 1),
            "tier_distribution": self.tier_distribution,
            "tier_revenue": {k: round(v, 2) for k, v in self.tier_revenue.items()},
            "at_risk_revenue": round(self.at_risk_revenue, 2),
            "growing_revenue": round(self.growing_revenue, 2),
        }


def classify_tier(monthly_revenue: float) -> str:
    """Classify client into revenue tier."""
    for tier, threshold in sorted(TIER_THRESHOLDS.items(), key=lambda x: x[1], reverse=True):
        if monthly_revenue >= threshold:
            return tier
    return "bronze"


def compute_revenue_trend(
    monthly_values: list[float],
) -> tuple[str, float]:
    """
    Compute revenue trend direction and change percentage.

    Returns (direction, change_pct).
    """
    if len(monthly_values) < 2:
        return "stable", 0.0

    recent = monthly_values[-1]
    previous = monthly_values[-2]

    if previous == 0:
        if recent > 0:
            return "growing", 100.0
        return "stable", 0.0

    change_pct = ((recent - previous) / previous) * 100.0

    if change_pct > 5.0:
        return "growing", change_pct
    if change_pct < -5.0:
        return "declining", change_pct
    return "stable", change_pct


def compute_hhi(revenue_shares: list[float]) -> float:
    """
    Compute Herfindahl-Hirschman Index for concentration.

    revenue_shares: list of fractional shares (should sum to ~1.0)
    Returns HHI (0-1). Higher = more concentrated.
    """
    if not revenue_shares:
        return 0.0
    return sum(s * s for s in revenue_shares)


def simple_linear_projection(
    values: list[float],
    periods_ahead: int = 3,
) -> float:
    """Simple linear extrapolation from recent values."""
    if len(values) < 2:
        return values[-1] if values else 0.0

    n = len(values)
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n

    numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
    denominator = sum((i - x_mean) ** 2 for i in range(n))

    if abs(denominator) < 1e-10:
        return values[-1]

    slope = numerator / denominator
    intercept = y_mean - slope * x_mean

    projected = slope * (n - 1 + periods_ahead) + intercept
    return max(0.0, projected)  # Revenue can't be negative


class RevenueAnalytics:
    """Revenue trend analysis and financial health insights."""

    def __init__(self) -> None:
        pass

    def analyze_client_revenue(
        self,
        entity_id: str,
        entity_name: str = "",
        monthly_revenues: list[float] | None = None,
    ) -> RevenueTrend:
        """Analyze revenue trend for a single client."""
        revenues = monthly_revenues or []

        current = revenues[-1] if revenues else 0.0
        previous = revenues[-2] if len(revenues) >= 2 else 0.0

        direction, change_pct = compute_revenue_trend(revenues)

        trailing_3m = sum(revenues[-3:]) / min(3, len(revenues)) if revenues else 0.0
        trailing_6m = sum(revenues[-6:]) / min(6, len(revenues)) if revenues else 0.0

        return RevenueTrend(
            entity_type="client",
            entity_id=entity_id,
            entity_name=entity_name,
            current_monthly=current,
            previous_monthly=previous,
            monthly_change=current - previous,
            monthly_change_pct=change_pct,
            trailing_3m_avg=trailing_3m,
            trailing_6m_avg=trailing_6m,
            trend_direction=direction,
            tier=classify_tier(current),
        )

    def forecast_profitability(
        self,
        entity_id: str,
        monthly_revenues: list[float],
        monthly_costs: list[float],
        periods_ahead: int = 3,
    ) -> ProfitabilityForecast:
        """Forecast profitability for a client."""
        if not monthly_revenues or not monthly_costs:
            return ProfitabilityForecast(entity_id=entity_id)

        current_rev = monthly_revenues[-1]
        current_cost = monthly_costs[-1]
        current_margin = (
            ((current_rev - current_cost) / current_rev * 100.0) if current_rev > 0 else 0.0
        )

        rev_proj = simple_linear_projection(monthly_revenues, periods_ahead)
        cost_proj = simple_linear_projection(monthly_costs, periods_ahead)
        proj_margin = ((rev_proj - cost_proj) / rev_proj * 100.0) if rev_proj > 0 else 0.0

        # Confidence based on data points and consistency
        n = min(len(monthly_revenues), len(monthly_costs))
        confidence = min(0.9, n * 0.15)  # More data = more confidence

        # Risk factors
        risks = []
        if proj_margin < current_margin - 5:
            risks.append("margin compression projected")
        if rev_proj < current_rev * 0.9:
            risks.append("revenue decline projected")
        if cost_proj > current_cost * 1.1:
            risks.append("cost growth projected")
        if current_margin < 20:
            risks.append("low current margin")

        return ProfitabilityForecast(
            entity_id=entity_id,
            current_margin_pct=current_margin,
            projected_margin_pct=proj_margin,
            revenue_projection=rev_proj,
            cost_projection=cost_proj,
            confidence=confidence,
            risk_factors=risks,
        )

    def compute_portfolio_financials(
        self,
        clients: list[dict[str, Any]],
    ) -> PortfolioFinancials:
        """
        Compute portfolio-level financial summary.

        Each client dict: {entity_id, monthly_revenue, monthly_cost,
                          health_score, trend_direction}
        """
        if not clients:
            return PortfolioFinancials()

        total_rev = sum(c.get("monthly_revenue", 0) for c in clients)
        total_cost = sum(c.get("monthly_cost", 0) for c in clients)
        margin_pct = ((total_rev - total_cost) / total_rev * 100.0) if total_rev > 0 else 0.0

        # Revenue concentration (HHI)
        shares = []
        for c in clients:
            rev = c.get("monthly_revenue", 0)
            if total_rev > 0:
                shares.append(rev / total_rev)
        hhi = compute_hhi(shares)

        # Top client concentration
        max_rev = max((c.get("monthly_revenue", 0) for c in clients), default=0)
        top_pct = (max_rev / total_rev * 100.0) if total_rev > 0 else 0.0

        # Tier distribution
        tier_dist: dict[str, int] = {"platinum": 0, "gold": 0, "silver": 0, "bronze": 0}
        tier_rev: dict[str, float] = {"platinum": 0, "gold": 0, "silver": 0, "bronze": 0}
        for c in clients:
            rev = c.get("monthly_revenue", 0)
            tier = classify_tier(rev)
            tier_dist[tier] = tier_dist.get(tier, 0) + 1
            tier_rev[tier] = tier_rev.get(tier, 0) + rev

        # At-risk and growing revenue
        at_risk = sum(
            c.get("monthly_revenue", 0)
            for c in clients
            if c.get("health_score", 50) < 50 or c.get("trend_direction") == "declining"
        )
        growing = sum(
            c.get("monthly_revenue", 0) for c in clients if c.get("trend_direction") == "growing"
        )

        return PortfolioFinancials(
            total_monthly_revenue=total_rev,
            total_monthly_cost=total_cost,
            portfolio_margin_pct=margin_pct,
            revenue_concentration_hhi=hhi,
            top_client_revenue_pct=top_pct,
            tier_distribution=tier_dist,
            tier_revenue=tier_rev,
            at_risk_revenue=at_risk,
            growing_revenue=growing,
        )

    def get_revenue_alerts(
        self,
        clients: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Generate financial alerts for the portfolio.

        Returns alerts for: high concentration, declining revenue,
        at-risk revenue, low margins.
        """
        alerts = []
        portfolio = self.compute_portfolio_financials(clients)

        if portfolio.revenue_concentration_hhi > 0.25:
            alerts.append(
                {
                    "type": "concentration_risk",
                    "severity": "warning",
                    "message": (
                        f"Revenue concentration is high (HHI={portfolio.revenue_concentration_hhi:.2f}). "
                        f"Top client accounts for {portfolio.top_client_revenue_pct:.0f}% of revenue."
                    ),
                }
            )

        if portfolio.at_risk_revenue > 0 and portfolio.total_monthly_revenue > 0:
            at_risk_pct = portfolio.at_risk_revenue / portfolio.total_monthly_revenue * 100
            if at_risk_pct > 20:
                alerts.append(
                    {
                        "type": "at_risk_revenue",
                        "severity": "critical" if at_risk_pct > 40 else "warning",
                        "message": (
                            f"{at_risk_pct:.0f}% of revenue "
                            f"({portfolio.at_risk_revenue:,.0f} AED) is at risk."
                        ),
                    }
                )

        if portfolio.portfolio_margin_pct < 20:
            alerts.append(
                {
                    "type": "low_margin",
                    "severity": "warning",
                    "message": (
                        f"Portfolio margin is {portfolio.portfolio_margin_pct:.1f}%, "
                        f"below 20% target."
                    ),
                }
            )

        # Client-level declining revenue alerts
        for c in clients:
            if c.get("trend_direction") == "declining" and c.get("monthly_revenue", 0) > 10000:
                alerts.append(
                    {
                        "type": "client_revenue_decline",
                        "severity": "warning",
                        "message": (
                            f"Client {c.get('entity_id', '?')} revenue declining "
                            f"(current: {c.get('monthly_revenue', 0):,.0f} AED)."
                        ),
                    }
                )

        return alerts
