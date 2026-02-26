"""
In-memory cache manager with TTL support, invalidation patterns, and LRU eviction.

Features:
- TTL-based entry expiration with lazy cleanup
- Glob pattern-based key invalidation
- Thread-safe operations with RLock
- LRU eviction when max size reached
- Namespace support (e.g., "client:123", "intelligence:portfolio")
- Hit/miss statistics tracking
"""

import fnmatch
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CacheStats:
    """Cache statistics."""

    hits: int = 0
    misses: int = 0
    size: int = 0
    hit_rate: float = 0.0
    oldest_entry_age: float | None = None

    def to_dict(self) -> dict:
        """Convert to dict."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "size": self.size,
            "hit_rate": self.hit_rate,
            "oldest_entry_age": self.oldest_entry_age,
        }


class CacheManager:
    """Thread-safe in-memory cache with TTL, LRU eviction, and pattern invalidation."""

    def __init__(self, max_size: int = 10000, default_ttl: int = 300):
        """
        Initialize cache manager.

        Args:
            max_size: Maximum number of entries before LRU eviction. Defaults to 10000.
            default_ttl: Default TTL in seconds. Defaults to 300 (5 minutes).
        """
        self._cache: dict[
            str, tuple[Any, float, float]
        ] = {}  # key -> (value, expiry_time, access_time)
        self._lock = threading.RLock()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        """
        Get value from cache.

        Performs lazy cleanup of expired entries. Returns None if key not found
        or entry has expired.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            value, expiry_time, _access_time = self._cache[key]

            # Check if expired
            if time.time() >= expiry_time:
                del self._cache[key]
                self._misses += 1
                return None

            # Update access time for LRU
            self._cache[key] = (value, expiry_time, time.time())
            self._hits += 1
            return value

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """
        Set value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: TTL in seconds. If None, uses default_ttl.
        """
        if ttl_seconds is None:
            ttl_seconds = self._default_ttl

        with self._lock:
            now = time.time()
            expiry_time = now + ttl_seconds

            # Set the value
            self._cache[key] = (value, expiry_time, now)

            # Evict LRU entry if cache is full
            if len(self._cache) > self._max_size:
                self._evict_lru()

    def delete(self, key: str) -> None:
        """
        Delete specific key from cache.

        Args:
            key: Cache key to delete
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching a glob pattern.

        Examples:
            - "client:*" matches "client:123", "client:456"
            - "intelligence:portfolio:*" matches "intelligence:portfolio:overview"
            - "*:cache" matches "user:cache", "data:cache"

        Args:
            pattern: Glob pattern to match

        Returns:
            Number of keys invalidated
        """
        with self._lock:
            keys_to_delete = [key for key in self._cache.keys() if fnmatch.fnmatch(key, pattern)]

            for key in keys_to_delete:
                del self._cache[key]

            return len(keys_to_delete)

    def clear(self) -> None:
        """Clear entire cache."""
        with self._lock:
            self._cache.clear()

    def stats(self) -> CacheStats:
        """
        Get cache statistics.

        Returns:
            CacheStats object with hits, misses, size, hit_rate, oldest_entry_age
        """
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0.0

            # Find oldest entry age
            oldest_entry_age = None
            if self._cache:
                now = time.time()
                oldest_access_time = min(
                    access_time for _value, _expiry, access_time in self._cache.values()
                )
                oldest_entry_age = now - oldest_access_time

            return CacheStats(
                hits=self._hits,
                misses=self._misses,
                size=len(self._cache),
                hit_rate=hit_rate,
                oldest_entry_age=oldest_entry_age,
            )

    def _evict_lru(self) -> None:
        """
        Evict least-recently-used entry.

        Should only be called while holding the lock.
        """
        if not self._cache:
            return

        # Find key with earliest access time
        lru_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k][2],  # access_time is at index 2
        )
        del self._cache[lru_key]
        logger.debug(f"Evicted LRU key: {lru_key}")

    def cleanup_expired(self) -> int:
        """
        Clean up all expired entries.

        Returns:
            Number of expired entries removed
        """
        with self._lock:
            now = time.time()
            expired_keys = [
                key for key, (_, expiry_time, _) in self._cache.items() if now >= expiry_time
            ]

            for key in expired_keys:
                del self._cache[key]

            return len(expired_keys)
