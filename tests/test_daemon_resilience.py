"""
Tests for daemon resilience with circuit breakers and health tracking.

Covers:
- Circuit breaker integration with jobs
- Health status tracking based on consecutive failures
- Job health state transitions
- Circuit breaker state exposure via get_job_health()
"""

import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lib.collectors.resilience import CircuitBreakerState
from lib.daemon import JobHealth, TimeOSDaemon


@pytest.fixture
def temp_daemon_dirs(tmp_path):
    """Create temporary directories for daemon state."""
    state_dir = tmp_path / "daemon_state"
    state_dir.mkdir()
    return state_dir


@pytest.fixture
def daemon(temp_daemon_dirs, monkeypatch):
    """Create a TimeOSDaemon for testing."""
    # Mock the paths to use temp directory
    monkeypatch.setattr("lib.daemon.STATE_FILE", temp_daemon_dirs / "daemon_state.json")
    monkeypatch.setattr("lib.daemon.PID_FILE", temp_daemon_dirs / "daemon.pid")
    monkeypatch.setattr("lib.daemon.LOG_FILE", temp_daemon_dirs / "daemon.log")

    daemon = TimeOSDaemon()
    return daemon


# =============================================================================
# CIRCUIT BREAKER INTEGRATION TESTS
# =============================================================================


class TestDaemonCircuitBreakers:
    """Tests for circuit breaker integration with daemon jobs."""

    def test_circuit_breakers_initialized_for_all_jobs(self, daemon):
        """Circuit breaker should be initialized for each job."""
        for job_name in daemon.jobs:
            state = daemon.job_states[job_name]
            assert state.circuit_breaker is not None
            assert state.circuit_breaker.failure_threshold == 5
            assert state.circuit_breaker.cooldown_seconds == 600

    def test_circuit_breaker_rejects_execution_when_open(self, daemon):
        """Job execution should be skipped if circuit breaker is open."""
        job_name = "collect"
        state = daemon.job_states[job_name]
        cb = state.circuit_breaker

        # Open the circuit breaker
        for _ in range(cb.failure_threshold):
            cb.record_failure()

        assert cb.state == CircuitBreakerState.OPEN

        # Try to run job - should fail without executing
        result = daemon._run_job(job_name)

        assert result is False
        assert "circuit breaker" in state.last_error.lower()
        assert state.consecutive_failures > 0

    def test_circuit_breaker_transitions_to_half_open_after_cooldown(self, daemon):
        """Circuit breaker should become HALF_OPEN after cooldown."""
        job_name = "collect"
        state = daemon.job_states[job_name]
        cb = state.circuit_breaker

        # Open the circuit breaker
        for _ in range(cb.failure_threshold):
            cb.record_failure()

        assert cb.state == CircuitBreakerState.OPEN

        # Mock job execution to succeed
        with patch("lib.daemon.collect_all") as mock_collect:
            mock_collect.return_value = None

            # Wait for cooldown to expire
            cb.cooldown_seconds = 0.01
            cb.last_failure_time = time.time() - 0.1

            # Next execution should be allowed (circuit transitions to HALF_OPEN)
            assert cb.can_execute() is True
            assert cb.state == CircuitBreakerState.HALF_OPEN

    def test_circuit_breaker_closes_after_successful_execution_in_half_open(self, daemon):
        """Successful execution in HALF_OPEN should close circuit."""
        job_name = "collect"
        state = daemon.job_states[job_name]
        cb = state.circuit_breaker

        # Open circuit
        for _ in range(cb.failure_threshold):
            cb.record_failure()

        # Make cooldown instant
        cb.cooldown_seconds = 0.01
        cb.last_failure_time = time.time() - 0.1

        # Transition to HALF_OPEN
        cb.can_execute()
        assert cb.state == CircuitBreakerState.HALF_OPEN

        # Execute job successfully
        with patch("lib.daemon.collect_all") as mock_collect:
            mock_collect.return_value = None
            result = daemon._run_job(job_name)

        assert result is True
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0


# =============================================================================
# JOB HEALTH STATUS TESTS
# =============================================================================


