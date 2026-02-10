"""
Time OS V5 — Entity Models

Core business entity models: Client, Brand, Project, Retainer, Task, Person.
"""

from dataclasses import dataclass, field
from datetime import datetime

from .base import (
    ArchivableModel,
    BaseModel,
    ClientTier,
    DetectedFrom,
    HealthStatus,
    PersonType,
    ProjectHealth,
    ProjectPhase,
    RetainerCycleStatus,
    RetainerStatus,
    TaskPriority,
    TaskStatus,
    VersionStatus,
    generate_id,
    json_dumps_safe,
    json_loads_safe,
    now_iso,
)

# =============================================================================
# PERSON
# =============================================================================


@dataclass
class Person(ArchivableModel):
    """Team member or contact."""

    # Identity
    name: str = ""
    email: str | None = None
    phone: str | None = None

    # Type
    person_type: PersonType = PersonType.OTHER

    # Team-specific
    role: str | None = None
    department: str | None = None
    is_active: bool = True

    # Client contact specific
    client_id: str | None = None
    is_primary_contact: bool = False

    def __post_init__(self):
        if not self.id:
            self.id = generate_id("per")


# =============================================================================
# CLIENT
# =============================================================================


@dataclass
class Client(ArchivableModel):
    """Client entity."""

    # Identity
    name: str = ""
    legal_name: str | None = None
    xero_contact_id: str | None = None

    # Classification
    tier: ClientTier = ClientTier.UNCLASSIFIED
    tier_reason: str | None = None
    tier_updated_at: str | None = None

    # Commercial
    annual_revenue_target: float = 0.0
    lifetime_revenue: float = 0.0

    # Relationship
    relationship_start_date: str | None = None
    primary_contact_id: str | None = None
    account_lead_id: str | None = None

    # Health (computed, cached)
    health_status: HealthStatus = HealthStatus.HEALTHY
    health_score: float = 100.0
    health_updated_at: str | None = None

    def __post_init__(self):
        if not self.id:
            self.id = generate_id("cli")
        if isinstance(self.tier, str):
            self.tier = ClientTier(self.tier)
        if isinstance(self.health_status, str):
            self.health_status = HealthStatus(self.health_status)

    def update_tier(self, tier: ClientTier, reason: str) -> None:
        """Update client tier with reason."""
        self.tier = tier
        self.tier_reason = reason
        self.tier_updated_at = now_iso()
        self.update_timestamp()

    def update_health(self, status: HealthStatus, score: float) -> None:
        """Update cached health status."""
        self.health_status = status
        self.health_score = score
        self.health_updated_at = now_iso()
        self.update_timestamp()


# =============================================================================
# BRAND
# =============================================================================


@dataclass
class Brand(ArchivableModel):
    """Brand entity under a client."""

    client_id: str = ""

    # Identity
    name: str = ""
    description: str | None = None

    # Health (computed)
    health_status: HealthStatus = HealthStatus.HEALTHY
    health_score: float = 100.0
    health_updated_at: str | None = None

    def __post_init__(self):
        if not self.id:
            self.id = generate_id("brd")
        if isinstance(self.health_status, str):
            self.health_status = HealthStatus(self.health_status)

    def update_health(self, status: HealthStatus, score: float) -> None:
        """Update cached health status."""
        self.health_status = status
        self.health_score = score
        self.health_updated_at = now_iso()
        self.update_timestamp()


# =============================================================================
# PROJECT
# =============================================================================


