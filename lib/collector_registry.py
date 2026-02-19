"""
Collector Registry — Single Source of Truth

This module defines THE ONLY list of enabled collectors.
Both scheduled_collect.py and CollectorOrchestrator must read from here.

DO NOT define collectors anywhere else.
"""

import fcntl
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from lib import paths

logger = logging.getLogger(__name__)

# ============================================================================
# LOCKFILE GUARD — Prevents double execution with stale lock detection
# ============================================================================
LOCK_FILE = paths.data_dir() / ".collector.lock"

# Default timeout for stale lock detection (20 minutes)
DEFAULT_LOCK_TTL_SECONDS = int(os.environ.get("COLLECTOR_LOCK_TTL_SECONDS", "1200"))


def _is_pid_running(pid: int) -> bool:
    """Check if a process with given PID is running."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we don't have permission to signal it
        return True
    except OSError:
        return False


def _read_lock_info(lock_path: Path) -> tuple[int | None, float | None]:
    """
    Read PID and mtime from lock file.

    Returns (pid, mtime) or (None, None) if lock doesn't exist or can't be read.
    """
    try:
        if not lock_path.exists():
            return None, None
        content = lock_path.read_text().strip()
        pid = int(content) if content else None
        mtime = lock_path.stat().st_mtime
        return pid, mtime
    except (ValueError, OSError, FileNotFoundError):
        return None, None


def _is_lock_stale(lock_path: Path, ttl_seconds: int = DEFAULT_LOCK_TTL_SECONDS) -> bool:
    """
    Determine if an existing lock is stale.

    A lock is stale if:
    1. The PID in the lock file is not running, OR
    2. The lock file is older than ttl_seconds

    Returns True if stale (safe to acquire), False if lock is valid.
    """
    pid, mtime = _read_lock_info(lock_path)

    if pid is None or mtime is None:
        # Can't read lock info, treat as stale
        return True

    # Check 1: Is the PID still running?
    if not _is_pid_running(pid):
        logger.warning(
            f"Stale lock detected: PID {pid} is not running. Removing stale lock at {lock_path}"
        )
        return True

    # Check 2: Is the lock older than TTL?
    lock_age = time.time() - mtime
    if lock_age > ttl_seconds:
        logger.warning(
            f"Stale lock detected: Lock age {lock_age:.0f}s exceeds TTL {ttl_seconds}s. "
            f"PID {pid} may be hung. Removing stale lock at {lock_path}"
        )
        return True

    return False


class CollectorLock:
    """
    Prevents concurrent collector runs with stale lock detection.

    Features:
    - File-based locking with fcntl.flock
    - Stale lock detection via PID check and TTL
    - Guaranteed release in __exit__ (even on exception)

    Usage:
        with CollectorLock() as lock:
            if not lock.acquired:
                print("Another collector is running")
                return
            # do collection

    Environment variables:
        COLLECTOR_LOCK_TTL_SECONDS: Max age of lock before considered stale (default: 1200)
    """

    def __init__(self, ttl_seconds: int | None = None):
        self.lock_file = LOCK_FILE
        self.lock_fd = None
        self.acquired = False
        self.ttl_seconds = ttl_seconds if ttl_seconds is not None else DEFAULT_LOCK_TTL_SECONDS

    def __enter__(self):
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)

        # Check for stale lock before attempting to acquire
        if self.lock_file.exists() and _is_lock_stale(self.lock_file, self.ttl_seconds):
            try:
                self.lock_file.unlink()
                logger.info(f"Removed stale lock file: {self.lock_file}")
            except OSError as e:
                logger.warning(f"Failed to remove stale lock: {e}")

        self.lock_fd = open(self.lock_file, "w")
        try:
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.lock_fd.write(f"{os.getpid()}\n")
            self.lock_fd.flush()
            self.acquired = True
            logger.debug(f"Acquired collector lock: PID {os.getpid()}")
        except BlockingIOError:
            # Lock held by another process - check if it's stale
            pid, _ = _read_lock_info(self.lock_file)
            logger.info(f"Collector lock held by PID {pid}. Another collection is in progress.")
            self.acquired = False
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.lock_fd:
            try:
                if self.acquired:
                    fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
                    logger.debug(f"Released collector lock: PID {os.getpid()}")
            except OSError as e:
                logger.warning(f"Error releasing lock: {e}")
            finally:
                try:
                    self.lock_fd.close()
                except OSError:
                    pass

                # Clean up lock file if we owned it
                if self.acquired:
                    try:
                        self.lock_file.unlink(missing_ok=True)
                    except OSError:
                        pass

        # Don't suppress exceptions - let them propagate
        return False


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