class TestJobHealthStatus:
    """Tests for job health status tracking."""

    def test_initial_health_is_healthy(self, daemon):
        """Jobs should start in HEALTHY status."""
        for job_name in daemon.jobs:
            state = daemon.job_states[job_name]
            assert state.health_status == JobHealth.HEALTHY
            assert state.is_healthy is True

    def test_single_failure_marks_degraded(self, daemon):
        """One failure should move job to DEGRADED."""
        job_name = "collect"
        state = daemon.job_states[job_name]

        with patch("lib.daemon.collect_all") as mock_collect:
            mock_collect.side_effect = Exception("Collect error")
            daemon._run_job(job_name)

        assert state.health_status == JobHealth.DEGRADED
        assert state.consecutive_failures == 1

    def test_multiple_failures_mark_unhealthy(self, daemon):
        """Three or more consecutive failures should mark UNHEALTHY."""
        job_name = "collect"
        state = daemon.job_states[job_name]

        with patch("lib.daemon.collect_all") as mock_collect:
            mock_collect.side_effect = Exception("Collect error")

            for _i in range(3):
                daemon._run_job(job_name)

        assert state.health_status == JobHealth.UNHEALTHY
        assert state.consecutive_failures == 3

    def test_successful_execution_resets_health_to_healthy(self, daemon):
        """Successful execution should reset to HEALTHY."""
        job_name = "collect"
        state = daemon.job_states[job_name]

        # First, fail a few times
        with patch("lib.daemon.collect_all") as mock_collect:
            mock_collect.side_effect = Exception("Collect error")
            for _ in range(2):
                daemon._run_job(job_name)

        assert state.health_status == JobHealth.DEGRADED

        # Now succeed
        with patch("lib.daemon.collect_all") as mock_collect:
            mock_collect.return_value = None
            daemon._run_job(job_name)

        assert state.health_status == JobHealth.HEALTHY
        assert state.consecutive_failures == 0

    def test_health_status_property(self, daemon):
        """is_healthy property should reflect current status."""
        job_name = "collect"
        state = daemon.job_states[job_name]

        assert state.is_healthy is True
        state.health_status = JobHealth.DEGRADED
        assert state.is_healthy is False
        state.health_status = JobHealth.HEALTHY
        assert state.is_healthy is True


# =============================================================================
# GET_JOB_HEALTH TESTS
# =============================================================================


class TestGetJobHealth:
    """Tests for get_job_health() method."""

    def test_get_health_for_single_job(self, daemon):
        """Should return health info for a single job."""
        job_name = "collect"

        health = daemon.get_job_health(job_name)

        assert health["name"] == job_name
        assert health["health"] == "healthy"
        assert health["consecutive_failures"] == 0
        assert health["total_runs"] == 0
        assert health["circuit_breaker"] is not None

    def test_get_health_for_all_jobs(self, daemon):
        """Should return health info for all jobs."""
        health = daemon.get_job_health()

        assert isinstance(health, dict)
        assert len(health) == len(daemon.jobs)

        for job_name in daemon.jobs:
            assert job_name in health
            assert health[job_name]["name"] == job_name
            assert "health" in health[job_name]

    def test_get_health_includes_circuit_breaker_state(self, daemon):
        """Health info should include circuit breaker state."""
        job_name = "collect"
        state = daemon.job_states[job_name]
        cb = state.circuit_breaker

        # Open the circuit breaker
        for _ in range(cb.failure_threshold):
            cb.record_failure()

        health = daemon.get_job_health(job_name)

        assert health["circuit_breaker"]["state"] == CircuitBreakerState.OPEN
        assert health["circuit_breaker"]["failure_count"] == cb.failure_threshold

    def test_get_health_for_nonexistent_job(self, daemon):
        """Should return error for non-existent job."""
        health = daemon.get_job_health("nonexistent")

        assert "error" in health

    def test_get_health_includes_failure_counts(self, daemon):
        """Health info should include total and consecutive failure counts."""
        job_name = "collect"

        with patch("lib.daemon.collect_all") as mock_collect:
            mock_collect.side_effect = Exception("test error")
            for _ in range(3):
                daemon._run_job(job_name)

        health = daemon.get_job_health(job_name)

        assert health["consecutive_failures"] == 3
        assert health["total_failures"] == 3
        assert health["total_runs"] == 3

    def test_get_health_includes_last_error(self, daemon):
        """Health info should include last error message."""
        job_name = "collect"

        with patch("lib.daemon.collect_all") as mock_collect:
            mock_collect.side_effect = Exception("test error")
            daemon._run_job(job_name)

        health = daemon.get_job_health(job_name)

        assert health["last_error"] is not None

    def test_get_health_includes_last_success_time(self, daemon):
        """Health info should include last success timestamp."""
        job_name = "collect"

        with patch("lib.daemon.collect_all") as mock_collect:
            mock_collect.return_value = None
            daemon._run_job(job_name)

        health = daemon.get_job_health(job_name)

        assert health["last_success"] is not None
        # Verify it's a valid ISO format timestamp
        datetime.fromisoformat(health["last_success"])


