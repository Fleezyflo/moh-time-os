"""
Collector Registry — Single Source of Truth

This module defines THE ONLY list of enabled collectors.
Both scheduled_collect.py and CollectorOrchestrator must read from here.

DO NOT define collectors anywhere else.
"""

import fcntl
import os
from collections.abc import Callable
from dataclasses import dataclass, field

from lib import paths

# ============================================================================
# LOCKFILE GUARD — Prevents double execution
# ============================================================================
LOCK_FILE = paths.data_dir() / ".collector.lock"


class CollectorLock:
    """
    Prevents concurrent collector runs.

    Usage:
        with CollectorLock() as lock:
            if not lock.acquired:
                print("Another collector is running")
                return
            # do collection
    """

    def __init__(self):
        self.lock_file = LOCK_FILE
        self.lock_fd = None
        self.acquired = False

    def __enter__(self):
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        self.lock_fd = open(self.lock_file, "w")
        try:
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.lock_fd.write(f"{os.getpid()}\n")
            self.lock_fd.flush()
            self.acquired = True
        except BlockingIOError:
            self.acquired = False
        return self

    def __exit__(self, *args):
        if self.lock_fd:
            if self.acquired:
                fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
            self.lock_fd.close()


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
COLLECTOR_REGISTRY: dict[str, CollectorSpec] = {
    "calendar": CollectorSpec(
        source="calendar",
        module="collectors.scheduled_collect",
        function="collect_calendar",
        json_output="calendar-next.json",
        sync_interval_seconds=60,
    ),
    "gmail": CollectorSpec(
        source="gmail",
        module="collectors.scheduled_collect",
        function="collect_gmail",
        json_output="gmail-full.json",
        sync_interval_seconds=120,
    ),
    "tasks": CollectorSpec(
        source="tasks",
        module="collectors.scheduled_collect",
        function="collect_tasks",
        json_output="tasks.json",
    ),
    "chat": CollectorSpec(
        source="chat",
        module="collectors.scheduled_collect",
        function="collect_chat",
        json_output="chat-full.json",
    ),
    "asana": CollectorSpec(
        source="asana",
        module="collectors.scheduled_collect",
        function="collect_asana",
        tables_written=["tasks"],
        json_output="asana-ops.json",
    ),
    "xero": CollectorSpec(
        source="xero",
        module="collectors.scheduled_collect",
        function="collect_xero",
        tables_written=["invoices"],
        json_output="xero-ar.json",
    ),
    "drive": CollectorSpec(
        source="drive",
        module="collectors.scheduled_collect",
        function="collect_drive",
        json_output="drive-recent.json",
        sync_interval_seconds=600,
    ),
    "contacts": CollectorSpec(
        source="contacts",
        module="collectors.scheduled_collect",
        function="collect_contacts",
        json_output="contacts.json",
        sync_interval_seconds=600,
    ),
}


def get_all_sources() -> list[str]:
    """Get list of all enabled source names."""
    return [s for s, spec in COLLECTOR_REGISTRY.items() if spec.enabled]


def get_collector_map() -> dict[str, Callable]:
    """
    Get collector function map for scheduled_collect.py.

    Returns dict of {source_name: collect_function}.
    This is the ONLY place this mapping should exist.
    """
    # Import here to avoid circular imports
    from collectors import scheduled_collect

    return {
        "calendar": scheduled_collect.collect_calendar,
        "gmail": scheduled_collect.collect_gmail,
        "tasks": scheduled_collect.collect_tasks,
        "chat": scheduled_collect.collect_chat,
        "asana": scheduled_collect.collect_asana,
        "xero": scheduled_collect.collect_xero,
        "drive": scheduled_collect.collect_drive,
        "contacts": scheduled_collect.collect_contacts,
    }
