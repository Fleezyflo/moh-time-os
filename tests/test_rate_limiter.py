"""
Test suite for rate limiter with sliding window algorithm.

Tests validate:
- Sliding window tracks requests correctly
- Rate limit enforcement
- Different role-based tiers
- Cleanup of expired entries
- Thread safety
"""

import threading
import time
from datetime import datetime, timedelta

import pytest

from lib.security.rate_limiter import DEFAULT_RATE_LIMITS, RateLimiter, RateLimitResult


class TestRateLimiterBasics:
    """Tests for basic rate limiter functionality."""

    def test_rate_limiter_initialization(self):
        """Test that rate limiter initializes with default limits."""
        limiter = RateLimiter()
        assert limiter.rate_limits == DEFAULT_RATE_LIMITS
        assert len(limiter.windows) == 0

    def test_rate_limiter_custom_limits(self):
        """Test that custom limits are used when provided."""
        custom_limits = {"admin": 1000, "viewer": 50}
        limiter = RateLimiter(rate_limits=custom_limits)
        assert limiter.rate_limits == custom_limits

    def test_first_request_allowed(self):
        """Test that first request is always allowed."""
        limiter = RateLimiter()
        base_time = datetime.utcnow()

        result = limiter.check_rate_limit("test-key", role="authenticated", current_time=base_time)

        assert result.allowed is True
        assert result.remaining == 99  # 100 limit - 1 used
        assert result.limit == 100
        assert result.reset_at == base_time + timedelta(seconds=60)

    def test_result_dataclass(self):
        """Test that RateLimitResult is a proper dataclass."""
        base_time = datetime.utcnow()
        result = RateLimitResult(
            allowed=True,
            remaining=50,
            limit=100,
            reset_at=base_time,
        )

        assert result.allowed is True
        assert result.remaining == 50
        assert result.limit == 100
        assert result.reset_at == base_time


class TestSlidingWindow:
    """Tests for sliding window algorithm."""

    def test_requests_tracked_in_window(self):
        """Test that requests are tracked correctly."""
        limiter = RateLimiter()
        base_time = datetime.utcnow()

        # Make 5 requests
        for i in range(5):
            result = limiter.check_rate_limit(
                "test-key",
                role="authenticated",
                current_time=base_time + timedelta(seconds=i),
            )
            assert result.allowed is True
            # After i-th request, remaining should be (100 - (i + 1))
            assert result.remaining == 100 - (i + 1)

        # Verify internal state
        stats = limiter.get_stats("test-key", current_time=base_time + timedelta(seconds=5))
        assert stats["request_count"] == 5

    def test_requests_outside_window_ignored(self):
        """Test that requests outside the window are ignored."""
        limiter = RateLimiter()
        base_time = datetime.utcnow()

        # Make request at time 0
        limiter.check_rate_limit("test-key", role="authenticated", current_time=base_time)

        # Check at time 0 - should count 1 request
        stats = limiter.get_stats("test-key", current_time=base_time)
        assert stats["request_count"] == 1

        # Check at time 70 (70 seconds later, past the 60-second window)
        # The first request should be expired
        stats = limiter.get_stats("test-key", current_time=base_time + timedelta(seconds=70))
        assert stats["request_count"] == 0

    def test_window_boundary_behavior(self):
        """Test behavior at window boundaries."""
        limiter = RateLimiter()
        base_time = datetime.utcnow()

        # Request at t=0
        limiter.check_rate_limit("test-key", role="authenticated", current_time=base_time)

        # Request at t=59 (still in window)
        limiter.check_rate_limit(
            "test-key",
            role="authenticated",
            current_time=base_time + timedelta(seconds=59),
        )
        stats = limiter.get_stats("test-key", current_time=base_time + timedelta(seconds=59))
        assert stats["request_count"] == 2

        # Request at t=60.1 (just past the window for first request)
        # First request expires, second still valid
        limiter.check_rate_limit(
            "test-key",
            role="authenticated",
            current_time=base_time + timedelta(seconds=60.1),
        )
        stats = limiter.get_stats("test-key", current_time=base_time + timedelta(seconds=60.1))
        assert stats["request_count"] == 2


