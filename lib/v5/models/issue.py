"""
Time OS V5 — Issue Model

Issue model with balance tracking and lifecycle.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from .base import BaseModel, generate_id, json_dumps_safe, json_loads_safe, now_iso

# =============================================================================
# ISSUE ENUMS
# =============================================================================


class IssueType(StrEnum):
    """Issue type categories."""

    SCHEDULE_DELIVERY = "schedule_delivery"
    QUALITY = "quality"
    FINANCIAL = "financial"
    COMMUNICATION = "communication"
    RELATIONSHIP = "relationship"
    PROCESS = "process"


class IssueSubtype(StrEnum):
    """Issue subtypes."""

    # Schedule/Delivery
    DEADLINE_RISK = "deadline_risk"
    DELIVERY_CRISIS = "delivery_crisis"

    # Quality
    REVISION_OVERLOAD = "revision_overload"
    APPROVAL_STALL = "approval_stall"

    # Financial
    AR_AGING = "ar_aging"
    PAYMENT_DELAY = "payment_delay"

    # Communication
    ENGAGEMENT_DECLINE = "engagement_decline"
    ESCALATION_ACTIVE = "escalation_active"
    RESPONSE_LAG = "response_lag"

    # Relationship
    RELATIONSHIP_AT_RISK = "relationship_at_risk"

    # Process
    RESOURCE_BOTTLENECK = "resource_bottleneck"
    WORKFLOW_BREAKDOWN = "workflow_breakdown"


class IssueSeverity(StrEnum):
    """Issue severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IssueState(StrEnum):
    """Issue lifecycle states."""

    DETECTED = "detected"  # System identified, not yet surfaced
    SURFACED = "surfaced"  # Shown in UI
    ACKNOWLEDGED = "acknowledged"  # User has seen it
    ADDRESSING = "addressing"  # User is working on it
    RESOLVED = "resolved"  # Fixed
    MONITORING = "monitoring"  # In 90-day regression watch
    CLOSED = "closed"  # Permanently closed


class IssueTrajectory(StrEnum):
    """Issue trajectory (trend direction)."""

    WORSENING = "worsening"
    STABLE = "stable"
    IMPROVING = "improving"


class ResolutionMethod(StrEnum):
    """How an issue was resolved."""

    SIGNALS_BALANCED = "signals_balanced"  # Positive signals outweighed negative
    TASKS_COMPLETED = "tasks_completed"  # Underlying tasks done
    MANUAL = "manual"  # User marked resolved
    AUTO_EXPIRED = "auto_expired"  # Signals expired
    DISMISSED = "dismissed"  # User dismissed (not a real issue)


class ScopeType(StrEnum):
    """Scope level for an issue."""

    TASK = "task"
    PROJECT = "project"
    RETAINER = "retainer"
    BRAND = "brand"
    CLIENT = "client"


class RecommendedUrgency(StrEnum):
    """Recommended urgency for addressing an issue."""

    IMMEDIATE = "immediate"
    THIS_WEEK = "this_week"
    THIS_MONTH = "this_month"


# =============================================================================
# SIGNAL BALANCE SUMMARY
# =============================================================================


@dataclass
class SignalBalance:
    """Summary of signal balance for an issue."""

    negative_count: int = 0
    negative_magnitude: float = 0.0
    neutral_count: int = 0
    positive_count: int = 0
    positive_magnitude: float = 0.0

    @property
    def net_score(self) -> float:
        """Calculate net score (positive - negative)."""
        return self.positive_magnitude - self.negative_magnitude

    @property
    def is_balanced(self) -> bool:
        """Check if positive signals balance negative."""
        return self.net_score >= 0

    @property
    def total_count(self) -> int:
        """Total signal count."""
        return self.negative_count + self.neutral_count + self.positive_count

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "negative_count": self.negative_count,
            "negative_magnitude": self.negative_magnitude,
            "neutral_count": self.neutral_count,
            "positive_count": self.positive_count,
            "positive_magnitude": self.positive_magnitude,
            "net_score": self.net_score,
        }


# =============================================================================
# ISSUE MODEL
# =============================================================================


