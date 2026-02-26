"""
In-memory rate limiter with sliding window algorithm.

Features:
- Thread-safe rate limiting by key (IP address or API key)
- Sliding window algorithm for precise rate control
- Configurable limits per role tier
- Automatic cleanup of expired windows
- RateLimitResult dataclass for structured responses
"""

import logging
import threading
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Default rate limits per minute by role
DEFAULT_RATE_LIMITS = {
    "admin": 500,  # 500 requests/minute for admins
    "operator": 200,  # 200 requests/minute for operators
    "viewer": 100,  # 100 requests/minute for viewers
    "authenticated": 100,  # 100 requests/minute for authenticated users
    "unauthenticated": 20,  # 20 requests/minute for unauthenticated users
}

# Window duration (1 minute)
WINDOW_DURATION = 60


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    remaining: int
    limit: int
    reset_at: datetime


class RateLimiter:
    """
    Thread-safe in-memory rate limiter using sliding window algorithm.

    Tracks requests per key with automatic expiration of old entries.
    Supports multiple rate tiers based on role.
    """

    def __init__(self, rate_limits: dict[str, int] | None = None):
        """
        Initialize the rate limiter.

        Args:
            rate_limits: Dict mapping role names to requests per minute.
                        Defaults to DEFAULT_RATE_LIMITS.
        """
        self.rate_limits = rate_limits or DEFAULT_RATE_LIMITS
        self.windows: dict[str, list[datetime]] = defaultdict(list)
        self.lock = threading.Lock()

    def check_rate_limit(
        self,
        key: str,
        role: str = "authenticated",
        current_time: datetime | None = None,
    ) -> RateLimitResult:
        """
        Check if a request from the given key is allowed.

        Args:
            key: Identifier (IP address, API key, user ID, etc.)
            role: User role for determining limit tier
            current_time: Current time (defaults to datetime.utcnow())

        Returns:
            RateLimitResult with allowed status, remaining requests, and reset time
        """
        if current_time is None:
            current_time = datetime.utcnow()

        # Get limit for role, fallback to authenticated tier if role not found
        if role in self.rate_limits:
            limit = self.rate_limits[role]
        else:
            # Fallback: use authenticated tier if it exists, otherwise get first default
            limit = self.rate_limits.get(
                "authenticated", list(self.rate_limits.values())[0] if self.rate_limits else 100
            )

        with self.lock:
            # Clean up expired entries (older than 1 minute)
            cutoff_time = current_time - timedelta(seconds=WINDOW_DURATION)
            self.windows[key] = [ts for ts in self.windows[key] if ts > cutoff_time]

            # Check if we're under the limit
            request_count = len(self.windows[key])

            if request_count < limit:
                # Record this request
                self.windows[key].append(current_time)
                remaining = limit - request_count - 1
                reset_at = current_time + timedelta(seconds=WINDOW_DURATION)

                return RateLimitResult(
                    allowed=True,
                    remaining=remaining,
                    limit=limit,
                    reset_at=reset_at,
                )
            else:
                # Over the limit
                oldest_request = self.windows[key][0]
                reset_at = oldest_request + timedelta(seconds=WINDOW_DURATION)

                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    limit=limit,
                    reset_at=reset_at,
                )

    def reset_key(self, key: str) -> None:
        """
        Reset rate limit for a specific key (clear all requests).

        Args:
            key: Identifier to reset
        """
        with self.lock:
            if key in self.windows:
                del self.windows[key]

    def cleanup_expired(self, current_time: datetime | None = None) -> None:
        """
        Clean up all expired entries across all keys.

        Args:
            current_time: Current time (defaults to datetime.utcnow())
        """
        if current_time is None:
            current_time = datetime.utcnow()

        cutoff_time = current_time - timedelta(seconds=WINDOW_DURATION)

        with self.lock:
            # Remove entries that have no requests within the window
            keys_to_delete = []
            for key, timestamps in self.windows.items():
                self.windows[key] = [ts for ts in timestamps if ts > cutoff_time]
                if not self.windows[key]:
                    keys_to_delete.append(key)

            for key in keys_to_delete:
                del self.windows[key]

    def get_stats(self, key: str, current_time: datetime | None = None) -> dict:
        """
        Get current stats for a key (for debugging/testing).

        Args:
            key: Identifier to check
            current_time: Current time (defaults to datetime.utcnow())

        Returns:
            Dict with request_count and timestamps
        """
        if current_time is None:
            current_time = datetime.utcnow()

        cutoff_time = current_time - timedelta(seconds=WINDOW_DURATION)

        with self.lock:
            valid_timestamps = [ts for ts in self.windows.get(key, []) if ts > cutoff_time]

            return {
                "request_count": len(valid_timestamps),
                "timestamps": valid_timestamps,
            }
