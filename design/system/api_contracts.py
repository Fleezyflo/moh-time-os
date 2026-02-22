"""
Intelligence Dashboard API Response Contracts

Pydantic v2 models for all dashboard-facing endpoints.
All responses follow a standard envelope: {"status": "ok", "data": ..., "computed_at": "..."}
"""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field, ConfigDict


# =============================================================================
# ENVELOPE & WRAPPER MODELS
# =============================================================================


class StandardEnvelope(BaseModel):
    """Standard response envelope for all API responses."""

    status: str = Field("ok", description="Response status: 'ok' or 'error'")
    data: Any = Field(description="Response payload")
    computed_at: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp when response was computed",
    )


class ErrorEnvelope(BaseModel):
    """Standard error response envelope."""

    status: str = Field("error", description="Always 'error'")
    error: str = Field(description="Error message")
    error_code: str = Field(default="ERROR", description="Error code")


# =============================================================================
# CLIENT PORTFOLIO MODELS
# =============================================================================


class ClientMetric(BaseModel):
    """Single client metrics for portfolio overview."""

    client_id: str = Field(description="Unique client identifier")
    name: str = Field(description="Client name")
    project_count: int = Field(description="Number of active projects")
    total_tasks: int = Field(description="Total tasks across all projects")
    active_tasks: int = Field(description="Currently active/open tasks")
    completed_tasks: int = Field(description="Completed tasks")
    overdue_tasks: int = Field(description="Tasks past due")
    invoice_count: int = Field(description="Number of invoices")
    total_invoiced: float = Field(description="Total amount invoiced")
    total_outstanding: float = Field(description="Amount still outstanding")
    health_score: float = Field(ge=0, le=100, description="Overall health score 0-100")
    trajectory: str = Field(
        description="Direction of change: 'increasing', 'stable', or 'declining'"
    )
    last_activity: datetime = Field(description="Last interaction timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "client_id": "client_001",
                "name": "Acme Corp",
                "project_count": 3,
                "total_tasks": 45,
                "active_tasks": 12,
                "completed_tasks": 28,
                "overdue_tasks": 5,
                "invoice_count": 8,
                "total_invoiced": 125000.0,
                "total_outstanding": 35000.0,
                "health_score": 72.5,
                "trajectory": "stable",
                "last_activity": "2026-02-21T10:30:00",
            }
        }
    )


class PortfolioDashboardResponse(BaseModel):
    """Portfolio overview with all clients and metrics."""

    clients: list[ClientMetric] = Field(description="List of all clients with metrics")
    total_clients: int = Field(description="Total number of clients")
    total_projects: int = Field(description="Total active projects across all clients")
    total_outstanding_revenue: float = Field(
        description="Total revenue not yet collected"
    )
    portfolio_health_score: float = Field(
        ge=0, le=100, description="Overall portfolio health 0-100"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "clients": [
                    {
                        "client_id": "client_001",
                        "name": "Acme Corp",
                        "project_count": 3,
                        "total_tasks": 45,
                        "active_tasks": 12,
                        "completed_tasks": 28,
                        "overdue_tasks": 5,
                        "invoice_count": 8,
                        "total_invoiced": 125000.0,
                        "total_outstanding": 35000.0,
                        "health_score": 72.5,
                        "trajectory": "stable",
                        "last_activity": "2026-02-21T10:30:00",
                    }
                ],
                "total_clients": 8,
                "total_projects": 24,
                "total_outstanding_revenue": 145000.0,
                "portfolio_health_score": 68.2,
            }
        }
    )


# =============================================================================
# CLIENT DETAIL MODELS
# =============================================================================


class Project(BaseModel):
    """Project within a client."""

    project_id: str = Field(description="Unique project identifier")
    name: str = Field(description="Project name")
    status: str = Field(description="Status: 'active', 'completed', 'on-hold'")
    start_date: datetime = Field(description="Project start date")
    end_date: Optional[datetime] = Field(None, description="Project end date if completed")
    progress: float = Field(ge=0, le=100, description="Completion percentage 0-100")
    task_count: int = Field(description="Total tasks in project")
    active_task_count: int = Field(description="Currently active tasks")


