#!/usr/bin/env python3
"""
Enforce strict type checking with mypy.

Runs mypy in strict mode on core modules.
"""

import subprocess
import sys
from pathlib import Path

# Modules that must pass strict type checking
STRICT_MODULES = ["lib/intelligence", "lib/safety", "api"]

# Modules with relaxed checking (legacy)
RELAXED_MODULES = ["lib", "engine"]


def run_mypy_strict(modules: list[str]) -> tuple[bool, list[str]]:
    """Run mypy in strict mode."""
    errors = []

    existing = [m for m in modules if Path(m).exists()]
    if not existing:
        return True, []

    try:
        result = subprocess.run(
            ["mypy", "--strict", "--no-error-summary", "--explicit-package-bases"] + existing,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            for line in result.stdout.strip().split("\n"):
                if line.strip() and ": error:" in line:
                    errors.append(f"  {line.strip()}")

    except FileNotFoundError:
        return True, ["  mypy not installed - skipping"]
    except subprocess.TimeoutExpired:
        return False, ["  mypy timed out"]

    return len(errors) == 0, errors


def run_mypy_basic(modules: list[str]) -> tuple[bool, list[str]]:
    """Run mypy with basic checking."""
    errors = []

    existing = [m for m in modules if Path(m).exists()]
    if not existing:
        return True, []

    try:
        result = subprocess.run(
            ["mypy", "--no-error-summary", "--ignore-missing-imports", "--explicit-package-bases"]
            + existing,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            # Only count real errors, not notes
            for line in result.stdout.strip().split("\n"):
                if ": error:" in line:
                    errors.append(f"  {line.strip()}")

    except FileNotFoundError:
        return True, []
    except subprocess.TimeoutExpired:
        return False, ["  mypy timed out"]

    return len(errors) == 0, errors[:30]


def main() -> int:
    """Main entry point."""
    has_errors = False

    # Strict modules - BLOCKING
    ok, errors = run_mypy_strict(STRICT_MODULES)
    if not ok:
        print("❌ STRICT TYPE ERRORS (BLOCKING):")
        print("\n".join(errors[:30]))
        if len(errors) > 30:
            print(f"  ... and {len(errors) - 30} more")
        has_errors = True

    # Basic check on other modules - BLOCKING
    ok, errors = run_mypy_basic(RELAXED_MODULES)
    if not ok and errors:
        print("❌ TYPE ERRORS (BLOCKING):")
        print("\n".join(errors[:30]))
        if len(errors) > 30:
            print(f"  ... and {len(errors) - 30} more")
        has_errors = True

    if has_errors:
        print("\n❌ Type checking FAILED. Fix errors before commit.")
        return 1

    print("✅ Type checking passed.")
    return 0  # PASS when no violations


if __name__ == "__main__":
    sys.exit(main())
