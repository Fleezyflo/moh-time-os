# MOH TIME OS - Core Library
"""
Exports for cli_v2.py and other consumers.
"""

from .backup import backup_status, create_backup
from .entities import find_client, list_clients
from .health import startup_check, status_report
from .queries import (
    client_summary_by_name,
    due_this_week,
    due_today,
    generate_brief,
    needs_attention,
    open_items,
    overdue,
    summary_stats,
    waiting,
)
from .store import init_db

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
