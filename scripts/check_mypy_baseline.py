#!/usr/bin/env python3
"""
Check mypy errors against baseline.

Usage:
    uv run python scripts/check_mypy_baseline.py [--update]

CI fails if:
- New errors are introduced (baseline grows)
- Passing means baseline can shrink (encourage fixes)

With --update: regenerates baseline from current errors.
"""

import argparse
import subprocess
import sys
from pathlib import Path

BASELINE_FILE = Path(".mypy-baseline.txt")
MYPY_TARGETS = ["api/", "lib/safety/", "lib/contracts/", "lib/observability/"]
MYPY_FLAGS = ["--ignore-missing-imports", "--explicit-package-bases"]


def run_mypy() -> list[str]:
    """Run mypy and capture errors."""
    cmd = [
        sys.executable, "-m", "mypy",
        *MYPY_TARGETS,
        *MYPY_FLAGS,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    errors = []
    for line in result.stdout.split("\n"):
        if ": error:" in line and line.startswith(("api/", "lib/")):
            errors.append(line.strip())

    return sorted(errors)


def load_baseline() -> list[str]:
    """Load baseline errors from file."""
    if not BASELINE_FILE.exists():
        return []
    return [line.strip() for line in BASELINE_FILE.read_text().split("\n") if line.strip()]


def save_baseline(errors: list[str]) -> None:
    """Save errors to baseline file."""
    BASELINE_FILE.write_text("\n".join(errors) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check mypy baseline")
    parser.add_argument("--update", action="store_true", help="Update baseline from current errors")
    args = parser.parse_args()

    current_errors = run_mypy()
    baseline_errors = load_baseline()

    if args.update:
        save_baseline(current_errors)
        print(f"✅ Updated baseline: {len(current_errors)} errors")
        return 0

    # Check for new errors
    new_errors = set(current_errors) - set(baseline_errors)
    fixed_errors = set(baseline_errors) - set(current_errors)

    print(f"Baseline: {len(baseline_errors)} errors")
    print(f"Current:  {len(current_errors)} errors")
    print(f"New:      {len(new_errors)}")
    print(f"Fixed:    {len(fixed_errors)}")

    if new_errors:
        print("\n❌ NEW ERRORS (not in baseline):")
        for error in sorted(new_errors):
            print(f"   + {error}")
        print("\nTo accept these as new baseline:")
        print("   uv run python scripts/check_mypy_baseline.py --update")
        return 1

    if fixed_errors:
        print("\n✅ FIXED (can update baseline):")
        for error in sorted(fixed_errors)[:10]:
            print(f"   - {error}")
        if len(fixed_errors) > 10:
            print(f"   ... and {len(fixed_errors) - 10} more")
        print("\nConsider updating baseline to lock in improvements:")
        print("   uv run python scripts/check_mypy_baseline.py --update")

    print("\n✅ Mypy baseline check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