class Communication(BaseModel):
    """Communication record."""

    communication_id: str = Field(description="Unique communication identifier")
    type: str = Field(description="Type: 'email', 'call', 'meeting', 'message'")
    timestamp: datetime = Field(description="When communication occurred")
    subject: str = Field(description="Subject or summary")
    participants: list[str] = Field(description="People involved")


class Invoice(BaseModel):
    """Invoice record."""

    invoice_id: str = Field(description="Unique invoice identifier")
    number: str = Field(description="Invoice number for reference")
    amount: float = Field(description="Invoice amount")
    issued_date: datetime = Field(description="Date invoice was issued")
    due_date: datetime = Field(description="Payment due date")
    status: str = Field(
        description="Status: 'draft', 'sent', 'partial', 'paid', 'overdue'"
    )
    days_outstanding: Optional[int] = Field(
        None, description="Days past due (null if not overdue)"
    )


class ClientDetailResponse(BaseModel):
    """Complete client profile for detail view."""

    client_id: str = Field(description="Unique client identifier")
    name: str = Field(description="Client name")
    status: str = Field(description="Client status: 'active', 'prospect', 'inactive'")
    industry: Optional[str] = Field(None, description="Industry classification")
    contact_email: Optional[str] = Field(None, description="Primary contact email")
    contact_phone: Optional[str] = Field(None, description="Primary contact phone")
    engagement_since: datetime = Field(description="Date client engagement started")
    total_projects: int = Field(description="Total projects (active + completed)")
    active_projects: list[Project] = Field(description="Currently active projects")
    total_communications: int = Field(description="Total communications on record")
    recent_communications: list[Communication] = Field(
        max_length=5, description="Most recent communications"
    )
    invoices: list[Invoice] = Field(description="All invoices for this client")
    total_invoiced: float = Field(description="Total amount invoiced")
    total_paid: float = Field(description="Total amount paid")
    total_outstanding: float = Field(description="Total amount outstanding")
    health_score: float = Field(ge=0, le=100, description="Client health 0-100")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "client_id": "client_001",
                "name": "Acme Corp",
                "status": "active",
                "industry": "Manufacturing",
                "contact_email": "john@acme.com",
                "contact_phone": "+1-555-0123",
                "engagement_since": "2024-03-15T00:00:00",
                "total_projects": 4,
                "active_projects": [
                    {
                        "project_id": "proj_001",
                        "name": "Website Redesign",
                        "status": "active",
                        "start_date": "2026-01-10T00:00:00",
                        "end_date": None,
                        "progress": 65.0,
                        "task_count": 18,
                        "active_task_count": 5,
                    }
                ],
                "total_communications": 42,
                "recent_communications": [
                    {
                        "communication_id": "comm_001",
                        "type": "email",
                        "timestamp": "2026-02-20T14:30:00",
                        "subject": "Weekly status update",
                        "participants": ["john@acme.com", "jane@acme.com"],
                    }
                ],
                "invoices": [
                    {
                        "invoice_id": "inv_001",
                        "number": "INV-2026-001",
                        "amount": 25000.0,
                        "issued_date": "2026-02-01T00:00:00",
                        "due_date": "2026-03-01T00:00:00",
                        "status": "sent",
                        "days_outstanding": None,
                    }
                ],
                "total_invoiced": 125000.0,
                "total_paid": 90000.0,
                "total_outstanding": 35000.0,
                "health_score": 72.5,
            }
        }
    )


# =============================================================================
# RESOLUTION QUEUE MODELS
# =============================================================================


class ProposedAction(BaseModel):
    """Proposed action for a resolution item."""

    action_id: str = Field(description="Unique action identifier")
    title: str = Field(description="Action title")
    description: str = Field(description="Detailed description")
    priority: str = Field(description="Priority: 'immediate', 'urgent', 'normal'")
    effort: str = Field(description="Estimated effort: 'quick', 'medium', 'substantial'")
    owner: str = Field(description="Person responsible for action")


class ResolutionItem(BaseModel):
    """Single item in resolution queue."""

    item_id: str = Field(description="Unique item identifier")
    entity_type: str = Field(description="Type: 'client', 'project', 'person', 'financial'")
    entity_id: str = Field(description="ID of the entity")
    entity_name: str = Field(description="Human-readable name of entity")
    issue: str = Field(description="What the problem is")
    impact: str = Field(description="Why it matters")
    urgency: str = Field(description="Urgency: 'immediate', 'this_week', 'soon', 'monitor'")
    proposed_actions: list[ProposedAction] = Field(
        description="Recommended actions to resolve"
    )
    confidence: float = Field(ge=0, le=1, description="Confidence in analysis 0-1")


