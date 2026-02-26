#!/usr/bin/env python3
"""
Dead code detection for Python modules.

Uses vulture to find unused code in api/ and lib/.
Allowlist prevents false positives for:
- CLI entry points
- FastAPI route handlers
- Magic methods
- Test fixtures

Usage:
    uv run python scripts/check_dead_code.py [--update-allowlist]

Exit codes:
    0: No dead code found (or only allowlisted)
    1: Dead code found
"""

import argparse
import subprocess
import sys
from pathlib import Path

ALLOWLIST_FILE = Path(".vulture-allowlist.py")

# Targets to scan
TARGETS = ["api/", "lib/"]

# Default allowlist entries (false positives)
DEFAULT_ALLOWLIST = """# Vulture allowlist - known false positives
# Format: one_unused_thing  # comment

# FastAPI route handlers (discovered dynamically)
_.get
_.post
_.put
_.patch
_.delete
_.options
_.head

# Pydantic model validators
_.model_validator
_.field_validator
_.root_validator

# Click CLI decorators
_.command
_.group
_.option
_.argument

# Test fixtures
_.fixture
_.pytest_configure
_.pytest_collection_modifyitems

# Magic methods
_.__init__
_.__str__
_.__repr__
_.__call__
_.__enter__
_.__exit__
_.__iter__
_.__next__

# Class attributes used by frameworks
_.model_config
_.Config
_.Meta

# Collector registry pattern
_.OUTPUT_TABLES
_.COLLECTOR_NAME
_.collect
_.validate

# FastAPI dependencies
_.Depends
_.Query
_.Path
_.Body
_.Header

# Schema fields used by ORM
_.id
_.created_at
_.updated_at
"""


def ensure_allowlist() -> None:
    """Create allowlist file if it doesn't exist."""
    if not ALLOWLIST_FILE.exists():
        ALLOWLIST_FILE.write_text(DEFAULT_ALLOWLIST)
        print(f"Created {ALLOWLIST_FILE}")


def run_vulture() -> tuple[int, str]:
    """Run vulture and return exit code + output."""
    ensure_allowlist()

    cmd = [
        sys.executable,
        "-m",
        "vulture",
        *TARGETS,
        str(ALLOWLIST_FILE),
        "--min-confidence",
        "80",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


def filter_output(output: str) -> list[str]:
    """Filter vulture output to remove known patterns."""
    lines = output.strip().split("\n")
    filtered = []

    for line in lines:
        if not line.strip():
            continue
        # Skip common false positives not in allowlist
        if any(
            skip in line
            for skip in [
                "unused import",  # Handled by ruff
                "__pycache__",
                ".pyc",
            ]
        ):
            continue
        filtered.append(line)

    return filtered


def main() -> int:
    parser = argparse.ArgumentParser(description="Check for dead code")
    parser.add_argument(
        "--update-allowlist", action="store_true", help="Regenerate default allowlist"
    )
    args = parser.parse_args()

    if args.update_allowlist:
        ALLOWLIST_FILE.write_text(DEFAULT_ALLOWLIST)
        print(f"✅ Updated {ALLOWLIST_FILE}")
        return 0

    print("🔍 Checking for dead code (vulture)...")
    print(f"   Targets: {', '.join(TARGETS)}")
    print(f"   Allowlist: {ALLOWLIST_FILE}")
    print("")

    # Check if vulture is installed
    try:
        subprocess.run(
            [sys.executable, "-m", "vulture", "--version"], capture_output=True, check=True
        )
    except subprocess.CalledProcessError:
        print("⚠️  vulture not installed, skipping dead code check")
        print("   Install with: uv pip install vulture")
        return 0

    exit_code, output = run_vulture()
    findings = filter_output(output)

    if not findings:
        print("✅ No dead code found")
        return 0

    print(f"❌ Found {len(findings)} potential dead code items:\n")
    for finding in findings[:20]:
        print(f"   {finding}")

    if len(findings) > 20:
        print(f"\n   ... and {len(findings) - 20} more")

    print("\nTo allowlist false positives, add to .vulture-allowlist.py")
    return 1


if __name__ == "__main__":
    sys.exit(main())
