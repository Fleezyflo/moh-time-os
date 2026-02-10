#!/usr/bin/env python3
"""
Migration Rehearsal Matrix.

Tests migrations from various starting points:
- Empty database
- Previous schema versions
- Last released schema

Usage:
    python scripts/migrate_matrix.py [--full]
"""

import argparse
import sqlite3
import sys
import tempfile
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.db import ensure_db_ready, SCHEMA_VERSION
from lib.safety import run_safety_migrations
from lib.safety.schema import SchemaAssertion

# Schema fixtures representing previous versions
SCHEMA_FIXTURES = {
    # Empty database (fresh install)
    "empty": None,
    # Version 8 (one behind current)
    "v8": """
        PRAGMA user_version = 8;
        CREATE TABLE IF NOT EXISTS clients (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            tier TEXT DEFAULT 'B'
        );
    """,
    # Minimal viable schema
    "minimal": """
        PRAGMA user_version = 1;
        CREATE TABLE IF NOT EXISTS clients (id TEXT PRIMARY KEY, name TEXT);
    """,
}


def create_test_db(fixture_name: str | None) -> str:
    """Create a test database with a specific fixture."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    if fixture_name and fixture_name in SCHEMA_FIXTURES:
        sql = SCHEMA_FIXTURES[fixture_name]
        if sql:
            conn = sqlite3.connect(db_path)
            conn.executescript(sql)
            conn.close()

    return db_path


def run_migration(db_path: str) -> dict:
    """Run migrations on a database and return results."""
    conn = sqlite3.connect(db_path)

    # Get starting version
    start_version = conn.execute("PRAGMA user_version").fetchone()[0]

    try:
        # Run safety migrations
        result = run_safety_migrations(conn)

        # Run main DB setup
        ensure_db_ready(conn)

        # Get final version
        end_version = conn.execute("PRAGMA user_version").fetchone()[0]

        # Verify schema assertions
        assertion = SchemaAssertion(conn)
        violations = assertion.assert_all()

        return {
            "success": True,
            "start_version": start_version,
            "end_version": end_version,
            "tables_created": result.get("tables_created", []),
            "violations": [v.message for v in violations],
        }

    except Exception as e:
        return {
            "success": False,
            "start_version": start_version,
            "error": str(e),
        }
    finally:
        conn.close()


def run_matrix(full: bool = False) -> list[dict]:
    """Run migration matrix tests."""
    results = []

    fixtures = ["empty", "v8"] if not full else list(SCHEMA_FIXTURES.keys())

    for fixture in fixtures:
        print(f"Testing migration from: {fixture}")

        db_path = create_test_db(fixture)
        try:
            result = run_migration(db_path)
            result["fixture"] = fixture
            results.append(result)

            if result["success"]:
                print(f"  ✅ {fixture}: v{result['start_version']} → v{result['end_version']}")
                if result.get("violations"):
                    print(f"     ⚠️  {len(result['violations'])} schema violations")
            else:
                print(f"  ❌ {fixture}: {result.get('error', 'Unknown error')}")

        finally:
            Path(db_path).unlink(missing_ok=True)

    return results


def main():
    parser = argparse.ArgumentParser(description="Migration rehearsal matrix")
    parser.add_argument("--full", action="store_true", help="Run full matrix")
    args = parser.parse_args()

    print("=" * 60)
    print("Migration Rehearsal Matrix")
    print(f"Target schema version: {SCHEMA_VERSION}")
    print("=" * 60)
    print()

    results = run_matrix(full=args.full)

    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)

    passed = sum(1 for r in results if r["success"])
    failed = len(results) - passed

    print(f"Passed: {passed}")
    print(f"Failed: {failed}")

    if failed > 0:
        print()
        print("Failures:")
        for r in results:
            if not r["success"]:
                print(f"  - {r['fixture']}: {r.get('error', 'Unknown')}")
        sys.exit(1)

    print()
    print("✅ All migrations successful")


if __name__ == "__main__":
    main()
