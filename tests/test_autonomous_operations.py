"""
Tests for AutonomousOperations — circuit breakers, retry, self-healing.

Brief 10 (AO), Task AO-1.1
"""

import time

import pytest

from lib.intelligence.autonomous_operations import (
    AutonomousOperations,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    LoopCycleReport,
    RetryConfig,
    SystemHealthReport,
    compute_backoff_delay,
)


class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = CircuitBreaker(CircuitBreakerConfig(name="test"))
        assert cb.state == CircuitState.CLOSED
        assert cb.is_available is True

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(CircuitBreakerConfig(name="test", failure_threshold=3))
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.is_available is False

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker(
            CircuitBreakerConfig(
                name="test",
                failure_threshold=2,
                recovery_timeout_s=0.05,
            )
        )
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.06)
        assert cb.is_available is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_closes_after_successes_in_half_open(self):
        cb = CircuitBreaker(
            CircuitBreakerConfig(
                name="test",
                failure_threshold=2,
                recovery_timeout_s=0.05,
                success_threshold=2,
            )
        )
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.06)
        _ = cb.is_available  # trigger transition to HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_reopens_on_failure_in_half_open(self):
        cb = CircuitBreaker(
            CircuitBreakerConfig(
                name="test",
                failure_threshold=2,
                recovery_timeout_s=0.05,
            )
        )
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.06)
        _ = cb.is_available
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_total_trips_counted(self):
        cb = CircuitBreaker(
            CircuitBreakerConfig(
                name="test",
                failure_threshold=1,
                recovery_timeout_s=0.05,
            )
        )
        cb.record_failure()
        assert cb.get_state()["total_trips"] == 1

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(CircuitBreakerConfig(name="test", failure_threshold=3))
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        # Now 2 more failures shouldn't open (count was reset)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

    def test_get_state_dict(self):
        cb = CircuitBreaker(CircuitBreakerConfig(name="test"))
        d = cb.get_state()
        assert d["name"] == "test"
        assert "state" in d
        assert "config" in d


class TestComputeBackoffDelay:
    def test_first_attempt(self):
        assert compute_backoff_delay(0) == 1.0

    def test_exponential_growth(self):
        assert compute_backoff_delay(1) == 2.0
        assert compute_backoff_delay(2) == 4.0
        assert compute_backoff_delay(3) == 8.0

    def test_max_cap(self):
        delay = compute_backoff_delay(20, max_delay=60.0)
        assert delay == 60.0

    def test_custom_base(self):
        assert compute_backoff_delay(0, base_delay=0.5) == 0.5


class TestAutonomousOperations:
    def test_register_job(self):
        ops = AutonomousOperations()
        ops.register_job("collector")
        assert "collector" in ops.circuit_breakers
        assert "collector" in ops.job_health

    def test_should_run_unregistered(self):
        ops = AutonomousOperations()
        assert ops.should_run_job("unknown") is True

    def test_should_run_healthy(self):
        ops = AutonomousOperations()
        ops.register_job("collector")
        assert ops.should_run_job("collector") is True

    def test_record_success(self):
        ops = AutonomousOperations()
        ops.register_job("collector")
        ops.record_job_success("collector", duration_ms=50.0)
        health = ops.job_health["collector"]
        assert health.status == "healthy"
        assert health.consecutive_successes == 1
        assert health.run_count == 1

    def test_record_failure_degrades(self):
        ops = AutonomousOperations()
        ops.register_job("collector")
        ops.record_job_failure("collector", error="timeout")
        ops.record_job_failure("collector", error="timeout")
        health = ops.job_health["collector"]
        assert health.status == "degraded"
        assert health.consecutive_failures == 2

    def test_record_failure_fails(self):
        ops = AutonomousOperations()
        ops.register_job("collector")
        for _ in range(5):
            ops.record_job_failure("collector", error="crash")
        health = ops.job_health["collector"]
        assert health.status == "failed"

    def test_system_health_healthy(self):
        ops = AutonomousOperations()
        ops.register_job("collector")
        ops.record_job_success("collector", duration_ms=10)
        report = ops.get_system_health()
        assert report.overall_status == "healthy"
        assert report.active_circuit_breakers == 0

    def test_system_health_degraded(self):
        ops = AutonomousOperations()
        ops.register_job("collector", failure_threshold=2)
        ops.record_job_failure("collector", error="err")
        ops.record_job_failure("collector", error="err")
        ops.record_job_failure("collector", error="err")
        ops.record_job_failure("collector", error="err")
        ops.record_job_failure("collector", error="err")
        report = ops.get_system_health()
        assert report.overall_status in ("degraded", "critical")
        assert report.active_circuit_breakers == 1

    def test_cycle_lifecycle(self):
        ops = AutonomousOperations()
        report = ops.start_cycle("cycle_001")
        assert report.status == "running"
        report.jobs_attempted = 3
        report.jobs_succeeded = 2
        report.jobs_failed = 1
        ops.complete_cycle(report)
        assert report.status == "partial"
        assert report.completed_at != ""

    def test_cycle_completed(self):
        ops = AutonomousOperations()
        report = ops.start_cycle("cycle_002")
        report.jobs_attempted = 3
        report.jobs_succeeded = 3
        report.jobs_failed = 0
        ops.complete_cycle(report)
        assert report.status == "completed"

    def test_system_health_to_dict(self):
        ops = AutonomousOperations()
        report = ops.get_system_health()
        d = report.to_dict()
        assert "overall_status" in d
        assert "job_health" in d
        assert "generated_at" in d
