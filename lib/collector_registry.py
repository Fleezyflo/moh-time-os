"""
Collector Registry — Single Source of Truth

This module defines THE ONLY list of enabled collectors.
Both scheduled_collect.py and CollectorOrchestrator must read from here.

DO NOT define collectors anywhere else.
"""

import fcntl
import logging
import os
from dataclasses import dataclass, field

from lib import paths

logger = logging.getLogger(__name__)

# ============================================================================
# LOCKFILE GUARD — Prevents double execution
# ============================================================================
LOCK_FILE = paths.data_dir() / ".collector.lock"


class CollectorLock:
    """
    Prevents concurrent collector runs with stale lock detection.

    Stores PID + timestamp on acquire. On contention, checks if the
    holding process is still alive. Breaks stale locks after TTL.

    Usage:
        with CollectorLock() as lock:
            if not lock.acquired:
                print("Another collector is running")
                return
            # do collection
    """

    TTL_SECONDS = 1800  # 30 minutes

    def __init__(self):
        self.lock_file = LOCK_FILE
        self.lock_fd = None
        self.acquired = False

    def _is_pid_alive(self, pid: int) -> bool:
        """Check if a process with the given PID is alive."""
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True  # Process exists but we can't signal it

    def _read_lock_info(self) -> tuple[int | None, float | None]:
        """Read PID and timestamp from lock file."""
        try:
            if self.lock_file.exists():
                content = self.lock_file.read_text().strip()
                parts = content.split("\n")
                pid = int(parts[0]) if parts else None
                timestamp = float(parts[1]) if len(parts) > 1 else None
                return pid, timestamp
        except (ValueError, OSError):
            pass
        return None, None

    def _break_stale_lock(self) -> bool:
        """Break a stale lock if the holding process is dead or TTL expired."""
        import time

        pid, timestamp = self._read_lock_info()
        if pid is None:
            return True  # No valid lock info, safe to acquire

        # Check if PID is alive
        if not self._is_pid_alive(pid):
            logger.warning("Breaking stale lock: PID %d is no longer alive", pid)
            return True

        # Check TTL
        if timestamp is not None:
            age = time.time() - timestamp
            if age > self.TTL_SECONDS:
                logger.warning(
                    "Breaking stale lock: held by PID %d for %.0fs (TTL=%ds)",
                    pid,
                    age,
                    self.TTL_SECONDS,
                )
                return True

        return False  # Lock is valid

    def __enter__(self):
        import time

        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        self.lock_fd = open(self.lock_file, "w")
        try:
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.lock_fd.write(f"{os.getpid()}\n{time.time()}\n")
            self.lock_fd.flush()
            self.acquired = True
        except BlockingIOError:
            # Lock contention — check if stale
            self.lock_fd.close()
            if self._break_stale_lock():
                # Try again after breaking stale lock
                self.lock_fd = open(self.lock_file, "w")
                try:
                    fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self.lock_fd.write(f"{os.getpid()}\n{time.time()}\n")
                    self.lock_fd.flush()
                    self.acquired = True
                except BlockingIOError:
                    self.acquired = False
            else:
                self.lock_fd = open(self.lock_file)
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
