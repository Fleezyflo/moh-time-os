"""
Tests for collector resilience infrastructure.

Covers:
- RetryConfig defaults and customization
- CircuitBreaker state transitions
- RateLimiter token bucket algorithm
- retry_with_backoff with exponential backoff + jitter
- BaseCollector integration with resilience
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from lib.collectors.base import BaseCollector
from lib.collectors.resilience import (
    CircuitBreaker,
    CircuitBreakerState,
    RateLimiter,
    RetryConfig,
    retry_with_backoff,
)
from lib.state_store import StateStore

# =============================================================================
# RETRYCONFIG TESTS
# =============================================================================


class TestRetryConfig:
    """Tests for RetryConfig dataclass."""

    def test_defaults(self):
        """RetryConfig should have sensible defaults."""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0

    def test_custom_values(self):
        """RetryConfig should accept custom values."""
        config = RetryConfig(
            max_retries=5,
            base_delay=0.5,
            max_delay=30.0,
            exponential_base=1.5,
        )
        assert config.max_retries == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 30.0
        assert config.exponential_base == 1.5


# =============================================================================
# CIRCUITBREAKER TESTS
# =============================================================================


class TestCircuitBreaker:
    """Tests for CircuitBreaker pattern."""

    def test_initial_state_closed(self):
        """Circuit breaker should start in CLOSED state."""
        cb = CircuitBreaker()
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.can_execute() is True

    def test_single_failure_allows_execution(self):
        """Single failure should not open circuit."""
        cb = CircuitBreaker(failure_threshold=5)
        cb.record_failure()
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.can_execute() is True
        assert cb.failure_count == 1

    def test_threshold_failures_open_circuit(self):
        """Reaching failure threshold should OPEN circuit."""
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN
        assert cb.can_execute() is False

    def test_open_circuit_rejects_calls(self):
        """OPEN circuit should reject calls."""
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN

        # Try to execute while open
        assert cb.can_execute() is False
        assert cb.can_execute() is False  # Still rejecting

    def test_open_circuit_transitions_to_half_open_after_cooldown(self):
        """OPEN circuit should become HALF_OPEN after cooldown."""
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.1)
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN

        # Wait for cooldown
        time.sleep(0.15)

        # Should transition to HALF_OPEN on next check
        assert cb.can_execute() is True
        assert cb.state == CircuitBreakerState.HALF_OPEN

    def test_half_open_allows_single_attempt(self):
        """HALF_OPEN should allow one attempt."""
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.1)
        cb.record_failure()
        time.sleep(0.15)
        cb.can_execute()  # Transition to HALF_OPEN

        assert cb.state == CircuitBreakerState.HALF_OPEN
        assert cb.can_execute() is True

    def test_success_in_half_open_closes_circuit(self):
        """Success in HALF_OPEN should reset to CLOSED."""
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.1)
        cb.record_failure()
        time.sleep(0.15)
        cb.can_execute()  # Transition to HALF_OPEN

        # Record success
        cb.record_success()
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0
        assert cb.can_execute() is True

    def test_failure_in_half_open_reopens_circuit(self):
        """Failure in HALF_OPEN should reopen circuit."""
        cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=0.1)
        cb.record_failure()
        cb.record_failure()  # Now at threshold
        assert cb.state == CircuitBreakerState.OPEN

        time.sleep(0.15)
        cb.can_execute()  # Transition to HALF_OPEN

        # Record another failure
        cb.record_failure()
        assert cb.failure_count == 3
        assert cb.state == CircuitBreakerState.OPEN


# =============================================================================
# RATELIMITER TESTS
# =============================================================================


class TestRateLimiter:
    """Tests for RateLimiter token bucket."""

    def test_initial_tokens_available(self):
        """RateLimiter should start with full tokens."""
        rl = RateLimiter(requests_per_minute=60)
        assert rl.allow_request() is True
        assert rl.tokens == 59.0  # One consumed

    def test_tokens_consumed_on_request(self):
        """Each request should consume one token."""
        rl = RateLimiter(requests_per_minute=5)
        initial_tokens = rl.tokens
        for _ in range(5):
            assert rl.allow_request() is True
        # After 5 requests, tokens should be near 0 (allowing for small refills)
        assert rl.tokens < initial_tokens

    def test_rate_limit_exceeded(self):
        """Requests should be denied when tokens exhausted."""
        rl = RateLimiter(requests_per_minute=2)
        assert rl.allow_request() is True
        assert rl.allow_request() is True
        assert rl.allow_request() is False  # No more tokens

    def test_tokens_refill_over_time(self):
        """Tokens should refill at configured rate."""
        rl = RateLimiter(requests_per_minute=60)  # 1 token/second
        assert rl.allow_request() is True  # Consume 1 token

        # Consume more tokens to ensure we're at 0
        while rl.tokens >= 1.0:
            rl.allow_request()

        # Now tokens should be < 1
        assert rl.tokens < 1.0

        # Wait for refill
        time.sleep(1.1)  # Wait enough to get a token

        # Should now be allowed
        assert rl.allow_request() is True

    def test_get_wait_time_when_tokens_available(self):
        """get_wait_time should return 0 when tokens available."""
        rl = RateLimiter(requests_per_minute=60)
        wait = rl.get_wait_time()
        assert wait == 0.0

    def test_get_wait_time_when_empty(self):
        """get_wait_time should return positive value when tokens exhausted."""
        rl = RateLimiter(requests_per_minute=2)
        rl.allow_request()
        rl.allow_request()
        wait = rl.get_wait_time()
        assert wait > 0.0


# =============================================================================
# RETRY_WITH_BACKOFF TESTS
# =============================================================================


class TestRetryWithBackoff:
    """Tests for retry_with_backoff function."""

    def test_succeeds_on_first_try(self):
        """Should return immediately on success."""
        func = MagicMock(return_value="success")
        config = RetryConfig()

        result = retry_with_backoff(func, config)
        assert result == "success"
        assert func.call_count == 1

    def test_succeeds_after_failures(self):
        """Should retry on failure and eventually succeed."""
        func = MagicMock(side_effect=[ValueError("fail"), ValueError("fail"), "success"])
        config = RetryConfig(max_retries=3, base_delay=0.01)

        result = retry_with_backoff(func, config)
        assert result == "success"
        assert func.call_count == 3

    def test_raises_after_exhausting_retries(self):
        """Should raise after max retries exceeded."""
        func = MagicMock(side_effect=ValueError("always fails"))
        config = RetryConfig(max_retries=2, base_delay=0.01)

        with pytest.raises(ValueError, match="always fails"):
            retry_with_backoff(func, config)

        assert func.call_count == 3  # 1 initial + 2 retries

    @patch("time.sleep")
    def test_exponential_backoff_delays(self, mock_sleep):
        """Should use exponential backoff between retries."""
        func = MagicMock(side_effect=[ValueError("fail"), ValueError("fail"), "ok"])
        config = RetryConfig(max_retries=2, base_delay=1.0, max_delay=60.0, exponential_base=2.0)

        retry_with_backoff(func, config)

        # Should sleep twice: after first attempt and second
        assert mock_sleep.call_count == 2

        # Check delays (with jitter, so check ranges)
        call_args = [call[0][0] for call in mock_sleep.call_args_list]
        # First sleep: base_delay * 2^0 = 1.0 + jitter (0-0.1)
        assert 1.0 <= call_args[0] <= 1.1
        # Second sleep: base_delay * 2^1 = 2.0 + jitter (0-0.2)
        assert 2.0 <= call_args[1] <= 2.2

    @patch("time.sleep")
    def test_max_delay_cap(self, mock_sleep):
        """Should not exceed max_delay."""
        func = MagicMock(side_effect=ValueError("fail"))
        config = RetryConfig(
            max_retries=10,  # Many retries
            base_delay=1.0,
            max_delay=5.0,  # Cap at 5 seconds
            exponential_base=2.0,
        )

        with pytest.raises(ValueError):
            retry_with_backoff(func, config)

        # All delays should be <= max_delay + jitter
        call_args = [call[0][0] for call in mock_sleep.call_args_list]
        for delay in call_args:
            assert delay <= 5.5  # 5.0 + 10% jitter

    def test_logging_on_retries(self):
        """Should log retry attempts if logger provided."""
        func = MagicMock(side_effect=[ValueError("fail"), "ok"])
        config = RetryConfig(max_retries=1, base_delay=0.01)
        mock_logger = MagicMock()

        retry_with_backoff(func, config, mock_logger)

        # Should log warning about retry
        assert mock_logger.warning.called


# =============================================================================
# BASECOLLECTOR INTEGRATION TESTS
# =============================================================================


class MockCollector(BaseCollector):
    """Test collector implementation."""

    @property
    def source_name(self) -> str:
        return "mock_source"

    @property
    def target_table(self) -> str:
        return "test_data"

    def collect(self):
        """Override in tests."""
        return {"items": []}

    def transform(self, raw_data):
        """Override in tests."""
        return []


class TestBaseCollectorResilience:
    """Tests for BaseCollector with resilience infrastructure."""

    @pytest.fixture
    def mock_store(self):
        """Create a mock StateStore."""
        store = MagicMock(spec=StateStore)
        store.insert_many.return_value = 0
        return store

    def test_collector_has_retry_config(self, mock_store):
        """BaseCollector should have retry_config."""
        config = {"max_retries": 5}
        collector = MockCollector(config, mock_store)

        assert collector.retry_config is not None
        assert collector.retry_config.max_retries == 5

    def test_collector_has_circuit_breaker(self, mock_store):
        """BaseCollector should have circuit_breaker."""
        config = {"failure_threshold": 3}
        collector = MockCollector(config, mock_store)

        assert collector.circuit_breaker is not None
        assert collector.circuit_breaker.failure_threshold == 3

    def test_collector_has_metrics(self, mock_store):
        """BaseCollector should track metrics."""
        collector = MockCollector({}, mock_store)
        assert "retries" in collector.metrics
        assert "circuit_opens" in collector.metrics
        assert "partial_failures" in collector.metrics

    def test_sync_with_circuit_breaker_open(self, mock_store):
        """Sync should fail if circuit breaker is open."""
        collector = MockCollector({}, mock_store)
        collector.circuit_breaker.state = CircuitBreakerState.OPEN
        collector.circuit_breaker.last_failure_time = time.time()

        result = collector.sync()

        assert result["success"] is False
        assert "circuit breaker" in result["error"].lower()
        assert collector.metrics["circuit_opens"] == 1

    def test_sync_retries_on_collect_failure(self, mock_store):
        """Sync should retry if collect fails."""
        collector = MockCollector({}, mock_store)
        call_count = [0]

        def failing_collect():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ValueError("transient error")
            return {"items": [{"id": 1, "name": "item"}]}

        collector.collect = failing_collect
        collector.transform = lambda x: x["items"]
        mock_store.insert_many.return_value = 1

        result = collector.sync()

        assert result["success"] is True
        assert call_count[0] == 2  # Failed once, then succeeded

    def test_sync_circuit_opens_after_failures(self, mock_store):
        """Sync should open circuit after threshold failures."""
        collector = MockCollector({"failure_threshold": 2, "max_retries": 0}, mock_store)
        collector.collect = MagicMock(side_effect=ValueError("persistent error"))

        # First sync fails (1 failure recorded)
        result1 = collector.sync()
        assert result1["success"] is False
        assert collector.circuit_breaker.failure_count == 1
        assert collector.circuit_breaker.state == CircuitBreakerState.CLOSED

        # Second sync fails (2 failures recorded, threshold reached, circuit opens)
        result2 = collector.sync()
        assert result2["success"] is False
        assert collector.circuit_breaker.state == CircuitBreakerState.OPEN

        # Third sync should be rejected by circuit breaker
        result3 = collector.sync()
        assert result3["success"] is False
        assert "circuit breaker" in result3["error"].lower()

    def test_sync_records_success_and_resets_circuit(self, mock_store):
        """Successful sync should reset circuit breaker."""
        collector = MockCollector({"failure_threshold": 5}, mock_store)
        collector.circuit_breaker.record_failure()
        collector.circuit_breaker.record_failure()
        assert collector.circuit_breaker.failure_count == 2

        # Mock successful sync
        collector.collect = MagicMock(return_value={"items": []})
        collector.transform = MagicMock(return_value=[])
        mock_store.insert_many.return_value = 0

        result = collector.sync()

        assert result["success"] is True
        assert collector.circuit_breaker.failure_count == 0
        assert collector.circuit_breaker.state == CircuitBreakerState.CLOSED

    def test_sync_with_partial_failure_stores_successful_items(self, mock_store):
        """Sync should store successful items even if transform fails."""
        collector = MockCollector({}, mock_store)

        # Collect succeeds
        collector.collect = MagicMock(return_value={"items": [{"id": 1}, {"id": 2}, {"id": 3}]})

        # Transform fails
        collector.transform = MagicMock(side_effect=ValueError("transform error"))
        mock_store.insert_many.return_value = 0

        result = collector.sync()

        # Sync should still complete (partial success)
        assert result["success"] is True
        assert collector.metrics["partial_failures"] == 1
        # Should attempt to store empty list
        mock_store.insert_many.assert_called()

    def test_sync_uses_configured_retry_settings(self, mock_store):
        """Sync should use custom retry config from init."""
        config = {
            "max_retries": 5,
            "base_delay": 0.5,
            "max_delay": 30.0,
            "exponential_base": 1.5,
        }
        collector = MockCollector(config, mock_store)

        assert collector.retry_config.max_retries == 5
        assert collector.retry_config.base_delay == 0.5
        assert collector.retry_config.max_delay == 30.0
        assert collector.retry_config.exponential_base == 1.5

    def test_backward_compatibility_no_resilience_config(self, mock_store):
        """Collector should work with empty config (backward compatible)."""
        collector = MockCollector({}, mock_store)

        # Should have default resilience config
        assert collector.retry_config is not None
        assert collector.circuit_breaker is not None
        assert collector.metrics is not None

        # Should use defaults
        assert collector.retry_config.max_retries == 3
        assert collector.circuit_breaker.failure_threshold == 5
