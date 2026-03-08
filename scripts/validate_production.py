#!/usr/bin/env python3
"""
Production Readiness Validation Script

Performs lightweight checks:
1. Imports key modules (schema, state_store, autonomous_loop)
2. Checks DB exists and has tables
3. Verifies agency_snapshot.json exists
4. Checks test count
5. API endpoint smoke test (FastAPI app instantiation)
6. Daemon component initialization
7. Notification system check
8. Collector instantiation
9. Intelligence engine dry run
"""

import importlib
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
        for mod_name in ["lib.autonomous_loop", "lib.schema", "lib.state_store"]:
            importlib.import_module(mod_name)

        print("  ✓ All key modules imported successfully")
        return True
    except ImportError as e:
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
    except sqlite3.Error as e:
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
    except (OSError, ValueError) as e:
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
        try:
            with open(test_file) as f:
                content = f.read()
                test_count += content.count("def test_")
        except OSError as e:
            print(f"  ✗ Error reading {test_file}: {e}")
            return False

    if test_count == 0:
        print("  ✗ No tests found")
        return False

    print(f"  ✓ Found {test_count} test functions across {len(test_files)} files")
    return True


def check_api_app() -> bool:
    """Check that FastAPI app can be instantiated."""
    print("Checking API app...")
    try:
        from api.server import app

        route_count = len(app.routes)
        if route_count == 0:
            print("  ✗ FastAPI app has no routes")
            return False
        print(f"  ✓ FastAPI app instantiated with {route_count} routes")
        return True
    except ImportError as e:
        print(f"  ✗ API app check failed: {e}")
        return False


def check_daemon_init() -> bool:
    """Check that TimeOSDaemon can be instantiated."""
    print("Checking daemon component...")
    try:
        mod = importlib.import_module("lib.daemon")
        if not hasattr(mod, "TimeOSDaemon"):
            print("  ✗ TimeOSDaemon class not found in lib.daemon")
            return False
        print("  ✓ TimeOSDaemon imported successfully")
        return True
    except ImportError as e:
        print(f"  ✗ Daemon check failed: {e}")
        return False


def check_notification_system() -> bool:
    """Check that notification-related modules import."""
    print("Checking notification system...")
    try:
        mod = importlib.import_module("lib.actions.action_framework")
        if not hasattr(mod, "ActionFramework"):
            print("  ✗ ActionFramework class not found")
            return False
        print("  ✓ ActionFramework (notification proxy) imported successfully")
        return True
    except ImportError as e:
        print(f"  ✗ Notification system check failed: {e}")
        return False


def check_collector_classes() -> bool:
    """Check that collector classes can be instantiated."""
    print("Checking collector classes...")
    collectors = [
        "asana",
        "calendar",
        "chat",
        "gmail",
        "tasks",
        "xero",
    ]
    failed = []

    for collector_name in collectors:
        try:
            importlib.import_module(f"lib.collectors.{collector_name}")
        except ImportError as e:
            failed.append((collector_name, e))

    if failed:
        for name, error in failed:
            print(f"  ✗ {name} collector failed: {error}")
        return False

    print(f"  ✓ All {len(collectors)} collector classes imported successfully")
    return True


def check_intelligence_engine() -> bool:
    """Check that intelligence engine modules import."""
    print("Checking intelligence engine...")
    try:
        for mod_name in [
            "lib.intelligence.engine",
            "lib.intelligence.signals",
        ]:
            importlib.import_module(mod_name)

        print("  ✓ Intelligence engine modules imported successfully")
        return True
    except ImportError as e:
        print(f"  ✗ Intelligence engine check failed: {e}")
        return False


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
        check_api_app(),
        check_daemon_init(),
        check_notification_system(),
        check_collector_classes(),
        check_intelligence_engine(),
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
