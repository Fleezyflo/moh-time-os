"""
Time OS V5 — Signal-Based Client Health Monitoring

This package provides the complete V5 architecture:
- Signals: Atomic observations from integrated sources
- Issues: Aggregated patterns requiring attention
- Resolution: Signal balancing and issue lifecycle

Main entry points:
- TimeOSOrchestrator: Full pipeline runner
- Database: SQLite database access
- API: FastAPI endpoints
"""

from .database import Database, get_db

# Detectors
from .detectors import (
    AsanaTaskDetector,
    CalendarMeetDetector,
    DetectorRegistry,
    GoogleChatDetector,
    SignalDetector,
    XeroFinancialDetector,
    get_registry,
)

# Issues
from .issues import (
    ALL_PATTERNS,
    IssueFormationService,
    IssuePattern,
)

# Models
from .models import (
    Issue,
    IssueSeverity,
    IssueState,
    IssueTrajectory,
    ResolutionMethod,
    Signal,
    SignalCategory,
    SignalStatus,
    generate_id,
    now_iso,
)
from .orchestrator import TimeOSOrchestrator

# Resolution
from .resolution import (
    BalanceService,
    ResolutionService,
)

# Services
from .services import (
    DetectionOrchestrator,
    SignalService,
)

__version__ = "5.0.0"

__all__ = [
    # Core
    "Database",
    "get_db",
    "TimeOSOrchestrator",
    # Models
    "Signal",
    "SignalCategory",
    "SignalStatus",
    "Issue",
    "IssueState",
    "IssueSeverity",
    "IssueTrajectory",
    "ResolutionMethod",
    "generate_id",
    "now_iso",
    # Detectors
    "SignalDetector",
    "DetectorRegistry",
    "get_registry",
    "AsanaTaskDetector",
    "XeroFinancialDetector",
    "GoogleChatDetector",
    "CalendarMeetDetector",
    # Services
    "SignalService",
    "DetectionOrchestrator",
    # Resolution
    "BalanceService",
    "ResolutionService",
    # Issues
    "IssuePattern",
    "IssueFormationService",
    "ALL_PATTERNS",
]