class ResolutionQueueResponse(BaseModel):
    """Queue of pending items requiring action."""

    items: list[ResolutionItem] = Field(description="Pending items sorted by urgency")
    total_items: int = Field(description="Total pending items")
    immediate_count: int = Field(description="Items needing immediate attention")
    this_week_count: int = Field(description="Items for this week")
    soon_count: int = Field(description="Items for upcoming period")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "item_id": "res_001",
                        "entity_type": "client",
                        "entity_id": "client_001",
                        "entity_name": "Acme Corp",
                        "issue": "2 invoices 60+ days overdue",
                        "impact": "Cash flow impact of $35K, client relationship at risk",
                        "urgency": "immediate",
                        "proposed_actions": [
                            {
                                "action_id": "act_001",
                                "title": "Contact client about payment",
                                "description": "Call John at Acme to discuss outstanding invoices",
                                "priority": "immediate",
                                "effort": "quick",
                                "owner": "person_001",
                            }
                        ],
                        "confidence": 0.95,
                    }
                ],
                "total_items": 7,
                "immediate_count": 2,
                "this_week_count": 3,
                "soon_count": 2,
            }
        }
    )


# =============================================================================
# SCENARIO & WHAT-IF MODELS
# =============================================================================


class ScenarioResult(BaseModel):
    """Result of a what-if scenario simulation."""

    metric: str = Field(description="Metric name")
    current_value: float = Field(description="Current actual value")
    projected_value: float = Field(description="Value under scenario")
    delta: float = Field(description="Difference (projected - current)")
    delta_pct: float = Field(description="Percentage change")


class ScenarioModelResponse(BaseModel):
    """What-if scenario analysis results."""

    scenario_id: str = Field(description="Unique scenario identifier")
    name: str = Field(description="Scenario name")
    description: str = Field(description="What was changed")
    baseline_date: datetime = Field(description="Date of baseline metrics")
    scenario_date: datetime = Field(description="Date of scenario projection")
    results: list[ScenarioResult] = Field(description="Impact on key metrics")
    feasibility: float = Field(
        ge=0, le=1, description="Feasibility assessment 0-1 (1=very feasible)"
    )
    risks: list[str] = Field(description="Identified risks or constraints")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "scenario_id": "scen_001",
                "name": "Hire 2 engineers Q2",
                "description": "Added 2 engineers to team in Q2 2026",
                "baseline_date": "2026-02-21T00:00:00",
                "scenario_date": "2026-06-30T00:00:00",
                "results": [
                    {
                        "metric": "team_capacity",
                        "current_value": 100.0,
                        "projected_value": 133.0,
                        "delta": 33.0,
                        "delta_pct": 33.0,
                    },
                    {
                        "metric": "avg_tasks_per_person",
                        "current_value": 8.5,
                        "projected_value": 6.4,
                        "delta": -2.1,
                        "delta_pct": -24.7,
                    },
                ],
                "feasibility": 0.8,
                "risks": ["Onboarding time", "Training costs", "Project delays"],
            }
        }
    )


# =============================================================================
# NOTIFICATION & ALERT MODELS
# =============================================================================


class Signal(BaseModel):
    """Detected signal/alert."""

    signal_id: str = Field(description="Unique signal identifier")
    severity: str = Field(description="Severity: 'high', 'medium', 'low'")
    type: str = Field(description="Signal type: 'threshold', 'pattern', 'anomaly'")
    entity_type: str = Field(description="What triggered it: 'client', 'project', etc")
    entity_id: str = Field(description="ID of affected entity")
    entity_name: str = Field(description="Name of affected entity")
    title: str = Field(description="Signal headline")
    description: str = Field(description="Detailed explanation")
    detected_at: datetime = Field(description="When signal was detected")
    resolved: bool = Field(default=False, description="Whether signal has been resolved")


