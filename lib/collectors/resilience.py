"""
Resilience infrastructure for collectors.

Provides:
- RetryConfig: Configuration for retry behavior
- CircuitBreaker: Fail-fast pattern for cascading failures
- RateLimiter: Token bucket rate limiting
- retry_with_backoff: Decorator/function for exponential backoff with jitter
"""

import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar
import sqlite3

T = TypeVar("T")

logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    """Configuration for retry behavior with exponential backoff."""

    max_retries: int = 3
    base_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    exponential_base: float = 2.0


class CircuitBreakerState:
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if recovered


class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures.

    States:
    - CLOSED: Normal operation, all calls allowed
    - OPEN: Failing, calls rejected immediately
    - HALF_OPEN: Testing recovery, one call allowed
    """

    def __init__(self, failure_threshold: int = 5, cooldown_seconds: int = 300):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of consecutive failures before opening
            cooldown_seconds: Seconds to wait before attempting recovery
        """
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED
        self.last_failure_time: float | None = None

    def can_execute(self) -> bool:
        """
        Check if a call can be executed.

        Returns:
            True if call should be attempted, False if circuit is open
        """
        if self.state == CircuitBreakerState.CLOSED:
            return True

        if self.state == CircuitBreakerState.OPEN:
            # Check if cooldown expired
            if self.last_failure_time is not None:
                elapsed = time.time() - self.last_failure_time
                if elapsed >= self.cooldown_seconds:
                    self.state = CircuitBreakerState.HALF_OPEN
                    return True
            return False

        # HALF_OPEN - allow one attempt
        return True

    def record_success(self):
        """Record a successful call - reset to CLOSED."""
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED

    def record_failure(self):
        """Record a failed call - move toward OPEN."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN


class RateLimiter:
    """Token bucket rate limiter for per-collector rate limiting."""

    def __init__(self, requests_per_minute: int = 60):
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests allowed per minute
        """
        self.requests_per_minute = requests_per_minute
        self.tokens = float(requests_per_minute)
        self.last_update = time.time()
        self.max_tokens = float(requests_per_minute)

    def allow_request(self) -> bool:
        """
        Check if a request should be allowed.

        Uses token bucket algorithm. Refills at rate_per_minute tokens/minute.

        Returns:
            True if request allowed, False if rate limit exceeded
        """
        now = time.time()
        elapsed = now - self.last_update
        self.last_update = now

        # Refill tokens based on elapsed time
        refill_rate = self.requests_per_minute / 60.0  # tokens per second
        self.tokens = min(self.max_tokens, self.tokens + elapsed * refill_rate)

        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True

        return False

    def get_wait_time(self) -> float:
        """
        Get seconds to wait before next token available.

        Returns:
            Seconds to wait (0 if tokens available)
        """
        if self.tokens >= 1.0:
            return 0.0

        # tokens needed to reach 1.0, at refill_rate tokens/second
        refill_rate = self.requests_per_minute / 60.0
        return (1.0 - self.tokens) / refill_rate


def retry_with_backoff(
    func: Callable[[], T],
    config: RetryConfig,
    logger_: logging.Logger | None = None,
) -> T:
    """
    Execute a function with exponential backoff and jitter.

    Args:
        func: Callable to execute
        config: RetryConfig with max_retries, base_delay, max_delay, exponential_base
        logger_: Optional logger for retry attempts

    Returns:
        Result of successful function call

    Raises:
        Last exception if all retries exhausted
    """
    last_error: Exception | None = None

    for attempt in range(config.max_retries + 1):
        try:
            return func()
        except (sqlite3.Error, ValueError, OSError, KeyError) as e:
            last_error = e

            if attempt < config.max_retries:
                # Calculate delay with exponential backoff
                delay = min(
                    config.base_delay * (config.exponential_base**attempt),
                    config.max_delay,
                )
                # Add jitter (up to 10% of delay)
                jitter = random.uniform(0, delay * 0.1)  # noqa: S311
                actual_delay = delay + jitter

                if logger_:
                    logger_.warning(
                        f"Attempt {attempt + 1} failed: {e}. Retrying in {actual_delay:.1f}s"
                    )
                time.sleep(actual_delay)

    # All retries exhausted
    if logger_ and last_error:
        logger_.error(f"All {config.max_retries + 1} attempts failed")

    if last_error is not None:
        raise last_error
    raise RuntimeError("All retries exhausted with no captured exception")