class TestRateLimitEnforcement:
    """Tests for rate limit enforcement."""

    def test_limit_exceeded_returns_denied(self):
        """Test that exceeding limit returns denied."""
        custom_limits = {"test": 5}
        limiter = RateLimiter(rate_limits=custom_limits)
        base_time = datetime.utcnow()

        # Fill up the limit
        for i in range(5):
            result = limiter.check_rate_limit(
                "test-key",
                role="test",
                current_time=base_time + timedelta(seconds=i * 0.1),
            )
            assert result.allowed is True

        # Try to exceed it
        result = limiter.check_rate_limit(
            "test-key",
            role="test",
            current_time=base_time + timedelta(seconds=1),
        )
        assert result.allowed is False
        assert result.remaining == 0
        assert result.limit == 5

    def test_denied_request_has_reset_time(self):
        """Test that denied requests include reset time."""
        custom_limits = {"test": 2}
        limiter = RateLimiter(rate_limits=custom_limits)
        base_time = datetime.utcnow()

        # Fill the limit
        for i in range(2):
            limiter.check_rate_limit(
                "test-key",
                role="test",
                current_time=base_time + timedelta(seconds=i * 0.1),
            )

        # Exceed it
        result = limiter.check_rate_limit(
            "test-key",
            role="test",
            current_time=base_time + timedelta(seconds=1),
        )

        assert result.allowed is False
        # Reset should be 60 seconds after the oldest request
        assert result.reset_at > base_time
        assert result.reset_at <= base_time + timedelta(seconds=60.1)

    def test_different_keys_independent(self):
        """Test that different keys have independent limits."""
        custom_limits = {"test": 2}
        limiter = RateLimiter(rate_limits=custom_limits)
        base_time = datetime.utcnow()

        # Fill limit for key1
        for i in range(2):
            limiter.check_rate_limit(
                "key1",
                role="test",
                current_time=base_time + timedelta(seconds=i * 0.1),
            )

        # key1 should be limited
        result = limiter.check_rate_limit(
            "key1",
            role="test",
            current_time=base_time + timedelta(seconds=1),
        )
        assert result.allowed is False

        # key2 should still be allowed
        result = limiter.check_rate_limit(
            "key2",
            role="test",
            current_time=base_time + timedelta(seconds=1),
        )
        assert result.allowed is True

    def test_many_requests_up_to_limit(self):
        """Test that all requests up to limit are allowed."""
        custom_limits = {"test": 100}
        limiter = RateLimiter(rate_limits=custom_limits)
        base_time = datetime.utcnow()

        # Make 100 requests
        for i in range(100):
            result = limiter.check_rate_limit(
                "test-key",
                role="test",
                current_time=base_time + timedelta(seconds=0.001 * i),
            )
            assert result.allowed is True, f"Request {i} should be allowed"

        # 101st should fail
        result = limiter.check_rate_limit(
            "test-key",
            role="test",
            current_time=base_time + timedelta(seconds=0.2),
        )
        assert result.allowed is False


class TestRoleTiers:
    """Tests for different role-based rate limits."""

    def test_admin_tier_limit(self):
        """Test admin role has higher limit (500/min)."""
        limiter = RateLimiter()
        base_time = datetime.utcnow()

        result = limiter.check_rate_limit("admin-key", role="admin", current_time=base_time)
        assert result.limit == 500
        assert result.remaining == 499

    def test_operator_tier_limit(self):
        """Test operator role limit (200/min)."""
        limiter = RateLimiter()
        base_time = datetime.utcnow()

        result = limiter.check_rate_limit("op-key", role="operator", current_time=base_time)
        assert result.limit == 200
        assert result.remaining == 199

    def test_viewer_tier_limit(self):
        """Test viewer role limit (100/min)."""
        limiter = RateLimiter()
        base_time = datetime.utcnow()

        result = limiter.check_rate_limit("viewer-key", role="viewer", current_time=base_time)
        assert result.limit == 100
        assert result.remaining == 99

    def test_authenticated_tier_limit(self):
        """Test authenticated user limit (100/min)."""
        limiter = RateLimiter()
        base_time = datetime.utcnow()

        result = limiter.check_rate_limit("user-key", role="authenticated", current_time=base_time)
        assert result.limit == 100
        assert result.remaining == 99

    def test_unauthenticated_tier_limit(self):
        """Test unauthenticated user limit (20/min)."""
        limiter = RateLimiter()
        base_time = datetime.utcnow()

        result = limiter.check_rate_limit(
            "guest-key", role="unauthenticated", current_time=base_time
        )
        assert result.limit == 20
        assert result.remaining == 19

    def test_unknown_role_defaults_to_authenticated(self):
        """Test that unknown roles default to authenticated tier."""
        limiter = RateLimiter()
        base_time = datetime.utcnow()

        result = limiter.check_rate_limit("key", role="unknown_role", current_time=base_time)
        assert result.limit == 100
        assert result.remaining == 99

    def test_different_tiers_independent(self):
        """Test that different tiers have independent limits."""
        custom_limits = {"admin": 5, "viewer": 2}
        limiter = RateLimiter(rate_limits=custom_limits)
        base_time = datetime.utcnow()

        # Fill viewer limit
        for i in range(2):
            limiter.check_rate_limit(
                "viewer-key",
                role="viewer",
                current_time=base_time + timedelta(seconds=i * 0.1),
            )

        # Viewer should be limited
        result = limiter.check_rate_limit(
            "viewer-key",
            role="viewer",
            current_time=base_time + timedelta(seconds=1),
        )
        assert result.allowed is False

        # Admin should still have requests available
        result = limiter.check_rate_limit(
            "admin-key",
            role="admin",
            current_time=base_time + timedelta(seconds=1),
        )
        assert result.allowed is True


