#!/usr/bin/env python3
"""
Check that new Python modules have corresponding test files.

For each lib/foo.py, expects tests/test_foo.py to exist.
Only checks staged/changed files in git.
"""

import subprocess
import sys
from pathlib import Path

# Directories that require tests
TESTABLE_DIRS = ["lib", "api", "engine"]

# Patterns to skip
SKIP_PATTERNS = [
    "__init__.py",
    "__pycache__",
    "_archive",
    "test_",
    "_test.py",
    "conftest.py",
]


def get_staged_files() -> list[Path]:
    """Get list of staged Python files."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=A"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            files = [Path(f.strip()) for f in result.stdout.strip().split("\n") if f.strip()]
            return [f for f in files if f.suffix == ".py"]
    except Exception:
        pass
    return []


def get_recently_added_files() -> list[Path]:
    """Get Python files added in recent commits (fallback)."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~5", "--diff-filter=A"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            files = [Path(f.strip()) for f in result.stdout.strip().split("\n") if f.strip()]
            return [f for f in files if f.suffix == ".py"]
    except Exception:
        pass
    return []


def should_skip(filepath: Path) -> bool:
    """Check if file should be skipped."""
    path_str = str(filepath)
    return any(pattern in path_str for pattern in SKIP_PATTERNS)


def get_expected_test_path(filepath: Path) -> Path | None:
    """Get expected test file path for a source file."""
    parts = list(filepath.parts)

    # Check if in testable directory
    if not parts or parts[0] not in TESTABLE_DIRS:
        return None

    # Convert lib/foo/bar.py -> tests/test_bar.py or tests/foo/test_bar.py
    filename = filepath.stem
    test_filename = f"test_{filename}.py"

    # Try multiple possible test locations
    possible_paths = [
        Path("tests") / test_filename,
        Path("tests") / parts[0] / test_filename,
    ]

    if len(parts) > 2:
        # For nested modules like lib/foo/bar.py -> tests/foo/test_bar.py
        subdir = "/".join(parts[1:-1])
        possible_paths.append(Path("tests") / subdir / test_filename)

    return possible_paths[0]  # Return primary expected location


def main() -> int:
    """Main entry point."""
    # Get new files
    new_files = get_staged_files()
    if not new_files:
        new_files = get_recently_added_files()

    if not new_files:
        print("✅ No new Python files to check.")
        return 0

    missing_tests = []

    for filepath in new_files:
        if should_skip(filepath):
            continue

        # Check if in testable directory
        if not any(str(filepath).startswith(d) for d in TESTABLE_DIRS):
            continue

        expected_test = get_expected_test_path(filepath)
        if expected_test is None:
            continue

        # Check if any test file exists for this module
        module_name = filepath.stem
        tests_dir = Path("tests")

        # Search for any test file containing this module name
        test_exists = False
        if tests_dir.exists():
            for test_file in tests_dir.rglob(f"test_*{module_name}*.py"):
                test_exists = True
                break
            for test_file in tests_dir.rglob(f"*{module_name}*_test.py"):
                test_exists = True
                break

        if not test_exists:
            missing_tests.append(f"  {filepath} -> expected: tests/test_{module_name}.py")

    if missing_tests:
        print("🧪 NEW CODE WITHOUT TESTS:")
        print("\n".join(missing_tests))
        print("\nAdd test files for new modules.")
        # BLOCKING, don't block
        return 1  # BLOCKING

    print("✅ All new modules have tests.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
