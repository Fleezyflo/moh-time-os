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

# Legacy monoliths - these files existed before the check was enforced
# They are tracked but not blocking until refactored
# Format: filepath -> max_allowed_lines (baseline at time of enforcement)
LEGACY_MONOLITHS = {
    "lib/intelligence/signals.py": 2000,
    "lib/intelligence/patterns.py": 1700,
    "lib/ui_spec_v21/tests/test_spec_cases.py": 1700,
    "lib/agency_snapshot/client360_page10.py": 2500,
    "lib/agency_snapshot/comms_commitments_page11.py": 1600,
    "lib/agency_snapshot/comms_commitments.py": 1700,
    "lib/agency_snapshot/generator.py": 1700,
    "lib/agency_snapshot/client360.py": 2300,
    "api/server.py": 5500,
    "time-os-ui/src/components/RoomDrawer.tsx": 600,
    "time-os-ui/src/pages/Inbox.tsx": 850,
    "time-os-ui/src/pages/Issues.tsx": 600,
    "time-os-ui/src/pages/ClientDetailSpec.tsx": 850,
}


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

            filepath_str = str(py_file)
            lines = count_lines(py_file)

            # Check if file is in legacy baseline
            max_allowed = LEGACY_MONOLITHS.get(filepath_str, PYTHON_MAX_LINES)

            if lines > max_allowed:
                violations.append(f"  {py_file}: {lines} lines (max {max_allowed})")

    return violations


def check_tsx_files() -> list[str]:
    """Check TSX files for monolith violations."""
    violations = []

    if not UI_DIR.exists():
        return violations

    for tsx_file in UI_DIR.rglob("*.tsx"):
        if should_exclude(tsx_file):
            continue

        filepath_str = str(tsx_file)
        lines = count_lines(tsx_file)

        # Check if file is in legacy baseline
        max_allowed = LEGACY_MONOLITHS.get(filepath_str, TSX_MAX_LINES)

        if lines > max_allowed:
            violations.append(f"  {tsx_file}: {lines} lines (max {max_allowed})")

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
