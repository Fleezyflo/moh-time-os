"""
Collector Registry — Single Source of Truth

This module defines THE ONLY list of enabled collectors.
CollectorOrchestrator reads from here.

DO NOT define collectors anywhere else.
"""

import logging
import os
import threading
import time
from dataclasses import dataclass, field

from lib import paths

logger = logging.getLogger(__name__)

# ============================================================================
# LOCKFILE GUARD — Prevents double execution
# ============================================================================


def _lock_dir():
    return paths.data_dir()


class CollectorLock:
    """
    Per-collector self-healing lock that NEVER requires manual intervention.

    Each collector gets its own lock file (.collector.{name}.lock) so a slow
    collector (e.g. Asana at 49 min) doesn't block faster ones.

    Three-layer protection:
    1. PID check: if the holder process is dead, break immediately.
    2. Heartbeat: while holding the lock, a daemon thread touches the
       lock file every 20s, keeping its mtime fresh.
    3. TTL (60s): if the lock file hasn't been touched in 60 seconds,
       the holder is dead (heartbeat stopped). Break immediately.

    Usage:
        with CollectorLock("tasks") as lock:
            if not lock.acquired:
                print("tasks collector is already running")
                return
            # do collection
    """

    TTL_SECONDS = 60  # 1 minute — heartbeat keeps live locks fresh
    HEARTBEAT_INTERVAL = 20  # Touch lock file every 20 seconds

    def __init__(self, name: str = "global"):
        self.lock_file = _lock_dir() / f".collector.{name}.lock"
        self.name = name
        self.acquired = False
        self._stop_heartbeat = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None

    def _lock_age(self) -> float | None:
        """Return age of lock file in seconds, or None if no lock."""
        try:
            if self.lock_file.exists():
                return time.time() - self.lock_file.stat().st_mtime
        except OSError:
            pass
        return None

    def _holder_pid(self) -> int | None:
        """Read PID from lock file, or None if unreadable."""
        try:
            content = self.lock_file.read_text().strip()
            return int(content)
        except (OSError, ValueError):
            return None

    def _holder_alive(self) -> bool:
        """Check if the process that wrote the lock still exists."""
        pid = self._holder_pid()
        if pid is None:
            return False
        if pid == os.getpid():
            return True
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False

    def _can_acquire(self) -> bool:
        """Check if we can acquire the lock. Self-heals dead holders."""
        age = self._lock_age()

        # No lock file — acquire
        if age is None:
            return True

        # Lock is stale (older than TTL) — heartbeat stopped = holder dead
        if age > self.TTL_SECONDS:
            logger.info(
                "Lock file is %.0fs old (TTL=%ds) -- holder dead, taking over",
                age,
                self.TTL_SECONDS,
            )
            return True

        # Lock is fresh — but is the holder actually alive?
        if not self._holder_alive():
            logger.info("Lock holder is dead (PID gone), taking over")
            return True

        # Lock is fresh AND holder appears alive — respect it
        return False

    def _write_lock(self) -> None:
        """Write our PID to the lock file."""
        import atexit

        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        self.lock_file.write_text(f"{os.getpid()}\n")
        atexit.register(self._cleanup)

    def _start_heartbeat(self) -> None:
        """Start daemon thread that touches lock file every HEARTBEAT_INTERVAL."""

        def _beat():
            while not self._stop_heartbeat.wait(self.HEARTBEAT_INTERVAL):
                try:
                    self.lock_file.write_text(f"{os.getpid()}\n")
                except OSError:
                    break

        self._heartbeat_thread = threading.Thread(target=_beat, daemon=True)
        self._heartbeat_thread.start()

    def _stop_heartbeat_thread(self) -> None:
        """Signal heartbeat to stop and wait for it."""
        self._stop_heartbeat.set()
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=5)

    def _cleanup(self) -> None:
        """Remove lock file if we own it."""
        try:
            content = self.lock_file.read_text().strip() if self.lock_file.exists() else ""
            if content == str(os.getpid()):
                self.lock_file.unlink(missing_ok=True)
        except OSError:
            pass

    def break_lock(self) -> None:
        """Forcibly remove the lock file regardless of holder state."""
        try:
            if self.lock_file.exists():
                pid = self._holder_pid()
                logger.warning("Breaking lock for %s (holder PID=%s)", self.name, pid)
                self.lock_file.unlink(missing_ok=True)
        except OSError as e:
            logger.warning("Failed to break lock for %s: %s", self.name, e)

    @classmethod
    def break_all(cls) -> int:
        """Remove all collector lock files. Returns count of locks broken."""
        count = 0
        for lock_file in _lock_dir().glob(".collector.*.lock"):
            try:
                pid_text = lock_file.read_text().strip()
                logger.warning("Breaking lock %s (PID=%s)", lock_file.name, pid_text)
                lock_file.unlink(missing_ok=True)
                count += 1
            except OSError as e:
                logger.warning("Failed to break %s: %s", lock_file.name, e)
        return count

    def __enter__(self):
        if self._can_acquire():
            self._write_lock()
            self._start_heartbeat()
            self.acquired = True
        else:
            age = self._lock_age()
            logger.warning("Lock file exists (age=%.0fs), skipping", age or 0)
            self.acquired = False
        return self

    def __exit__(self, *args):
        if self.acquired:
            self._stop_heartbeat_thread()
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