@dataclass
class Issue(BaseModel):
    """
    Issue model formed from signal patterns.

    Issues represent actionable problems detected from signals.
    They have:
    - Balance tracking (negative vs positive signal magnitudes)
    - Lifecycle states (detected → surfaced → addressing → resolved → monitoring → closed)
    - Regression tracking (can reopen if problem recurs)
    """

    # Classification
    issue_type: IssueType = IssueType.PROCESS
    issue_subtype: str = ""  # More flexible than enum

    # Scope
    scope_type: ScopeType = ScopeType.CLIENT
    scope_id: str = ""

    # Scope chain (for context)
    scope_task_ids: str | None = None  # JSON array
    scope_project_ids: str | None = None  # JSON array
    scope_retainer_id: str | None = None
    scope_brand_id: str | None = None
    scope_client_id: str | None = None

    # Display
    headline: str = ""
    description: str | None = None

    # Severity
    severity: IssueSeverity = IssueSeverity.MEDIUM
    priority_score: float = 0.0
    trajectory: IssueTrajectory = IssueTrajectory.STABLE

    # Signal evidence
    signal_ids: str = "[]"  # JSON array of contributing signal IDs

    # Signal balance (cached for performance)
    balance_negative_count: int = 0
    balance_negative_magnitude: float = 0.0
    balance_neutral_count: int = 0
    balance_positive_count: int = 0
    balance_positive_magnitude: float = 0.0
    balance_net_score: float = 0.0

    # Recommended action
    recommended_action: str | None = None
    recommended_owner_role: str | None = None  # "account_lead", "pm", "team_member"
    recommended_urgency: RecommendedUrgency | None = None

    # Lifecycle
    state: IssueState = IssueState.DETECTED

    # Timestamps
    detected_at: str = field(default_factory=now_iso)
    surfaced_at: str | None = None
    acknowledged_at: str | None = None
    acknowledged_by: str | None = None
    addressing_started_at: str | None = None
    resolved_at: str | None = None
    monitoring_until: str | None = None
    closed_at: str | None = None

    # Resolution
    resolution_method: ResolutionMethod | None = None
    resolution_notes: str | None = None
    resolved_by: str | None = None

    # Regression
    regression_count: int = 0
    last_regression_at: str | None = None

    # History
    state_history: str | None = None  # JSON array of {state, timestamp, by}
    score_history: str | None = None  # JSON array of {score, timestamp}

    def __post_init__(self):
        if not self.id:
            self.id = generate_id("iss")
        if isinstance(self.issue_type, str):
            self.issue_type = IssueType(self.issue_type)
        if isinstance(self.scope_type, str):
            self.scope_type = ScopeType(self.scope_type)
        if isinstance(self.severity, str):
            self.severity = IssueSeverity(self.severity)
        if isinstance(self.trajectory, str):
            self.trajectory = IssueTrajectory(self.trajectory)
        if isinstance(self.state, str):
            self.state = IssueState(self.state)
        if isinstance(self.resolution_method, str):
            self.resolution_method = ResolutionMethod(self.resolution_method)
        if isinstance(self.recommended_urgency, str):
            self.recommended_urgency = RecommendedUrgency(self.recommended_urgency)

    # =========================================================================
    # Signal IDs Access
    # =========================================================================

    def get_signal_ids(self) -> list[str]:
        """Get signal IDs as list."""
        return json_loads_safe(self.signal_ids) or []

    def set_signal_ids(self, ids: list[str]) -> None:
        """Set signal IDs from list."""
        self.signal_ids = json_dumps_safe(ids) or "[]"

    def add_signal_id(self, signal_id: str) -> None:
        """Add a signal ID."""
        ids = self.get_signal_ids()
        if signal_id not in ids:
            ids.append(signal_id)
            self.set_signal_ids(ids)

    # =========================================================================
    # Scope Chain Access
    # =========================================================================

    def get_scope_task_ids(self) -> list[str]:
        """Get scope task IDs as list."""
        return json_loads_safe(self.scope_task_ids) or []

    def get_scope_project_ids(self) -> list[str]:
        """Get scope project IDs as list."""
        return json_loads_safe(self.scope_project_ids) or []

    # =========================================================================
    # Balance
    # =========================================================================

    @property
    def balance(self) -> SignalBalance:
        """Get signal balance summary."""
        return SignalBalance(
            negative_count=self.balance_negative_count,
            negative_magnitude=self.balance_negative_magnitude,
            neutral_count=self.balance_neutral_count,
            positive_count=self.balance_positive_count,
            positive_magnitude=self.balance_positive_magnitude,
        )

    def update_balance(self, balance: SignalBalance) -> None:
        """Update cached balance."""
        self.balance_negative_count = balance.negative_count
        self.balance_negative_magnitude = balance.negative_magnitude
        self.balance_neutral_count = balance.neutral_count
        self.balance_positive_count = balance.positive_count
        self.balance_positive_magnitude = balance.positive_magnitude
        self.balance_net_score = balance.net_score
        self.update_timestamp()

    # =========================================================================
    # Lifecycle Methods
    # =========================================================================

    def _record_state_change(
        self, new_state: IssueState, by: str | None = None
    ) -> None:
        """Record state change in history."""
        history = json_loads_safe(self.state_history) or []
        history.append({"state": new_state.value, "timestamp": now_iso(), "by": by})
        self.state_history = json_dumps_safe(history)

    def surface(self) -> None:
        """Surface issue for user attention."""
        self._record_state_change(IssueState.SURFACED)
        self.state = IssueState.SURFACED
        self.surfaced_at = now_iso()
        self.update_timestamp()

    def acknowledge(self, by: str) -> None:
        """Mark issue as acknowledged."""
        self._record_state_change(IssueState.ACKNOWLEDGED, by)
        self.state = IssueState.ACKNOWLEDGED
        self.acknowledged_at = now_iso()
        self.acknowledged_by = by
        self.update_timestamp()

    def start_addressing(self, by: str | None = None) -> None:
        """Mark issue as being addressed."""
        self._record_state_change(IssueState.ADDRESSING, by)
        self.state = IssueState.ADDRESSING
        self.addressing_started_at = now_iso()
        self.update_timestamp()

    def resolve(
        self, method: ResolutionMethod, by: str | None = None, notes: str | None = None
    ) -> None:
        """Resolve the issue and start monitoring."""
        self._record_state_change(IssueState.RESOLVED, by)
        self.state = IssueState.RESOLVED
        self.resolution_method = method
        self.resolved_by = by
        self.resolution_notes = notes
        self.resolved_at = now_iso()

        # Set monitoring period (90 days)
        monitoring_end = datetime.now() + timedelta(days=90)
        self.monitoring_until = monitoring_end.isoformat()

        # Move to monitoring state
        self._record_state_change(IssueState.MONITORING)
        self.state = IssueState.MONITORING

        self.update_timestamp()

    def dismiss(self, by: str, reason: str | None = None) -> None:
        """Dismiss issue as not relevant."""
        self._record_state_change(IssueState.CLOSED, by)
        self.state = IssueState.CLOSED
        self.resolution_method = ResolutionMethod.DISMISSED
        self.resolved_by = by
        self.resolution_notes = reason
        self.resolved_at = now_iso()
        self.closed_at = now_iso()
        self.update_timestamp()

    def close(self) -> None:
        """Permanently close issue after successful monitoring."""
        self._record_state_change(IssueState.CLOSED)
        self.state = IssueState.CLOSED
        self.closed_at = now_iso()
        self.update_timestamp()

    def regress(self) -> None:
        """Reopen issue due to regression."""
        self._record_state_change(IssueState.SURFACED)
        self.state = IssueState.SURFACED
        self.regression_count += 1
        self.last_regression_at = now_iso()

        # Clear resolution fields
        self.resolved_at = None
        self.resolution_method = None
        self.monitoring_until = None

        self.update_timestamp()

    # =========================================================================
    # State Checks
    # =========================================================================

    @property
    def is_open(self) -> bool:
        """Check if issue is still open (not resolved or closed)."""
        return self.state not in (
            IssueState.RESOLVED,
            IssueState.MONITORING,
            IssueState.CLOSED,
        )

    @property
    def is_active(self) -> bool:
        """Check if issue needs attention."""
        return self.state in (
            IssueState.SURFACED,
            IssueState.ACKNOWLEDGED,
            IssueState.ADDRESSING,
        )

    @property
    def is_monitoring(self) -> bool:
        """Check if in monitoring period."""
        return self.state == IssueState.MONITORING

    @property
    def should_close_monitoring(self) -> bool:
        """Check if monitoring period is complete."""
        if not self.is_monitoring or not self.monitoring_until:
            return False
        try:
            until = datetime.fromisoformat(self.monitoring_until)
            return datetime.now() > until
        except (ValueError, TypeError):
            return False

    # =========================================================================
    # Priority Calculation
    # =========================================================================

    def calculate_priority(self) -> float:
        """Calculate priority score."""
        # Base score from severity
        severity_base = {
            IssueSeverity.CRITICAL: 100,
            IssueSeverity.HIGH: 70,
            IssueSeverity.MEDIUM: 40,
            IssueSeverity.LOW: 20,
        }

        # Scope multiplier (higher scope = more important)
        scope_mult = {
            ScopeType.TASK: 0.5,
            ScopeType.PROJECT: 1.0,
            ScopeType.RETAINER: 1.2,
            ScopeType.BRAND: 1.5,
            ScopeType.CLIENT: 2.0,
        }

        # Trajectory multiplier
        trajectory_mult = {
            IssueTrajectory.WORSENING: 1.3,
            IssueTrajectory.STABLE: 1.0,
            IssueTrajectory.IMPROVING: 0.8,
        }

        base = severity_base.get(self.severity, 40)
        scope = scope_mult.get(self.scope_type, 1.0)
        traj = trajectory_mult.get(self.trajectory, 1.0)

        # Factor in magnitude
        mag_factor = 1 + (abs(self.balance_net_score) * 0.1)

        # Regression penalty
        regression_penalty = 1 + (self.regression_count * 0.2)

        return base * scope * traj * mag_factor * regression_penalty

    def update_priority(self) -> None:
        """Update priority score."""
        self.priority_score = self.calculate_priority()
        self.update_timestamp()
