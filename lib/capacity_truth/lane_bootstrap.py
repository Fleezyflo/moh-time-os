"""
Capacity lane bootstrap — creates lanes from team_members.default_lane
and maps tasks to lanes through assignee matching.

Usage:
    from lib.capacity_truth.lane_bootstrap import bootstrap_lanes, lane_load_report

    result = bootstrap_lanes(db_path)
    report = lane_load_report(db_path)
"""

import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from lib.paths import db_path as canonical_db_path

logger = logging.getLogger(__name__)

# Lane display names and config overrides
LANE_CONFIG = {
    "growth": {
        "display_name": "Growth & Strategy",
        "weekly_hours": 45,
        "buffer_pct": 0.15,
        "color": "#4CAF50",
    },
    "client": {
        "display_name": "Client Services",
        "weekly_hours": 40,
        "buffer_pct": 0.20,
        "color": "#2196F3",
    },
    "creative": {
        "display_name": "Creative",
        "weekly_hours": 40,
        "buffer_pct": 0.20,
        "color": "#9C27B0",
    },
    "finance": {
        "display_name": "Finance",
        "weekly_hours": 40,
        "buffer_pct": 0.20,
        "color": "#FF9800",
    },
    "ops": {
        "display_name": "Operations",
        "weekly_hours": 40,
        "buffer_pct": 0.20,
        "color": "#607D8B",
    },
    "music": {
        "display_name": "Music",
        "weekly_hours": 40,
        "buffer_pct": 0.20,
        "color": "#E91E63",
    },
    "people": {
        "display_name": "People & Culture",
        "weekly_hours": 40,
        "buffer_pct": 0.20,
        "color": "#00BCD4",
    },
}

DEFAULT_LANE = {
    "weekly_hours": 40,
    "buffer_pct": 0.20,
    "color": "#9E9E9E",
}


def _get_db_path(db_path: Optional[str] = None) -> str:
    if db_path:
        return str(db_path)
    return str(canonical_db_path())


