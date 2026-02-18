#!/usr/bin/env python3
"""
Coverage threshold enforcement.

Enforces minimum coverage thresholds for critical modules.
CI fails if coverage drops below thresholds.

Usage:
    uv run python scripts/check_coverage.py [--html] [--fail-under 80]
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Coverage thresholds by module (critical modules have higher thresholds)
THRESHOLDS = {
    "lib/safety": 80,
    "lib/contracts": 80,
    "lib/observability": 70,
    "lib/collectors": 60,
    "api": 50,
}

# Global minimum
GLOBAL_MINIMUM = 40


def run_coverage(html: bool = False) -> dict:
    """Run pytest with coverage and return report."""
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "--cov=lib",
        "--cov=api",
        "--cov-report=json:coverage.json",
        "-v",
        "--tb=short",
    ]

    if html:
        cmd.append("--cov-report=html:htmlcov")

    subprocess.run(cmd, capture_output=True, text=True, check=False)

    # Parse coverage report
    coverage_file = Path("coverage.json")
    if not coverage_file.exists():
        print("❌ Coverage report not generated")
        return {}

    return json.loads(coverage_file.read_text())


def check_thresholds(coverage_data: dict) -> tuple[bool, list[str]]:
    """Check coverage against thresholds."""
    violations = []

    # Get per-file coverage
    files = coverage_data.get("files", {})

    # Aggregate by module
    module_coverage = {}
    for filepath, data in files.items():
        # Find which module this file belongs to
        for module in THRESHOLDS:
            if filepath.startswith(module):
                if module not in module_coverage:
                    module_coverage[module] = {"covered": 0, "total": 0}
                summary = data.get("summary", {})
                module_coverage[module]["covered"] += summary.get("covered_lines", 0)
                module_coverage[module]["total"] += summary.get("num_statements", 0)
                break

    # Check each module
    for module, threshold in THRESHOLDS.items():
        if module in module_coverage:
            mc = module_coverage[module]
            if mc["total"] > 0:
                pct = (mc["covered"] / mc["total"]) * 100
                if pct < threshold:
                    violations.append(f"{module}: {pct:.1f}% < {threshold}% threshold")

    # Check global coverage
    totals = coverage_data.get("totals", {})
    global_pct = totals.get("percent_covered", 0)
    if global_pct < GLOBAL_MINIMUM:
        violations.append(f"Global: {global_pct:.1f}% < {GLOBAL_MINIMUM}% minimum")

    return len(violations) == 0, violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Check coverage thresholds")
    parser.add_argument("--html", action="store_true", help="Generate HTML report")
    parser.add_argument("--fail-under", type=int, help="Override global minimum")
    args = parser.parse_args()

    if args.fail_under:
        global GLOBAL_MINIMUM
        GLOBAL_MINIMUM = args.fail_under

    print("📊 Running coverage analysis...")
    coverage_data = run_coverage(html=args.html)

    if not coverage_data:
        return 1

    passed, violations = check_thresholds(coverage_data)

    # Print summary
    totals = coverage_data.get("totals", {})
    print(f"\n📈 Global Coverage: {totals.get('percent_covered', 0):.1f}%")
    print(f"   Lines: {totals.get('covered_lines', 0)}/{totals.get('num_statements', 0)}")

    if violations:
        print("\n❌ Coverage violations:")
        for v in violations:
            print(f"   {v}")
        return 1

    print("\n✅ All coverage thresholds met")
    return 0


if __name__ == "__main__":
    sys.exit(main())
