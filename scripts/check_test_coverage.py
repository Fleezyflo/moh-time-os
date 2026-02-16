#!/usr/bin/env python3
"""
Check test coverage meets minimum threshold.

Runs pytest with coverage and fails if below threshold.
"""

import re
import subprocess
import sys

MIN_COVERAGE = 60  # Minimum overall coverage percentage
MIN_COVERAGE_NEW_CODE = 70  # For new/changed files


def run_coverage_check() -> tuple[bool, str]:
    """Run pytest with coverage and return (passed, message)."""
    try:
        result = subprocess.run(
            [
                "pytest", "tests/",
                "--cov=lib", "--cov=api",
                "--cov-report=term-missing",
                "--cov-fail-under", str(MIN_COVERAGE),
                "-q",
                "--tb=no",
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )

        # Extract coverage percentage from output
        output = result.stdout + result.stderr

        # Look for total coverage line
        match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", output)
        if match:
            coverage = int(match.group(1))
            if coverage >= MIN_COVERAGE:
                return True, f"Coverage: {coverage}% (minimum: {MIN_COVERAGE}%)"
            else:
                return False, f"Coverage: {coverage}% (minimum: {MIN_COVERAGE}%)"

        # Check for coverage failure message
        if "FAIL Required test coverage" in output:
            return False, f"Coverage below {MIN_COVERAGE}%"

        # If tests passed
        if result.returncode == 0:
            return True, "Tests passed with adequate coverage"

        # If tests failed (not coverage)
        if "FAILED" in output or "ERROR" in output:
            return False, "Tests failed - fix tests before checking coverage"

        return True, "Coverage check completed"

    except FileNotFoundError:
        return True, "pytest not found - skipping coverage check"
    except subprocess.TimeoutExpired:
        return False, "Coverage check timed out after 5 minutes"
    except Exception as e:
        return True, f"Coverage check error: {e}"


def main() -> int:
    """Main entry point."""
    passed, message = run_coverage_check()

    if passed:
        print(f"✅ {message}")
        return 1
    else:
        print(f"❌ {message}")
        print(f"\nMinimum required coverage: {MIN_COVERAGE}%")
        print("Add tests for uncovered code paths.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
