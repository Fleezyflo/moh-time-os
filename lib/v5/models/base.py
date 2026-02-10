"""
Time OS V5 — Base Models

Base classes and common enums for all models.
"""

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

# =============================================================================
# ID GENERATION
# =============================================================================


def generate_id(prefix: str = "") -> str:
    """Generate a unique ID with optional prefix."""
    uid = uuid.uuid4().hex[:16]
    if prefix:
        return f"{prefix}_{uid}"
    return uid


# =============================================================================
# COMMON ENUMS
# =============================================================================


class HealthStatus(StrEnum):
    """Health status for clients, brands, projects."""

    HEALTHY = "healthy"
    COOLING = "cooling"  # Client-level only
    AT_RISK = "at_risk"
    CRITICAL = "critical"


class ProjectHealth(StrEnum):
    """Health status specifically for projects."""

    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    OFF_TRACK = "off_track"


class ClientTier(StrEnum):
    """Client tier classification."""

    A = "A"
    B = "B"
    C = "C"
    UNCLASSIFIED = "unclassified"


class PersonType(StrEnum):
    """Type of person."""

    TEAM = "team"
    CLIENT_CONTACT = "client_contact"
    VENDOR = "vendor"
    OTHER = "other"


class TaskStatus(StrEnum):
    """Task status."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    REVIEW = "review"
    DONE = "done"
    CANCELLED = "cancelled"


class TaskPriority(StrEnum):
    """Task priority."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class ProjectPhase(StrEnum):
    """Project lifecycle phase."""

    OPPORTUNITY = "opportunity"
    CONFIRMED = "confirmed"
    KICKOFF = "kickoff"
    EXECUTION = "execution"
    DELIVERY = "delivery"
    CLOSEOUT = "closeout"
    COMPLETE = "complete"
    CANCELLED = "cancelled"


class RetainerStatus(StrEnum):
    """Retainer contract status."""

    ACTIVE = "active"
    PAUSED = "paused"
    CHURNED = "churned"
    RENEWED = "renewed"


class RetainerCycleStatus(StrEnum):
    """Retainer cycle status."""

    UPCOMING = "upcoming"
    PLANNING = "planning"
    ACTIVE = "active"
    DELIVERED = "delivered"
    INVOICED = "invoiced"
    PAID = "paid"
    CLOSED = "closed"


class VersionStatus(StrEnum):
    """Task version status."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"


class DetectedFrom(StrEnum):
    """How a project was detected."""

    QUOTE = "quote"
    INVOICE = "invoice"
    TASKS = "tasks"
    MANUAL = "manual"


# =============================================================================
# BASE MODEL
# =============================================================================


@dataclass
class BaseModel:
    """Base class for all models."""

    id: str = field(default_factory=lambda: generate_id())
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert model to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BaseModel":
        """Create model from dictionary."""
        # Filter to only fields that exist in the dataclass
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "BaseModel":
        """Create model from database row (dict)."""
        return cls.from_dict(row)

    def update_timestamp(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now().isoformat()


@dataclass
class ArchivableModel(BaseModel):
    """Base class for models that can be archived."""

    archived_at: str | None = None

    def archive(self) -> None:
        """Mark as archived."""
        self.archived_at = datetime.now().isoformat()
        self.update_timestamp()

    def unarchive(self) -> None:
        """Remove archive status."""
        self.archived_at = None
        self.update_timestamp()

    @property
    def is_archived(self) -> bool:
        """Check if archived."""
        return self.archived_at is not None


# =============================================================================
# JSON HELPERS
# =============================================================================


def json_loads_safe(data: str | None) -> Any:
    """Safely load JSON, returning None on failure."""
    if data is None:
        return None
    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return None


def json_dumps_safe(data: Any) -> str | None:
    """Safely dump to JSON, returning None for None input."""
    if data is None:
        return None
    return json.dumps(data)


# =============================================================================
# DATETIME HELPERS
# =============================================================================


def now_iso() -> str:
    """Get current datetime as ISO string."""
    return datetime.now().isoformat()


def parse_datetime(dt_str: str | None) -> datetime | None:
    """Parse ISO datetime string."""
    if dt_str is None:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def days_between(date1: str, date2: str) -> int:
    """Calculate days between two date strings."""
    d1 = parse_datetime(date1)
    d2 = parse_datetime(date2)
    if d1 is None or d2 is None:
        return 0
    return (d2 - d1).days


def days_from_now(date_str: str) -> int:
    """Calculate days from now to date (positive = future, negative = past)."""
    dt = parse_datetime(date_str)
    if dt is None:
        return 0
    now = datetime.now()
    if dt.tzinfo is not None:
        now = now.replace(tzinfo=dt.tzinfo)
    return (dt - now).days