class NotificationFeedResponse(BaseModel):
    """Real-time notifications and feed."""

    signals: list[Signal] = Field(description="Recent signals/alerts")
    total_unresolved: int = Field(description="Count of unresolved signals")
    critical_count: int = Field(description="Number of critical signals")
    last_check: datetime = Field(description="Last time signals were checked")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "signals": [
                    {
                        "signal_id": "sig_001",
                        "severity": "high",
                        "type": "threshold",
                        "entity_type": "client",
                        "entity_id": "client_001",
                        "entity_name": "Acme Corp",
                        "title": "Invoice aging beyond SLA",
                        "description": "Invoice INV-2026-001 is 55 days overdue",
                        "detected_at": "2026-02-20T14:30:00",
                        "resolved": False,
                    }
                ],
                "total_unresolved": 5,
                "critical_count": 2,
                "last_check": "2026-02-21T10:30:00",
            }
        }
    )


# =============================================================================
# TEAM & CAPACITY MODELS
# =============================================================================


class PersonLoad(BaseModel):
    """Individual person's workload."""

    person_id: str = Field(description="Unique person identifier")
    name: str = Field(description="Person's name")
    assigned_tasks: int = Field(description="Total assigned tasks")
    active_tasks: int = Field(description="Currently active tasks")
    project_count: int = Field(description="Number of projects")
    load_score: float = Field(
        ge=0, le=100, description="Load score 0-100 (100=overloaded)"
    )
    utilization: float = Field(ge=0, le=1, description="Utilization rate 0-1")
    status: str = Field(
        description="Status: 'available', 'fully_loaded', 'overloaded'"
    )


class TeamCapacityResponse(BaseModel):
    """Team capacity overview and distribution."""

    people: list[PersonLoad] = Field(description="Load for each team member")
    total_people: int = Field(description="Number of people")
    total_active_tasks: int = Field(description="Total active tasks across team")
    avg_tasks_per_person: float = Field(description="Average tasks per person")
    people_overloaded: int = Field(description="Number of people overloaded")
    people_available: int = Field(description="Number of people with capacity")
    team_utilization: float = Field(
        ge=0, le=1, description="Overall team utilization 0-1"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "people": [
                    {
                        "person_id": "person_001",
                        "name": "Alice Johnson",
                        "assigned_tasks": 8,
                        "active_tasks": 6,
                        "project_count": 3,
                        "load_score": 65.0,
                        "utilization": 0.65,
                        "status": "fully_loaded",
                    }
                ],
                "total_people": 12,
                "total_active_tasks": 85,
                "avg_tasks_per_person": 7.08,
                "people_overloaded": 3,
                "people_available": 4,
                "team_utilization": 0.72,
            }
        }
    )


# =============================================================================
# FINANCIAL MODELS
# =============================================================================


class AgingBucket(BaseModel):
    """Invoice aging bracket."""

    bracket: str = Field(description="Bracket: 'current', '30', '60', '90+'")
    count: int = Field(description="Number of invoices in bracket")
    amount: float = Field(description="Total amount in bracket")
    client_count: int = Field(description="Number of clients with invoices in bracket")


class ClientAging(BaseModel):
    """Client's aging summary."""

    client_id: str = Field(description="Unique client identifier")
    client_name: str = Field(description="Client name")
    total_outstanding: float = Field(description="Total amount owed")
    oldest_invoice_days: int = Field(description="Days since oldest unpaid invoice")


class FinancialAgingResponse(BaseModel):
    """Invoice aging report."""

    total_outstanding: float = Field(description="Total amount not yet collected")
    by_bucket: list[AgingBucket] = Field(description="Breakdown by age bracket")
    clients_with_overdue: list[ClientAging] = Field(
        description="Clients with overdue amounts"
    )
    total_invoices_overdue: int = Field(description="Number of overdue invoices")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_outstanding": 145000.0,
                "by_bucket": [
                    {"bracket": "current", "count": 12, "amount": 55000.0, "client_count": 5},
                    {"bracket": "30", "count": 8, "amount": 38000.0, "client_count": 3},
                    {
                        "bracket": "60",
                        "count": 5,
                        "amount": 35000.0,
                        "client_count": 2,
                    },
                    {
                        "bracket": "90+",
                        "count": 2,
                        "amount": 17000.0,
                        "client_count": 1,
                    },
                ],
                "clients_with_overdue": [
                    {
                        "client_id": "client_001",
                        "client_name": "Acme Corp",
                        "total_outstanding": 35000.0,
                        "oldest_invoice_days": 68,
                    }
                ],
                "total_invoices_overdue": 15,
            }
        }
    )