def bootstrap_lanes(
    db_path: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    """
    Create capacity lanes from team_members.default_lane values.

    - Extracts unique default_lane values from team_members
    - Creates one capacity_lane per unique lane
    - Skips lanes that already exist

    Returns:
        {"created": N, "skipped": N, "lanes": [...], "dry_run": bool}
    """
    db = _get_db_path(db_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    now = datetime.now(timezone.utc).isoformat()

    # Get unique lanes from team_members
    rows = conn.execute(
        "SELECT DISTINCT default_lane FROM team_members "
        "WHERE default_lane IS NOT NULL AND default_lane != ''"
    ).fetchall()
    unique_lanes = [r["default_lane"] for r in rows]

    # Get existing lanes
    existing = conn.execute("SELECT name FROM capacity_lanes").fetchall()
    existing_names = {r["name"] for r in existing}

    created = 0
    skipped = 0
    lanes = []

    for lane_name in unique_lanes:
        if lane_name in existing_names:
            skipped += 1
            continue

        config = LANE_CONFIG.get(lane_name, {})
        display_name = config.get("display_name", lane_name.title())
        weekly_hours = config.get("weekly_hours", DEFAULT_LANE["weekly_hours"])
        buffer_pct = config.get("buffer_pct", DEFAULT_LANE["buffer_pct"])
        color = config.get("color", DEFAULT_LANE["color"])

        lane_id = f"lane_{lane_name}"

        lane_data = {
            "id": lane_id,
            "name": lane_name,
            "display_name": display_name,
            "weekly_hours": weekly_hours,
            "buffer_pct": buffer_pct,
            "color": color,
        }
        lanes.append(lane_data)

        if not dry_run:
            conn.execute(
                "INSERT INTO capacity_lanes (id, name, display_name, owner, weekly_hours, buffer_pct, color, created_at, updated_at) "
                "VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?)",
                (lane_id, lane_name, display_name, weekly_hours, buffer_pct, color, now, now),
            )
        created += 1

    if not dry_run:
        conn.commit()

    conn.close()

    return {
        "created": created,
        "skipped": skipped,
        "lanes": lanes,
        "dry_run": dry_run,
    }


def assign_tasks_to_lanes(
    db_path: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    """
    Map tasks to lanes through: task.assignee → team_members.name → team_members.default_lane.

    Adds a lane_id column to tasks if it doesn't exist, then updates it.

    Returns:
        {"assigned": N, "unmatched": N, "dry_run": bool}
    """
    db = _get_db_path(db_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    # Ensure lane_id column exists
    columns = [
        r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()
    ]
    if "lane_id" not in columns:
        if not dry_run:
            conn.execute("ALTER TABLE tasks ADD COLUMN lane_id TEXT")
            conn.commit()

    # Build assignee → lane_id mapping
    team_rows = conn.execute(
        "SELECT name, default_lane FROM team_members "
        "WHERE default_lane IS NOT NULL AND default_lane != ''"
    ).fetchall()

    # Map: assignee name → lane_id
    name_to_lane = {}
    for row in team_rows:
        lane_id = f"lane_{row['default_lane']}"
        name_to_lane[row["name"].lower()] = lane_id

    # Get tasks with assignees
    tasks = conn.execute(
        "SELECT rowid, assignee FROM tasks "
        "WHERE assignee IS NOT NULL AND assignee != ''"
    ).fetchall()

    assigned = 0
    unmatched = 0
    updates = []

    for task in tasks:
        assignee = task["assignee"].strip().lower()
        lane_id = name_to_lane.get(assignee)

        if lane_id:
            updates.append((lane_id, task["rowid"]))
            assigned += 1
        else:
            unmatched += 1

    if not dry_run and updates:
        conn.executemany(
            "UPDATE tasks SET lane_id = ? WHERE rowid = ?",
            updates,
        )
        conn.commit()

    conn.close()

    return {
        "assigned": assigned,
        "unmatched": unmatched,
        "total_with_assignee": len(tasks),
        "dry_run": dry_run,
    }


def lane_load_report(db_path: Optional[str] = None) -> dict:
    """
    Generate per-lane workload report.

    Returns:
        {
            "lanes": [
                {
                    "lane_id": ..., "name": ..., "display_name": ...,
                    "weekly_hours": ..., "buffer_pct": ...,
                    "team_count": N, "total_tasks": N, "active_tasks": N, "overdue_tasks": N,
                    "members": [{"name": ..., "task_count": N, "overdue_count": N}, ...]
                },
                ...
            ],
            "summary": {"total_lanes": N, "total_people": N, "total_tasks_in_lanes": N}
        }
    """
    db = _get_db_path(db_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    # Get lanes
    lanes = conn.execute("SELECT * FROM capacity_lanes ORDER BY name").fetchall()

    result_lanes = []
    total_people = 0
    total_tasks_in_lanes = 0

    for lane in lanes:
        lane_name = lane["name"]
        lane_id = lane["id"]

        # Get team members in this lane
        members = conn.execute(
            "SELECT name FROM team_members WHERE default_lane = ? ORDER BY name",
            (lane_name,),
        ).fetchall()
        member_names = [m["name"] for m in members]

        # Check if lane_id column exists on tasks
        columns = [r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]
        has_lane_id = "lane_id" in columns

        member_details = []
        lane_total = 0
        lane_active = 0
        lane_overdue = 0

        for member_name in member_names:
            # Count tasks by assignee
            task_count = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE LOWER(assignee) = LOWER(?)",
                (member_name,),
            ).fetchone()[0]

            overdue_count = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE LOWER(assignee) = LOWER(?) AND status = 'overdue'",
                (member_name,),
            ).fetchone()[0]

            member_details.append({
                "name": member_name,
                "task_count": task_count,
                "overdue_count": overdue_count,
            })

            lane_total += task_count
            lane_overdue += overdue_count

        # Active = total - completed (approximate)
        if has_lane_id:
            lane_active = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE lane_id = ? AND status != 'completed'",
                (lane_id,),
            ).fetchone()[0]
        else:
            lane_active = lane_total  # Approximate if no lane_id column

        result_lanes.append({
            "lane_id": lane_id,
            "name": lane_name,
            "display_name": lane["display_name"],
            "weekly_hours": lane["weekly_hours"],
            "buffer_pct": lane["buffer_pct"],
            "team_count": len(member_names),
            "total_tasks": lane_total,
            "active_tasks": lane_active,
            "overdue_tasks": lane_overdue,
            "members": member_details,
        })

        total_people += len(member_names)
        total_tasks_in_lanes += lane_total

    conn.close()

    return {
        "lanes": result_lanes,
        "summary": {
            "total_lanes": len(result_lanes),
            "total_people": total_people,
            "total_tasks_in_lanes": total_tasks_in_lanes,
        },
    }


def full_bootstrap(
    db_path: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    """Run full bootstrap: create lanes + assign tasks."""
    lane_result = bootstrap_lanes(db_path, dry_run=dry_run)
    assign_result = assign_tasks_to_lanes(db_path, dry_run=dry_run)

    return {
        "lanes": lane_result,
        "assignments": assign_result,
        "dry_run": dry_run,
    }


if __name__ == "__main__":
    import json
    import sys

    dry = "--dry-run" in sys.argv

    print("=" * 60)
    print("MOH TIME OS — Capacity Lane Bootstrap")
    print("=" * 60)

    result = full_bootstrap(dry_run=dry)

    print(f"\nMode: {'DRY RUN' if dry else 'LIVE'}")
    print(f"\nLanes created: {result['lanes']['created']}")
    print(f"Lanes skipped: {result['lanes']['skipped']}")
    for lane in result["lanes"]["lanes"]:
        print(f"  {lane['name']}: {lane['display_name']} ({lane['weekly_hours']}h/wk, {lane['buffer_pct']*100:.0f}% buffer)")

    print(f"\nTasks assigned: {result['assignments']['assigned']}")
    print(f"Tasks unmatched: {result['assignments']['unmatched']}")

    if not dry:
        print("\n--- Lane Load Report ---")
        report = lane_load_report()
        print(json.dumps(report["summary"], indent=2))
        for lane in report["lanes"]:
            print(f"\n  {lane['display_name']}: {lane['team_count']} people, {lane['total_tasks']} tasks ({lane['overdue_tasks']} overdue)")
            for m in lane["members"]:
                print(f"    {m['name']}: {m['task_count']} tasks ({m['overdue_count']} overdue)")
