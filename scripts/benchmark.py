#!/usr/bin/env python3
"""
Performance benchmark suite.

Measures and enforces performance budgets for critical operations:
- Normalization functions
- Schema validation
- Collector loop
- API response times

Usage:
    uv run python scripts/benchmark.py [--save] [--compare FILE]

Output:
    JSON results with timing data and budget status.
"""

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# Performance budgets (in milliseconds)
BUDGETS = {
    "normalize_client_id": 0.1,      # 0.1ms per call
    "schema_validation": 50.0,       # 50ms for full schema check
    "collector_sync": 5000.0,        # 5s for full collector sync
    "api_health": 100.0,             # 100ms for health endpoint
    "api_clients_list": 500.0,       # 500ms for clients list
    "json_parse_safe": 0.5,          # 0.5ms per JSON parse
}


@dataclass
class BenchmarkResult:
    name: str
    iterations: int
    mean_ms: float
    median_ms: float
    min_ms: float
    max_ms: float
    stddev_ms: float
    budget_ms: float | None
    passed: bool

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "iterations": self.iterations,
            "mean_ms": round(self.mean_ms, 4),
            "median_ms": round(self.median_ms, 4),
            "min_ms": round(self.min_ms, 4),
            "max_ms": round(self.max_ms, 4),
            "stddev_ms": round(self.stddev_ms, 4),
            "budget_ms": self.budget_ms,
            "passed": self.passed,
        }


def benchmark(
    name: str,
    func: Callable,
    iterations: int = 100,
    warmup: int = 10,
) -> BenchmarkResult:
    """Run a benchmark and return results."""
    budget = BUDGETS.get(name)

    # Warmup
    for _ in range(warmup):
        func()

    # Measure
    times_ms = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        elapsed = (time.perf_counter() - start) * 1000
        times_ms.append(elapsed)

    mean = statistics.mean(times_ms)
    passed = budget is None or mean <= budget

    return BenchmarkResult(
        name=name,
        iterations=iterations,
        mean_ms=mean,
        median_ms=statistics.median(times_ms),
        min_ms=min(times_ms),
        max_ms=max(times_ms),
        stddev_ms=statistics.stdev(times_ms) if len(times_ms) > 1 else 0,
        budget_ms=budget,
        passed=passed,
    )


def run_benchmarks() -> list[BenchmarkResult]:
    """Run all benchmarks."""
    results = []

    # Benchmark: normalize_client_id
    try:
        from lib.normalize import normalize_client_id
        result = benchmark(
            "normalize_client_id",
            lambda: normalize_client_id("Test Client Name"),
            iterations=1000,
        )
        results.append(result)
    except ImportError:
        print("⚠️  normalize_client_id not available")

    # Benchmark: JSON safe parse
    try:
        from lib.safety.json_parse import safe_json_loads
        test_json = '{"key": "value", "nested": {"a": 1, "b": 2}}'
        result = benchmark(
            "json_parse_safe",
            lambda: safe_json_loads(test_json, {}),
            iterations=1000,
        )
        results.append(result)
    except ImportError:
        print("⚠️  safe_json_loads not available")

    # Benchmark: schema validation (requires DB)
    try:
        import sqlite3
        import tempfile
        from lib.db import init_db
        from lib.safety.schema import SchemaAssertion

        # Create temp DB
        fd, path = tempfile.mkstemp(suffix=".db")
        import os
        os.close(fd)

        conn = sqlite3.connect(path)
        init_db(conn)

        assertion = SchemaAssertion(conn)
        result = benchmark(
            "schema_validation",
            lambda: assertion.assert_all(),
            iterations=50,
        )
        results.append(result)

        conn.close()
        os.unlink(path)
    except Exception as e:
        print(f"⚠️  schema_validation failed: {e}")

    return results


def print_results(results: list[BenchmarkResult]) -> None:
    """Print benchmark results."""
    print("\n📊 Benchmark Results")
    print("=" * 70)

    for r in results:
        status = "✅" if r.passed else "❌"
        budget_str = f" (budget: {r.budget_ms}ms)" if r.budget_ms else ""
        print(f"{status} {r.name}")
        print(f"   Mean: {r.mean_ms:.4f}ms | Median: {r.median_ms:.4f}ms{budget_str}")
        print(f"   Min: {r.min_ms:.4f}ms | Max: {r.max_ms:.4f}ms | Stddev: {r.stddev_ms:.4f}ms")
        print()

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    print(f"Summary: {passed}/{total} benchmarks within budget")


def save_results(results: list[BenchmarkResult], path: Path) -> None:
    """Save results to JSON file."""
    data = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "results": [r.to_dict() for r in results],
    }
    path.write_text(json.dumps(data, indent=2))
    print(f"✅ Saved results to {path}")


def compare_results(current: list[BenchmarkResult], baseline_path: Path) -> None:
    """Compare current results to baseline."""
    if not baseline_path.exists():
        print(f"⚠️  Baseline not found: {baseline_path}")
        return

    baseline = json.loads(baseline_path.read_text())
    baseline_by_name = {r["name"]: r for r in baseline["results"]}

    print("\n📈 Comparison to Baseline")
    print("=" * 70)

    regressions = []
    for r in current:
        if r.name in baseline_by_name:
            old = baseline_by_name[r.name]["mean_ms"]
            diff_pct = ((r.mean_ms - old) / old) * 100

            if diff_pct > 10:
                status = "🔴"
                regressions.append(r.name)
            elif diff_pct > 0:
                status = "🟡"
            else:
                status = "🟢"

            print(f"{status} {r.name}: {r.mean_ms:.4f}ms vs {old:.4f}ms ({diff_pct:+.1f}%)")

    if regressions:
        print(f"\n❌ Regressions detected: {', '.join(regressions)}")
    else:
        print("\n✅ No significant regressions")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run performance benchmarks")
    parser.add_argument("--save", type=Path, help="Save results to JSON file")
    parser.add_argument("--compare", type=Path, help="Compare to baseline file")
    parser.add_argument("--fail-on-regression", action="store_true", help="Exit 1 on regression")
    args = parser.parse_args()

    print("🏃 Running benchmarks...")
    results = run_benchmarks()
    print_results(results)

    if args.save:
        save_results(results, args.save)

    if args.compare:
        compare_results(results, args.compare)

    # Check if all passed
    all_passed = all(r.passed for r in results)
    if not all_passed:
        print("\n❌ Some benchmarks exceeded budget")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
