"""
Time OS V5 — Issue Patterns

Defines patterns that trigger issue formation.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class IssuePattern:
    """
    Defines a pattern that triggers issue formation.

    When signals matching this pattern are detected, an issue is created.
    """

    # Issue classification
    issue_type: str
    issue_subtype: str

    # Signal matching
    required_signal_types: list[str]  # Must have at least one of these
    optional_signal_types: list[str]  # Adds to severity if present

    # Thresholds
    min_signal_count: int  # Minimum signals to trigger
    min_negative_magnitude: float  # Minimum total negative magnitude

    # Scope level
    scope_level: str  # task, project, retainer, brand, client

    # Severity determination
    severity_rules: dict[str, dict[str, Any]]

    # Display templates
    headline_template: str
    description_template: str

    # Recommended action
    recommended_action_template: str
    recommended_owner_role: str  # account_lead, pm, team_member
    recommended_urgency: str  # immediate, this_week, this_month


# =============================================================================
# SCHEDULE & DELIVERY PATTERNS
# =============================================================================

DEADLINE_RISK_PATTERN = IssuePattern(
    issue_type="schedule_delivery",
    issue_subtype="deadline_risk",
    required_signal_types=["task_overdue", "task_approaching"],
    optional_signal_types=["task_blocked", "task_due_moved_out"],
    min_signal_count=3,
    min_negative_magnitude=1.5,
    scope_level="project",
    severity_rules={
        "critical": {"overdue_count": 10, "magnitude": 5.0},
        "high": {"overdue_count": 5, "magnitude": 3.0},
        "medium": {"overdue_count": 3, "magnitude": 1.5},
    },
    headline_template="{scope_name}: {overdue_count} overdue, {approaching_count} approaching",
    description_template="Delivery at risk. {overdue_count} tasks overdue (worst: {worst_days}d). {approaching_count} approaching deadline.",
    recommended_action_template="Review task priorities, reassign or escalate blockers",
    recommended_owner_role="pm",
    recommended_urgency="this_week",
)

DELIVERY_CRISIS_PATTERN = IssuePattern(
    issue_type="schedule_delivery",
    issue_subtype="delivery_crisis",
    required_signal_types=["task_overdue"],
    optional_signal_types=["task_blocked", "task_completed_late"],
    min_signal_count=10,
    min_negative_magnitude=5.0,
    scope_level="project",
    severity_rules={
        "critical": {"overdue_count": 10, "magnitude": 5.0},
    },
    headline_template="{scope_name}: DELIVERY CRISIS - {overdue_count} overdue",
    description_template="Critical delivery failure. {overdue_count} tasks overdue. Immediate intervention required.",
    recommended_action_template="Emergency triage: identify critical path, reassign resources, client communication",
    recommended_owner_role="account_lead",
    recommended_urgency="immediate",
)


# =============================================================================
# QUALITY PATTERNS
# =============================================================================

REVISION_OVERLOAD_PATTERN = IssuePattern(
    issue_type="quality",
    issue_subtype="revision_overload",
    required_signal_types=["revision_cycle_high", "revision_cycle_excessive"],
    optional_signal_types=["sentiment_negative", "meeting_concern_raised"],
    min_signal_count=1,
    min_negative_magnitude=0.5,
    scope_level="task",
    severity_rules={
        "high": {"excessive_count": 1},
        "medium": {"high_count": 1},
    },
    headline_template="{scope_name}: {version_count} versions",
    description_template="Excessive revisions indicate alignment or quality issue. Review brief clarity and feedback loop.",
    recommended_action_template="Schedule alignment call with client, review brief, assess if scope changed",
    recommended_owner_role="pm",
    recommended_urgency="this_week",
)

APPROVAL_STALL_PATTERN = IssuePattern(
    issue_type="quality",
    issue_subtype="approval_stall",
    required_signal_types=["communication_gap"],
    optional_signal_types=["response_slow_client"],
    min_signal_count=1,
    min_negative_magnitude=0.3,
    scope_level="project",
    severity_rules={
        "high": {"gap_days": 10},
        "medium": {"gap_days": 5},
    },
    headline_template="{scope_name}: Awaiting response ({gap_days}d)",
    description_template="Deliverable waiting for client feedback/approval. Risk of blocking downstream work.",
    recommended_action_template="Follow up with client, confirm receipt, request feedback timeline",
    recommended_owner_role="pm",
    recommended_urgency="this_week",
)


# =============================================================================
# FINANCIAL PATTERNS
# =============================================================================

AR_AGING_PATTERN = IssuePattern(
    issue_type="financial",
    issue_subtype="ar_aging",
    required_signal_types=[
        "invoice_overdue_30",
        "invoice_overdue_60",
        "invoice_overdue_90",
    ],
    optional_signal_types=["communication_gap", "sentiment_negative"],
    min_signal_count=1,
    min_negative_magnitude=0.5,
    scope_level="client",
    severity_rules={
        "critical": {"bucket": "90+", "amount": 50000},
        "high": {"bucket": "61-90", "amount": 20000},
        "medium": {"bucket": "31-60", "amount": 5000},
    },
    headline_template="{scope_name}: {currency} {amount:,.0f} AR ({bucket})",
    description_template="Invoice(s) overdue. Total: {currency} {amount:,.0f}. Oldest: {days_overdue}d.",
    recommended_action_template="Finance to follow up, review payment terms, escalate if no response",
    recommended_owner_role="account_lead",
    recommended_urgency="this_week",
)


# =============================================================================
# COMMUNICATION PATTERNS
# =============================================================================

ENGAGEMENT_DECLINE_PATTERN = IssuePattern(
    issue_type="communication",
    issue_subtype="engagement_decline",
    required_signal_types=["communication_gap"],
    optional_signal_types=["response_slow_client", "meeting_noshow_client"],
    min_signal_count=1,
    min_negative_magnitude=0.5,
    scope_level="client",
    severity_rules={
        "high": {"gap_days": 14},
        "medium": {"gap_days": 7},
    },
    headline_template="{scope_name}: Engagement declining",
    description_template="Communication frequency down. Last meaningful contact: {gap_days}d ago.",
    recommended_action_template="Proactive outreach - schedule check-in, understand if concerns",
    recommended_owner_role="account_lead",
    recommended_urgency="this_week",
)

ESCALATION_PATTERN = IssuePattern(
    issue_type="communication",
    issue_subtype="escalation_active",
    required_signal_types=["escalation_detected"],
    optional_signal_types=["sentiment_negative", "meeting_title_urgent"],
    min_signal_count=1,
    min_negative_magnitude=0.8,
    scope_level="client",
    severity_rules={
        "critical": {"count": 1},  # Any escalation is serious
    },
    headline_template="{scope_name}: ESCALATION DETECTED",
    description_template="Client using escalation language. Immediate attention required.",
    recommended_action_template="Senior account contact within 24h, understand issue, propose resolution",
    recommended_owner_role="account_lead",
    recommended_urgency="immediate",
)


# =============================================================================
# RELATIONSHIP PATTERNS
# =============================================================================

RELATIONSHIP_AT_RISK_PATTERN = IssuePattern(
    issue_type="relationship",
    issue_subtype="relationship_at_risk",
    required_signal_types=[],  # Any combination of negatives
    optional_signal_types=[
        "task_overdue",
        "invoice_overdue_30",
        "invoice_overdue_60",
        "invoice_overdue_90",
        "communication_gap",
        "sentiment_negative",
        "revision_cycle_high",
        "revision_cycle_excessive",
        "escalation_detected",
        "meeting_noshow_client",
        "meeting_concern_raised",
    ],
    min_signal_count=5,  # Multiple issues across categories
    min_negative_magnitude=3.0,
    scope_level="client",
    severity_rules={
        "critical": {"categories": 4, "magnitude": 5.0},
        "high": {"categories": 3, "magnitude": 3.0},
    },
    headline_template="{scope_name}: RELATIONSHIP AT RISK",
    description_template="Multiple issues detected across {category_count} categories. Net signal score: {net_score:.1f}. Immediate intervention needed.",
    recommended_action_template="Executive attention: full relationship review, address all open issues, rebuild trust",
    recommended_owner_role="account_lead",
    recommended_urgency="immediate",
)


# =============================================================================
# PATTERN REGISTRY
# =============================================================================

ALL_PATTERNS: list[IssuePattern] = [
    # Schedule & Delivery
    DEADLINE_RISK_PATTERN,
    DELIVERY_CRISIS_PATTERN,
    # Quality
    REVISION_OVERLOAD_PATTERN,
    APPROVAL_STALL_PATTERN,
    # Financial
    AR_AGING_PATTERN,
    # Communication
    ENGAGEMENT_DECLINE_PATTERN,
    ESCALATION_PATTERN,
    # Relationship
    RELATIONSHIP_AT_RISK_PATTERN,
]


def get_pattern(issue_subtype: str) -> IssuePattern | None:
    """Get pattern by subtype."""
    for pattern in ALL_PATTERNS:
        if pattern.issue_subtype == issue_subtype:
            return pattern
    return None


def get_patterns_for_type(issue_type: str) -> list[IssuePattern]:
    """Get all patterns for an issue type."""
    return [p for p in ALL_PATTERNS if p.issue_type == issue_type]
