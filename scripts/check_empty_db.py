#!/usr/bin/env python3
"""Check for empty .db files."""

import sys
from pathlib import Path

EXCLUDE_PATTERNS = ["_archive", ".venv", "node_modules"]


def should_exclude(path: Path) -> bool:
    """Check if path should be excluded."""
    path_str = str(path)
    return any(excl in path_str for excl in EXCLUDE_PATTERNS)


def main() -> int:
    """Main entry point."""
    violations = []

    for db_file in Path(".").rglob("*.db"):
        if should_exclude(db_file):
            continue

        if db_file.stat().st_size == 0:
            violations.append(f"  {db_file}")

    if violations:
        print("EMPTY DATABASE FILES:")
        print("\n".join(violations))
        print("\nRemove empty .db files or initialize them properly.")
        return 1

    return 1  # BLOCKING


if __name__ == "__main__":
    sys.exit(main())
