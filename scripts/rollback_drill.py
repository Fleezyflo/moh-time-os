#!/usr/bin/env python3
"""
Database Rollback Drill.

Tests the backup → migrate → smoke → restore → smoke cycle.

Usage:
    python scripts/rollback_drill.py
"""

import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.db import SCHEMA_VERSION, run_migrations
from lib.safety import run_safety_migrations


def run_smoke_check(conn: sqlite3.Connection) -> tuple[bool, str]:
    """Run basic smoke check on database."""
    try:
        # Check tables exist
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = [t[0] for t in tables]

        if "clients" not in table_names:
            return False, "Missing clients table"

        # Check version
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version < 1:
            return False, f"Invalid schema version: {version}"

        # Check we can query
        conn.execute("SELECT COUNT(*) FROM clients")

        return True, f"OK (v{version}, {len(table_names)} tables)"

    except Exception as e:
        return False, str(e)


def run_drill() -> bool:
    """Run the full rollback drill."""
    print("=" * 60)
    print("Database Rollback Drill")
    print("=" * 60)
    print()

    # Create a temporary working directory
    with tempfile.TemporaryDirectory() as work_dir:
        work_path = Path(work_dir)
        db_path = work_path / "test.db"
        backup_path = work_path / "test.db.backup"

        # Step 1: Create initial database with data
        print("Step 1: Create initial database with test data")
        conn = sqlite3.connect(str(db_path))
        run_migrations(conn)
        run_safety_migrations(conn)  # After main migrations (triggers need tables)

        # Insert test data
        conn.execute("""
            INSERT OR REPLACE INTO clients (id, name, tier)
            VALUES ('drill-001', 'Drill Client', 'A')
        """)
        conn.commit()

        ok, msg = run_smoke_check(conn)
        if not ok:
            print(f"  ❌ Initial smoke failed: {msg}")
            return False
        print(f"  ✅ Initial state: {msg}")

        # Step 2: Create backup
        print()
        print("Step 2: Create backup")
        conn.close()
        shutil.copy(db_path, backup_path)
        print(f"  ✅ Backup created: {backup_path.stat().st_size} bytes")

        # Step 3: Make changes (simulate migration)
        print()
        print("Step 3: Apply changes (simulate migration)")
        conn = sqlite3.connect(str(db_path))

        # Add some changes
        conn.execute("""
            INSERT INTO clients (id, name, tier)
            VALUES ('drill-002', 'New Client', 'B')
        """)
        conn.commit()

        count = conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        print(f"  ✅ Changes applied: {count} clients now")

        ok, msg = run_smoke_check(conn)
        if not ok:
            print(f"  ❌ Post-change smoke failed: {msg}")
            return False
        print(f"  ✅ Post-change smoke: {msg}")
        conn.close()

        # Step 4: Restore from backup
        print()
        print("Step 4: Restore from backup")
        shutil.copy(backup_path, db_path)
        print("  ✅ Backup restored")

        # Step 5: Verify restored state
        print()
        print("Step 5: Verify restored state")
        conn = sqlite3.connect(str(db_path))

        count = conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        print(f"  📊 Client count: {count}")

        # Verify test client exists
        row = conn.execute("SELECT id FROM clients WHERE id = 'drill-001'").fetchone()
        if not row:
            print("  ❌ Original data not restored")
            return False
        print("  ✅ Original data present")

        # Verify new client NOT present (rolled back)
        row = conn.execute("SELECT id FROM clients WHERE id = 'drill-002'").fetchone()
        if row:
            print("  ❌ New data should have been rolled back")
            return False
        print("  ✅ Changes successfully rolled back")

        ok, msg = run_smoke_check(conn)
        if not ok:
            print(f"  ❌ Final smoke failed: {msg}")
            return False
        print(f"  ✅ Final smoke: {msg}")

        conn.close()

    print()
    print("=" * 60)
    print("✅ Rollback drill completed successfully")
    print("=" * 60)
    return True


def main():
    success = run_drill()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