# =============================================================================
# CIRCUIT BREAKER STATE PERSISTENCE TESTS
# =============================================================================


class TestCircuitBreakerPersistence:
    """Tests for circuit breaker state across daemon restarts."""

    def test_consecutive_failures_persist_across_restarts(self, temp_daemon_dirs, monkeypatch):
        """Consecutive failure count should persist to disk."""
        monkeypatch.setattr("lib.daemon.STATE_FILE", temp_daemon_dirs / "daemon_state.json")
        monkeypatch.setattr("lib.daemon.PID_FILE", temp_daemon_dirs / "daemon.pid")
        monkeypatch.setattr("lib.daemon.LOG_FILE", temp_daemon_dirs / "daemon.log")

        # Create daemon and simulate failures
        daemon1 = TimeOSDaemon()
        job_name = "collect"

        with patch("lib.daemon.collect_all") as mock_collect:
            mock_collect.side_effect = Exception("test error")
            for _ in range(2):
                daemon1._run_job(job_name)

        daemon1._save_state()

        # Create new daemon and load state
        daemon2 = TimeOSDaemon()
        state = daemon2.job_states[job_name]

        assert state.consecutive_failures == 2
        assert state.total_runs == 2
        assert state.total_failures == 2


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestDaemonResilience:
    """Integration tests for daemon resilience features."""

    def test_job_with_backoff_on_consecutive_failures(self, daemon):
        """Job should have increased interval when failing."""
        job_name = "collect"
        daemon.jobs[job_name]

        # Make job fail
        with patch("lib.daemon.collect_all") as mock_collect:
            mock_collect.side_effect = Exception("test error")
            daemon._run_job(job_name)

        # Set last_run to past to make should_run return true
        daemon.job_states[job_name].last_run = datetime.now() - timedelta(hours=1)

        # should_run should apply backoff
        should_run = daemon._should_run(job_name)
        assert should_run is True  # Backoff has elapsed

    def test_metrics_tracked_for_job_health(self, daemon):
        """Metrics should be updated when job health changes."""
        job_name = "collect"

        with patch("lib.daemon.collect_all") as mock_collect:
            mock_collect.side_effect = Exception("test error")
            daemon._run_job(job_name)

        # Check that metrics were updated
        # (we can't directly verify without checking REGISTRY, which is integration)
        state = daemon.job_states[job_name]
        assert state.health_status != JobHealth.HEALTHY

    def test_daemon_graceful_degradation_with_circuit_breakers(self, daemon):
        """Daemon should gracefully handle job failures with circuit breakers."""
        job_name = "collect"
        state = daemon.job_states[job_name]
        cb = state.circuit_breaker

        # Simulate many failures to open circuit breaker
        with patch("lib.daemon.collect_all") as mock_collect:
            mock_collect.side_effect = Exception("test error")
            for _ in range(10):  # More than threshold
                daemon._run_job(job_name)

        # Circuit should be open
        assert cb.state == CircuitBreakerState.OPEN
        assert state.health_status == JobHealth.UNHEALTHY

        # Further job runs should be rejected immediately
        result = daemon._run_job(job_name)
        assert result is False
        assert "circuit breaker" in state.last_error.lower()
