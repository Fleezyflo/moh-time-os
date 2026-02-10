"""
Collectors - Data acquisition layer.
All collectors write to StateStore. That's the wiring.
"""

from .base import BaseCollector
from .calendar import CalendarCollector
from .gmail import GmailCollector
from .orchestrator import CollectorOrchestrator
from .tasks import TasksCollector

__all__ = [
    "BaseCollector",
    "TasksCollector",
    "CalendarCollector",
    "GmailCollector",
    "CollectorOrchestrator",
]
