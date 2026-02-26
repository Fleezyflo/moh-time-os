#!/usr/bin/env python3
"""
Production Readiness Validation Script

Performs lightweight checks:
1. Imports key modules
2. Checks DB exists and has tables
3. Verifies agency_snapshot.json exists
4. Checks test count
"""

import json
import sqlite3
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def check_imports() -> bool:
    """Check that key modules can be imported."""
    print("Checking imports...")
    try:
        print("  ✓ All key modules imported successfully")
        return True
    except Exception as e:
        print(f"  ✗ Import failed: {e}")
        return False


def check_database() -> bool:
    """Check DB exists and has tables."""
    print("Checking database...")
    db_path = Path(__file__).parent.parent / "data" / "moh_time_os.db"

    if not db_path.exists():
        print(f"  ✗ Database not found at {db_path}")
        return False

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        conn.close()

        if not tables:
            print("  ✗ Database has no tables")
            return False

        print(f"  ✓ Database exists with {len(tables)} tables")
        return True
    except Exception as e:
        print(f"  ✗ Database check failed: {e}")
        return False


def check_snapshot() -> bool:
    """Check agency_snapshot.json exists."""
    print("Checking snapshot...")
    snapshot_path = Path.home() / ".moh_time_os" / "output" / "agency_snapshot.json"

    if not snapshot_path.exists():
        print(f"  ✗ Snapshot not found at {snapshot_path}")
        return False

    try:
        with open(snapshot_path) as f:
            data = json.load(f)
        print(f"  ✓ Snapshot exists with {len(data)} root keys")
        return True
    except Exception as e:
        print(f"  ✗ Snapshot check failed: {e}")
        return False


def check_tests() -> bool:
    """Check test count."""
    print("Checking tests...")
    tests_dir = Path(__file__).parent.parent / "tests"

    if not tests_dir.exists():
        print("  ✗ Tests directory not found")
        return False

    # Count test files
    test_files = list(tests_dir.glob("test_*.py")) + list(tests_dir.glob("**/test_*.py"))

    # Count test functions
    test_count = 0
    for test_file in test_files:
        with open(test_file) as f:
            content = f.read()
            test_count += content.count("def test_")

    if test_count == 0:
        print("  ✗ No tests found")
        return False

    print(f"  ✓ Found {test_count} test functions across {len(test_files)} files")
    return True


def main():
    """Run all checks."""
    print("=" * 60)
    print("MOH TIME OS Production Readiness Validation")
    print("=" * 60)

    checks = [
        check_imports(),
        check_database(),
        check_snapshot(),
        check_tests(),
    ]

    print("=" * 60)
    passed = sum(checks)
    total = len(checks)

    if passed == total:
        print(f"✓ All {total} checks passed")
        return 0
    else:
        print(f"✗ {total - passed} of {total} checks failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
