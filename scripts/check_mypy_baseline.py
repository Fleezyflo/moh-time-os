#!/usr/bin/env python3
"""
Mypy baseline check with strict islands enforcement.

Strict islands are directories that MUST have zero type errors.
Baseline covers legacy code where errors are tracked but not blocking.

Usage:
    uv run python scripts/check_mypy_baseline.py [--update] [--strict-only]

CI fails if:
- Any error in strict islands (api/, lib/safety/, lib/contracts/, lib/observability/)
- Baseline grows in legacy modules

With --update: regenerates baseline from current errors.
With --strict-only: only check strict islands (faster).
"""

import argparse
import subprocess
import sys
from pathlib import Path

BASELINE_FILE = Path(".mypy-baseline.txt")

# Strict islands: MUST be zero errors
STRICT_ISLANDS = [
    "api/spec_router.py",
    "lib/safety/",
    "lib/contracts/",
    "lib/observability/",
]

# Legacy modules: errors tracked in baseline
LEGACY_MODULES = [
    "api/server.py",
    "lib/collectors/",
    "lib/ui_spec_v21/",
]

MYPY_FLAGS = ["--ignore-missing-imports", "--explicit-package-bases", "--no-error-summary"]


def run_mypy(targets: list[str]) -> list[str]:
    """Run mypy on targets and capture errors."""
    if not targets:
        return []

    cmd = [
        sys.executable, "-m", "mypy",
        *targets,
        *MYPY_FLAGS,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    errors = []
    for line in result.stdout.split("\n") + result.stderr.split("\n"):
        if ": error:" in line:
            # Normalize path for comparison
            stripped = line.strip()
            if stripped.startswith(("api/", "lib/")):
                errors.append(stripped)

    return sorted(set(errors))


def load_baseline() -> list[str]:
    """Load baseline errors from file."""
    if not BASELINE_FILE.exists():
        return []
    return [line.strip() for line in BASELINE_FILE.read_text().split("\n") if line.strip()]


def save_baseline(errors: list[str]) -> None:
    """Save errors to baseline file."""
    BASELINE_FILE.write_text("\n".join(sorted(errors)) + "\n" if errors else "")


def categorize_errors(errors: list[str]) -> tuple[list[str], list[str]]:
    """Split errors into strict island errors and legacy errors."""
    strict_errors = []
    legacy_errors = []

    for error in errors:
        is_strict = any(error.startswith(island.rstrip("/")) for island in STRICT_ISLANDS)
        if is_strict:
            strict_errors.append(error)
        else:
            legacy_errors.append(error)

    return strict_errors, legacy_errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Check mypy baseline with strict islands")
    parser.add_argument("--update", action="store_true", help="Update baseline from current errors")
    parser.add_argument("--strict-only", action="store_true", help="Only check strict islands")
    args = parser.parse_args()

    # Determine targets
    if args.strict_only:
        targets = STRICT_ISLANDS
    else:
        targets = STRICT_ISLANDS + LEGACY_MODULES

    # Expand directory targets
    expanded_targets = []
    for target in targets:
        path = Path(target)
        if path.exists():
            expanded_targets.append(target)

    print(f"Checking: {', '.join(expanded_targets)}")

    current_errors = run_mypy(expanded_targets)
    strict_errors, legacy_errors = categorize_errors(current_errors)

    print(f"\n📊 Mypy Summary:")
    print(f"   Strict island errors: {len(strict_errors)}")
    print(f"   Legacy module errors: {len(legacy_errors)}")

    if args.update:
        save_baseline(legacy_errors)
        print(f"\n✅ Updated baseline: {len(legacy_errors)} legacy errors")
        if strict_errors:
            print(f"⚠️  Warning: {len(strict_errors)} strict island errors exist (not in baseline)")
            for err in strict_errors[:5]:
                print(f"   {err}")
            if len(strict_errors) > 5:
                print(f"   ... and {len(strict_errors) - 5} more")
        return 0

    # Check strict islands (must be zero)
    if strict_errors:
        print("\n❌ STRICT ISLAND ERRORS (must fix):")
        for error in strict_errors[:10]:
            print(f"   {error}")
        if len(strict_errors) > 10:
            print(f"   ... and {len(strict_errors) - 10} more")
        return 1

    # Check legacy baseline (must not grow)
    baseline_errors = load_baseline()
    new_errors = set(legacy_errors) - set(baseline_errors)
    fixed_errors = set(baseline_errors) - set(legacy_errors)

    print(f"   Baseline: {len(baseline_errors)} errors")

    if new_errors:
        print("\n❌ NEW LEGACY ERRORS (baseline grew):")
        for error in sorted(new_errors)[:10]:
            print(f"   + {error}")
        if len(new_errors) > 10:
            print(f"   ... and {len(new_errors) - 10} more")
        print("\nTo accept as new baseline:")
        print("   uv run python scripts/check_mypy_baseline.py --update")
        return 1

    if fixed_errors:
        print(f"\n✅ Fixed {len(fixed_errors)} errors! Consider updating baseline.")

    print("\n✅ Mypy check passed (strict islands clean, baseline stable)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
