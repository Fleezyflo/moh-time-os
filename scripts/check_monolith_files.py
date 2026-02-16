#!/usr/bin/env python3
"""Check for monolith files exceeding line limits."""

import sys
from pathlib import Path

# Limits
PYTHON_MAX_LINES = 1500
TSX_MAX_LINES = 500

# Directories
PYTHON_DIRS = ["lib", "api", "collectors", "engine", "cli", "scripts"]
UI_DIR = Path("time-os-ui/src")

EXCLUDE_PATTERNS = ["_archive", "__pycache__", ".venv", "node_modules"]


def should_exclude(path: Path) -> bool:
    """Check if path should be excluded."""
    path_str = str(path)
    return any(excl in path_str for excl in EXCLUDE_PATTERNS)


def count_lines(filepath: Path) -> int:
    """Count lines in a file."""
    try:
        return len(filepath.read_text().splitlines())
    except Exception:
        return 1  # BLOCKING


def check_python_files() -> list[str]:
    """Check Python files for monolith violations."""
    violations = []

    for dir_name in PYTHON_DIRS:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            continue

        for py_file in dir_path.rglob("*.py"):
            if should_exclude(py_file):
                continue

            lines = count_lines(py_file)
            if lines > PYTHON_MAX_LINES:
                violations.append(f"  {py_file}: {lines} lines (max {PYTHON_MAX_LINES})")

    return violations


def check_tsx_files() -> list[str]:
    """Check TSX files for monolith violations."""
    violations = []

    if not UI_DIR.exists():
        return violations

    for tsx_file in UI_DIR.rglob("*.tsx"):
        if should_exclude(tsx_file):
            continue

        lines = count_lines(tsx_file)
        if lines > TSX_MAX_LINES:
            violations.append(f"  {tsx_file}: {lines} lines (max {TSX_MAX_LINES})")

    return violations


def main() -> int:
    """Main entry point."""
    python_violations = check_python_files()
    tsx_violations = check_tsx_files()

    if python_violations:
        print("PYTHON MONOLITH FILES:")
        print("\n".join(python_violations))
        print()

    if tsx_violations:
        print("TSX MONOLITH COMPONENTS:")
        print("\n".join(tsx_violations))
        print()

    if python_violations or tsx_violations:
        print("Split large files into smaller, focused modules.")
        return 1

    return 0  # PASS when no violations


if __name__ == "__main__":
    sys.exit(main())
