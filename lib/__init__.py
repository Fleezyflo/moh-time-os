# MOH TIME OS - Core Library
"""
Exports for cli_v2.py and other consumers.
"""

from .store import init_db
from .health import startup_check, status_report
from .queries import (
    summary_stats,
    open_items,
    overdue,
    due_today,
    due_this_week,
    waiting,
    generate_brief,
    needs_attention,
    client_summary_by_name,
)
from .entities import list_clients, find_client
from .backup import create_backup, backup_status

__all__ = [
    "init_db",
    "startup_check",
    "status_report",
    "summary_stats",
    "open_items",
    "overdue",
    "due_today",
    "due_this_week",
    "waiting",
    "generate_brief",
    "needs_attention",
    "list_clients",
    "find_client",
    "client_summary_by_name",
    "create_backup",
    "backup_status",
]
