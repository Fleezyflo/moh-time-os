"""
Time OS V5 — Calendar & Meet Integration Models

Models for Calendar events and Gemini meeting notes.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from .base import BaseModel, generate_id, json_dumps_safe, json_loads_safe, now_iso

# =============================================================================
# CALENDAR ENUMS
# =============================================================================


class TitleCategory(StrEnum):
    """Meeting title category."""

    KICKOFF = "kickoff"
    REVIEW = "review"
    SYNC = "sync"
    URGENT = "urgent"
    OTHER = "other"


class EventStatus(StrEnum):
    """Calendar event status."""

    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    CANCELLED = "cancelled"


class MeetingSentiment(StrEnum):
    """Overall meeting sentiment."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    MIXED = "mixed"


class AttendeeResponse(StrEnum):
    """Attendee response status."""

    ACCEPTED = "accepted"
    DECLINED = "declined"
    TENTATIVE = "tentative"
    NEEDS_ACTION = "needsAction"


# =============================================================================
# CALENDAR SYNC STATE
# =============================================================================


@dataclass
class CalendarSyncState:
    """Calendar sync state."""

    calendar_id: str = ""  # Primary key
    calendar_name: str | None = None

    last_sync_at: str | None = None
    sync_token: str | None = None  # For incremental sync

    updated_at: str = field(default_factory=now_iso)

    def record_sync(self, sync_token: str | None = None) -> None:
        """Record a sync operation."""
        self.last_sync_at = now_iso()
        if sync_token:
            self.sync_token = sync_token
        self.updated_at = now_iso()


# =============================================================================
# ATTENDEE
# =============================================================================


@dataclass
class Attendee:
    """Meeting attendee."""

    email: str = ""
    name: str | None = None
    response_status: AttendeeResponse = AttendeeResponse.NEEDS_ACTION
    is_organizer: bool = False
    is_optional: bool = False

    def __post_init__(self):
        if isinstance(self.response_status, str):
            self.response_status = AttendeeResponse(self.response_status)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "email": self.email,
            "name": self.name,
            "response_status": self.response_status.value,
            "is_organizer": self.is_organizer,
            "is_optional": self.is_optional,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Attendee":
        """Create from dict."""
        return cls(
            email=data.get("email", ""),
            name=data.get("name"),
            response_status=AttendeeResponse(
                data.get("response_status", "needsAction")
            ),
            is_organizer=data.get("is_organizer", False),
            is_optional=data.get("is_optional", False),
        )


# =============================================================================
# CALENDAR EVENT
# =============================================================================


