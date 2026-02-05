"""
Executor - Action execution layer.
Executes approved decisions against external systems.
"""

from .engine import ExecutorEngine
from .handlers import TaskHandler, CalendarHandler, NotificationHandler

__all__ = [
    'ExecutorEngine',
    'TaskHandler',
    'CalendarHandler', 
    'NotificationHandler'
]
