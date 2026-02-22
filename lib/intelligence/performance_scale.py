"""
Performance & Scale — MOH TIME OS

Caching layer, query optimization tools, pagination helpers,
and database abstraction for production scaling.

Brief 14 (PS), Tasks PS-1.1 through PS-5.1

Addresses performance bottlenecks for production readiness.
"""

import hashlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Caching Layer (PS-2.1)
# ---------------------------------------------------------------------------


@dataclass
class CacheEntry:
    """A cached value with TTL metadata."""

    key: str
    value: Any
    created_at: float  # monotonic
    ttl_s: float
    hit_count: int = 0

    @property
    def is_expired(self) -> bool:
        return (time.monotonic() - self.created_at) >= self.ttl_s

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "ttl_s": self.ttl_s,
            "hit_count": self.hit_count,
            "is_expired": self.is_expired,
            "age_s": round(time.monotonic() - self.created_at, 1),
        }


@dataclass
class CacheStats:
    """Cache performance statistics."""

    total_entries: int = 0
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expired_evictions: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total

    def to_dict(self) -> dict:
        return {
            "total_entries": self.total_entries,
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "expired_evictions": self.expired_evictions,
            "hit_rate": round(self.hit_rate, 3),
        }


class InMemoryCache:
    """
    In-memory cache with TTL and LRU eviction.

    Caches expensive computations like health snapshots,
    truth-value aggregations, and cost-to-serve calculations.
    """

    def __init__(self, max_entries: int = 1000, default_ttl_s: float = 300) -> None:
        self.max_entries = max_entries
        self.default_ttl_s = default_ttl_s
        self._cache: dict[str, CacheEntry] = {}
        self._access_order: list[str] = []  # Most recent at end
        self.stats = CacheStats()

    def get(self, key: str) -> Any | None:
        """Get a value from cache. Returns None on miss or expiry."""
        entry = self._cache.get(key)
        if entry is None:
            self.stats.misses += 1
            return None
        if entry.is_expired:
            self._remove(key)
            self.stats.misses += 1
            self.stats.expired_evictions += 1
            return None
        # Cache hit
        entry.hit_count += 1
        self.stats.hits += 1
        self._touch(key)
        return entry.value

    def set(self, key: str, value: Any, ttl_s: float | None = None) -> None:
        """Set a value in cache with optional TTL override."""
        ttl = ttl_s if ttl_s is not None else self.default_ttl_s

        if key in self._cache:
            self._remove(key)

        # Evict LRU if at capacity
        while len(self._cache) >= self.max_entries:
            self._evict_lru()

        entry = CacheEntry(
            key=key,
            value=value,
            created_at=time.monotonic(),
            ttl_s=ttl,
        )
        self._cache[key] = entry
        self._access_order.append(key)
        self.stats.total_entries = len(self._cache)

    def invalidate(self, key: str) -> bool:
        """Remove a specific key from cache."""
        if key in self._cache:
            self._remove(key)
            return True
        return False

    def invalidate_prefix(self, prefix: str) -> int:
        """Remove all keys matching a prefix."""
        keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
        for k in keys_to_remove:
            self._remove(k)
        return len(keys_to_remove)

    def clear(self) -> None:
        """Clear entire cache."""
        self._cache.clear()
        self._access_order.clear()
        self.stats.total_entries = 0

    def get_stats(self) -> CacheStats:
        """Get cache performance stats."""
        self.stats.total_entries = len(self._cache)
        return self.stats

    def _touch(self, key: str) -> None:
        """Move key to end of access order (most recently used)."""
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)

    def _remove(self, key: str) -> None:
        """Remove a key from cache and access order."""
        self._cache.pop(key, None)
        if key in self._access_order:
            self._access_order.remove(key)
        self.stats.total_entries = len(self._cache)

    def _evict_lru(self) -> None:
        """Evict the least recently used entry."""
        if not self._access_order:
            return
        lru_key = self._access_order[0]
        self._remove(lru_key)
        self.stats.evictions += 1


