"""
Intelligence Index — MOH TIME OS

Aggregation service layer powering the live intelligence dashboard.
Provides fast, pre-computed access to all intelligence data organized
by view (command center, client, team, financial, snapshot).

Brief 12 (IX), Task IX-2.1

Single entry point: "give me everything the dashboard needs."
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CommandCenterView:
    """Top-level agency health snapshot for the command center."""

    agency_health_score: float = 0.0
    total_clients: int = 0
    total_projects: int = 0
    active_signals: int = 0
    critical_signals: int = 0
    capacity_utilization_pct: float = 0.0
    total_monthly_revenue: float = 0.0
    revenue_trend: str = "stable"
    entities_declining: int = 0
    attention_queue_size: int = 0
    last_cycle_at: str = ""
    generated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "agency_health_score": round(self.agency_health_score, 1),
            "total_clients": self.total_clients,
            "total_projects": self.total_projects,
            "active_signals": self.active_signals,
            "critical_signals": self.critical_signals,
            "capacity_utilization_pct": round(self.capacity_utilization_pct, 1),
            "total_monthly_revenue": round(self.total_monthly_revenue, 2),
            "revenue_trend": self.revenue_trend,
            "entities_declining": self.entities_declining,
            "attention_queue_size": self.attention_queue_size,
            "last_cycle_at": self.last_cycle_at,
            "generated_at": self.generated_at,
        }


@dataclass
class ClientIntelligenceCard:
    """Summary card for a single client in the client list view."""

    entity_id: str
    entity_name: str = ""
    health_score: float = 0.0
    health_classification: str = "fair"
    trend_direction: str = "stable"
    monthly_revenue: float = 0.0
    revenue_tier: str = "bronze"
    active_signals: int = 0
    critical_signals: int = 0
    days_since_review: int = 0
    attention_level: str = "normal"
    top_risk: str = ""

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "health_score": round(self.health_score, 1),
            "health_classification": self.health_classification,
            "trend_direction": self.trend_direction,
            "monthly_revenue": round(self.monthly_revenue, 2),
            "revenue_tier": self.revenue_tier,
            "active_signals": self.active_signals,
            "critical_signals": self.critical_signals,
            "days_since_review": self.days_since_review,
            "attention_level": self.attention_level,
            "top_risk": self.top_risk,
        }


@dataclass
class TeamCapacityCard:
    """Capacity summary for a team member."""

    person_id: str
    person_name: str = ""
    utilization_pct: float = 0.0
    active_tasks: int = 0
    overdue_tasks: int = 0
    meeting_hours_week: float = 0.0
    overload_warning: bool = False
    capacity_status: str = "normal"  # normal | busy | overloaded | underutilized

    def to_dict(self) -> dict:
        return {
            "person_id": self.person_id,
            "person_name": self.person_name,
            "utilization_pct": round(self.utilization_pct, 1),
            "active_tasks": self.active_tasks,
            "overdue_tasks": self.overdue_tasks,
            "meeting_hours_week": round(self.meeting_hours_week, 1),
            "overload_warning": self.overload_warning,
            "capacity_status": self.capacity_status,
        }


@dataclass
class FinancialOverview:
    """Portfolio-level financial intelligence."""

    total_monthly_revenue: float = 0.0
    total_monthly_cost: float = 0.0
    portfolio_margin_pct: float = 0.0
    revenue_by_client: list[dict[str, Any]] = field(default_factory=list)
    at_risk_revenue: float = 0.0
    growing_revenue: float = 0.0
    concentration_hhi: float = 0.0
    top_client_pct: float = 0.0
    revenue_trend: str = "stable"
    alerts: list[dict[str, Any]] = field(default_factory=list)
    generated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "total_monthly_revenue": round(self.total_monthly_revenue, 2),
            "total_monthly_cost": round(self.total_monthly_cost, 2),
            "portfolio_margin_pct": round(self.portfolio_margin_pct, 1),
            "revenue_by_client": self.revenue_by_client,
            "at_risk_revenue": round(self.at_risk_revenue, 2),
            "growing_revenue": round(self.growing_revenue, 2),
            "concentration_hhi": round(self.concentration_hhi, 3),
            "top_client_pct": round(self.top_client_pct, 1),
            "revenue_trend": self.revenue_trend,
            "alerts": self.alerts,
            "generated_at": self.generated_at,
        }


@dataclass
class ResolutionQueueItem:
    """An item in the resolution queue for review."""

    item_id: str
    entity_type: str
    entity_id: str
    entity_name: str = ""
    signal_type: str = ""
    severity: str = "WARNING"
    description: str = ""
    suggested_action: str = ""
    created_at: str = ""
    status: str = "pending"  # pending | approved | rejected | deferred

    def to_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "signal_type": self.signal_type,
            "severity": self.severity,
            "description": self.description,
            "suggested_action": self.suggested_action,
            "created_at": self.created_at,
            "status": self.status,
        }


@dataclass
class DashboardIndex:
    """Complete dashboard payload — all views in one response."""

    command_center: CommandCenterView = field(default_factory=CommandCenterView)
    client_cards: list[ClientIntelligenceCard] = field(default_factory=list)
    team_capacity: list[TeamCapacityCard] = field(default_factory=list)
    financial_overview: FinancialOverview = field(default_factory=FinancialOverview)
    resolution_queue: list[ResolutionQueueItem] = field(default_factory=list)
    generated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "command_center": self.command_center.to_dict(),
            "client_cards": [c.to_dict() for c in self.client_cards],
            "team_capacity": [t.to_dict() for t in self.team_capacity],
            "financial_overview": self.financial_overview.to_dict(),
            "resolution_queue": [r.to_dict() for r in self.resolution_queue],
            "generated_at": self.generated_at,
        }


def classify_capacity_status(utilization_pct: float) -> str:
    """Classify team member capacity status."""
    if utilization_pct >= 110:
        return "overloaded"
    if utilization_pct >= 85:
        return "busy"
    if utilization_pct <= 40:
        return "underutilized"
    return "normal"


def classify_health(score: float) -> str:
    """Classify health score into label."""
    if score >= 80:
        return "excellent"
    if score >= 65:
        return "good"
    if score >= 50:
        return "fair"
    if score >= 35:
        return "poor"
    return "critical"


def classify_attention_level(
    health_score: float,
    critical_signals: int,
    days_since_review: int,
) -> str:
    """Determine attention level from indicators."""
    if critical_signals >= 2 or health_score < 30:
        return "urgent"
    if critical_signals >= 1 or health_score < 50 or days_since_review > 21:
        return "high"
    if health_score < 65 or days_since_review > 14:
        return "elevated"
    return "normal"


class IntelligenceIndex:
    """
    Aggregation service that builds dashboard-ready data structures.

    Takes raw intelligence data and produces view-specific payloads
    optimized for fast dashboard rendering.
    """

    def __init__(self) -> None:
        pass

    def build_command_center(
        self,
        clients: list[dict[str, Any]],
        projects: list[dict[str, Any]] | None = None,
        signals: list[dict[str, Any]] | None = None,
        revenue_data: dict[str, Any] | None = None,
        capacity_data: dict[str, Any] | None = None,
        last_cycle_at: str = "",
    ) -> CommandCenterView:
        """Build the command center overview."""
        projects = projects or []
        signals = signals or []
        revenue_data = revenue_data or {}
        capacity_data = capacity_data or {}

        # Aggregate health scores
        client_health_scores = [c.get("health_score", 50) for c in clients]
        avg_health = (
            sum(client_health_scores) / len(client_health_scores) if client_health_scores else 0.0
        )

        # Count signals
        active = len(signals)
        critical = sum(1 for s in signals if s.get("severity") == "CRITICAL")

        # Declining entities
        declining = sum(1 for c in clients if c.get("trend_direction") == "declining")

        return CommandCenterView(
            agency_health_score=avg_health,
            total_clients=len(clients),
            total_projects=len(projects),
            active_signals=active,
            critical_signals=critical,
            capacity_utilization_pct=capacity_data.get("avg_utilization", 0.0),
            total_monthly_revenue=revenue_data.get("total_monthly", 0.0),
            revenue_trend=revenue_data.get("trend", "stable"),
            entities_declining=declining,
            attention_queue_size=sum(
                1
                for c in clients
                if c.get("health_score", 50) < 50 or c.get("critical_signals", 0) > 0
            ),
            last_cycle_at=last_cycle_at,
            generated_at=datetime.now().isoformat(),
        )

    def build_client_cards(
        self,
        clients: list[dict[str, Any]],
    ) -> list[ClientIntelligenceCard]:
        """Build client intelligence cards for the client list view."""
        cards = []
        for c in clients:
            health = c.get("health_score", 50.0)
            critical = c.get("critical_signals", 0)
            days_review = c.get("days_since_review", 0)

            cards.append(
                ClientIntelligenceCard(
                    entity_id=c.get("entity_id", ""),
                    entity_name=c.get("entity_name", ""),
                    health_score=health,
                    health_classification=classify_health(health),
                    trend_direction=c.get("trend_direction", "stable"),
                    monthly_revenue=c.get("monthly_revenue", 0.0),
                    revenue_tier=c.get("revenue_tier", "bronze"),
                    active_signals=c.get("active_signals", 0),
                    critical_signals=critical,
                    days_since_review=days_review,
                    attention_level=classify_attention_level(
                        health,
                        critical,
                        days_review,
                    ),
                    top_risk=c.get("top_risk", ""),
                )
            )

        # Sort by health ascending (worst first)
        cards.sort(key=lambda x: x.health_score)
        return cards

    def build_team_capacity(
        self,
        team_members: list[dict[str, Any]],
    ) -> list[TeamCapacityCard]:
        """Build team capacity cards."""
        cards = []
        for m in team_members:
            util = m.get("utilization_pct", 0.0)
            cards.append(
                TeamCapacityCard(
                    person_id=m.get("person_id", ""),
                    person_name=m.get("person_name", ""),
                    utilization_pct=util,
                    active_tasks=m.get("active_tasks", 0),
                    overdue_tasks=m.get("overdue_tasks", 0),
                    meeting_hours_week=m.get("meeting_hours_week", 0.0),
                    overload_warning=util >= 100,
                    capacity_status=classify_capacity_status(util),
                )
            )

        # Sort by utilization descending (most loaded first)
        cards.sort(key=lambda x: x.utilization_pct, reverse=True)
        return cards

    def build_financial_overview(
        self,
        clients: list[dict[str, Any]],
    ) -> FinancialOverview:
        """Build financial overview from client data."""
        if not clients:
            return FinancialOverview(generated_at=datetime.now().isoformat())

        total_rev = sum(c.get("monthly_revenue", 0) for c in clients)
        total_cost = sum(c.get("monthly_cost", 0) for c in clients)
        margin_pct = ((total_rev - total_cost) / total_rev * 100) if total_rev > 0 else 0.0

        # Revenue by client
        rev_by_client = [
            {
                "entity_id": c.get("entity_id", ""),
                "entity_name": c.get("entity_name", ""),
                "monthly_revenue": c.get("monthly_revenue", 0),
                "revenue_tier": c.get("revenue_tier", "bronze"),
            }
            for c in clients
        ]
        rev_by_client.sort(
            key=lambda x: x["monthly_revenue"],
            reverse=True,
        )

        # At-risk revenue
        at_risk = sum(
            c.get("monthly_revenue", 0)
            for c in clients
            if c.get("health_score", 50) < 50 or c.get("trend_direction") == "declining"
        )

        # Growing revenue
        growing = sum(
            c.get("monthly_revenue", 0) for c in clients if c.get("trend_direction") == "growing"
        )

        # Concentration (HHI)
        if total_rev > 0:
            shares = [c.get("monthly_revenue", 0) / total_rev for c in clients]
            hhi = sum(s * s for s in shares)
            top_pct = max(shares) * 100 if shares else 0.0
        else:
            hhi = 0.0
            top_pct = 0.0

        # Alerts
        alerts = []
        if hhi > 0.4:
            alerts.append(
                {
                    "type": "concentration_risk",
                    "severity": "warning",
                    "message": f"Revenue highly concentrated (HHI: {hhi:.2f})",
                }
            )
        if at_risk > total_rev * 0.3 and total_rev > 0:
            alerts.append(
                {
                    "type": "at_risk_revenue",
                    "severity": "critical",
                    "message": f"At-risk revenue: {at_risk:,.0f} AED ({at_risk / total_rev * 100:.0f}%)",
                }
            )

        return FinancialOverview(
            total_monthly_revenue=total_rev,
            total_monthly_cost=total_cost,
            portfolio_margin_pct=margin_pct,
            revenue_by_client=rev_by_client,
            at_risk_revenue=at_risk,
            growing_revenue=growing,
            concentration_hhi=hhi,
            top_client_pct=top_pct,
            revenue_trend="growing"
            if growing > at_risk
            else "declining"
            if at_risk > growing
            else "stable",
            alerts=alerts,
            generated_at=datetime.now().isoformat(),
        )

    def build_resolution_queue(
        self,
        items: list[dict[str, Any]],
        status_filter: str = "pending",
    ) -> list[ResolutionQueueItem]:
        """Build resolution queue from raw items."""
        queue = []
        for item in items:
            if status_filter and item.get("status", "pending") != status_filter:
                continue
            queue.append(
                ResolutionQueueItem(
                    item_id=item.get("item_id", ""),
                    entity_type=item.get("entity_type", ""),
                    entity_id=item.get("entity_id", ""),
                    entity_name=item.get("entity_name", ""),
                    signal_type=item.get("signal_type", ""),
                    severity=item.get("severity", "WARNING"),
                    description=item.get("description", ""),
                    suggested_action=item.get("suggested_action", ""),
                    created_at=item.get("created_at", ""),
                    status=item.get("status", "pending"),
                )
            )

        # Sort by severity (CRITICAL first), then by date
        severity_order = {"CRITICAL": 0, "WARNING": 1, "WATCH": 2, "INFO": 3}
        queue.sort(
            key=lambda x: (
                severity_order.get(x.severity, 9),
                x.created_at,
            )
        )
        return queue

    def build_full_index(
        self,
        clients: list[dict[str, Any]],
        projects: list[dict[str, Any]] | None = None,
        team_members: list[dict[str, Any]] | None = None,
        signals: list[dict[str, Any]] | None = None,
        revenue_data: dict[str, Any] | None = None,
        capacity_data: dict[str, Any] | None = None,
        resolution_items: list[dict[str, Any]] | None = None,
        last_cycle_at: str = "",
    ) -> DashboardIndex:
        """Build the complete dashboard index in one call."""
        return DashboardIndex(
            command_center=self.build_command_center(
                clients,
                projects,
                signals,
                revenue_data,
                capacity_data,
                last_cycle_at,
            ),
            client_cards=self.build_client_cards(clients),
            team_capacity=self.build_team_capacity(team_members or []),
            financial_overview=self.build_financial_overview(clients),
            resolution_queue=self.build_resolution_queue(
                resolution_items or [],
            ),
            generated_at=datetime.now().isoformat(),
        )
