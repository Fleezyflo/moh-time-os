"""
Autonomous Operations — MOH TIME OS

Production-grade autonomous loop hardening with circuit breakers,
retry logic, self-healing, and observability.

Brief 10 (AO), Tasks AO-1.1 through AO-3.1

Makes the autonomous loop survive failures without manual intervention.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for a circuit breaker."""

    name: str
    failure_threshold: int = 3  # Failures before opening
    recovery_timeout_s: float = 60  # Seconds before trying again
    success_threshold: int = 2  # Successes in half-open before closing

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout_s": self.recovery_timeout_s,
            "success_threshold": self.success_threshold,
        }


@dataclass
class CircuitBreakerState:
    """Runtime state of a circuit breaker."""

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_at: float | None = None
    last_transition_at: float = 0.0
    total_trips: int = 0

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "total_trips": self.total_trips,
        }


class CircuitBreaker:
    """
    Circuit breaker for autonomous loop jobs.

    Prevents cascading failures by temporarily disabling failing components.
    """

    def __init__(self, config: CircuitBreakerConfig) -> None:
        self.config = config
        self._state = CircuitBreakerState(last_transition_at=time.monotonic())

    @property
    def state(self) -> CircuitState:
        return self._state.state

    @property
    def is_available(self) -> bool:
        """Check if calls should be allowed."""
        if self._state.state == CircuitState.CLOSED:
            return True
        if self._state.state == CircuitState.OPEN:
            elapsed = time.monotonic() - (self._state.last_failure_at or 0)
            if elapsed >= self.config.recovery_timeout_s:
                self._transition(CircuitState.HALF_OPEN)
                return True
            return False
        # HALF_OPEN: allow calls to test recovery
        return True

    def record_success(self) -> None:
        """Record a successful call."""
        if self._state.state == CircuitState.HALF_OPEN:
            self._state.success_count += 1
            if self._state.success_count >= self.config.success_threshold:
                self._transition(CircuitState.CLOSED)
        elif self._state.state == CircuitState.CLOSED:
            self._state.failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call."""
        self._state.failure_count += 1
        self._state.last_failure_at = time.monotonic()

        if self._state.state == CircuitState.HALF_OPEN:
            self._transition(CircuitState.OPEN)
        elif self._state.state == CircuitState.CLOSED:
            if self._state.failure_count >= self.config.failure_threshold:
                self._transition(CircuitState.OPEN)

    def _transition(self, new_state: CircuitState) -> None:
        """Transition to a new state."""
        old_state = self._state.state
        self._state.state = new_state
        self._state.last_transition_at = time.monotonic()
        if new_state == CircuitState.OPEN:
            self._state.total_trips += 1
        if new_state == CircuitState.HALF_OPEN:
            self._state.success_count = 0
        if new_state == CircuitState.CLOSED:
            self._state.failure_count = 0
            self._state.success_count = 0
        logger.info(
            "Circuit breaker %s: %s -> %s",
            self.config.name,
            old_state.value,
            new_state.value,
        )

    def get_state(self) -> dict:
        """Get current circuit breaker state."""
        return {
            "name": self.config.name,
            **self._state.to_dict(),
            "config": self.config.to_dict(),
        }


@dataclass
class RetryConfig:
    """Configuration for retry logic."""

    max_retries: int = 3
    base_delay_s: float = 1.0
    max_delay_s: float = 60.0
    backoff_factor: float = 2.0
    retryable_errors: list[str] = field(
        default_factory=lambda: [
            "ConnectionError",
            "TimeoutError",
            "TemporaryError",
        ]
    )

    def to_dict(self) -> dict:
        return {
            "max_retries": self.max_retries,
            "base_delay_s": self.base_delay_s,
            "max_delay_s": self.max_delay_s,
            "backoff_factor": self.backoff_factor,
        }


@dataclass
class RetryResult:
    """Result of a retried operation."""

    success: bool
    attempts: int
    last_error: str = ""
    total_delay_s: float = 0.0

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "attempts": self.attempts,
            "last_error": self.last_error,
            "total_delay_s": round(self.total_delay_s, 2),
        }


def compute_backoff_delay(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    factor: float = 2.0,
) -> float:
    """Compute exponential backoff delay for a retry attempt."""
    delay = base_delay * (factor**attempt)
    return min(delay, max_delay)


@dataclass
class JobHealth:
    """Health status of an autonomous loop job."""

    job_name: str
    status: str = "healthy"  # healthy | degraded | failed | disabled
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_run_at: str = ""
    last_success_at: str = ""
    last_error: str = ""
    circuit_breaker_state: str = "closed"
    avg_duration_ms: float = 0.0
    run_count: int = 0

    def to_dict(self) -> dict:
        return {
            "job_name": self.job_name,
            "status": self.status,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "last_run_at": self.last_run_at,
            "last_success_at": self.last_success_at,
            "last_error": self.last_error,
            "circuit_breaker_state": self.circuit_breaker_state,
            "avg_duration_ms": round(self.avg_duration_ms, 1),
            "run_count": self.run_count,
        }


@dataclass
class LoopCycleReport:
    """Report for a single autonomous loop cycle."""

    cycle_id: str
    started_at: str
    completed_at: str = ""
    duration_ms: float = 0.0
    jobs_attempted: int = 0
    jobs_succeeded: int = 0
    jobs_failed: int = 0
    jobs_skipped: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)
    status: str = "running"  # running | completed | partial | failed

    def to_dict(self) -> dict:
        return {
            "cycle_id": self.cycle_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": round(self.duration_ms, 1),
            "jobs_attempted": self.jobs_attempted,
            "jobs_succeeded": self.jobs_succeeded,
            "jobs_failed": self.jobs_failed,
            "jobs_skipped": self.jobs_skipped,
            "errors": self.errors,
            "status": self.status,
        }


@dataclass
class SystemHealthReport:
    """Overall system health report."""

    job_health: list[JobHealth] = field(default_factory=list)
    overall_status: str = "healthy"
    active_circuit_breakers: int = 0
    total_cycles: int = 0
    recent_error_rate: float = 0.0
    uptime_pct: float = 100.0
    generated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "job_health": [j.to_dict() for j in self.job_health],
            "overall_status": self.overall_status,
            "active_circuit_breakers": self.active_circuit_breakers,
            "total_cycles": self.total_cycles,
            "recent_error_rate": round(self.recent_error_rate, 2),
            "uptime_pct": round(self.uptime_pct, 2),
            "generated_at": self.generated_at,
        }


class AutonomousOperations:
    """
    Manages autonomous loop health, circuit breakers, and self-healing.

    Provides production-grade resilience for the autonomous engine.
    """

    def __init__(self) -> None:
        self.circuit_breakers: dict[str, CircuitBreaker] = {}
        self.job_health: dict[str, JobHealth] = {}
        self.cycle_history: list[LoopCycleReport] = []

    def register_job(
        self,
        job_name: str,
        failure_threshold: int = 3,
        recovery_timeout_s: float = 60,
    ) -> None:
        """Register a job with a circuit breaker."""
        config = CircuitBreakerConfig(
            name=job_name,
            failure_threshold=failure_threshold,
            recovery_timeout_s=recovery_timeout_s,
        )
        self.circuit_breakers[job_name] = CircuitBreaker(config)
        self.job_health[job_name] = JobHealth(job_name=job_name)

    def should_run_job(self, job_name: str) -> bool:
        """Check if a job should run based on circuit breaker state."""
        cb = self.circuit_breakers.get(job_name)
        if not cb:
            return True
        return cb.is_available

    def record_job_success(
        self,
        job_name: str,
        duration_ms: float = 0.0,
    ) -> None:
        """Record a successful job execution."""
        cb = self.circuit_breakers.get(job_name)
        if cb:
            cb.record_success()

        health = self.job_health.get(job_name)
        if health:
            health.consecutive_failures = 0
            health.consecutive_successes += 1
            health.status = "healthy"
            health.last_run_at = datetime.now().isoformat()
            health.last_success_at = health.last_run_at
            health.run_count += 1
            health.circuit_breaker_state = cb.state.value if cb else "closed"
            # Update rolling average
            if health.run_count == 1:
                health.avg_duration_ms = duration_ms
            else:
                health.avg_duration_ms = health.avg_duration_ms * 0.8 + duration_ms * 0.2

    def record_job_failure(
        self,
        job_name: str,
        error: str,
    ) -> None:
        """Record a failed job execution."""
        cb = self.circuit_breakers.get(job_name)
        if cb:
            cb.record_failure()

        health = self.job_health.get(job_name)
        if health:
            health.consecutive_failures += 1
            health.consecutive_successes = 0
            health.last_run_at = datetime.now().isoformat()
            health.last_error = error
            health.run_count += 1
            health.circuit_breaker_state = cb.state.value if cb else "closed"

            if health.consecutive_failures >= 5:
                health.status = "failed"
            elif health.consecutive_failures >= 2:
                health.status = "degraded"

    def get_system_health(self) -> SystemHealthReport:
        """Get overall system health report."""
        jobs = list(self.job_health.values())
        active_cbs = sum(
            1 for cb in self.circuit_breakers.values() if cb.state != CircuitState.CLOSED
        )

        # Calculate overall status
        failed_count = sum(1 for j in jobs if j.status == "failed")
        degraded_count = sum(1 for j in jobs if j.status == "degraded")

        if failed_count > len(jobs) * 0.5:
            overall = "critical"
        elif failed_count > 0:
            overall = "degraded"
        elif degraded_count > 0:
            overall = "warning"
        else:
            overall = "healthy"

        # Recent error rate from cycle history
        recent = self.cycle_history[-10:] if self.cycle_history else []
        if recent:
            total_jobs = sum(c.jobs_attempted for c in recent)
            total_failed = sum(c.jobs_failed for c in recent)
            error_rate = total_failed / max(1, total_jobs)
        else:
            error_rate = 0.0

        return SystemHealthReport(
            job_health=jobs,
            overall_status=overall,
            active_circuit_breakers=active_cbs,
            total_cycles=len(self.cycle_history),
            recent_error_rate=error_rate,
            generated_at=datetime.now().isoformat(),
        )

    def start_cycle(self, cycle_id: str) -> LoopCycleReport:
        """Start a new autonomous loop cycle."""
        report = LoopCycleReport(
            cycle_id=cycle_id,
            started_at=datetime.now().isoformat(),
        )
        self.cycle_history.append(report)
        # Keep only last 100 cycles
        if len(self.cycle_history) > 100:
            self.cycle_history = self.cycle_history[-100:]
        return report

    def complete_cycle(self, report: LoopCycleReport) -> None:
        """Complete a cycle with final stats."""
        report.completed_at = datetime.now().isoformat()
        if report.jobs_failed == 0:
            report.status = "completed"
        elif report.jobs_succeeded > 0:
            report.status = "partial"
        else:
            report.status = "failed"
