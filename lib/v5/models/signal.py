"""
Time OS V5 — Signal Model

Core signal model with valence, magnitude, and lifecycle.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, StrEnum
from typing import Any

from .base import BaseModel, generate_id, json_dumps_safe, json_loads_safe, now_iso

# =============================================================================
# SIGNAL ENUMS
# =============================================================================


class SignalCategory(StrEnum):
    """Signal category for grouping."""

    SCHEDULE = "schedule"
    QUALITY = "quality"
    FINANCIAL = "financial"
    COMMUNICATION = "communication"
    RELATIONSHIP = "relationship"
    PROCESS = "process"


class SignalStatus(StrEnum):
    """Signal lifecycle status."""

    ACTIVE = "active"
    CONSUMED = "consumed"  # Part of an issue
    BALANCED = "balanced"  # Neutralized by positive signal
    EXPIRED = "expired"  # Past expiry date
    ARCHIVED = "archived"  # Historical, no longer relevant


class SignalSource(StrEnum):
    """Source system for signal."""

    ASANA = "asana"
    XERO = "xero"
    GCHAT = "gchat"
    CALENDAR = "calendar"
    GMEET = "gmeet"
    EMAIL = "email"
    MANUAL = "manual"


class Valence(int, Enum):
    """Signal valence (direction)."""

    NEGATIVE = -1
    NEUTRAL = 0
    POSITIVE = 1


# =============================================================================
# SIGNAL TYPES (Registry)
# =============================================================================

# Schedule signals
SIGNAL_TYPES_SCHEDULE = {
    "task_created": {"category": SignalCategory.SCHEDULE, "default_valence": 0},
    "task_assigned": {"category": SignalCategory.SCHEDULE, "default_valence": 0},
    "task_completed_early": {"category": SignalCategory.SCHEDULE, "default_valence": 1},
    "task_completed_ontime": {
        "category": SignalCategory.SCHEDULE,
        "default_valence": 1,
    },
    "task_completed_late": {"category": SignalCategory.SCHEDULE, "default_valence": -1},
    "task_overdue": {"category": SignalCategory.SCHEDULE, "default_valence": -1},
    "task_approaching": {"category": SignalCategory.SCHEDULE, "default_valence": 0},
    "task_blocked": {"category": SignalCategory.SCHEDULE, "default_valence": -1},
    "task_unblocked": {"category": SignalCategory.SCHEDULE, "default_valence": 1},
    "task_due_moved_out": {"category": SignalCategory.SCHEDULE, "default_valence": -1},
}

# Quality signals
SIGNAL_TYPES_QUALITY = {
    "version_created": {"category": SignalCategory.QUALITY, "default_valence": 0},
    "revision_cycle_normal": {"category": SignalCategory.QUALITY, "default_valence": 0},
    "revision_cycle_high": {"category": SignalCategory.QUALITY, "default_valence": -1},
    "revision_cycle_excessive": {
        "category": SignalCategory.QUALITY,
        "default_valence": -1,
    },
}

# Financial signals
SIGNAL_TYPES_FINANCIAL = {
    "quote_accepted": {"category": SignalCategory.FINANCIAL, "default_valence": 1},
    "quote_rejected": {"category": SignalCategory.FINANCIAL, "default_valence": -1},
    "invoice_advance_issued": {
        "category": SignalCategory.FINANCIAL,
        "default_valence": 0,
    },
    "invoice_advance_paid": {
        "category": SignalCategory.FINANCIAL,
        "default_valence": 1,
    },
    "invoice_final_issued": {
        "category": SignalCategory.FINANCIAL,
        "default_valence": 0,
    },
    "invoice_final_paid": {"category": SignalCategory.FINANCIAL, "default_valence": 1},
    "payment_received_ontime": {
        "category": SignalCategory.FINANCIAL,
        "default_valence": 1,
    },
    "payment_received_late": {
        "category": SignalCategory.FINANCIAL,
        "default_valence": 1,
    },
    "invoice_overdue_30": {"category": SignalCategory.FINANCIAL, "default_valence": -1},
    "invoice_overdue_60": {"category": SignalCategory.FINANCIAL, "default_valence": -1},
    "invoice_overdue_90": {"category": SignalCategory.FINANCIAL, "default_valence": -1},
}

# Communication signals
SIGNAL_TYPES_COMMUNICATION = {
    "response_fast_team": {
        "category": SignalCategory.COMMUNICATION,
        "default_valence": 1,
    },
    "response_slow_team": {
        "category": SignalCategory.COMMUNICATION,
        "default_valence": -1,
    },
    "response_fast_client": {
        "category": SignalCategory.COMMUNICATION,
        "default_valence": 1,
    },
    "response_slow_client": {
        "category": SignalCategory.COMMUNICATION,
        "default_valence": -1,
    },
    "sentiment_positive": {
        "category": SignalCategory.COMMUNICATION,
        "default_valence": 1,
    },
    "sentiment_negative": {
        "category": SignalCategory.COMMUNICATION,
        "default_valence": -1,
    },
    "escalation_detected": {
        "category": SignalCategory.COMMUNICATION,
        "default_valence": -1,
    },
    "engagement_increasing": {
        "category": SignalCategory.COMMUNICATION,
        "default_valence": 1,
    },
    "engagement_decreasing": {
        "category": SignalCategory.COMMUNICATION,
        "default_valence": -1,
    },
    "communication_gap": {
        "category": SignalCategory.COMMUNICATION,
        "default_valence": -1,
    },
}

# Relationship signals
SIGNAL_TYPES_RELATIONSHIP = {
    "meeting_scheduled": {
        "category": SignalCategory.RELATIONSHIP,
        "default_valence": 0,
    },
    "meeting_occurred": {"category": SignalCategory.RELATIONSHIP, "default_valence": 1},
    "meeting_noshow_client": {
        "category": SignalCategory.RELATIONSHIP,
        "default_valence": -1,
    },
    "meeting_noshow_team": {
        "category": SignalCategory.RELATIONSHIP,
        "default_valence": -1,
    },
    "meeting_cancelled": {
        "category": SignalCategory.RELATIONSHIP,
        "default_valence": 0,
    },
    "meeting_decision_made": {
        "category": SignalCategory.RELATIONSHIP,
        "default_valence": 1,
    },
    "meeting_approval_given": {
        "category": SignalCategory.RELATIONSHIP,
        "default_valence": 1,
    },
    "meeting_concern_raised": {
        "category": SignalCategory.RELATIONSHIP,
        "default_valence": -1,
    },
    "meeting_action_item": {
        "category": SignalCategory.RELATIONSHIP,
        "default_valence": 0,
    },
    "action_item_not_tasked": {
        "category": SignalCategory.RELATIONSHIP,
        "default_valence": -1,
    },
    "meeting_title_urgent": {
        "category": SignalCategory.RELATIONSHIP,
        "default_valence": -1,
    },
}

# All signal types combined
SIGNAL_TYPES = {
    **SIGNAL_TYPES_SCHEDULE,
    **SIGNAL_TYPES_QUALITY,
    **SIGNAL_TYPES_FINANCIAL,
    **SIGNAL_TYPES_COMMUNICATION,
    **SIGNAL_TYPES_RELATIONSHIP,
}


def get_signal_category(signal_type: str) -> SignalCategory:
    """Get category for a signal type."""
    info = SIGNAL_TYPES.get(signal_type)
    if info:
        return info["category"]
    return SignalCategory.PROCESS  # Default


def get_default_valence(signal_type: str) -> int:
    """Get default valence for a signal type."""
    info = SIGNAL_TYPES.get(signal_type)
    if info:
        return info["default_valence"]
    return 0  # Neutral default


# =============================================================================
# DECAY CALCULATION
# =============================================================================


def calculate_decay_multiplier(age_days: int) -> float:
    """
    Calculate decay multiplier based on signal age.

    Older signals have less weight:
    - 0-30 days: 1.0 (full weight)
    - 31-90 days: 0.8
    - 91-180 days: 0.5
    - 181-365 days: 0.25
    - 365+ days: 0.1
    """
    if age_days > 365:
        return 0.1
    if age_days > 180:
        return 0.25
    if age_days > 90:
        return 0.5
    if age_days > 30:
        return 0.8
    return 1.0


# =============================================================================
# SIGNAL MODEL
# =============================================================================


@dataclass
class Signal(BaseModel):
    """
    Core signal model.

    Signals are atomic observations with:
    - Valence: direction (-1 negative, 0 neutral, +1 positive)
    - Magnitude: intensity (0.0 to 1.0)
    - Scope chain: links to entity hierarchy
    - Lifecycle: active → consumed/balanced/expired
    """

    # Classification
    signal_type: str = ""
    signal_category: SignalCategory = SignalCategory.PROCESS

    # Valence and magnitude (THE KEY FIELDS)
    valence: int = 0  # -1, 0, or 1
    magnitude: float = 0.5  # 0.0 to 1.0

    # Entity reference
    entity_type: str = ""  # task, project, retainer, brand, client, invoice, etc.
    entity_id: str = ""

    # Scope chain (for aggregation up the hierarchy)
    scope_task_id: str | None = None
    scope_project_id: str | None = None
    scope_retainer_id: str | None = None
    scope_brand_id: str | None = None
    scope_client_id: str | None = None
    scope_person_id: str | None = None

    # Source evidence
    source_type: SignalSource = SignalSource.MANUAL
    source_id: str | None = None
    source_url: str | None = None
    source_excerpt: str | None = None

    # Payload (signal-specific data)
    value_json: str = "{}"  # JSON string

    # Confidence
    detection_confidence: float = 0.9
    attribution_confidence: float = 0.9

    # Lifecycle
    status: SignalStatus = SignalStatus.ACTIVE
    balanced_by_signal_id: str | None = None
    consumed_by_issue_id: str | None = None

    # Timing
    occurred_at: str = field(default_factory=now_iso)
    detected_at: str = field(default_factory=now_iso)
    expires_at: str | None = None
    balanced_at: str | None = None

    # Detector info
    detector_id: str = ""
    detector_version: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = generate_id("sig")
        if isinstance(self.signal_category, str):
            self.signal_category = SignalCategory(self.signal_category)
        if isinstance(self.source_type, str):
            self.source_type = SignalSource(self.source_type)
        if isinstance(self.status, str):
            self.status = SignalStatus(self.status)
        # Auto-set category from type if not set
        if self.signal_type and self.signal_category == SignalCategory.PROCESS:
            self.signal_category = get_signal_category(self.signal_type)

    # =========================================================================
    # Value (Payload) Access
    # =========================================================================

    @property
    def value(self) -> dict[str, Any]:
        """Get value as dict."""
        return json_loads_safe(self.value_json) or {}

    @value.setter
    def value(self, data: dict[str, Any]) -> None:
        """Set value from dict."""
        self.value_json = json_dumps_safe(data) or "{}"

    def get_value(self, key: str, default: Any = None) -> Any:
        """Get a specific value from payload."""
        return self.value.get(key, default)

    # =========================================================================
    # Decay and Effective Magnitude
    # =========================================================================

    @property
    def age_days(self) -> int:
        """Calculate signal age in days."""
        try:
            detected = datetime.fromisoformat(self.detected_at)
            return (datetime.now() - detected).days
        except (ValueError, TypeError):
            return 0

    @property
    def decay_multiplier(self) -> float:
        """Get decay multiplier based on age."""
        return calculate_decay_multiplier(self.age_days)

    @property
    def effective_magnitude(self) -> float:
        """Get magnitude adjusted for decay."""
        return self.magnitude * self.decay_multiplier

    @property
    def weighted_valence(self) -> float:
        """Get valence weighted by effective magnitude."""
        return self.valence * self.effective_magnitude

    # =========================================================================
    # Lifecycle Methods
    # =========================================================================

    def mark_consumed(self, issue_id: str) -> None:
        """Mark signal as consumed by an issue."""
        self.status = SignalStatus.CONSUMED
        self.consumed_by_issue_id = issue_id
        self.update_timestamp()

    def mark_balanced(self, by_signal_id: str) -> None:
        """Mark signal as balanced by a positive signal."""
        self.status = SignalStatus.BALANCED
        self.balanced_by_signal_id = by_signal_id
        self.balanced_at = now_iso()
        self.update_timestamp()

    def mark_expired(self) -> None:
        """Mark signal as expired."""
        self.status = SignalStatus.EXPIRED
        self.update_timestamp()

    def archive(self) -> None:
        """Archive signal."""
        self.status = SignalStatus.ARCHIVED
        self.update_timestamp()

    @property
    def is_active(self) -> bool:
        """Check if signal is active."""
        return self.status == SignalStatus.ACTIVE

    @property
    def is_expired(self) -> bool:
        """Check if signal should be expired based on expires_at."""
        if self.expires_at is None:
            return False
        try:
            expires = datetime.fromisoformat(self.expires_at)
            return datetime.now() > expires
        except (ValueError, TypeError):
            return False

    # =========================================================================
    # Validation
    # =========================================================================

    def validate(self) -> bool:
        """Validate signal data."""
        if not self.signal_type:
            return False
        if self.valence not in (-1, 0, 1):
            return False
        if not (0.0 <= self.magnitude <= 1.0):
            return False
        if not self.entity_type or not self.entity_id:
            return False
        return self.detector_id


# =============================================================================
# SIGNAL CREATE DTO
# =============================================================================


@dataclass
class SignalCreate:
    """Data transfer object for creating a new signal."""

    signal_type: str
    valence: int
    magnitude: float

    entity_type: str
    entity_id: str

    source_type: SignalSource
    source_id: str | None = None
    source_url: str | None = None
    source_excerpt: str | None = None

    value: dict[str, Any] | None = None

    # Scope (optional, can be enriched)
    scope_task_id: str | None = None
    scope_project_id: str | None = None
    scope_retainer_id: str | None = None
    scope_brand_id: str | None = None
    scope_client_id: str | None = None
    scope_person_id: str | None = None

    # Timing
    occurred_at: str | None = None
    expires_at: str | None = None

    # Confidence
    detection_confidence: float = 0.9
    attribution_confidence: float = 0.9

    # Detector
    detector_id: str = ""
    detector_version: str = ""

    def to_signal(self) -> Signal:
        """Convert to Signal model."""
        return Signal(
            signal_type=self.signal_type,
            signal_category=get_signal_category(self.signal_type),
            valence=self.valence,
            magnitude=self.magnitude,
            entity_type=self.entity_type,
            entity_id=self.entity_id,
            scope_task_id=self.scope_task_id,
            scope_project_id=self.scope_project_id,
            scope_retainer_id=self.scope_retainer_id,
            scope_brand_id=self.scope_brand_id,
            scope_client_id=self.scope_client_id,
            scope_person_id=self.scope_person_id,
            source_type=self.source_type,
            source_id=self.source_id,
            source_url=self.source_url,
            source_excerpt=self.source_excerpt,
            value_json=json_dumps_safe(self.value) or "{}",
            detection_confidence=self.detection_confidence,
            attribution_confidence=self.attribution_confidence,
            occurred_at=self.occurred_at or now_iso(),
            expires_at=self.expires_at,
            detector_id=self.detector_id,
            detector_version=self.detector_version,
        )
