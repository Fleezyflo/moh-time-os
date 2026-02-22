"""
Comprehensive tests for in-memory cache layer.

Tests cover:
- Basic get/set operations
- TTL expiration
- Deletion
- Pattern-based invalidation
- Statistics tracking
- Thread safety
- LRU eviction
- Namespace support
- Decorators (cached and cache_invalidate)
- Expired entry cleanup
"""

import asyncio
import threading
import time

import pytest

from lib.cache import CacheManager, CacheStats, cache_invalidate, cached, get_cache


class TestCacheBasicOperations:
    """Test basic cache operations."""

    def test_set_and_get(self):
        """Test setting and getting a value."""
        cache = CacheManager()
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_nonexistent_key(self):
        """Test getting a key that doesn't exist."""
        cache = CacheManager()
        assert cache.get("nonexistent") is None

    def test_get_empty_string_value(self):
        """Test that empty strings are returned correctly."""
        cache = CacheManager()
        cache.set("empty", "")
        assert cache.get("empty") == ""

    def test_set_none_value(self):
        """Test that None values are treated as empty (not cached)."""
        cache = CacheManager()
        cache.set("none_key", None)
        # Note: None is returned as cached value, should be treated carefully
        assert cache.get("none_key") is None

    def test_get_with_custom_ttl(self):
        """Test setting value with custom TTL."""
        cache = CacheManager()
        cache.set("key1", "value1", ttl_seconds=1)
        assert cache.get("key1") == "value1"

    def test_delete_key(self):
        """Test deleting a specific key."""
        cache = CacheManager()
        cache.set("key1", "value1")
        cache.delete("key1")
        assert cache.get("key1") is None

    def test_delete_nonexistent_key(self):
        """Test deleting a key that doesn't exist (should not raise)."""
        cache = CacheManager()
        cache.delete("nonexistent")  # Should not raise
        assert cache.get("nonexistent") is None

    def test_set_overwrites_existing_value(self):
        """Test that setting a key overwrites previous value."""
        cache = CacheManager()
        cache.set("key1", "value1")
        cache.set("key1", "value2")
        assert cache.get("key1") == "value2"

    def test_set_different_data_types(self):
        """Test caching different data types."""
        cache = CacheManager()

        cache.set("str", "string")
        assert cache.get("str") == "string"

        cache.set("int", 42)
        assert cache.get("int") == 42

        cache.set("float", 3.14)
        assert cache.get("float") == 3.14

        cache.set("list", [1, 2, 3])
        assert cache.get("list") == [1, 2, 3]

        cache.set("dict", {"key": "value"})
        assert cache.get("dict") == {"key": "value"}


class TestCacheTTL:
    """Test TTL expiration."""

    def test_ttl_expiration(self):
        """Test that cached value expires after TTL."""
        cache = CacheManager()
        cache.set("key1", "value1", ttl_seconds=1)
        assert cache.get("key1") == "value1"

        time.sleep(1.1)
        assert cache.get("key1") is None

    def test_default_ttl(self):
        """Test default TTL."""
        cache = CacheManager(default_ttl=1)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

        time.sleep(1.1)
        assert cache.get("key1") is None

    def test_custom_ttl_overrides_default(self):
        """Test that custom TTL overrides default."""
        cache = CacheManager(default_ttl=10)
        cache.set("key1", "value1", ttl_seconds=1)

        time.sleep(1.1)
        assert cache.get("key1") is None

    def test_ttl_with_multiple_entries(self):
        """Test TTL expiration with multiple entries."""
        cache = CacheManager(default_ttl=10)
        cache.set("key1", "value1", ttl_seconds=1)
        cache.set("key2", "value2", ttl_seconds=2)

        time.sleep(1.1)
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"

        time.sleep(1.0)
        assert cache.get("key2") is None


class TestClearAll:
    """Test clearing entire cache."""

    def test_clear(self):
        """Test clearing entire cache."""
        cache = CacheManager()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_clear_empty_cache(self):
        """Test clearing an empty cache (should not raise)."""
        cache = CacheManager()
        cache.clear()  # Should not raise