@dataclass
class CalendarEvent(BaseModel):
    """Calendar event entity."""

    google_event_id: str = ""
    calendar_id: str | None = None

    # Event details
    title: str = ""
    description: str | None = None

    # Time
    start_time: str = ""
    end_time: str | None = None
    all_day: bool = False

    # Attendees
    attendees_json: str | None = None  # JSON array of Attendee dicts
    organizer_email: str | None = None

    # Client/project link
    client_id: str | None = None
    brand_id: str | None = None
    project_id: str | None = None

    # Analysis
    title_category: TitleCategory = TitleCategory.OTHER

    # Status
    status: EventStatus = EventStatus.CONFIRMED

    # Meeting occurred?
    meeting_occurred: bool | None = None
    gemini_notes_id: str | None = None

    # Sync
    synced_at: str | None = None

    def __post_init__(self):
        if not self.id:
            self.id = generate_id("evt")
        if isinstance(self.title_category, str):
            self.title_category = TitleCategory(self.title_category)
        if isinstance(self.status, str):
            self.status = EventStatus(self.status)

    # =========================================================================
    # Attendees Access
    # =========================================================================

    def get_attendees(self) -> list[Attendee]:
        """Get attendees as list."""
        data = json_loads_safe(self.attendees_json) or []
        return [Attendee.from_dict(a) for a in data]

    def set_attendees(self, attendees: list[Attendee]) -> None:
        """Set attendees from list."""
        data = [a.to_dict() for a in attendees]
        self.attendees_json = json_dumps_safe(data)

    def add_attendee(self, attendee: Attendee) -> None:
        """Add an attendee."""
        attendees = self.get_attendees()
        attendees.append(attendee)
        self.set_attendees(attendees)

    @property
    def attendee_count(self) -> int:
        """Get attendee count."""
        return len(self.get_attendees())

    @property
    def accepted_count(self) -> int:
        """Get count of accepted attendees."""
        return sum(
            1
            for a in self.get_attendees()
            if a.response_status == AttendeeResponse.ACCEPTED
        )

    # =========================================================================
    # Title Categorization
    # =========================================================================

    def categorize_title(self) -> TitleCategory:
        """Categorize meeting by title."""
        import re

        title_lower = self.title.lower()

        # Urgent patterns
        urgent_patterns = [
            r"\burgent\b",
            r"\basap\b",
            r"\bemergency\b",
            r"\bcritical\b",
            r"\bescalation\b",
            r"\bimmediate\b",
        ]
        for pattern in urgent_patterns:
            if re.search(pattern, title_lower):
                self.title_category = TitleCategory.URGENT
                return self.title_category

        # Kickoff patterns
        kickoff_patterns = [
            r"\bkickoff\b",
            r"\bkick-off\b",
            r"\bkick off\b",
            r"\bproject start\b",
            r"\bonboarding\b",
            r"\bintro\b",
        ]
        for pattern in kickoff_patterns:
            if re.search(pattern, title_lower):
                self.title_category = TitleCategory.KICKOFF
                return self.title_category

        # Review patterns
        review_patterns = [
            r"\breview\b",
            r"\bapproval\b",
            r"\bsign-off\b",
            r"\bsignoff\b",
            r"\bfeedback\b",
            r"\bpresentation\b",
        ]
        for pattern in review_patterns:
            if re.search(pattern, title_lower):
                self.title_category = TitleCategory.REVIEW
                return self.title_category

        # Sync patterns
        if any(
            kw in title_lower
            for kw in [
                "sync",
                "standup",
                "stand-up",
                "weekly",
                "daily",
                "check-in",
                "checkin",
                "catch up",
                "catchup",
            ]
        ):
            self.title_category = TitleCategory.SYNC
            return self.title_category

        self.title_category = TitleCategory.OTHER
        return self.title_category

    # =========================================================================
    # Time Properties
    # =========================================================================

    @property
    def duration_minutes(self) -> int | None:
        """Get meeting duration in minutes."""
        if not self.end_time:
            return None
        try:
            start = datetime.fromisoformat(self.start_time.replace("Z", "+00:00"))
            end = datetime.fromisoformat(self.end_time.replace("Z", "+00:00"))
            return int((end - start).total_seconds() / 60)
        except (ValueError, TypeError):
            return None

    @property
    def is_past(self) -> bool:
        """Check if event is in the past."""
        try:
            start = datetime.fromisoformat(self.start_time.replace("Z", "+00:00"))
            return datetime.now(start.tzinfo) > start
        except (ValueError, TypeError):
            return False

    @property
    def is_cancelled(self) -> bool:
        """Check if event is cancelled."""
        return self.status == EventStatus.CANCELLED


# =============================================================================
# GEMINI MEETING NOTES
# =============================================================================


