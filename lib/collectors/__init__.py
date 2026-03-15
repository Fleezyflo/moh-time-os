"""
Collectors - Data acquisition layer.
All collectors write to StateStore. That's the wiring.
"""

from .asana import AsanaCollector
from .base import BaseCollector
from .calendar import CalendarCollector
from .chat import ChatCollector
from .contacts import ContactsCollector
from .drive import DriveCollector
from .gmail import GmailCollector
from .orchestrator import CollectorOrchestrator
from .result import CollectorResult, CollectorStatus
from .tasks import TasksCollector
from .xero import XeroCollector

__all__ = [
    "AsanaCollector",
    "BaseCollector",
    "CalendarCollector",
    "ChatCollector",
    "CollectorOrchestrator",
    "CollectorResult",
    "CollectorStatus",
    "ContactsCollector",
    "DriveCollector",
    "GmailCollector",
    "TasksCollector",
    "XeroCollector",
]