class TestInvalidatePattern:
    """Test pattern-based invalidation."""

    def test_invalidate_pattern_glob(self):
        """Test invalidating with glob pattern."""
        cache = CacheManager()
        cache.set("client:1", "data1")
        cache.set("client:2", "data2")
        cache.set("project:1", "data3")

        count = cache.invalidate_pattern("client:*")
        assert count == 2
        assert cache.get("client:1") is None
        assert cache.get("client:2") is None
        assert cache.get("project:1") == "data3"

    def test_invalidate_pattern_exact_match(self):
        """Test invalidating with exact key match."""
        cache = CacheManager()
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        count = cache.invalidate_pattern("key1")
        assert count == 1
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"

    def test_invalidate_pattern_no_matches(self):
        """Test invalidating pattern with no matches."""
        cache = CacheManager()
        cache.set("key1", "value1")

        count = cache.invalidate_pattern("nonexistent:*")
        assert count == 0
        assert cache.get("key1") == "value1"

    def test_invalidate_pattern_namespace(self):
        """Test invalidating namespaced keys."""
        cache = CacheManager()
        cache.set("intelligence:portfolio:overview", "data1")
        cache.set("intelligence:portfolio:risks", "data2")
        cache.set("intelligence:client:1", "data3")

        count = cache.invalidate_pattern("intelligence:portfolio:*")
        assert count == 2
        assert cache.get("intelligence:portfolio:overview") is None
        assert cache.get("intelligence:portfolio:risks") is None
        assert cache.get("intelligence:client:1") == "data3"

    def test_invalidate_pattern_complex_glob(self):
        """Test complex glob patterns."""
        cache = CacheManager()
        cache.set("user:1:profile", "data1")
        cache.set("user:1:posts", "data2")
        cache.set("user:2:profile", "data3")
        cache.set("admin:profile", "data4")

        count = cache.invalidate_pattern("user:*:profile")
        assert count == 2
        assert cache.get("user:1:profile") is None
        assert cache.get("user:2:profile") is None
        assert cache.get("user:1:posts") == "data2"
        assert cache.get("admin:profile") == "data4"


class TestStats:
    """Test statistics tracking."""

    def test_stats_hits_and_misses(self):
        """Test hit and miss counting."""
        cache = CacheManager()
        cache.set("key1", "value1")

        # Hit
        cache.get("key1")
        # Miss
        cache.get("key2")
        # Miss
        cache.get("key3")

        stats = cache.stats()
        assert stats.hits == 1
        assert stats.misses == 2
        assert stats.size == 1

    def test_stats_hit_rate(self):
        """Test hit rate calculation."""
        cache = CacheManager()
        cache.set("key1", "value1")

        # 2 hits, 1 miss = 66.67% hit rate
        cache.get("key1")
        cache.get("key1")
        cache.get("key2")

        stats = cache.stats()
        assert stats.hits == 2
        assert stats.misses == 1
        assert abs(stats.hit_rate - 2 / 3) < 0.01

    def test_stats_zero_hit_rate(self):
        """Test hit rate when no requests made."""
        cache = CacheManager()
        stats = cache.stats()
        assert stats.hit_rate == 0.0

    def test_stats_size(self):
        """Test size counting."""
        cache = CacheManager()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        stats = cache.stats()
        assert stats.size == 3

    def test_stats_oldest_entry_age(self):
        """Test oldest entry age calculation."""
        cache = CacheManager()
        cache.set("key1", "value1")
        time.sleep(0.1)
        cache.set("key2", "value2")

        stats = cache.stats()
        assert stats.oldest_entry_age is not None
        assert stats.oldest_entry_age >= 0.1

    def test_stats_oldest_entry_age_empty_cache(self):
        """Test oldest entry age with empty cache."""
        cache = CacheManager()
        stats = cache.stats()
        assert stats.oldest_entry_age is None

    def test_stats_to_dict(self):
        """Test CacheStats.to_dict() method."""
        stats = CacheStats(hits=10, misses=5, size=100, hit_rate=0.667)
        data = stats.to_dict()
        assert isinstance(data, dict)
        assert data["hits"] == 10
        assert data["misses"] == 5
        assert data["size"] == 100
        assert data["hit_rate"] == 0.667


