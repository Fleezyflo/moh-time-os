#!/usr/bin/env python3
"""
Data fix: Set is_internal flag and run lane assignment.

Marks projects as internal based on name patterns, then runs the
lane assigner to update task lane assignments.

Usage:
    MOH_TIME_OS_DB=data/moh_time_os.db python scripts/fix_project_lanes.py

The script is idempotent and safe to run multiple times.
"""

import logging
import os
import sqlite3
import sys

# Ensure we can import lib/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Verify DB path is set
db_path_env = os.environ.get("MOH_TIME_OS_DB")
if not db_path_env:
    print("ERROR: Set MOH_TIME_OS_DB env var (e.g. MOH_TIME_OS_DB=data/moh_time_os.db)")
    sys.exit(1)

if not os.path.exists(db_path_env):
    print(f"ERROR: DB not found at {db_path_env}")
    sys.exit(1)

from lib import lane_assigner

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(name)s - %(levelname)s - %(message)s",
)

# Internal project name patterns (case-insensitive substring match)
INTERNAL_PATTERNS = [
    "invoice tracker",
    "crm",
    "traffic",
    "candidates",
    "equipment",
    "hires",
    "payroll",
    "reimbursement",
    "on-boarding",
    "onboarding",
    "off-boarding",
    "offboarding",
    "hr &",
    "hrmny",
    "managerial",
    "templates",
    "procurement",
    "office equipment",
    "timesheets",
    "marketing hub",
    "daily workflow",
    "launch | codename",
]


def get_conn(read_only: bool = False):
    """
    Get database connection.

    Args:
        read_only: If True, open in read-only mode for safety
    """
    uri = db_path_env if not read_only else f"file:{db_path_env}?mode=ro"
    conn = sqlite3.connect(uri, uri=read_only, timeout=30)
    conn.row_factory = sqlite3.Row
    if not read_only:
        # Disable synchronous mode for faster writes
        conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def count_current_internal():
    """Count projects currently marked as internal."""
    try:
        conn = get_conn(read_only=True)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM projects WHERE is_internal = 1")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except sqlite3.OperationalError as e:
        logger.error(f"Failed to count internal projects: {e}")
        raise


def get_lane_distribution(conn):
    """Get distribution of lanes across all tasks."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT lane, COUNT(*) as count
            FROM tasks
            WHERE lane IS NOT NULL
            GROUP BY lane
            ORDER BY count DESC
        """)
        return dict(cursor.fetchall())
    except sqlite3.OperationalError as e:
        logger.error(f"Failed to get lane distribution: {e}")
        return {}


def fix_is_internal():
    """Set is_internal=1 for projects matching internal patterns."""
    try:
        conn = get_conn()
        cursor = conn.cursor()

        # Get all projects
        cursor.execute("SELECT id, name FROM projects")
        projects = cursor.fetchall()

        marked = 0
        for project in projects:
            project_id = project["id"]
            project_name = (project["name"] or "").lower()

            # Check if name matches any internal pattern
            is_internal = 0
            for pattern in INTERNAL_PATTERNS:
                if pattern in project_name:
                    is_internal = 1
                    break

            if is_internal == 1:
                cursor.execute(
                    "UPDATE projects SET is_internal = ? WHERE id = ?",
                    (1, project_id),
                )
                marked += 1

        conn.commit()
        conn.close()

        return marked
    except sqlite3.OperationalError as e:
        logger.error(f"Failed to fix is_internal: {e}")
        raise


def get_lane_stats():
    """Get task lane statistics."""
    try:
        conn = get_conn(read_only=True)
        distribution = get_lane_distribution(conn)
        conn.close()
        return distribution
    except sqlite3.OperationalError as e:
        logger.error(f"Failed to get lane stats: {e}")
        return {}


def main():
    """Run the fix."""
    print("\n" + "=" * 60)
    print("MOH TIME OS: Project Lane Fix")
    print("=" * 60)

    try:
        # Get before state
        print("\n[BEFORE] Scanning database...")
        internal_before = count_current_internal()
        lanes_before = get_lane_stats()

        print(f"  Projects marked as internal: {internal_before}")
        print("  Task lane distribution:")
        for lane, count in sorted(lanes_before.items(), key=lambda x: -x[1]):
            print(f"    {lane}: {count}")

        # Fix is_internal
        print("\n[FIXING] Setting is_internal flag...")
        marked = fix_is_internal()
        print(f"  Marked {marked} projects as internal")

        # Run lane assigner
        print("\n[ASSIGNING] Running lane assigner...")
        result = lane_assigner.run_assignment()

        internal_after = count_current_internal()
        lanes_after = result["distribution"]
        changed_count = result["changed"]

        # Print after state
        print("\n[AFTER] Updated state:")
        print(f"  Projects marked as internal: {internal_after} (was {internal_before})")
        print(f"  Tasks with lane changes: {changed_count}")
        print("  Task lane distribution:")
        for lane, count in sorted(lanes_after.items(), key=lambda x: -x[1]):
            print(f"    {lane}: {count}")

        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Internal projects marked: {marked}")
        print(f"Tasks reassigned: {changed_count}")
        print("Status: OK")
        print("=" * 60 + "\n")

        return 0

    except Exception as e:
        logger.exception("Fix script failed")
        print(f"\nERROR: {e}")
        print("=" * 60 + "\n")
        return 1


if __name__ == "__main__":
    exit(main())