class TestCleanup:
    """Tests for cleanup of expired entries."""

    def test_cleanup_expired_entries(self):
        """Test that cleanup removes expired entries."""
        limiter = RateLimiter()
        base_time = datetime.utcnow()

        # Make a request
        limiter.check_rate_limit("test-key", role="authenticated", current_time=base_time)

        # Verify it's tracked
        assert "test-key" in limiter.windows

        # Cleanup 61 seconds later
        limiter.cleanup_expired(current_time=base_time + timedelta(seconds=61))

        # Key should be removed since all requests expired
        assert "test-key" not in limiter.windows

    def test_cleanup_preserves_recent_requests(self):
        """Test that cleanup preserves recent requests."""
        limiter = RateLimiter()
        base_time = datetime.utcnow()

        # Make requests at different times
        limiter.check_rate_limit("test-key", role="authenticated", current_time=base_time)
        limiter.check_rate_limit(
            "test-key",
            role="authenticated",
            current_time=base_time + timedelta(seconds=50),
        )

        # Cleanup 61 seconds after first request
        # First request should be gone, second should remain
        limiter.cleanup_expired(current_time=base_time + timedelta(seconds=61))

        stats = limiter.get_stats("test-key", current_time=base_time + timedelta(seconds=61))
        assert stats["request_count"] == 1

    def test_automatic_cleanup_in_check_rate_limit(self):
        """Test that check_rate_limit automatically cleans expired entries."""
        limiter = RateLimiter()
        base_time = datetime.utcnow()

        # Make a request
        limiter.check_rate_limit("test-key", role="authenticated", current_time=base_time)

        # Check 61 seconds later - should auto-cleanup
        limiter.check_rate_limit(
            "test-key",
            role="authenticated",
            current_time=base_time + timedelta(seconds=61),
        )

        # The old request should be cleaned up
        stats = limiter.get_stats("test-key", current_time=base_time + timedelta(seconds=61))
        assert stats["request_count"] == 1

    def test_reset_key(self):
        """Test that reset_key clears a key's history."""
        limiter = RateLimiter()
        base_time = datetime.utcnow()

        # Make multiple requests
        for i in range(5):
            limiter.check_rate_limit(
                "test-key",
                role="authenticated",
                current_time=base_time + timedelta(seconds=i * 0.1),
            )

        # Verify they're tracked
        stats = limiter.get_stats("test-key", current_time=base_time)
        assert stats["request_count"] == 5

        # Reset the key
        limiter.reset_key("test-key")

        # Should be gone
        stats = limiter.get_stats("test-key", current_time=base_time)
        assert stats["request_count"] == 0

    def test_reset_key_allows_new_requests(self):
        """Test that reset key allows requests immediately after."""
        custom_limits = {"test": 2}
        limiter = RateLimiter(rate_limits=custom_limits)
        base_time = datetime.utcnow()

        # Fill the limit
        for i in range(2):
            limiter.check_rate_limit(
                "test-key",
                role="test",
                current_time=base_time + timedelta(seconds=i * 0.1),
            )

        # Should be limited
        result = limiter.check_rate_limit(
            "test-key",
            role="test",
            current_time=base_time + timedelta(seconds=1),
        )
        assert result.allowed is False

        # Reset
        limiter.reset_key("test-key")

        # Should be allowed again
        result = limiter.check_rate_limit(
            "test-key",
            role="test",
            current_time=base_time + timedelta(seconds=1),
        )
        assert result.allowed is True


