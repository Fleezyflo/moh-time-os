"""
Tests for PerformanceScale — caching, query optimization, pagination.

Brief 14 (PS), Task PS-1.1
"""

import time

from lib.intelligence.performance_scale import (
    IndexRecommendation,
    InMemoryCache,
    PaginationParams,
    PerformanceMonitor,
    QueryOptimizer,
    make_cache_key,
    paginate,
)


class TestInMemoryCache:
    def test_set_and_get(self):
        cache = InMemoryCache()
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_miss(self):
        cache = InMemoryCache()
        assert cache.get("nonexistent") is None

    def test_ttl_expiry(self):
        cache = InMemoryCache(default_ttl_s=0.05)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        time.sleep(0.06)
        assert cache.get("key1") is None

    def test_custom_ttl(self):
        cache = InMemoryCache(default_ttl_s=10.0)
        cache.set("key1", "value1", ttl_s=0.05)
        time.sleep(0.06)
        assert cache.get("key1") is None

    def test_lru_eviction(self):
        cache = InMemoryCache(max_entries=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # should evict "a"
        assert cache.get("a") is None
        assert cache.get("d") == 4

    def test_lru_touch_on_get(self):
        cache = InMemoryCache(max_entries=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.get("a")  # touch "a" so it's most recent
        cache.set("d", 4)  # should evict "b" (LRU)
        assert cache.get("a") == 1
        assert cache.get("b") is None

    def test_invalidate(self):
        cache = InMemoryCache()
        cache.set("key1", "value1")
        assert cache.invalidate("key1") is True
        assert cache.get("key1") is None
        assert cache.invalidate("key1") is False

    def test_invalidate_prefix(self):
        cache = InMemoryCache()
        cache.set("client:1", "a")
        cache.set("client:2", "b")
        cache.set("project:1", "c")
        removed = cache.invalidate_prefix("client:")
        assert removed == 2
        assert cache.get("project:1") == "c"

    def test_clear(self):
        cache = InMemoryCache()
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_stats(self):
        cache = InMemoryCache()
        cache.set("a", 1)
        cache.get("a")  # hit
        cache.get("b")  # miss
        stats = cache.get_stats()
        assert stats.hits == 1
        assert stats.misses == 1
        assert stats.hit_rate == 0.5

    def test_overwrite_key(self):
        cache = InMemoryCache()
        cache.set("a", 1)
        cache.set("a", 2)
        assert cache.get("a") == 2


class TestMakeCacheKey:
    def test_deterministic(self):
        assert make_cache_key("a", "b", 1) == make_cache_key("a", "b", 1)

    def test_different_inputs(self):
        assert make_cache_key("a", "b") != make_cache_key("b", "a")


class TestQueryOptimizer:
    def test_log_query(self):
        opt = QueryOptimizer()
        opt.log_query("SELECT * FROM clients", 50.0, rows_returned=10)
        assert len(opt.query_log) == 1

    def test_detect_n_plus_one(self):
        opt = QueryOptimizer()
        for i in range(5):
            opt.log_query(f"SELECT * FROM clients WHERE id = '{i}'", 10.0)  # noqa: S608
        patterns = opt.detect_n_plus_one()
        assert len(patterns) >= 1
        assert patterns[0]["count"] == 5

    def test_no_n_plus_one(self):
        opt = QueryOptimizer()
        opt.log_query("SELECT * FROM clients", 10.0)
        opt.log_query("SELECT * FROM projects", 10.0)
        patterns = opt.detect_n_plus_one()
        assert len(patterns) == 0

    def test_slow_queries(self):
        opt = QueryOptimizer()
        opt.log_query("SELECT * FROM big_table", 200.0)
        opt.log_query("SELECT * FROM small_table", 5.0)
        slow = opt.get_slow_queries(threshold_ms=100.0)
        assert len(slow) == 1
        assert slow[0]["duration_ms"] == 200.0

    def test_recommend_indexes(self):
        opt = QueryOptimizer()
        recs = opt.recommend_indexes(
            {
                "clients": ["entity_id", "entity_id", "name"],
            }
        )
        assert len(recs) >= 1
        assert recs[0].table == "clients"
        assert "entity_id" in recs[0].columns


class TestIndexRecommendation:
    def test_to_sql(self):
        rec = IndexRecommendation(table="clients", columns=["entity_id"])
        sql = rec.to_sql()
        assert "CREATE INDEX" in sql
        assert "clients" in sql
        assert "entity_id" in sql

    def test_auto_name(self):
        rec = IndexRecommendation(table="clients", columns=["entity_id"])
        assert rec.index_name == "idx_clients_entity_id"

    def test_to_dict(self):
        rec = IndexRecommendation(table="t", columns=["c"])
        d = rec.to_dict()
        assert "sql" in d


class TestPagination:
    def test_basic_paginate(self):
        items = list(range(100))
        result = paginate(items, PaginationParams(limit=10, offset=0))
        assert len(result.items) == 10
        assert result.total_count == 100
        assert result.has_more is True
        assert result.next_cursor == "10"

    def test_last_page(self):
        items = list(range(25))
        result = paginate(items, PaginationParams(limit=10, offset=20))
        assert len(result.items) == 5
        assert result.has_more is False

    def test_empty_items(self):
        result = paginate([], PaginationParams())
        assert result.total_count == 0
        assert result.has_more is False

    def test_limit_clamped(self):
        params = PaginationParams(limit=200)
        assert params.limit == 100

    def test_negative_offset(self):
        params = PaginationParams(offset=-5)
        assert params.offset == 0


class TestPerformanceMonitor:
    def test_record_and_report(self):
        monitor = PerformanceMonitor()
        monitor.set_baseline("dashboard", target_ms=100.0)
        for ms in [50, 60, 70, 80, 90]:
            monitor.record_timing("dashboard", ms)
        report = monitor.get_baseline_report("dashboard")
        assert report.sample_count == 5
        assert report.meets_target is True
        assert report.p50_ms == 70.0

    def test_violation(self):
        monitor = PerformanceMonitor()
        monitor.set_baseline("slow_endpoint", target_ms=50.0)
        for ms in [100, 120, 130, 140, 150]:
            monitor.record_timing("slow_endpoint", ms)
        violations = monitor.get_violations()
        assert len(violations) == 1
        assert violations[0].name == "slow_endpoint"

    def test_no_samples(self):
        monitor = PerformanceMonitor()
        monitor.set_baseline("empty", target_ms=100.0)
        report = monitor.get_baseline_report("empty")
        assert report.sample_count == 0
        assert report.meets_target is True

    def test_all_reports(self):
        monitor = PerformanceMonitor()
        monitor.set_baseline("a", 100)
        monitor.set_baseline("b", 200)
        monitor.record_timing("a", 50)
        reports = monitor.get_all_reports()
        assert len(reports) == 2

    def test_to_dict(self):
        monitor = PerformanceMonitor()
        monitor.set_baseline("test", 100)
        monitor.record_timing("test", 50)
        d = monitor.get_baseline_report("test").to_dict()
        assert "p50_ms" in d
        assert "meets_target" in d
