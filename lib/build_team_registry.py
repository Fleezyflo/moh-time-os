"""
Build Team Member Registry

Populates team_members table from task assignees.
This enables capacity calculations.
"""

import logging
import sqlite3
import uuid
from datetime import datetime

from lib import paths

logger = logging.getLogger(__name__)


DB_PATH = paths.db_path()


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def build_team_registry() -> dict:
    """Build team member registry from task assignees."""
    conn = get_conn()
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    # Get distinct assignees with their most common lane
    cursor.execute("""
        SELECT
            assignee,
            (SELECT lane FROM tasks t2
             WHERE t2.assignee = t1.assignee
             GROUP BY lane
             ORDER BY COUNT(*) DESC
             LIMIT 1) as default_lane,
            COUNT(*) as task_count
        FROM tasks t1
        WHERE assignee IS NOT NULL
        AND assignee != 'unassigned'
        AND assignee != ''
        GROUP BY assignee
        ORDER BY task_count DESC
    """)
    assignees = cursor.fetchall()

    inserted = 0
    skipped = 0

    for a in assignees:
        name = a["assignee"]
        lane = a["default_lane"] or "ops"

        # Check if already exists
        cursor.execute(
            "SELECT id FROM team_members WHERE LOWER(name) = LOWER(?)", (name,)
        )
        if cursor.fetchone():
            skipped += 1
            continue

        # Try to infer email from name (hrmny pattern)
        # Most team members are name@hrmny.co
        name_parts = name.lower().split()
        email = f"{name_parts[0]}@hrmny.co" if name_parts else None

        # Insert
        member_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO team_members (id, name, email, default_lane, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (member_id, name, email, lane, now, now),
        )
        inserted += 1

    conn.commit()

    # Update tasks.assignee_id to point to team_members
    cursor.execute("""
        UPDATE tasks
        SET assignee_id = (
            SELECT id FROM team_members WHERE LOWER(name) = LOWER(tasks.assignee)
        )
        WHERE assignee IS NOT NULL
        AND assignee != 'unassigned'
        AND assignee_id IS NULL
    """)
    linked = cursor.rowcount
    conn.commit()

    conn.close()

    return {"inserted": inserted, "skipped": skipped, "tasks_linked": linked}


def run():
    """Run team registry build."""
    conn = get_conn()
    cursor = conn.cursor()

    # Count before
    cursor.execute("SELECT COUNT(*) as cnt FROM team_members")
    before = cursor.fetchone()["cnt"]

    logger.info("Building team registry...")
    result = build_team_registry()

    # Count after
    cursor.execute("SELECT COUNT(*) as cnt FROM team_members")
    after = cursor.fetchone()["cnt"]

    logger.info(f"\nTeam members: {before} → {after} (+{result['inserted']})")
    logger.info(f"Skipped (already existed): {result['skipped']}")
    logger.info(f"Tasks linked to members: {result['tasks_linked']}")
    # Show team members
    cursor.execute("""
        SELECT tm.name, tm.default_lane, tm.email,
               (SELECT COUNT(*) FROM tasks t WHERE t.assignee = tm.name) as task_count
        FROM team_members tm
        ORDER BY task_count DESC
        LIMIT 20
    """)
    rows = cursor.fetchall()
    logger.info(f"\nTeam members ({len(rows)}):")
    for r in rows:
        email = r["email"] or "no email"
        logger.info(
            f"  {r['name']:25} | {r['default_lane']:10} | {r['task_count']:4} tasks | {email}"
        )
    conn.close()
    return result


if __name__ == "__main__":
    run()