def make_cache_key(*parts: Any) -> str:
    """Generate a deterministic cache key from parts."""
    raw = ":".join(str(p) for p in parts)
    return hashlib.md5(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Query Optimization Tools (PS-1.1)
# ---------------------------------------------------------------------------


@dataclass
class QueryPlan:
    """Analysis of a query's execution plan."""

    query: str
    estimated_rows: int = 0
    uses_index: bool = False
    scan_type: str = "full"  # full | index | covering
    suggested_index: str = ""
    optimization_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "query": self.query[:100],
            "estimated_rows": self.estimated_rows,
            "uses_index": self.uses_index,
            "scan_type": self.scan_type,
            "suggested_index": self.suggested_index,
            "optimization_notes": self.optimization_notes,
        }


@dataclass
class IndexRecommendation:
    """Recommendation for a database index."""

    table: str
    columns: list[str]
    index_name: str = ""
    reason: str = ""
    estimated_improvement: str = ""  # e.g., "10x faster"

    def __post_init__(self):
        if not self.index_name:
            cols = "_".join(self.columns)
            self.index_name = f"idx_{self.table}_{cols}"

    def to_sql(self) -> str:
        cols = ", ".join(self.columns)
        return f"CREATE INDEX IF NOT EXISTS {self.index_name} ON {self.table} ({cols})"

    def to_dict(self) -> dict:
        return {
            "table": self.table,
            "columns": self.columns,
            "index_name": self.index_name,
            "reason": self.reason,
            "sql": self.to_sql(),
        }


class QueryOptimizer:
    """
    Analyzes queries and recommends optimizations.

    Detects N+1 patterns, suggests indexes, and identifies slow queries.
    """

    # Common N+1 patterns
    N_PLUS_ONE_INDICATORS = [
        "SELECT",  # repeated in loop
    ]

    def __init__(self) -> None:
        self.query_log: list[dict[str, Any]] = []
        self._slow_threshold_ms: float = 100.0

    def log_query(
        self,
        query: str,
        duration_ms: float,
        rows_returned: int = 0,
        source: str = "",
    ) -> None:
        """Log a query execution for analysis."""
        self.query_log.append(
            {
                "query": query,
                "duration_ms": duration_ms,
                "rows_returned": rows_returned,
                "source": source,
                "timestamp": datetime.now().isoformat(),
            }
        )
        # Keep last 1000
        if len(self.query_log) > 1000:
            self.query_log = self.query_log[-1000:]

    def detect_n_plus_one(self, window_ms: float = 500.0) -> list[dict[str, Any]]:
        """
        Detect N+1 query patterns: many similar queries in a short window.

        Returns groups of queries that look like N+1 patterns.
        """
        if len(self.query_log) < 3:
            return []

        patterns: dict[str, list[dict[str, Any]]] = {}
        for entry in self.query_log:
            # Normalize query to detect similar patterns
            normalized = self._normalize_query(entry["query"])
            if normalized not in patterns:
                patterns[normalized] = []
            patterns[normalized].append(entry)

        # N+1: same normalized query executed 3+ times
        results = []
        for normalized, entries in patterns.items():
            if len(entries) >= 3:
                results.append(
                    {
                        "pattern": normalized[:100],
                        "count": len(entries),
                        "total_duration_ms": sum(e["duration_ms"] for e in entries),
                        "recommendation": "Use JOIN or batch query instead of loop",
                    }
                )
        return results

    def get_slow_queries(self, threshold_ms: float | None = None) -> list[dict[str, Any]]:
        """Get queries that exceed the slow threshold."""
        threshold = threshold_ms or self._slow_threshold_ms
        return [entry for entry in self.query_log if entry["duration_ms"] >= threshold]

    def recommend_indexes(
        self,
        table_queries: dict[str, list[str]],
    ) -> list[IndexRecommendation]:
        """
        Recommend indexes based on common query patterns.

        table_queries: {table_name: [list of WHERE clause columns]}
        """
        recommendations = []
        for table, columns_list in table_queries.items():
            # Count frequency of column usage in WHERE clauses
            col_freq: dict[str, int] = {}
            for cols in columns_list:
                for col in cols.split(","):
                    col = col.strip()
                    if col:
                        col_freq[col] = col_freq.get(col, 0) + 1

            # Recommend indexes for frequently queried columns
            for col, freq in sorted(col_freq.items(), key=lambda x: -x[1]):
                if freq >= 2:
                    recommendations.append(
                        IndexRecommendation(
                            table=table,
                            columns=[col],
                            reason=f"Column '{col}' used in {freq} queries",
                            estimated_improvement=f"~{freq}x fewer full scans",
                        )
                    )
        return recommendations

    @staticmethod
    def _normalize_query(query: str) -> str:
        """Normalize a query for pattern matching (strip literals)."""
        import re

        # Replace string literals
        normalized = re.sub(r"'[^']*'", "'?'", query)
        # Replace numbers
        normalized = re.sub(r"\b\d+\b", "?", normalized)
        # Collapse whitespace
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized


