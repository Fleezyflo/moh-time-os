"""
Tests for collector lock functionality.

Tests cover:
- Stale lock detection (PID dead, lock too old)
- Lock release on exception
- Watchdog timeout behavior
- Concurrent lock acquisition

Note: These tests need clean sys.modules state for collectors imports.
Other tests (test_cash_ar.py, test_comms_commitments.py) add lib/ to sys.path
which causes import conflicts. We clean up before importing.
"""

import os
import sys
import time
from pathlib import Path

import pytest


def _clean_collectors_imports():
    """
    Clean up sys.modules to fix import issues caused by other tests.

    Some tests add lib/ directly to sys.path, which causes 'collectors'
    to be importable from two locations (lib/collectors and ./collectors),
    breaking relative imports in lib/collectors/base.py.
    """
    # Remove lib/ from sys.path if it was added by other tests
    lib_path = str(Path(__file__).parent.parent / "lib")
    while lib_path in sys.path:
        sys.path.remove(lib_path)

    # Clear any cached imports that might be broken
    for mod in list(sys.modules.keys()):
        if mod.startswith("collectors") or mod == "collectors":
            del sys.modules[mod]
        if mod.startswith("lib.collectors"):
            del sys.modules[mod]


@pytest.fixture(autouse=True)
def clean_import_state():
    """Ensure clean import state for collector tests."""
    _clean_collectors_imports()
    yield
    _clean_collectors_imports()


class TestCollectorLock:
    """Tests for CollectorLock stale detection and cleanup."""

    def test_lock_acquired_on_fresh_start(self, tmp_path, monkeypatch):
        """Lock is acquired when no lock file exists."""
        import lib.collector_registry
        from lib.collector_registry import CollectorLock

        lock_file = tmp_path / ".collector.lock"
        monkeypatch.setattr(lib.collector_registry, "LOCK_FILE", lock_file)

        with CollectorLock() as lock:
            assert lock.acquired is True
            assert lock_file.exists()
            content = lock_file.read_text().strip()
            assert content == str(os.getpid())

    def test_lock_released_after_exit(self, tmp_path, monkeypatch):
        """Lock file is cleaned up after context exit."""
        import lib.collector_registry
        from lib.collector_registry import CollectorLock

        lock_file = tmp_path / ".collector.lock"
        monkeypatch.setattr(lib.collector_registry, "LOCK_FILE", lock_file)

        with CollectorLock() as lock:
            assert lock.acquired is True

        assert not lock_file.exists()

    def test_lock_released_on_exception(self, tmp_path, monkeypatch):
        """Lock is released even when exception occurs inside context."""
        import lib.collector_registry
        from lib.collector_registry import CollectorLock

        lock_file = tmp_path / ".collector.lock"
        monkeypatch.setattr(lib.collector_registry, "LOCK_FILE", lock_file)

        with pytest.raises(ValueError, match="test exception"):
            with CollectorLock() as lock:
                assert lock.acquired is True
                raise ValueError("test exception")

        assert not lock_file.exists()

    def test_stale_lock_detected_by_dead_pid(self, tmp_path, monkeypatch):
        """Stale lock with dead PID is detected and removed."""
        import lib.collector_registry
        from lib.collector_registry import CollectorLock, _is_lock_stale

        lock_file = tmp_path / ".collector.lock"
        monkeypatch.setattr(lib.collector_registry, "LOCK_FILE", lock_file)

        lock_file.write_text("99999999\n")

        assert _is_lock_stale(lock_file, ttl_seconds=3600) is True

        with CollectorLock() as lock:
            assert lock.acquired is True

    def test_stale_lock_detected_by_ttl(self, tmp_path, monkeypatch):
        """Lock older than TTL is detected as stale."""
        import lib.collector_registry
        from lib.collector_registry import CollectorLock, _is_lock_stale

        lock_file = tmp_path / ".collector.lock"
        monkeypatch.setattr(lib.collector_registry, "LOCK_FILE", lock_file)

        lock_file.write_text(f"{os.getpid()}\n")

        old_mtime = time.time() - 7200
        os.utime(lock_file, (old_mtime, old_mtime))

        assert _is_lock_stale(lock_file, ttl_seconds=3600) is True

        with CollectorLock(ttl_seconds=3600) as lock:
            assert lock.acquired is True

    def test_valid_lock_not_stale(self, tmp_path, monkeypatch):
        """Recent lock with running PID is not stale."""
        import lib.collector_registry
        from lib.collector_registry import _is_lock_stale

        lock_file = tmp_path / ".collector.lock"
        monkeypatch.setattr(lib.collector_registry, "LOCK_FILE", lock_file)

        lock_file.write_text(f"{os.getpid()}\n")

        assert _is_lock_stale(lock_file, ttl_seconds=3600) is False

    def test_concurrent_lock_second_blocked(self, tmp_path, monkeypatch):
        """Second lock attempt is blocked when first holds lock."""
        import lib.collector_registry
        from lib.collector_registry import CollectorLock

        lock_file = tmp_path / ".collector.lock"
        monkeypatch.setattr(lib.collector_registry, "LOCK_FILE", lock_file)

        with CollectorLock() as lock1:
            assert lock1.acquired is True

            with CollectorLock() as lock2:
                assert lock2.acquired is False

    def test_is_pid_running_for_current_process(self):
        """_is_pid_running returns True for current process."""
        from lib.collector_registry import _is_pid_running

        assert _is_pid_running(os.getpid()) is True

    def test_is_pid_running_for_dead_process(self):
        """_is_pid_running returns False for non-existent PID."""
        from lib.collector_registry import _is_pid_running

        assert _is_pid_running(99999999) is False

    def test_is_pid_running_for_invalid_pid(self):
        """_is_pid_running returns False for invalid PIDs."""
        from lib.collector_registry import _is_pid_running

        assert _is_pid_running(0) is False
        assert _is_pid_running(-1) is False