@dataclass
class GeminiNotes(BaseModel):
    """Parsed Gemini meeting notes."""

    event_id: str | None = None  # FK to CalendarEvent
    google_event_id: str | None = None

    # Meeting metadata
    meeting_title: str | None = None
    meeting_date: str | None = None
    duration_minutes: int | None = None

    # Attendees
    expected_attendees: str | None = None  # JSON array
    actual_attendees: str | None = None  # JSON array (from Meet)

    # Extracted content
    raw_summary: str | None = None  # Full Gemini output

    # Parsed sections (all JSON arrays)
    decisions: str | None = None
    action_items: str | None = None  # Array of {action, owner, due_date}
    concerns: str | None = None
    approvals: str | None = None
    blockers: str | None = None

    # Analysis
    overall_sentiment: MeetingSentiment | None = None

    # Processing
    processed_at: str | None = None

    def __post_init__(self):
        if not self.id:
            self.id = generate_id("gmn")
        if isinstance(self.overall_sentiment, str):
            self.overall_sentiment = MeetingSentiment(self.overall_sentiment)

    # =========================================================================
    # Parsed Data Access
    # =========================================================================

    def get_decisions(self) -> list[str]:
        """Get decisions as list."""
        return json_loads_safe(self.decisions) or []

    def set_decisions(self, items: list[str]) -> None:
        """Set decisions from list."""
        self.decisions = json_dumps_safe(items)

    def get_action_items(self) -> list[dict[str, Any]]:
        """Get action items as list of dicts."""
        return json_loads_safe(self.action_items) or []

    def set_action_items(self, items: list[dict[str, Any]]) -> None:
        """Set action items from list."""
        self.action_items = json_dumps_safe(items)

    def get_concerns(self) -> list[str]:
        """Get concerns as list."""
        return json_loads_safe(self.concerns) or []

    def set_concerns(self, items: list[str]) -> None:
        """Set concerns from list."""
        self.concerns = json_dumps_safe(items)

    def get_approvals(self) -> list[str]:
        """Get approvals as list."""
        return json_loads_safe(self.approvals) or []

    def set_approvals(self, items: list[str]) -> None:
        """Set approvals from list."""
        self.approvals = json_dumps_safe(items)

    def get_blockers(self) -> list[str]:
        """Get blockers as list."""
        return json_loads_safe(self.blockers) or []

    def set_blockers(self, items: list[str]) -> None:
        """Set blockers from list."""
        self.blockers = json_dumps_safe(items)

    def get_expected_attendees(self) -> list[str]:
        """Get expected attendees as list."""
        return json_loads_safe(self.expected_attendees) or []

    def get_actual_attendees(self) -> list[str]:
        """Get actual attendees as list."""
        return json_loads_safe(self.actual_attendees) or []

    # =========================================================================
    # Analysis Properties
    # =========================================================================

    @property
    def has_decisions(self) -> bool:
        """Check if meeting had decisions."""
        return len(self.get_decisions()) > 0

    @property
    def has_action_items(self) -> bool:
        """Check if meeting had action items."""
        return len(self.get_action_items()) > 0

    @property
    def has_concerns(self) -> bool:
        """Check if meeting had concerns raised."""
        return len(self.get_concerns()) > 0

    @property
    def has_approvals(self) -> bool:
        """Check if meeting had approvals."""
        return len(self.get_approvals()) > 0

    @property
    def has_blockers(self) -> bool:
        """Check if meeting had blockers."""
        return len(self.get_blockers()) > 0

    @property
    def action_item_count(self) -> int:
        """Get count of action items."""
        return len(self.get_action_items())

    @property
    def unassigned_action_items(self) -> list[dict[str, Any]]:
        """Get action items without an owner."""
        return [ai for ai in self.get_action_items() if not ai.get("owner")]

    @property
    def attendance_rate(self) -> float | None:
        """Calculate attendance rate."""
        expected = self.get_expected_attendees()
        actual = self.get_actual_attendees()
        if not expected:
            return None
        return len(actual) / len(expected)

    def mark_processed(self) -> None:
        """Mark notes as processed."""
        self.processed_at = now_iso()
        self.update_timestamp()


# =============================================================================
# ACTION ITEM
# =============================================================================


@dataclass
class ActionItem:
    """Action item from meeting notes."""

    action: str = ""
    owner: str | None = None
    owner_email: str | None = None
    due_date: str | None = None

    # Tracking
    asana_task_id: str | None = None  # If converted to task
    status: str = "pending"  # pending, tasked, completed

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "action": self.action,
            "owner": self.owner,
            "owner_email": self.owner_email,
            "due_date": self.due_date,
            "asana_task_id": self.asana_task_id,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActionItem":
        """Create from dict."""
        return cls(
            action=data.get("action", ""),
            owner=data.get("owner"),
            owner_email=data.get("owner_email"),
            due_date=data.get("due_date"),
            asana_task_id=data.get("asana_task_id"),
            status=data.get("status", "pending"),
        )

    @property
    def is_tasked(self) -> bool:
        """Check if action item has been converted to a task."""
        return self.asana_task_id is not None

    @property
    def is_assigned(self) -> bool:
        """Check if action item has an owner."""
        return self.owner is not None or self.owner_email is not None
