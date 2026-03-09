"""
Collector Registry — Single Source of Truth

This module defines THE ONLY list of enabled collectors.
CollectorOrchestrator reads from here.

DO NOT define collectors anywhere else.
"""

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
    PID-file lock that self-heals without manual intervention.

    How it works:
    - Write our PID + timestamp to the lock file
    - On contention: check if holding PID is alive. If dead, take over.
    - TTL safety net: if lock is older than 15 min, break it regardless.
    - Cleanup: always delete lock file on exit (including crashes via atexit).

    No fcntl.flock — that approach breaks when files are rm'd (inode mismatch)
    and doesn't survive process crashes cleanly.

    Usage:
        with CollectorLock() as lock:
            if not lock.acquired:
                print("Another collector is running")
                return
            # do collection
    """

    TTL_SECONDS = 900  # 15 minutes — matches cron interval

    def __init__(self):
        self.lock_file = LOCK_FILE
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

    def _can_acquire(self) -> bool:
        """Check if we can acquire the lock. Self-heals stale locks."""
        import time

        pid, timestamp = self._read_lock_info()

        # No lock file or unreadable — acquire
        if pid is None:
            return True

        # Holding process is dead — acquire
        if not self._is_pid_alive(pid):
            logger.info("Lock held by dead PID %d, taking over", pid)
            return True

        # TTL expired — acquire (safety net for zombie processes)
        if timestamp is not None:
            age = time.time() - timestamp
            if age > self.TTL_SECONDS:
                logger.warning(
                    "Lock held by PID %d for %.0fs (TTL=%ds), forcing takeover",
                    pid,
                    age,
                    self.TTL_SECONDS,
                )
                return True

        # Lock is valid — someone else is running
        return False

    def _write_lock(self) -> None:
        """Write our PID and timestamp to the lock file."""
        import atexit
        import time

        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        self.lock_file.write_text(f"{os.getpid()}\n{time.time()}\n")
        # Register cleanup so lock is released even on unhandled exceptions
        atexit.register(self._cleanup)

    def _cleanup(self) -> None:
        """Remove lock file if we own it."""
        try:
            pid, _ = self._read_lock_info()
            if pid == os.getpid():
                self.lock_file.unlink(missing_ok=True)
        except OSError:
            pass

    def __enter__(self):
        if self._can_acquire():
            self._write_lock()
            self.acquired = True
        else:
            pid, _ = self._read_lock_info()
            logger.warning("Lock held by PID %d, skipping", pid)
            self.acquired = False
        return self

    def __exit__(self, *args):
        if self.acquired:
            self._cleanup()


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