class TestWatchdogTimer:
    """Tests for watchdog timeout functionality."""

    def test_watchdog_no_timeout_when_fast(self):
        """Watchdog does not trigger when work completes quickly."""
        import collectors.scheduled_collect as sc

        with sc.WatchdogTimer(timeout_seconds=5) as timer:
            time.sleep(0.1)
            assert timer.expired is False

    def test_watchdog_timeout_raises(self):
        """Watchdog raises CollectionTimeoutError on expiry."""
        import collectors.scheduled_collect as sc

        with pytest.raises(sc.CollectionTimeoutError, match="exceeded timeout"):
            with sc.WatchdogTimer(timeout_seconds=1):
                time.sleep(3)

    def test_watchdog_zero_timeout_disabled(self):
        """Watchdog with timeout=0 does not trigger."""
        import collectors.scheduled_collect as sc

        with sc.WatchdogTimer(timeout_seconds=0) as timer:
            time.sleep(0.1)
            assert timer.expired is False

    def test_watchdog_canceled_on_normal_exit(self):
        """SIGALRM is canceled after normal context exit."""
        import collectors.scheduled_collect as sc

        with sc.WatchdogTimer(timeout_seconds=2):
            pass

        time.sleep(0.5)


class TestCollectAllLocking:
    """Integration tests for collect_all lock behavior."""

    def test_collect_all_returns_locked_when_lock_held(self, tmp_path, monkeypatch):
        """collect_all returns locked status when another instance holds lock."""
        import collectors.scheduled_collect as sc
        import lib.collector_registry
        from lib.collector_registry import CollectorLock

        lock_file = tmp_path / ".collector.lock"
        # Patch using module object, not string path
        monkeypatch.setattr(lib.collector_registry, "LOCK_FILE", lock_file)
        monkeypatch.setattr(sc, "collect_calendar", lambda: {})
        monkeypatch.setattr(lib.collector_registry, "get_all_sources", lambda: [])

        with CollectorLock() as outer_lock:
            assert outer_lock.acquired is True

            result = sc.collect_all(sources=[], v4_ingest=False, timeout_seconds=0)

            assert result["status"] == "locked"
            assert "Another collector" in result["error"]

    def test_collect_all_releases_lock_on_error(self, tmp_path, monkeypatch):
        """Lock is released even when collection raises exception."""
        import collectors.scheduled_collect as sc
        import lib.collector_registry
        from lib.collector_registry import CollectorLock

        lock_file = tmp_path / ".collector.lock"
        monkeypatch.setattr(lib.collector_registry, "LOCK_FILE", lock_file)

        def failing_collector():
            raise RuntimeError("Collector exploded")

        monkeypatch.setattr(sc, "collect_calendar", failing_collector)
        monkeypatch.setattr(lib.collector_registry, "get_all_sources", lambda: ["calendar"])

        result = sc.collect_all(sources=["calendar"], v4_ingest=False, timeout_seconds=0)

        assert not lock_file.exists()
        assert "calendar" in result

    def test_collect_all_timeout_returns_structured_error(self, tmp_path, monkeypatch):
        """Timeout returns structured error and releases lock."""
        import collectors.scheduled_collect as sc
        import lib.collector_registry

        lock_file = tmp_path / ".collector.lock"
        monkeypatch.setattr(lib.collector_registry, "LOCK_FILE", lock_file)

        def slow_collector():
            time.sleep(5)
            return {}

        monkeypatch.setattr(sc, "collect_calendar", slow_collector)
        monkeypatch.setattr(lib.collector_registry, "get_all_sources", lambda: ["calendar"])

        result = sc.collect_all(sources=["calendar"], v4_ingest=False, timeout_seconds=1)

        assert result["status"] == "timeout"
        assert "timeout_seconds" in result
        assert not lock_file.exists()
