"""
Executor - Action execution layer.
Executes approved decisions against external systems.
"""

from .engine import ExecutorEngine
from .handlers import CalendarHandler, NotificationHandler, TaskHandler

__all__ = ["ExecutorEngine", "TaskHandler", "CalendarHandler", "NotificationHandler"]
