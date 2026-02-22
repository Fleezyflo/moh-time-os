"""
In-memory cache layer for MOH Time OS.

Provides:
- CacheManager: TTL-based cache with LRU eviction and pattern invalidation
- @cached: Decorator for caching function results
- @cache_invalidate: Decorator for invalidating cache on writes
- get_cache: Access global cache instance
"""

from .cache_manager import CacheManager, CacheStats
from .decorators import cache_invalidate, cached, get_cache

__all__ = [
    "CacheManager",
    "CacheStats",
    "cached",
    "cache_invalidate",
    "get_cache",
]
