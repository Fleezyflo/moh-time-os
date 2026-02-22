"""
Time OS V5 — Models Package

All data models for V5.
"""

# Base
from .base import (
    ArchivableModel,
    BaseModel,
    ClientTier,
    DetectedFrom,
    # Enums
    HealthStatus,
    PersonType,
    ProjectHealth,
    ProjectPhase,
    RetainerCycleStatus,
    RetainerStatus,
    TaskPriority,
    TaskStatus,
    VersionStatus,
    days_between,
    days_from_now,
    generate_id,
    json_dumps_safe,
    json_loads_safe,
    now_iso,
    parse_datetime,
)

# Calendar & Meet
from .calendar import (
    ActionItem,
    Attendee,
    AttendeeResponse,
    CalendarEvent,
    CalendarSyncState,
    EventStatus,
    GeminiNotes,
    MeetingSentiment,
    TitleCategory,
)

# Entities
from .entities import (
    Brand,
    Client,
    Person,
    Project,
    Retainer,
    RetainerCycle,
    Task,
    TaskVersion,
)

# Google Chat
from .gchat import (
    GChatMessage,
    GChatSyncState,
    ResponseTimeMetrics,
    SenderType,
    Sentiment,
    SpaceType,
)

# Issue
from .issue import (
    Issue,
    IssueSeverity,
    IssueState,
    IssueSubtype,
    IssueTrajectory,
    IssueType,
    RecommendedUrgency,
    ResolutionMethod,
    ScopeType,
    SignalBalance,
)

# Signal
from .signal import (
    SIGNAL_TYPES,
    SIGNAL_TYPES_COMMUNICATION,
    SIGNAL_TYPES_FINANCIAL,
    SIGNAL_TYPES_QUALITY,
    SIGNAL_TYPES_RELATIONSHIP,
    SIGNAL_TYPES_SCHEDULE,
    Signal,
    SignalCategory,
    SignalCreate,
    SignalSource,
    SignalStatus,
    Valence,
    calculate_decay_multiplier,
    get_default_valence,
    get_signal_category,
)

# Xero
from .xero import (
    AgingBucket,
    InvoiceStatus,
    InvoiceType,
    XeroInvoice,
    XeroPayment,
    XeroSyncState,
)

__all__ = [
    # Base
    "BaseModel",
    "ArchivableModel",
    "generate_id",
    "now_iso",
    "json_loads_safe",
    "json_dumps_safe",
    "parse_datetime",
    "days_between",
    "days_from_now",
    "HealthStatus",
    "ProjectHealth",
    "ClientTier",
    "PersonType",
    "TaskStatus",
    "TaskPriority",
    "ProjectPhase",
    "RetainerStatus",
    "RetainerCycleStatus",
    "VersionStatus",
    "DetectedFrom",
    # Entities
    "Person",
    "Client",
    "Brand",
    "Project",
    "Retainer",
    "RetainerCycle",
    "Task",
    "TaskVersion",
    # Signal
    "Signal",
    "SignalCreate",
    "SignalCategory",
    "SignalStatus",
    "SignalSource",
    "Valence",
    "SIGNAL_TYPES",
    "SIGNAL_TYPES_SCHEDULE",
    "SIGNAL_TYPES_QUALITY",
    "SIGNAL_TYPES_FINANCIAL",
    "SIGNAL_TYPES_COMMUNICATION",
    "SIGNAL_TYPES_RELATIONSHIP",
    "get_signal_category",
    "get_default_valence",
    "calculate_decay_multiplier",
    # Issue
    "Issue",
    "SignalBalance",
    "IssueType",
    "IssueSubtype",
    "IssueSeverity",
    "IssueState",
    "IssueTrajectory",
    "ResolutionMethod",
    "ScopeType",
    "RecommendedUrgency",
    # Xero
    "XeroInvoice",
    "XeroPayment",
    "XeroSyncState",
    "InvoiceType",
    "InvoiceStatus",
    "AgingBucket",
    # Google Chat
    "GChatSyncState",
    "GChatMessage",
    "ResponseTimeMetrics",
    "SpaceType",
    "SenderType",
    "Sentiment",
    # Calendar
    "CalendarSyncState",
    "CalendarEvent",
    "GeminiNotes",
    "ActionItem",
    "Attendee",
    "TitleCategory",
    "EventStatus",
    "MeetingSentiment",
    "AttendeeResponse",
]