@dataclass
class Project(BaseModel):
    """Project entity (detected, not declared)."""

    brand_id: str = ""
    client_id: str = ""

    # Identity
    name: str = ""
    description: str | None = None

    # Detection evidence
    detected_from: DetectedFrom | None = None
    detection_confidence: float = 1.0

    # Xero links
    quote_id: str | None = None
    quote_number: str | None = None
    advance_invoice_id: str | None = None
    final_invoice_id: str | None = None

    # Value
    quoted_value: float | None = None
    invoiced_value: float = 0.0
    paid_value: float = 0.0

    # Lifecycle
    phase: ProjectPhase = ProjectPhase.OPPORTUNITY
    phase_changed_at: str | None = None
    phase_history: str | None = None  # JSON array

    # Timeline
    detected_at: str = field(default_factory=now_iso)
    expected_start_date: str | None = None
    expected_end_date: str | None = None
    actual_start_date: str | None = None
    actual_end_date: str | None = None

    # Health
    health_status: ProjectHealth = ProjectHealth.ON_TRACK
    health_score: float = 100.0
    health_updated_at: str | None = None

    def __post_init__(self):
        if not self.id:
            self.id = generate_id("prj")
        if isinstance(self.phase, str):
            self.phase = ProjectPhase(self.phase)
        if isinstance(self.detected_from, str):
            self.detected_from = DetectedFrom(self.detected_from)
        if isinstance(self.health_status, str):
            self.health_status = ProjectHealth(self.health_status)

    def advance_phase(self, new_phase: ProjectPhase) -> None:
        """Advance to new phase, recording history."""
        history = json_loads_safe(self.phase_history) or []
        history.append({"phase": self.phase.value, "timestamp": now_iso()})
        self.phase_history = json_dumps_safe(history)
        self.phase = new_phase
        self.phase_changed_at = now_iso()
        self.update_timestamp()

    def update_health(self, status: ProjectHealth, score: float) -> None:
        """Update cached health status."""
        self.health_status = status
        self.health_score = score
        self.health_updated_at = now_iso()
        self.update_timestamp()

    @property
    def is_active(self) -> bool:
        """Check if project is in active phase."""
        return self.phase in (
            ProjectPhase.CONFIRMED,
            ProjectPhase.KICKOFF,
            ProjectPhase.EXECUTION,
            ProjectPhase.DELIVERY,
            ProjectPhase.CLOSEOUT,
        )


# =============================================================================
# RETAINER
# =============================================================================


@dataclass
class Retainer(BaseModel):
    """Retainer contract."""

    brand_id: str = ""
    client_id: str = ""

    # Identity
    name: str = ""
    description: str | None = None
    scope_definition: str | None = None

    # Commercial
    monthly_value: float = 0.0
    currency: str = "AED"

    # Timeline
    start_date: str = ""
    end_date: str | None = None
    renewal_date: str | None = None

    # Status
    status: RetainerStatus = RetainerStatus.ACTIVE
    status_changed_at: str | None = None
    churn_reason: str | None = None

    # Health
    health_status: HealthStatus = HealthStatus.HEALTHY
    health_score: float = 100.0
    health_updated_at: str | None = None

    def __post_init__(self):
        if not self.id:
            self.id = generate_id("ret")
        if isinstance(self.status, str):
            self.status = RetainerStatus(self.status)
        if isinstance(self.health_status, str):
            self.health_status = HealthStatus(self.health_status)

    def churn(self, reason: str) -> None:
        """Mark retainer as churned."""
        self.status = RetainerStatus.CHURNED
        self.churn_reason = reason
        self.status_changed_at = now_iso()
        self.update_timestamp()

    def renew(self, new_renewal_date: str | None = None) -> None:
        """Mark retainer as renewed."""
        self.status = RetainerStatus.RENEWED
        self.status_changed_at = now_iso()
        if new_renewal_date:
            self.renewal_date = new_renewal_date
        self.update_timestamp()


# =============================================================================
# RETAINER CYCLE
# =============================================================================


@dataclass
class RetainerCycle(BaseModel):
    """Monthly retainer cycle."""

    retainer_id: str = ""

    # Period
    cycle_month: str = ""  # "2026-02"
    start_date: str = ""
    end_date: str = ""

    # Status
    status: RetainerCycleStatus = RetainerCycleStatus.UPCOMING

    # Financials
    invoice_id: str | None = None
    invoice_amount: float | None = None
    paid_amount: float = 0.0
    paid_at: str | None = None

    # Metrics
    tasks_planned: int = 0
    tasks_completed: int = 0
    tasks_overdue: int = 0

    def __post_init__(self):
        if not self.id:
            self.id = generate_id("cyc")
        if isinstance(self.status, str):
            self.status = RetainerCycleStatus(self.status)

    def advance_status(self, new_status: RetainerCycleStatus) -> None:
        """Advance to new status."""
        self.status = new_status
        self.update_timestamp()

    @property
    def completion_rate(self) -> float:
        """Calculate task completion rate."""
        if self.tasks_planned == 0:
            return 0.0
        return self.tasks_completed / self.tasks_planned


