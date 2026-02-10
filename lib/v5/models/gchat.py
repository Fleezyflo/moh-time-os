"""
Time OS V5 — Google Chat Integration Models

Models for Google Chat spaces, messages, and sync state.
"""

from dataclasses import dataclass, field
from enum import StrEnum

from .base import BaseModel, generate_id, json_dumps_safe, json_loads_safe, now_iso

# =============================================================================
# GOOGLE CHAT ENUMS
# =============================================================================


class SpaceType(StrEnum):
    """Google Chat space type."""

    ROOM = "ROOM"
    DM = "DM"
    GROUP = "GROUP"


class SenderType(StrEnum):
    """Sender type classification."""

    TEAM = "team"
    CLIENT = "client"
    UNKNOWN = "unknown"


class Sentiment(StrEnum):
    """Message sentiment."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    MIXED = "mixed"


# =============================================================================
# GOOGLE CHAT SYNC STATE
# =============================================================================


@dataclass
class GChatSyncState:
    """Google Chat space sync state."""

    space_id: str = ""  # Primary key (e.g., "spaces/AAAA123")
    space_name: str | None = None
    space_type: SpaceType | None = None

    # Mapping to our entities
    client_id: str | None = None
    brand_id: str | None = None
    project_id: str | None = None

    # Sync state
    last_sync_at: str | None = None
    last_message_id: str | None = None
    last_message_at: str | None = None

    # Metrics (cached)
    message_count_30d: int = 0
    avg_response_time_hours: float | None = None

    updated_at: str = field(default_factory=now_iso)

    def __post_init__(self):
        if isinstance(self.space_type, str):
            self.space_type = SpaceType(self.space_type)

    def record_sync(self, message_id: str, message_at: str) -> None:
        """Record a message sync."""
        self.last_sync_at = now_iso()
        self.last_message_id = message_id
        self.last_message_at = message_at
        self.updated_at = now_iso()

    def update_metrics(self, message_count: int, avg_response: float | None) -> None:
        """Update cached metrics."""
        self.message_count_30d = message_count
        self.avg_response_time_hours = avg_response
        self.updated_at = now_iso()

    def link_to_client(
        self, client_id: str, brand_id: str | None = None, project_id: str | None = None
    ) -> None:
        """Link space to client/brand/project."""
        self.client_id = client_id
        self.brand_id = brand_id
        self.project_id = project_id
        self.updated_at = now_iso()


# =============================================================================
# GOOGLE CHAT MESSAGE
# =============================================================================


@dataclass
class GChatMessage(BaseModel):
    """Google Chat message entity."""

    space_id: str = ""

    # Message info
    message_id: str = ""  # Google's ID
    thread_id: str | None = None

    # Sender
    sender_email: str | None = None
    sender_name: str | None = None
    sender_type: SenderType = SenderType.UNKNOWN

    # Content
    text_snippet: str | None = None  # First 500 chars
    has_attachments: bool = False

    # Analysis
    sentiment: Sentiment | None = None
    sentiment_keywords: str | None = None  # JSON array
    is_escalation: bool = False

    # Sync
    synced_at: str = field(default_factory=now_iso)

    def __post_init__(self):
        if not self.id:
            self.id = generate_id("gmsg")
        if isinstance(self.sender_type, str):
            self.sender_type = SenderType(self.sender_type)
        if isinstance(self.sentiment, str):
            self.sentiment = Sentiment(self.sentiment)

    # =========================================================================
    # Sentiment Keywords Access
    # =========================================================================

    def get_sentiment_keywords(self) -> list[str]:
        """Get sentiment keywords as list."""
        return json_loads_safe(self.sentiment_keywords) or []

    def set_sentiment_keywords(self, keywords: list[str]) -> None:
        """Set sentiment keywords from list."""
        self.sentiment_keywords = json_dumps_safe(keywords)

    # =========================================================================
    # Analysis Methods
    # =========================================================================

    def analyze_sentiment(
        self,
        positive_keywords: list[str],
        negative_keywords: list[str],
        escalation_markers: list[str],
    ) -> None:
        """
        Analyze message sentiment based on keyword matching.

        Args:
            positive_keywords: List of positive sentiment keywords
            negative_keywords: List of negative sentiment keywords
            escalation_markers: List of escalation indicator keywords
        """
        if not self.text_snippet:
            self.sentiment = Sentiment.NEUTRAL
            return

        text_lower = self.text_snippet.lower()

        # Find matches
        positive_found = [kw for kw in positive_keywords if kw.lower() in text_lower]
        negative_found = [kw for kw in negative_keywords if kw.lower() in text_lower]
        escalation_found = [kw for kw in escalation_markers if kw.lower() in text_lower]

        # Store keywords
        all_keywords = positive_found + negative_found
        self.set_sentiment_keywords(all_keywords)

        # Determine sentiment
        if positive_found and not negative_found:
            self.sentiment = Sentiment.POSITIVE
        elif negative_found and not positive_found:
            self.sentiment = Sentiment.NEGATIVE
        elif positive_found and negative_found:
            self.sentiment = Sentiment.MIXED
        else:
            self.sentiment = Sentiment.NEUTRAL

        # Check escalation
        self.is_escalation = len(escalation_found) > 0

    @property
    def is_from_client(self) -> bool:
        """Check if message is from client."""
        return self.sender_type == SenderType.CLIENT

    @property
    def is_from_team(self) -> bool:
        """Check if message is from team."""
        return self.sender_type == SenderType.TEAM

    @property
    def has_negative_sentiment(self) -> bool:
        """Check if message has negative sentiment."""
        return self.sentiment in (Sentiment.NEGATIVE, Sentiment.MIXED)

    @property
    def has_positive_sentiment(self) -> bool:
        """Check if message has positive sentiment."""
        return self.sentiment == Sentiment.POSITIVE


# =============================================================================
# RESPONSE TIME TRACKING
# =============================================================================


@dataclass
class ResponseTimeMetrics:
    """Response time metrics for a space."""

    space_id: str = ""
    period_days: int = 30

    # Team metrics
    team_responses: int = 0
    team_total_hours: float = 0.0
    team_fastest_hours: float | None = None
    team_slowest_hours: float | None = None

    # Client metrics
    client_responses: int = 0
    client_total_hours: float = 0.0
    client_fastest_hours: float | None = None
    client_slowest_hours: float | None = None

    @property
    def team_avg_response_hours(self) -> float | None:
        """Average team response time in hours."""
        if self.team_responses == 0:
            return None
        return self.team_total_hours / self.team_responses

    @property
    def client_avg_response_hours(self) -> float | None:
        """Average client response time in hours."""
        if self.client_responses == 0:
            return None
        return self.client_total_hours / self.client_responses

    def record_team_response(self, hours: float) -> None:
        """Record a team response time."""
        self.team_responses += 1
        self.team_total_hours += hours

        if self.team_fastest_hours is None or hours < self.team_fastest_hours:
            self.team_fastest_hours = hours
        if self.team_slowest_hours is None or hours > self.team_slowest_hours:
            self.team_slowest_hours = hours

    def record_client_response(self, hours: float) -> None:
        """Record a client response time."""
        self.client_responses += 1
        self.client_total_hours += hours

        if self.client_fastest_hours is None or hours < self.client_fastest_hours:
            self.client_fastest_hours = hours
        if self.client_slowest_hours is None or hours > self.client_slowest_hours:
            self.client_slowest_hours = hours
