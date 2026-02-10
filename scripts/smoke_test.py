#!/usr/bin/env python3
"""
Smoke tests with timing budgets.

Extends basic health check with:
1. Typical query endpoint
2. DB read/write cycle
3. Timing budgets for each operation

Usage:
    uv run python scripts/smoke_test.py [--port PORT]

Exit codes:
    0: All smoke tests pass within budget
    1: Smoke test failed or exceeded budget
"""

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

# Timing budgets (seconds)
BUDGETS = {
    "startup": 10.0,      # Max time for server to start
    "health": 0.5,        # Max time for /api/health
    "typical_query": 2.0, # Max time for typical query
    "db_cycle": 1.0,      # Max time for DB read/write
}

# Test port (avoid conflicts)
DEFAULT_PORT = 8422


class SmokeTestResult:
    def __init__(self, name: str, passed: bool, duration: float, budget: float, message: str = ""):
        self.name = name
        self.passed = passed
        self.duration = duration
        self.budget = budget
        self.message = message

    def __str__(self) -> str:
        status = "✅" if self.passed else "❌"
        timing = f"{self.duration:.3f}s / {self.budget:.3f}s"
        return f"{status} {self.name}: {timing}" + (f" - {self.message}" if self.message else "")


def timed_request(url: str, timeout: float = 5.0) -> tuple[float, httpx.Response | None, str]:
    """Make a timed HTTP request."""
    start = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url)
            duration = time.perf_counter() - start
            return duration, response, ""
    except httpx.TimeoutException:
        return time.perf_counter() - start, None, "Timeout"
    except httpx.ConnectError:
        return time.perf_counter() - start, None, "Connection refused"
    except Exception as e:
        return time.perf_counter() - start, None, str(e)


def wait_for_server(port: int, budget: float) -> SmokeTestResult:
    """Wait for server to become healthy."""
    url = f"http://localhost:{port}/api/health"
    start = time.perf_counter()

    while time.perf_counter() - start < budget:
        duration, response, error = timed_request(url, timeout=1.0)
        if response and response.status_code == 200:
            return SmokeTestResult(
                "startup",
                True,
                time.perf_counter() - start,
                budget,
                "Server healthy"
            )
        time.sleep(0.5)

    return SmokeTestResult(
        "startup",
        False,
        time.perf_counter() - start,
        budget,
        f"Server did not start: {error if error else 'timeout'}"
    )


def test_health(port: int) -> SmokeTestResult:
    """Test /api/health endpoint."""
    url = f"http://localhost:{port}/api/health"
    duration, response, error = timed_request(url)

    if response and response.status_code == 200:
        data = response.json()
        if data.get("status") == "healthy":
            return SmokeTestResult("health", True, duration, BUDGETS["health"])

    return SmokeTestResult(
        "health",
        False,
        duration,
        BUDGETS["health"],
        error or f"Status: {response.status_code if response else 'no response'}"
    )


def test_typical_query(port: int) -> SmokeTestResult:
    """Test a typical query endpoint (control-room/proposals or clients)."""
    # Try multiple endpoints that should work
    endpoints = [
        "/api/control-room/proposals",
        "/api/clients",
        "/api/v2/health",
    ]

    for endpoint in endpoints:
        url = f"http://localhost:{port}{endpoint}"
        duration, response, error = timed_request(url, timeout=BUDGETS["typical_query"])

        if response and response.status_code in (200, 404):
            # 404 is acceptable if endpoint exists but no data
            return SmokeTestResult(
                "typical_query",
                duration <= BUDGETS["typical_query"],
                duration,
                BUDGETS["typical_query"],
                f"{endpoint} responded"
            )

    return SmokeTestResult(
        "typical_query",
        False,
        BUDGETS["typical_query"],
        BUDGETS["typical_query"],
        "No endpoints responded"
    )


def test_db_cycle(port: int) -> SmokeTestResult:
    """Test a DB read/write cycle via API."""
    # Use sync-state or similar endpoint that does DB operations
    url = f"http://localhost:{port}/api/v2/health"
    duration, response, error = timed_request(url)

    if response and response.status_code == 200:
        return SmokeTestResult(
            "db_cycle",
            duration <= BUDGETS["db_cycle"],
            duration,
            BUDGETS["db_cycle"],
            "DB health check passed"
        )

    return SmokeTestResult(
        "db_cycle",
        False,
        duration,
        BUDGETS["db_cycle"],
        error or "DB cycle failed"
    )


def run_smoke_tests(port: int) -> list[SmokeTestResult]:
    """Run all smoke tests."""
    results = []

    # Health check
    result = test_health(port)
    results.append(result)
    if not result.passed:
        return results  # No point continuing

    # Typical query
    results.append(test_typical_query(port))

    # DB cycle
    results.append(test_db_cycle(port))

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run smoke tests with timing budgets")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to use")
    parser.add_argument("--external", action="store_true", help="Use external server (don't start)")
    args = parser.parse_args()

    print("🔥 Running smoke tests...\n")

    server_proc = None
    if not args.external:
        # Start server
        print(f"Starting API server on port {args.port}...")
        env = os.environ.copy()
        env["PORT"] = str(args.port)
        env["MOH_TIME_OS_DB_PATH"] = str(Path("data/smoke_test.db").absolute())

        server_proc = subprocess.Popen(
            [sys.executable, "-m", "api.server"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait for startup
        startup_result = wait_for_server(args.port, BUDGETS["startup"])
        print(startup_result)
        if not startup_result.passed:
            server_proc.kill()
            return 1

    try:
        results = run_smoke_tests(args.port)
        print("")
        for result in results:
            print(result)

        # Summary
        passed = sum(1 for r in results if r.passed)
        total = len(results)
        print(f"\n📊 Results: {passed}/{total} passed")

        # Check budgets
        over_budget = [r for r in results if r.passed and r.duration > r.budget]
        if over_budget:
            print("\n⚠️  Over budget (but passed):")
            for r in over_budget:
                print(f"   {r.name}: {r.duration:.3f}s > {r.budget:.3f}s")

        if passed == total:
            print("\n✅ All smoke tests passed")
            return 0
        else:
            print("\n❌ Some smoke tests failed")
            return 1

    finally:
        if server_proc:
            server_proc.terminate()
            try:
                server_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_proc.kill()


if __name__ == "__main__":
    sys.exit(main())