# =============================================================================
# TASK
# =============================================================================


@dataclass
class Task(BaseModel):
    """Task entity with enhanced tracking."""

    # Asana link
    asana_gid: str | None = None
    asana_project_gid: str | None = None
    asana_parent_gid: str | None = None

    # Content
    title: str = ""
    description: str | None = None

    # Assignment
    assignee_id: str | None = None
    assignee_name: str | None = None
    assignee_email: str | None = None

    # Status
    status: TaskStatus = TaskStatus.NOT_STARTED
    status_changed_at: str | None = None
    completed_at: str | None = None

    # Timeline
    due_date: str | None = None
    due_time: str | None = None
    start_date: str | None = None

    # Hierarchy links
    project_id: str | None = None
    retainer_cycle_id: str | None = None
    brand_id: str | None = None
    client_id: str | None = None

    # Versioning
    is_deliverable: bool = False
    current_version: int = 0

    # Priority
    priority: TaskPriority = TaskPriority.MEDIUM
    priority_score: int = 50

    # Sync
    synced_at: str | None = None

    def __post_init__(self):
        if not self.id:
            self.id = generate_id("tsk")
        if isinstance(self.status, str):
            self.status = TaskStatus(self.status)
        if isinstance(self.priority, str):
            self.priority = TaskPriority(self.priority)

    def complete(self) -> None:
        """Mark task as completed."""
        self.status = TaskStatus.DONE
        self.completed_at = now_iso()
        self.status_changed_at = now_iso()
        self.update_timestamp()

    def update_status(self, new_status: TaskStatus) -> None:
        """Update task status."""
        self.status = new_status
        self.status_changed_at = now_iso()
        if new_status == TaskStatus.DONE:
            self.completed_at = now_iso()
        self.update_timestamp()

    @property
    def is_complete(self) -> bool:
        """Check if task is complete."""
        return self.status == TaskStatus.DONE

    @property
    def is_overdue(self) -> bool:
        """Check if task is overdue."""
        if self.due_date is None:
            return False
        if self.status in (TaskStatus.DONE, TaskStatus.CANCELLED):
            return False
        try:
            due = datetime.fromisoformat(self.due_date[:10])
            return datetime.now().date() > due.date()
        except (ValueError, TypeError):
            return False

    def calculate_days_overdue(self) -> int:
        """Calculate days overdue (0 if not overdue)."""
        if not self.is_overdue:
            return 0
        try:
            due = datetime.fromisoformat(self.due_date[:10])
            return (datetime.now().date() - due.date()).days
        except (ValueError, TypeError):
            return 0


# =============================================================================
# TASK VERSION
# =============================================================================


@dataclass
class TaskVersion(BaseModel):
    """Version of a deliverable task."""

    task_id: str = ""

    # Version info
    version_number: int = 1
    version_label: str | None = None  # "v01", "V02", etc.

    # Asana link (subtask)
    asana_subtask_gid: str | None = None

    # Status
    status: VersionStatus = VersionStatus.DRAFT
    status_changed_at: str | None = None

    # Timestamps
    submitted_at: str | None = None
    reviewed_at: str | None = None

    # Feedback
    feedback_summary: str | None = None
    feedback_sentiment: str | None = None  # positive, neutral, negative

    def __post_init__(self):
        if not self.id:
            self.id = generate_id("ver")
        if isinstance(self.status, str):
            self.status = VersionStatus(self.status)

    def submit(self) -> None:
        """Mark version as submitted."""
        self.status = VersionStatus.SUBMITTED
        self.submitted_at = now_iso()
        self.status_changed_at = now_iso()
        self.update_timestamp()

    def approve(self, feedback: str | None = None) -> None:
        """Mark version as approved."""
        self.status = VersionStatus.APPROVED
        self.reviewed_at = now_iso()
        self.status_changed_at = now_iso()
        self.feedback_summary = feedback
        self.feedback_sentiment = "positive"
        self.update_timestamp()

    def reject(self, feedback: str) -> None:
        """Mark version as rejected."""
        self.status = VersionStatus.REJECTED
        self.reviewed_at = now_iso()
        self.status_changed_at = now_iso()
        self.feedback_summary = feedback
        self.feedback_sentiment = "negative"
        self.update_timestamp()