# ---------------------------------------------------------------------------
# Pagination Helpers (PS-4.1)
# ---------------------------------------------------------------------------


@dataclass
class PaginationParams:
    """Parsed pagination parameters."""

    limit: int = 50
    offset: int = 0
    cursor: str = ""

    def __post_init__(self):
        self.limit = max(1, min(self.limit, 100))
        self.offset = max(0, self.offset)

    def to_dict(self) -> dict:
        return {
            "limit": self.limit,
            "offset": self.offset,
            "cursor": self.cursor,
        }


@dataclass
class PaginatedResult:
    """A paginated result set."""

    items: list[Any]
    total_count: int
    limit: int
    offset: int
    has_more: bool
    next_cursor: str = ""

    def to_dict(self) -> dict:
        return {
            "items": self.items,
            "total_count": self.total_count,
            "limit": self.limit,
            "offset": self.offset,
            "has_more": self.has_more,
            "next_cursor": self.next_cursor,
        }


def paginate(
    items: list[Any],
    params: PaginationParams,
) -> PaginatedResult:
    """Apply pagination to a list of items."""
    total = len(items)
    start = params.offset
    end = start + params.limit
    page = items[start:end]
    has_more = end < total

    return PaginatedResult(
        items=page,
        total_count=total,
        limit=params.limit,
        offset=params.offset,
        has_more=has_more,
        next_cursor=str(end) if has_more else "",
    )


# ---------------------------------------------------------------------------
# Performance Baselines (PS-5.1)
# ---------------------------------------------------------------------------


@dataclass
class PerformanceBaseline:
    """Performance baseline for an endpoint or operation."""

    name: str
    target_ms: float
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    sample_count: int = 0
    meets_target: bool = True

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "target_ms": self.target_ms,
            "p50_ms": round(self.p50_ms, 1),
            "p95_ms": round(self.p95_ms, 1),
            "p99_ms": round(self.p99_ms, 1),
            "sample_count": self.sample_count,
            "meets_target": self.meets_target,
        }


class PerformanceMonitor:
    """
    Tracks operation timing and compares against baselines.
    """

    def __init__(self) -> None:
        self.timings: dict[str, list[float]] = {}  # name → [durations_ms]
        self.baselines: dict[str, float] = {}  # name → target_ms

    def set_baseline(self, name: str, target_ms: float) -> None:
        """Set a performance target for an operation."""
        self.baselines[name] = target_ms

    def record_timing(self, name: str, duration_ms: float) -> None:
        """Record an operation timing."""
        if name not in self.timings:
            self.timings[name] = []
        self.timings[name].append(duration_ms)
        # Keep last 1000 per operation
        if len(self.timings[name]) > 1000:
            self.timings[name] = self.timings[name][-1000:]

    def get_baseline_report(self, name: str) -> PerformanceBaseline:
        """Get performance report for a specific operation."""
        target = self.baselines.get(name, 1000.0)
        samples = self.timings.get(name, [])

        if not samples:
            return PerformanceBaseline(name=name, target_ms=target)

        sorted_samples = sorted(samples)
        n = len(sorted_samples)

        p50 = sorted_samples[int(n * 0.5)]
        p95 = sorted_samples[min(int(n * 0.95), n - 1)]
        p99 = sorted_samples[min(int(n * 0.99), n - 1)]

        return PerformanceBaseline(
            name=name,
            target_ms=target,
            p50_ms=p50,
            p95_ms=p95,
            p99_ms=p99,
            sample_count=n,
            meets_target=p95 <= target,
        )

    def get_all_reports(self) -> list[PerformanceBaseline]:
        """Get reports for all tracked operations."""
        names = set(list(self.timings.keys()) + list(self.baselines.keys()))
        return [self.get_baseline_report(name) for name in sorted(names)]

    def get_violations(self) -> list[PerformanceBaseline]:
        """Get operations that don't meet their targets."""
        return [r for r in self.get_all_reports() if not r.meets_target]
