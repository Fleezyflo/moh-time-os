#!/usr/bin/env python3
"""
Brief 14: Performance & Scale — Validation Script (PS-5.1)

Validates all deliverables from Brief 14:
- PS-1.1: Fix N+1 queries + add indexes
- PS-2.1: In-memory cache layer (TTL, invalidation)
- PS-3.1: PostgreSQL compatibility layer
- PS-4.1: Pagination + async background tasks
"""

import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    status = "PASS" if condition else "FAIL"
    if condition:
        PASS += 1
    else:
        FAIL += 1
    msg = f"  [{status}] {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)


def run_tests(test_files: list[str]) -> tuple[int, int]:
    cmd = [sys.executable, "-m", "pytest"] + test_files + ["-q", "--tb=no"]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(BASE))
    output = result.stdout + result.stderr
    passed = failed = 0
    for line in output.split("\n"):
        if "passed" in line:
            parts = line.split()
            for i, p in enumerate(parts):
                if p == "passed":
                    try:
                        passed = int(parts[i - 1])
                    except (ValueError, IndexError):
                        pass
                if p == "failed":
                    try:
                        failed = int(parts[i - 1])
                    except (ValueError, IndexError):
                        pass
    return passed, failed


def main() -> int:
    global PASS, FAIL

    print("=" * 60)
    print("Brief 14: Performance & Scale — Validation")
    print("=" * 60)

    # Check 1: Query Optimization (PS-1.1)
    print("\n1. Query Optimization (PS-1.1)")
    qo = BASE / "lib" / "db" / "query_optimizer.py"
    idx = BASE / "lib" / "db" / "indexes.py"
    check("query_optimizer.py exists", qo.exists())
    check("indexes.py exists", idx.exists())
    if qo.exists():
        code = qo.read_text()
        check("Has BatchLoader", "BatchLoader" in code)
        check("Has prefetch_related", "prefetch_related" in code)
        check("Has QueryStats", "QueryStats" in code)
    if idx.exists():
        code = idx.read_text()
        check("Has ensure_indexes", "ensure_indexes" in code)
        check("Has CREATE INDEX IF NOT EXISTS", "CREATE INDEX IF NOT EXISTS" in code)
        # Count index definitions — indexes are defined as tuples in PERFORMANCE_INDEXES list
        # Each line like '    ("table", ["col"]),'' is one index definition
        idx_count = len(
            [line for line in code.split("\n") if line.strip().startswith('("') and "[" in line]
        )
        check("Has 20+ indexes defined", idx_count >= 20, f"{idx_count} indexes")

    # Check 2: Cache Layer (PS-2.1)
    print("\n2. Cache Layer (PS-2.1)")
    cm = BASE / "lib" / "cache" / "cache_manager.py"
    dec = BASE / "lib" / "cache" / "decorators.py"
    check("cache_manager.py exists", cm.exists())
    check("decorators.py exists", dec.exists())
    if cm.exists():
        code = cm.read_text()
        check("Has CacheManager", "CacheManager" in code)
        check("Has TTL support", "ttl" in code.lower())
        check("Thread-safe (Lock)", "Lock" in code)
        check(
            "Has LRU eviction",
            "lru" in code.lower() or "evict" in code.lower() or "max_size" in code,
        )
    if dec.exists():
        code = dec.read_text()
        check("Has @cached decorator", "cached" in code)
        check("Has @cache_invalidate", "cache_invalidate" in code)

    # Check 3: PostgreSQL Compat (PS-3.1)
    print("\n3. PostgreSQL Compatibility (PS-3.1)")
    adapter = BASE / "lib" / "db" / "db_adapter.py"
    compat = BASE / "lib" / "db" / "sql_compat.py"
    pool = BASE / "lib" / "db" / "connection_pool.py"
    check("db_adapter.py exists", adapter.exists())
    check("sql_compat.py exists", compat.exists())
    check("connection_pool.py exists", pool.exists())
    if adapter.exists():
        code = adapter.read_text()
        check("Has DatabaseAdapter ABC", "DatabaseAdapter" in code)
        check("Has SQLiteAdapter", "SQLiteAdapter" in code)
    if compat.exists():
        code = compat.read_text()
        check("Has translate_sqlite_to_pg", "translate_sqlite_to_pg" in code)
        check("Has detect_dialect", "detect_dialect" in code)
    if pool.exists():
        code = pool.read_text()
        check("Has ConnectionPool", "ConnectionPool" in code)

    # Check 4: Pagination + Async (PS-4.1)
    print("\n4. Pagination + Async (PS-4.1)")
    pag = BASE / "lib" / "api" / "pagination.py"
    bg = BASE / "lib" / "api" / "background_tasks.py"
    pr = BASE / "api" / "paginated_router.py"
    check("pagination.py exists", pag.exists())
    check("background_tasks.py exists", bg.exists())
    check("paginated_router.py exists", pr.exists())
    if pag.exists():
        code = pag.read_text()
        check("Has PaginatedResponse", "PaginatedResponse" in code)
        check("Has CursorPaginatedResponse", "CursorPaginatedResponse" in code)
    if bg.exists():
        code = bg.read_text()
        check("Has TaskManager", "TaskManager" in code)
        check("Has ThreadPoolExecutor", "ThreadPoolExecutor" in code)

    # Check 5: Server Integration
    print("\n5. Server Integration")
    server = BASE / "api" / "server.py"
    if server.exists():
        code = server.read_text()
        check("Paginated router wired", "paginated_router" in code)

    # Check 6: Test Suite
    print("\n6. Test Suite")
    test_files = [
        "tests/test_query_optimizer.py",
        "tests/test_cache.py",
        "tests/test_db_adapter.py",
        "tests/test_pagination.py",
        "tests/test_background_tasks.py",
    ]
    existing = [f for f in test_files if (BASE / f).exists()]
    check("All 5 test files exist", len(existing) == 5, f"{len(existing)}/5")

    if existing:
        passed, failed = run_tests(existing)
        check("All Brief 14 tests pass", failed == 0, f"{passed} passed, {failed} failed")
        check("Test count >= 150", passed >= 150, f"{passed} tests")

    # Summary
    print("\n" + "=" * 60)
    total = PASS + FAIL
    print(f"Results: {PASS}/{total} checks passed")
    if FAIL == 0:
        print("STATUS: ✅ ALL CHECKS PASSED — Brief 14 VALIDATED")
    else:
        print(f"STATUS: ❌ {FAIL} CHECK(S) FAILED")
    print("=" * 60)

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
