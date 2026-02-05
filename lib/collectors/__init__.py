"""
Collectors - Data acquisition layer.
All collectors write to StateStore. That's the wiring.
"""

from .base import BaseCollector
from .tasks import TasksCollector
from .calendar import CalendarCollector
from .gmail import GmailCollector
from .orchestrator import CollectorOrchestrator

__all__ = [
    'BaseCollector',
    'TasksCollector', 
    'CalendarCollector',
    'GmailCollector',
    'CollectorOrchestrator'
]
