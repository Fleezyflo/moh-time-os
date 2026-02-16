#!/usr/bin/env python3
"""Check for SQL f-string injection vulnerabilities in all Python directories."""

import re
import sys
from pathlib import Path

DIRS_TO_CHECK = ["lib", "api", "collectors", "engine", "cli", "scripts"]
EXCLUDE_PATTERNS = ["_archive", "__pycache__", ".venv"]

# Pattern: execute followed by f-string
SQL_FSTRING_PATTERN = re.compile(r'execute\s*\(\s*f["\']')


def should_exclude(path: Path) -> bool:
    """Check if path should be excluded."""
    path_str = str(path)
    return any(excl in path_str for excl in EXCLUDE_PATTERNS)


def check_file(filepath: Path) -> list[tuple[int, str]]:
    """Check a single file for SQL f-string injection."""
    violations = []
    try:
        content = filepath.read_text()
        for i, line in enumerate(content.splitlines(), 1):
            if SQL_FSTRING_PATTERN.search(line):
                # Skip if marked as safe (table/column names from code, not user input)
                if "# nosql" in line.lower() or "# safe:" in line.lower():
                    continue
                violations.append((i, line.strip()))
    except (OSError, UnicodeDecodeError):
        # Skip files that can't be read
        pass
    return violations


def main() -> int:
    """Main entry point."""
    all_violations = []

    for dir_name in DIRS_TO_CHECK:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            continue

        for py_file in dir_path.rglob("*.py"):
            if should_exclude(py_file):
                continue

            violations = check_file(py_file)
            for line_num, line in violations:
                all_violations.append(f"  {py_file}:{line_num}: {line}")

    if all_violations:
        print("SQL F-STRING INJECTION DETECTED:")
        print("\n".join(all_violations))
        print("\nUse parameterized queries instead: cursor.execute(sql, params)")
        return 1

    return 0  # PASS when no violations


if __name__ == "__main__":
    sys.exit(main())
