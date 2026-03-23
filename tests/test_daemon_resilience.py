"""
Tests for daemon resilience — failure tracking, backoff, and state persistence.

The daemon is a thin scheduler that delegates all pipeline work to
AutonomousLoop via subprocess. These tests verify:
- Job state tracking (success/failure counts)
- Exponential backoff on consecutive failures
- State persistence across daemon restarts
- Graceful handling of subprocess failures
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from lib.daemon import TimeOSDaemon


@pytest.fixture
def temp_daemon_dirs(tmp_path):
    """Create temporary directories for daemon state."""
    state_dir = tmp_path / "daemon_state"
    state_dir.mkdir()
    return state_dir


@pytest.fixture
def daemon(temp_daemon_dirs, monkeypatch):
    """Create a TimeOSDaemon for testing."""
    monkeypatch.setattr("lib.daemon.STATE_FILE", temp_daemon_dirs / "daemon_state.json")
    monkeypatch.setattr("lib.daemon.PID_FILE", temp_daemon_dirs / "daemon.pid")
    monkeypatch.setattr("lib.daemon.LOG_FILE", temp_daemon_dirs / "daemon.log")
    monkeypatch.setattr("lib.daemon._ENV_FILE_PATHS", [])

    daemon = TimeOSDaemon()
    return daemon


# =============================================================================
# JOB STATE TRACKING TESTS
# =============================================================================


class TestJobStateTracking:
    """Tests for job success/failure state tracking."""

    def test_initial_state_is_clean(self, daemon):
        """Jobs should start with zero failures and no last_run."""
        for job_name in daemon.jobs:
            state = daemon.job_states[job_name]
            assert state.consecutive_failures == 0
            assert state.total_runs == 0
            assert state.total_failures == 0
            assert state.last_run is None
            assert state.last_success is None
            assert state.last_error is None

    def test_successful_run_updates_state(self, daemon):
        """Successful subprocess run should update success fields."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "OK"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            daemon._run_job("autonomous")

        state = daemon.job_states["autonomous"]
        assert state.total_runs == 1
        assert state.total_failures == 0
        assert state.consecutive_failures == 0
        assert state.last_success is not None
        assert state.last_error is None

    def test_failed_run_tracks_failure(self, daemon):
        """Failed subprocess run should increment failure counters."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error occurred"

        with patch("subprocess.run", return_value=mock_result):
            daemon._run_job("autonomous")

        state = daemon.job_states["autonomous"]
        assert state.total_runs == 1
        assert state.total_failures == 1
        assert state.consecutive_failures == 1
        assert state.last_error is not None

    def test_success_resets_consecutive_failures(self, daemon):
        """Successful run should reset consecutive failure count."""
        fail_result = MagicMock()
        fail_result.returncode = 1
        fail_result.stdout = ""
        fail_result.stderr = "Error"

        ok_result = MagicMock()
        ok_result.returncode = 0
        ok_result.stdout = "OK"
        ok_result.stderr = ""

        # Fail twice
        with patch("subprocess.run", return_value=fail_result):
            daemon._run_job("autonomous")
            daemon._run_job("autonomous")

        assert daemon.job_states["autonomous"].consecutive_failures == 2

        # Then succeed
        with patch("subprocess.run", return_value=ok_result):
            daemon._run_job("autonomous")

        state = daemon.job_states["autonomous"]
        assert state.consecutive_failures == 0
        assert state.total_failures == 2  # Total doesn't reset
        assert state.total_runs == 3

    def test_subprocess_exception_tracked_as_failure(self, daemon):
        """If subprocess.run raises, it should be tracked as a failure."""
        with patch("subprocess.run", side_effect=OSError("Command not found")):
            daemon._run_job("autonomous")

        state = daemon.job_states["autonomous"]
        assert state.consecutive_failures == 1
        assert state.total_failures == 1
        assert "Command not found" in state.last_error


# =============================================================================
# BACKOFF TESTS
# =============================================================================


class TestExponentialBackoff:
    """Tests for exponential backoff on consecutive failures."""

    def test_no_backoff_on_first_failure(self, daemon):
        """First failure should not prevent next run when interval elapses."""
        state = daemon.job_states["autonomous"]
        state.consecutive_failures = 1
        state.last_run = datetime.now() - timedelta(minutes=16)

        assert daemon._should_run("autonomous") is True

    def test_backoff_increases_with_failures(self, daemon):
        """More failures should require longer wait before next run.

        Backoff formula: min(interval_minutes, backoff_base ^ consecutive_failures)
        With 3 failures, base=2: min(15, 2^3) = min(15, 8) = 8 minutes.
        """
        state = daemon.job_states["autonomous"]

        # With 3 consecutive failures, backoff = min(15, 2^3) = 8 min
        state.consecutive_failures = 3
        state.last_run = datetime.now() - timedelta(minutes=5)

        # 5 minutes ago is not enough for 8-minute backoff
        assert daemon._should_run("autonomous") is False

        # But 9 minutes ago should be enough
        state.last_run = datetime.now() - timedelta(minutes=9)
        assert daemon._should_run("autonomous") is True


# =============================================================================
# STATE PERSISTENCE TESTS
# =============================================================================


class TestStatePersistence:
    """Tests for daemon state persistence across restarts."""

    def test_failure_count_persists(self, temp_daemon_dirs, monkeypatch):
        """Consecutive failure count should persist across daemon restarts."""
        monkeypatch.setattr("lib.daemon.STATE_FILE", temp_daemon_dirs / "daemon_state.json")
        monkeypatch.setattr("lib.daemon.PID_FILE", temp_daemon_dirs / "daemon.pid")
        monkeypatch.setattr("lib.daemon.LOG_FILE", temp_daemon_dirs / "daemon.log")
        monkeypatch.setattr("lib.daemon._ENV_FILE_PATHS", [])

        fail_result = MagicMock()
        fail_result.returncode = 1
        fail_result.stdout = ""
        fail_result.stderr = "Error"

        # First daemon instance — fail twice
        daemon1 = TimeOSDaemon()
        with patch("subprocess.run", return_value=fail_result):
            daemon1._run_job("autonomous")
            daemon1._run_job("autonomous")
        daemon1._save_state()

        # Second daemon instance — should load persisted state
        daemon2 = TimeOSDaemon()
        state = daemon2.job_states["autonomous"]

        assert state.consecutive_failures == 2
        assert state.total_runs == 2
        assert state.total_failures == 2


# =============================================================================
# JOB REGISTRATION TESTS
# =============================================================================


class TestJobRegistration:
    """Tests for default job registration."""

    def test_default_jobs_registered(self, daemon):
        """Daemon should register autonomous and backup jobs."""
        assert "autonomous" in daemon.jobs
        assert "backup" in daemon.jobs

    def test_autonomous_job_config(self, daemon):
        """Autonomous job should run every 15 minutes."""
        config = daemon.jobs["autonomous"]
        assert config.interval_minutes == 15
        assert "autonomous_loop" in " ".join(str(c) for c in config.command)

    def test_backup_job_config(self, daemon):
        """Backup job should run every 24 hours."""
        config = daemon.jobs["backup"]
        assert config.interval_minutes == 1440
        assert "backup" in " ".join(str(c) for c in config.command)