# =============================================================================
# SNAPSHOT & BRIEFING MODELS
# =============================================================================


class BriefingItem(BaseModel):
    """Single item in daily briefing."""

    category: str = Field(
        description="Category: 'immediate', 'this_week', 'monitor', 'positive'"
    )
    title: str = Field(description="Item headline")
    description: str = Field(description="Detailed description")
    entity_type: str = Field(description="Type of entity")
    entity_id: str = Field(description="ID of entity")
    action_recommended: Optional[str] = Field(
        None, description="Recommended action if any"
    )


class DailyBriefingResponse(BaseModel):
    """Daily briefing summary."""

    date: datetime = Field(description="Date of briefing")
    immediate_items: list[BriefingItem] = Field(
        description="Items needing immediate attention"
    )
    this_week_items: list[BriefingItem] = Field(
        description="Items for this week"
    )
    monitoring_items: list[BriefingItem] = Field(
        description="Items to monitor"
    )
    positive_items: list[BriefingItem] = Field(
        description="Positive developments"
    )
    portfolio_health: float = Field(
        ge=0, le=100, description="Overall portfolio health 0-100"
    )
    key_metrics: dict[str, Any] = Field(
        description="Key metrics snapshot"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date": "2026-02-21T00:00:00",
                "immediate_items": [
                    {
                        "category": "immediate",
                        "title": "Acme Corp - Invoice overdue",
                        "description": "INV-2026-001 is 55 days overdue",
                        "entity_type": "client",
                        "entity_id": "client_001",
                        "action_recommended": "Call client today",
                    }
                ],
                "this_week_items": [],
                "monitoring_items": [],
                "positive_items": [
                    {
                        "category": "positive",
                        "title": "Team utilization improving",
                        "description": "Two staff members now have capacity",
                        "entity_type": "team",
                        "entity_id": "team_001",
                        "action_recommended": None,
                    }
                ],
                "portfolio_health": 68.2,
                "key_metrics": {
                    "total_clients": 8,
                    "active_projects": 24,
                    "team_utilization": 0.72,
                    "outstanding_revenue": 145000.0,
                },
            }
        }
    )


# =============================================================================
# COMPREHENSIVE SNAPSHOT MODEL
# =============================================================================


class IntelligenceSnapshot(BaseModel):
    """Complete intelligence snapshot from full pipeline."""

    timestamp: datetime = Field(description="When snapshot was generated")
    portfolio: PortfolioDashboardResponse = Field(
        description="Portfolio overview"
    )
    signals: list[Signal] = Field(description="All detected signals")
    patterns: list[str] = Field(description="Detected patterns")
    proposals: list[ResolutionItem] = Field(description="Generated proposals")
    briefing: DailyBriefingResponse = Field(description="Daily briefing")
    team_capacity: TeamCapacityResponse = Field(description="Team capacity")
    financial: FinancialAgingResponse = Field(description="Financial aging")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2026-02-21T10:30:00",
                "portfolio": {
                    "clients": [],
                    "total_clients": 8,
                    "total_projects": 24,
                    "total_outstanding_revenue": 145000.0,
                    "portfolio_health_score": 68.2,
                },
                "signals": [],
                "patterns": ["revenue_concentration", "capacity_overload"],
                "proposals": [],
                "briefing": {
                    "date": "2026-02-21T00:00:00",
                    "immediate_items": [],
                    "this_week_items": [],
                    "monitoring_items": [],
                    "positive_items": [],
                    "portfolio_health": 68.2,
                    "key_metrics": {},
                },
                "team_capacity": {
                    "people": [],
                    "total_people": 12,
                    "total_active_tasks": 85,
                    "avg_tasks_per_person": 7.08,
                    "people_overloaded": 3,
                    "people_available": 4,
                    "team_utilization": 0.72,
                },
                "financial": {
                    "total_outstanding": 145000.0,
                    "by_bucket": [],
                    "clients_with_overdue": [],
                    "total_invoices_overdue": 15,
                },
            }
        }
    )
