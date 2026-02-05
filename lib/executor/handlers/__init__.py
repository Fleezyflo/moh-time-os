"""
Executor Handlers - Action handlers for different domains.

Each handler knows how to execute actions in its domain
(tasks, calendar, email, delegation, notifications).
"""

from .task import TaskHandler
from .calendar import CalendarHandler
from .notification import NotificationHandler
from .email import EmailHandler
from .delegation import DelegationHandler

__all__ = [
    'TaskHandler',
    'CalendarHandler', 
    'NotificationHandler',
    'EmailHandler',
    'DelegationHandler'
]
