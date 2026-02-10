"""
Executor Handlers - Action handlers for different domains.

Each handler knows how to execute actions in its domain
(tasks, calendar, email, delegation, notifications).
"""

from .calendar import CalendarHandler
from .delegation import DelegationHandler
from .email import EmailHandler
from .notification import NotificationHandler
from .task import TaskHandler

__all__ = [
    "TaskHandler",
    "CalendarHandler",
    "NotificationHandler",
    "EmailHandler",
    "DelegationHandler",
]
