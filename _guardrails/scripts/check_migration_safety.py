#!/usr/bin/env python3
"""
Check for unsafe database migrations.

Flags destructive operations without explicit approval:
- DROP TABLE
- DROP COLUMN
- DELETE FROM (without WHERE)
- TRUNCATE
- ALTER TABLE ... DROP
"""

import re
import sys
from pathlib import Path

MIGRATION_DIRS = [
    Path("lib/migrations"),
    Path("migrations"),
    Path("alembic/versions"),
]

EXCLUDE_PATTERNS = ["_archive", "__pycache__", ".venv"]

# Dangerous patterns in SQL
DANGEROUS_PATTERNS = [
    (r"\bDROP\s+TABLE\b", "DROP TABLE"),
    (r"\bDROP\s+COLUMN\b", "DROP COLUMN"),
    (r"\bDELETE\s+FROM\s+\w+\s*(?:;|$)", "DELETE without WHERE"),
    (r"\bTRUNCATE\b", "TRUNCATE"),
    (r"\bALTER\s+TABLE\s+\w+\s+DROP\b", "ALTER TABLE DROP"),
]

# Approval marker
APPROVAL_MARKER = "# APPROVED_DESTRUCTIVE:"


def should_exclude(path: Path) -> bool:
    """Check if path should be excluded."""
    path_str = str(path)
    return any(excl in path_str for excl in EXCLUDE_PATTERNS)


def check_file(filepath: Path) -> list[str]:
    """Check a migration file for dangerous operations."""
    violations = []

    try:
        content = filepath.read_text()
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            # Skip if line has approval marker
            if APPROVAL_MARKER in line:
                continue

            # Skip comments
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("--"):
                continue

            for pattern, name in DANGEROUS_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    violations.append(f"  {filepath}:{i}: {name}\n    {line.strip()[:80]}")
                    break

    except (OSError, UnicodeDecodeError):
        pass

    return violations


def main() -> int:
    """Main entry point."""
    all_violations = []

    for migration_dir in MIGRATION_DIRS:
        if not migration_dir.exists():
            continue

        for py_file in migration_dir.rglob("*.py"):
            if should_exclude(py_file):
                continue

            violations = check_file(py_file)
            all_violations.extend(violations)

        for sql_file in migration_dir.rglob("*.sql"):
            if should_exclude(sql_file):
                continue

            violations = check_file(sql_file)
            all_violations.extend(violations)

    if all_violations:
        print("💥 UNSAFE MIGRATION OPERATIONS:")
        print("\n".join(all_violations[:20]))
        if len(all_violations) > 20:
            print(f"  ... and {len(all_violations) - 20} more")
        print("\nThese operations can cause data loss.")
        print("To approve, add comment: # APPROVED_DESTRUCTIVE: <reason>")
        return 1

    print("✅ No unsafe migration operations found.")
    return 0  # PASS when no violations


if __name__ == "__main__":
    sys.exit(main())
