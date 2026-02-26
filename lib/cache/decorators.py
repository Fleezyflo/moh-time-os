"""
Caching decorators for functions.

Provides decorators to cache function results and invalidate cache on writes.
Supports both sync and async functions.
"""

import asyncio
import functools
import hashlib
import logging
import sqlite3
from collections.abc import Callable
from typing import Any

from .cache_manager import CacheManager

logger = logging.getLogger(__name__)

# Global cache instance
_cache_instance: CacheManager | None = None


def get_cache() -> CacheManager:
    """Get or create global cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = CacheManager()
    return _cache_instance


def _generate_cache_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """
    Generate a cache key from function name and arguments.

    Args:
        func_name: Function name
        args: Function arguments
        kwargs: Function keyword arguments

    Returns:
        Cache key
    """
    # Convert args and kwargs to a string representation
    key_parts = [func_name]

    # Add positional args
    for arg in args:
        try:
            key_parts.append(str(arg))
        except (sqlite3.Error, ValueError, OSError):
            key_parts.append(repr(arg))

    # Add keyword args
    for k, v in sorted(kwargs.items()):
        try:
            key_parts.append(f"{k}={v}")
        except (sqlite3.Error, ValueError, OSError):
            key_parts.append(f"{k}={repr(v)}")

    key_str = "|".join(key_parts)

    # Use hash if key is too long
    if len(key_str) > 256:
        key_hash = hashlib.md5(key_str.encode()).hexdigest()  # nosec B324 # noqa: S324 — cache key, not crypto
        return f"{func_name}:{key_hash}"

    return f"{func_name}:{key_str}"


def cached(
    ttl: int = 300,
    key_func: Callable[..., str] | None = None,
) -> Callable:
    """
    Decorator to cache function results.

    Caches the return value of a function with configurable TTL.
    Supports both sync and async functions.

    Args:
        ttl: Time-to-live in seconds. Defaults to 300 (5 minutes).
        key_func: Optional function to generate custom cache key.
                 Should accept same args as decorated function and return string.

    Returns:
        Decorated function

    Example:
        @cached(ttl=120)
        def get_user(user_id):
            return db.users.get(user_id)

        @cached(ttl=60, key_func=lambda client_id: f"client:{client_id}")
        def get_client_data(client_id):
            return db.query(client_id)
    """

    def decorator(func: Callable) -> Callable:
        is_async = asyncio.iscoroutinefunction(func)

        if is_async:

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                cache = get_cache()

                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    cache_key = _generate_cache_key(func.__name__, args, kwargs)

                # Try to get from cache
                cached_value = cache.get(cache_key)
                if cached_value is not None:
                    logger.debug(f"Cache hit for {cache_key}")
                    return cached_value

                # Call function
                result = await func(*args, **kwargs)

                # Store in cache
                cache.set(cache_key, result, ttl_seconds=ttl)
                return result

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                cache = get_cache()

                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    cache_key = _generate_cache_key(func.__name__, args, kwargs)

                # Try to get from cache
                cached_value = cache.get(cache_key)
                if cached_value is not None:
                    logger.debug(f"Cache hit for {cache_key}")
                    return cached_value

                # Call function
                result = func(*args, **kwargs)

                # Store in cache
                cache.set(cache_key, result, ttl_seconds=ttl)
                return result

            return sync_wrapper

    return decorator


def cache_invalidate(pattern: str) -> Callable:
    """
    Decorator to invalidate cache entries matching a pattern on function call.

    Used on write operations to clear related cached reads.
    Invalidates cache AFTER the function executes.

    Args:
        pattern: Glob pattern to match cache keys.
                Examples: "client:*", "intelligence:portfolio:*"

    Returns:
        Decorated function

    Example:
        @cache_invalidate("client:*")
        def update_client(client_id, data):
            db.clients.update(client_id, data)

        @cache_invalidate("intelligence:*")
        def create_task():
            db.tasks.insert(...)
    """

    def decorator(func: Callable) -> Callable:
        is_async = asyncio.iscoroutinefunction(func)

        if is_async:

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    result = await func(*args, **kwargs)
                finally:
                    cache = get_cache()
                    count = cache.invalidate_pattern(pattern)
                    logger.debug(f"Invalidated {count} cache keys matching pattern: {pattern}")

                return result

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    result = func(*args, **kwargs)
                finally:
                    cache = get_cache()
                    count = cache.invalidate_pattern(pattern)
                    logger.debug(f"Invalidated {count} cache keys matching pattern: {pattern}")

                return result

            return sync_wrapper

    return decorator
