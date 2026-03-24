"""
Collector Registry — Single Source of Truth

This module defines THE ONLY list of enabled collectors.
CollectorOrchestrator reads from here.

DO NOT define collectors anywhere else.

Note: CollectorLock lives in lib/collector_lock.py to avoid a circular import
between this module and lib/collectors/orchestrator.py. It is re-exported here
for backward compatibility.
"""

import logging
from dataclasses import dataclass, field

# Re-export CollectorLock so existing callers (and contract tests) still work.
from lib.collector_lock import CollectorLock  # noqa: F401 — backward-compat re-export

logger = logging.getLogger(__name__)


# ============================================================================
# COLLECTOR REGISTRY
# ============================================================================
@dataclass
class CollectorSpec:
    """Specification for a collector."""

    source: str
    module: str
    function: str
    tables_written: list[str] = field(default_factory=list)
    json_output: str | None = None
    enabled: bool = True
    sync_interval_seconds: int = 300


# THE CANONICAL REGISTRY — This is the ONLY place where collectors are defined.
# All collectors are class-based in lib/collectors/ using service account auth.
COLLECTOR_REGISTRY: dict[str, CollectorSpec] = {
    "calendar": CollectorSpec(
        source="calendar",
        module="lib.collectors.calendar",
        function="CalendarCollector",
        tables_written=["events"],
        sync_interval_seconds=60,
    ),
    "gmail": CollectorSpec(
        source="gmail",
        module="lib.collectors.gmail",
        function="GmailCollector",
        tables_written=["communications"],
        sync_interval_seconds=120,
    ),
    "tasks": CollectorSpec(
        source="tasks",
        module="lib.collectors.tasks",
        function="TasksCollector",
        tables_written=["tasks"],
    ),
    "chat": CollectorSpec(
        source="chat",
        module="lib.collectors.chat",
        function="ChatCollector",
        tables_written=["chat_messages"],
    ),
    "asana": CollectorSpec(
        source="asana",
        module="lib.collectors.asana",
        function="AsanaCollector",
        tables_written=[
            "tasks",
            "asana_custom_fields",
            "asana_subtasks",
            "asana_stories",
            "asana_task_dependencies",
            "asana_attachments",
            "asana_portfolios",
            "asana_goals",
        ],
    ),
    "xero": CollectorSpec(
        source="xero",
        module="lib.collectors.xero",
        function="XeroCollector",
        tables_written=["invoices"],
    ),
    "drive": CollectorSpec(
        source="drive",
        module="lib.collectors.drive",
        function="DriveCollector",
        tables_written=["drive_files"],
        sync_interval_seconds=600,
    ),
    "contacts": CollectorSpec(
        source="contacts",
        module="lib.collectors.contacts",
        function="ContactsCollector",
        tables_written=["contacts"],
        sync_interval_seconds=600,
    ),
}


def get_all_sources() -> list[str]:
    """Get list of all enabled source names."""
    return [s for s, spec in COLLECTOR_REGISTRY.items() if spec.enabled]


def get_collector_map() -> dict[str, type]:
    """
    Get collector class map.

    Returns dict of {source_name: CollectorClass}.
    All collectors are class-based in lib/collectors/.
    """
    from lib.collectors.asana import AsanaCollector
    from lib.collectors.calendar import CalendarCollector
    from lib.collectors.chat import ChatCollector
    from lib.collectors.contacts import ContactsCollector
    from lib.collectors.drive import DriveCollector
    from lib.collectors.gmail import GmailCollector
    from lib.collectors.tasks import TasksCollector
    from lib.collectors.xero import XeroCollector

    return {
        "calendar": CalendarCollector,
        "gmail": GmailCollector,
        "tasks": TasksCollector,
        "chat": ChatCollector,
        "asana": AsanaCollector,
        "xero": XeroCollector,
        "drive": DriveCollector,
        "contacts": ContactsCollector,
    }
