"""
Domain Models — Canonical Types for Normalized Data.

These are the intermediate representations AFTER extraction and BEFORE aggregation.
They carry resolution metadata (resolved_client_id, unresolved_reason, etc.)

Per IMPLEMENTATION_PLAN_V4_FROZEN.md:
- NormalizedData includes ResolutionStats
- Stats are used for threshold checks
- No silent None — always have a reason
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

# =============================================================================
# RESOLUTION STATS (for threshold checks)
# =============================================================================


@dataclass
class ResolutionStats:
    """
    Resolution statistics computed during normalization.

    These stats are used by thresholds.py to enforce quality gates.
    """

    # Commitment resolution
    commitments_total: int = 0
    commitments_resolved: int = 0

    @property
    def commitments_resolution_rate(self) -> float:
        return (
            self.commitments_resolved / self.commitments_total
            if self.commitments_total > 0
            else 0.0
        )

    # Thread-client linkage
    threads_total: int = 0
    threads_with_client: int = 0

    @property
    def threads_client_rate(self) -> float:
        return (
            self.threads_with_client / self.threads_total
            if self.threads_total > 0
            else 0.0
        )

    # Invoice validity
    invoices_total: int = 0
    invoices_valid: int = 0

    @property
    def invoices_valid_rate(self) -> float:
        return (
            self.invoices_valid / self.invoices_total
            if self.invoices_total > 0
            else 0.0
        )

    # People hours completeness
    people_total: int = 0
    people_with_hours: int = 0

    @property
    def people_hours_rate(self) -> float:
        return (
            self.people_with_hours / self.people_total if self.people_total > 0 else 0.0
        )

    # Project-client linkage
    projects_total: int = 0
    projects_with_client: int = 0

    @property
    def projects_client_rate(self) -> float:
        return (
            self.projects_with_client / self.projects_total
            if self.projects_total > 0
            else 0.0
        )


# =============================================================================
# DOMAIN MODELS
# =============================================================================


@dataclass
class Project:
    """Normalized project representation."""

    project_id: str
    name: str
    status: Literal["RED", "YELLOW", "GREEN", "UNKNOWN"] = "UNKNOWN"
    client_id: str | None = None
    client_name: str | None = None
    overdue_count: int = 0
    total_tasks: int = 0
    slip_risk_score: float = 0.0
    time_to_slip_hours: float | None = None
    top_driver: str | None = None
    confidence: Literal["HIGH", "MED", "LOW"] = "MED"

    # Resolution metadata
    client_resolved: bool = False
    unresolved_reason: str | None = None


@dataclass
class Client:
    """Normalized client representation."""

    client_id: str
    name: str
    tier: Literal["A", "B", "C", "D", "untiered"] = "untiered"
    health_score: float = 0.5
    health_status: Literal["critical", "poor", "fair", "good", "excellent"] = "fair"
    total_ar: float = 0.0
    overdue_tasks: int = 0
    at_risk: bool = False

    # Source reference
    source: str = "unknown"
    source_id: str | None = None


@dataclass
class Invoice:
    """Normalized invoice representation."""

    invoice_id: str
    invoice_number: str | None = None
    client_id: str | None = None
    client_name: str | None = None
    amount: float = 0.0
    currency: str = "AED"
    status: Literal["draft", "sent", "overdue", "paid", "void"] = "draft"
    due_date: str | None = None
    payment_date: str | None = None

    @property
    def is_unpaid(self) -> bool:
        return self.status in ("sent", "overdue") and self.payment_date is None

    @property
    def is_valid_ar(self) -> bool:
        """Valid for AR calculation if has required fields."""
        return (
            self.is_unpaid
            and self.due_date is not None
            and self.client_id is not None
            and self.amount > 0
        )

    @property
    def days_overdue(self) -> int:
        """Calculate days overdue. Returns 0 if not overdue."""
        if not self.due_date or not self.is_unpaid:
            return 0
        try:
            due = datetime.fromisoformat(self.due_date.replace("Z", "+00:00"))
            now = datetime.now(due.tzinfo) if due.tzinfo else datetime.now()
            diff = (now - due).days
            return max(0, diff)
        except (ValueError, TypeError):
            return 0


@dataclass
class Commitment:
    """
    Normalized commitment representation.

    Per Amendment 2: resolved_client_id=None REQUIRES unresolved_reason.
    No silent None allowed.
    """

    commitment_id: str
    content: str
    scope_ref_type: str
    scope_ref_id: str

    # Resolution result — one of these must be set
    resolved_client_id: str | None = None
    unresolved_reason: str | None = None

    # Additional metadata
    due_date: str | None = None
    created_at: str | None = None
    source_thread_id: str | None = None

    @property
    def is_resolved(self) -> bool:
        return self.resolved_client_id is not None

    @property
    def is_overdue(self) -> bool:
        if not self.due_date:
            return False
        try:
            due = datetime.fromisoformat(self.due_date.replace("Z", "+00:00"))
            now = datetime.now(due.tzinfo) if due.tzinfo else datetime.now()
            return now > due
        except (ValueError, TypeError):
            return False


@dataclass
class Communication:
    """Normalized communication/thread representation."""

    thread_id: str
    subject: str
    client_id: str | None = None
    client_name: str | None = None
    last_activity: str | None = None
    message_count: int = 0
    commitment_count: int = 0

    # Source metadata
    source: str = "unknown"  # email, slack, etc.
    participants: list[str] = field(default_factory=list)


@dataclass
class Person:
    """Normalized person representation."""

    person_id: str | None = None
    name: str = ""
    email: str | None = None
    hours_assigned: float = 0.0
    hours_capacity: float = 0.0

    @property
    def utilization(self) -> float:
        if self.hours_capacity <= 0:
            return 0.0
        return self.hours_assigned / self.hours_capacity

    @property
    def gap_hours(self) -> float:
        return self.hours_assigned - self.hours_capacity

    @property
    def is_overloaded(self) -> bool:
        return self.hours_assigned > self.hours_capacity


# =============================================================================
# NORMALIZED DATA CONTAINER
# =============================================================================


@dataclass
class NormalizedData:
    """
    Container for all normalized domain data.

    This is the output of the normalization phase and input to aggregation.
    Includes resolution stats for threshold checks.
    """

    projects: list[Project] = field(default_factory=list)
    clients: list[Client] = field(default_factory=list)
    invoices: list[Invoice] = field(default_factory=list)
    commitments: list[Commitment] = field(default_factory=list)
    communications: list[Communication] = field(default_factory=list)
    people: list[Person] = field(default_factory=list)

    # Resolution statistics
    stats: ResolutionStats = field(default_factory=ResolutionStats)

    def compute_stats(self) -> ResolutionStats:
        """Compute resolution stats from current data."""
        stats = ResolutionStats()

        # Commitment resolution
        stats.commitments_total = len(self.commitments)
        stats.commitments_resolved = sum(1 for c in self.commitments if c.is_resolved)

        # Thread-client linkage
        stats.threads_total = len(self.communications)
        stats.threads_with_client = sum(1 for t in self.communications if t.client_id)

        # Invoice validity
        stats.invoices_total = len(self.invoices)
        stats.invoices_valid = sum(1 for i in self.invoices if i.is_valid_ar)

        # People hours completeness
        stats.people_total = len(self.people)
        stats.people_with_hours = sum(1 for p in self.people if p.hours_assigned > 0)

        # Project-client linkage
        stats.projects_total = len(self.projects)
        stats.projects_with_client = sum(1 for p in self.projects if p.client_id)

        self.stats = stats
        return stats