class TestThreadSafety:
    """Test thread-safe operations."""

    def test_concurrent_set_and_get(self):
        """Test concurrent set and get operations."""
        cache = CacheManager()
        results = []

        def worker(key_num):
            for i in range(100):
                cache.set(f"key:{key_num}:{i}", f"value:{key_num}:{i}")
                val = cache.get(f"key:{key_num}:{i}")
                if val is not None:
                    results.append(val)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify all writes succeeded
        stats = cache.stats()
        assert stats.size > 0

    def test_concurrent_delete(self):
        """Test concurrent delete operations."""
        cache = CacheManager()

        for i in range(100):
            cache.set(f"key:{i}", f"value:{i}")

        def worker(key_num):
            for i in range(50):
                cache.delete(f"key:{key_num * 50 + i}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        stats = cache.stats()
        # All 100 entries should be deleted
        assert stats.size == 0

    def test_concurrent_invalidate_pattern(self):
        """Test concurrent pattern invalidation."""
        cache = CacheManager()

        for i in range(100):
            cache.set(f"client:{i}", f"data:{i}")
            cache.set(f"project:{i}", f"data:{i}")

        def invalidate_clients():
            for _ in range(10):
                cache.invalidate_pattern("client:*")

        def set_projects():
            for i in range(50, 150):
                cache.set(f"project:{i}", f"data:{i}")

        threads = [
            threading.Thread(target=invalidate_clients),
            threading.Thread(target=set_projects),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should complete without deadlock


class TestLRUEviction:
    """Test LRU eviction when cache is full."""

    def test_lru_eviction(self):
        """Test LRU eviction when max size reached."""
        cache = CacheManager(max_size=3)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        # Access key1 to make it recently used
        cache.get("key1")

        # Add new key, should evict key2 (least recently used)
        cache.set("key4", "value4")

        assert cache.get("key1") == "value1"
        assert cache.get("key2") is None
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"

    def test_lru_eviction_with_expiry(self):
        """Test LRU eviction respects access time from expiry."""
        cache = CacheManager(max_size=2)
        cache.set("key1", "value1", ttl_seconds=10)
        cache.set("key2", "value2", ttl_seconds=10)

        # Get key1 to update access time
        cache.get("key1")

        # Add key3, should evict key2 (older access time)
        cache.set("key3", "value3", ttl_seconds=10)

        assert cache.get("key1") == "value1"
        assert cache.get("key2") is None
        assert cache.get("key3") == "value3"

    def test_lru_eviction_multiple_times(self):
        """Test multiple LRU evictions."""
        cache = CacheManager(max_size=3)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        cache.set("key4", "value4")  # Evicts key1
        cache.set("key5", "value5")  # Evicts key2

        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"
        assert cache.get("key5") == "value5"


class TestCleanupExpired:
    """Test cleanup of expired entries."""

    def test_cleanup_expired(self):
        """Test manual cleanup of expired entries."""
        cache = CacheManager()
        cache.set("key1", "value1", ttl_seconds=1)
        cache.set("key2", "value2", ttl_seconds=10)

        time.sleep(1.1)

        count = cache.cleanup_expired()
        assert count == 1
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"

    def test_cleanup_expired_no_expired(self):
        """Test cleanup when no entries are expired."""
        cache = CacheManager()
        cache.set("key1", "value1", ttl_seconds=10)

        count = cache.cleanup_expired()
        assert count == 0

    def test_cleanup_expired_all(self):
        """Test cleanup when all entries are expired."""
        cache = CacheManager()
        cache.set("key1", "value1", ttl_seconds=1)
        cache.set("key2", "value2", ttl_seconds=1)

        time.sleep(1.1)

        count = cache.cleanup_expired()
        assert count == 2
        assert cache.get("key1") is None
        assert cache.get("key2") is None


class TestCachedDecorator:
    """Test @cached decorator."""

    def test_cached_decorator_basic(self):
        """Test basic @cached decorator functionality."""
        call_count = 0

        @cached(ttl=10)
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count == 1

        # Second call (cached)
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # Not called again

        # Different argument
        result3 = expensive_function(10)
        assert result3 == 20
        assert call_count == 2

    def test_cached_decorator_with_multiple_args(self):
        """Test @cached decorator with multiple arguments."""
        call_count = 0

        @cached(ttl=10)
        def add(a, b):
            nonlocal call_count
            call_count += 1
            return a + b

        assert add(2, 3) == 5
        assert call_count == 1

        assert add(2, 3) == 5
        assert call_count == 1

        assert add(2, 4) == 6
        assert call_count == 2

    def test_cached_decorator_with_kwargs(self):
        """Test @cached decorator with keyword arguments."""
        call_count = 0

        @cached(ttl=10)
        def func(a, b=10):
            nonlocal call_count
            call_count += 1
            return a + b

        assert func(5) == 15
        assert call_count == 1

        # func(5, b=20) is different from func(5) which has default b=10
        assert func(5, b=20) == 25
        assert call_count == 2

        # func(5, b=20) again should be cached
        assert func(5, b=20) == 25
        assert call_count == 2

    def test_cached_decorator_custom_key_func(self):
        """Test @cached decorator with custom key function."""
        call_count = 0

        @cached(ttl=10, key_func=lambda user_id: f"user:{user_id}")
        def get_user(user_id):
            nonlocal call_count
            call_count += 1
            return {"id": user_id, "name": f"User {user_id}"}

        result1 = get_user(123)
        assert call_count == 1

        get_user(123)
        assert call_count == 1

        cache = get_cache()
        assert cache.get("user:123") == result1

    def test_cached_decorator_ttl_expiration(self):
        """Test @cached decorator respects TTL."""
        call_count = 0

        @cached(ttl=1)
        def slow_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        assert slow_function(5) == 10
        assert call_count == 1

        assert slow_function(5) == 10
        assert call_count == 1

        time.sleep(1.1)

        assert slow_function(5) == 10
        assert call_count == 2

    def test_cached_decorator_async(self):
        """Test @cached decorator with async function."""
        call_count = 0

        @cached(ttl=10)
        async def async_function(x):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return x * 2

        # Test async execution
        async def test():
            result1 = await async_function(5)
            assert result1 == 10
            assert call_count == 1

            result2 = await async_function(5)
            assert result2 == 10
            assert call_count == 1

            result3 = await async_function(10)
            assert result3 == 20
            assert call_count == 2

        asyncio.run(test())


class TestCacheInvalidateDecorator:
    """Test @cache_invalidate decorator."""

    def test_cache_invalidate_decorator(self):
        """Test @cache_invalidate decorator."""
        # Clear global cache first
        get_cache().clear()

        call_count = 0

        @cached(ttl=10, key_func=lambda client_id: f"client:{client_id}")
        def get_data(client_id):
            nonlocal call_count
            call_count += 1
            return f"data for {client_id}"

        @cache_invalidate("client:*")
        def update_data(client_id):
            return f"updated {client_id}"

        # Populate cache
        assert get_data(123) == "data for 123"
        assert call_count == 1

        # Second call should hit cache
        assert get_data(123) == "data for 123"
        assert call_count == 1

        # Update should invalidate cache
        update_data(123)

        # Next call should recompute
        assert get_data(123) == "data for 123"
        assert call_count == 2

    def test_cache_invalidate_pattern_matching(self):
        """Test @cache_invalidate with pattern matching."""
        cache = get_cache()
        cache.clear()

        @cached(ttl=10, key_func=lambda prefix: f"{prefix}:data")
        def get_item(prefix):
            return f"result for {prefix}"

        @cache_invalidate("intelligence:*")
        def update_intelligence():
            pass

        # Set some cache entries
        get_item("intelligence")
        get_item("other")

        assert cache.get("intelligence:data") is not None
        assert cache.get("other:data") is not None

        # Invalidate intelligence:*
        update_intelligence()

        assert cache.get("intelligence:data") is None
        assert cache.get("other:data") is not None

    def test_cache_invalidate_always_executes_function(self):
        """Test that @cache_invalidate always executes function even if exception occurs."""
        cache = get_cache()
        cache.clear()

        call_count = 0

        @cache_invalidate("test:*")
        def failing_function():
            nonlocal call_count
            call_count += 1
            raise ValueError("Test error")

        cache.set("test:key", "value")
        assert cache.get("test:key") is not None

        with pytest.raises(ValueError):
            failing_function()

        assert call_count == 1
        assert cache.get("test:key") is None  # Cache was invalidated

    def test_cache_invalidate_decorator_async(self):
        """Test @cache_invalidate with async function."""

        async def test_async_invalidate():
            cache = get_cache()
            cache.clear()

            call_count = 0

            @cached(ttl=10, key_func=lambda key: f"async:{key}")
            async def async_get(key):
                nonlocal call_count
                call_count += 1
                return f"value for {key}"

            @cache_invalidate("async:*")
            async def async_update():
                await asyncio.sleep(0.01)

            # Populate cache
            result1 = await async_get("test")
            assert result1 == "value for test"
            assert call_count == 1

            # Hit cache
            result2 = await async_get("test")
            assert result2 == "value for test"
            assert call_count == 1

            # Invalidate
            await async_update()

            # Should recompute
            result3 = await async_get("test")
            assert result3 == "value for test"
            assert call_count == 2

        asyncio.run(test_async_invalidate())


class TestNamespaceSupport:
    """Test namespace support in cache keys."""

    def test_namespace_keys(self):
        """Test using namespace-style keys."""
        cache = CacheManager()

        cache.set("client:123:profile", {"name": "Alice"})
        cache.set("client:123:tasks", [1, 2, 3])
        cache.set("client:456:profile", {"name": "Bob"})

        assert cache.get("client:123:profile") == {"name": "Alice"}
        assert cache.get("client:123:tasks") == [1, 2, 3]
        assert cache.get("client:456:profile") == {"name": "Bob"}

    def test_namespace_invalidation(self):
        """Test invalidating all keys for a namespace."""
        cache = CacheManager()

        cache.set("user:1:profile", "profile1")
        cache.set("user:1:settings", "settings1")
        cache.set("user:2:profile", "profile2")
        cache.set("admin:profile", "admin_profile")

        # Invalidate all user:1:* keys
        count = cache.invalidate_pattern("user:1:*")
        assert count == 2
        assert cache.get("user:1:profile") is None
        assert cache.get("user:1:settings") is None
        assert cache.get("user:2:profile") == "profile2"
        assert cache.get("admin:profile") == "admin_profile"

    def test_nested_namespace(self):
        """Test deeply nested namespace keys."""
        cache = CacheManager()

        cache.set("intelligence:portfolio:overview", "data1")
        cache.set("intelligence:portfolio:risks", "data2")
        cache.set("intelligence:client:123:profile", "data3")

        assert cache.get("intelligence:portfolio:overview") == "data1"
        assert cache.get("intelligence:portfolio:risks") == "data2"
        assert cache.get("intelligence:client:123:profile") == "data3"

        count = cache.invalidate_pattern("intelligence:portfolio:*")
        assert count == 2
        assert cache.get("intelligence:client:123:profile") == "data3"


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_cache_with_max_size_one(self):
        """Test cache with max_size of 1."""
        cache = CacheManager(max_size=1)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

        cache.set("key2", "value2")
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"

    def test_cache_with_very_long_ttl(self):
        """Test cache with very long TTL."""
        cache = CacheManager()
        cache.set("key1", "value1", ttl_seconds=1000000)
        assert cache.get("key1") == "value1"

    def test_cache_with_zero_ttl(self):
        """Test cache with zero TTL (expires immediately)."""
        cache = CacheManager()
        cache.set("key1", "value1", ttl_seconds=0)
        time.sleep(0.01)
        assert cache.get("key1") is None

    def test_cache_with_complex_nested_data(self):
        """Test caching complex nested data structures."""
        cache = CacheManager()
        complex_data = {
            "clients": [
                {"id": 1, "name": "Client A", "projects": [{"id": 1, "name": "Project 1"}]},
                {"id": 2, "name": "Client B", "projects": []},
            ],
            "stats": {"total": 2, "active": 1},
        }
        cache.set("portfolio:overview", complex_data)
        retrieved = cache.get("portfolio:overview")
        assert retrieved == complex_data

    def test_multiple_cache_instances(self):
        """Test multiple independent cache instances."""
        cache1 = CacheManager()
        cache2 = CacheManager()

        cache1.set("key", "value1")
        cache2.set("key", "value2")

        assert cache1.get("key") == "value1"
        assert cache2.get("key") == "value2"

    def test_pattern_with_special_glob_chars(self):
        """Test patterns with glob special characters."""
        cache = CacheManager()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key123", "value3")

        # Match with character class [12] matches key1 and key2
        count = cache.invalidate_pattern("key[12]")
        assert count == 2
        assert cache.get("key123") == "value3"

    def test_stats_cleared_after_clear(self):
        """Test that stats persist after clearing (only size changes)."""
        cache = CacheManager()
        cache.set("key1", "value1")
        cache.get("key1")  # Hit
        cache.get("key2")  # Miss

        cache.clear()
        stats = cache.stats()

        # Hits and misses should persist
        assert stats.hits == 1
        assert stats.misses == 1
        # But size should be 0
        assert stats.size == 0