class TestThreadSafety:
    """Tests for thread-safe behavior."""

    def test_concurrent_requests_same_key(self):
        """Test that concurrent requests to same key are handled safely."""
        custom_limits = {"test": 100}
        limiter = RateLimiter(rate_limits=custom_limits)
        base_time = datetime.utcnow()
        results = []

        def make_request(key):
            result = limiter.check_rate_limit(key, role="test", current_time=base_time)
            results.append(result)

        # Create 50 threads all requesting same key
        threads = []
        for _i in range(50):
            thread = threading.Thread(target=make_request, args=("concurrent-key",))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Should have 50 results
        assert len(results) == 50

        # 50 should be allowed, rest blocked (since limit is 100)
        allowed_count = sum(1 for r in results if r.allowed)
        assert allowed_count == 50

    def test_concurrent_requests_different_keys(self):
        """Test concurrent requests to different keys."""
        custom_limits = {"test": 10}
        limiter = RateLimiter(rate_limits=custom_limits)
        base_time = datetime.utcnow()
        results = []

        def make_request(key_num):
            result = limiter.check_rate_limit(f"key-{key_num}", role="test", current_time=base_time)
            results.append(result)

        # Create 30 threads with different keys
        threads = []
        for i in range(30):
            thread = threading.Thread(target=make_request, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # All should be allowed since each key is independent
        assert len(results) == 30
        assert all(r.allowed for r in results)

    def test_concurrent_cleanup_and_checks(self):
        """Test that cleanup and checks work safely together."""
        limiter = RateLimiter()
        base_time = datetime.utcnow()

        def make_requests(key_prefix, count):
            for i in range(count):
                limiter.check_rate_limit(
                    f"{key_prefix}-{i}",
                    role="authenticated",
                    current_time=base_time + timedelta(seconds=i * 0.01),
                )

        # Make requests in one thread
        thread1 = threading.Thread(target=make_requests, args=("batch1", 20))
        # Cleanup in another thread
        thread2 = threading.Thread(
            target=lambda: limiter.cleanup_expired(current_time=base_time + timedelta(seconds=100))
        )

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        # Should complete without errors
        assert True


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_zero_remaining_shows_correct_reset_time(self):
        """Test that denied requests show accurate reset time."""
        custom_limits = {"test": 1}
        limiter = RateLimiter(rate_limits=custom_limits)
        base_time = datetime.utcnow()

        # Fill limit at t=10
        result = limiter.check_rate_limit(
            "key", role="test", current_time=base_time + timedelta(seconds=10)
        )
        assert result.allowed is True

        # Try to exceed at t=20 (still within window)
        result = limiter.check_rate_limit(
            "key", role="test", current_time=base_time + timedelta(seconds=20)
        )
        assert result.allowed is False

        # Reset time should be ~70 (10 + 60)
        expected_reset = base_time + timedelta(seconds=70)
        assert abs((result.reset_at - expected_reset).total_seconds()) < 1

    def test_empty_key_handling(self):
        """Test that empty string key is handled."""
        limiter = RateLimiter()
        base_time = datetime.utcnow()

        # Should not crash with empty key
        result = limiter.check_rate_limit("", role="authenticated", current_time=base_time)
        assert result.allowed is True

    def test_very_long_key(self):
        """Test that very long keys work."""
        limiter = RateLimiter()
        base_time = datetime.utcnow()

        long_key = "key" * 1000

        result = limiter.check_rate_limit(long_key, role="authenticated", current_time=base_time)
        assert result.allowed is True

    def test_special_characters_in_key(self):
        """Test that special characters in keys work."""
        limiter = RateLimiter()
        base_time = datetime.utcnow()

        special_key = "192.168.1.1:8080/api/v1?query=test&token=abc123"

        result = limiter.check_rate_limit(special_key, role="authenticated", current_time=base_time)
        assert result.allowed is True

    def test_millisecond_precision(self):
        """Test that millisecond-precision timing works."""
        custom_limits = {"test": 100}
        limiter = RateLimiter(rate_limits=custom_limits)
        base_time = datetime.utcnow()

        # Make requests with millisecond spacing
        for i in range(10):
            result = limiter.check_rate_limit(
                "key",
                role="test",
                current_time=base_time + timedelta(milliseconds=i * 10),
            )
            assert result.allowed is True

        stats = limiter.get_stats("key", current_time=base_time)
        assert stats["request_count"] == 10
