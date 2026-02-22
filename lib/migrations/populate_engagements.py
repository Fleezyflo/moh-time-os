"""
Populate engagements table from project data.

Creates engagements from projects, grouping retainers by client+brand.
Adds engagement_id column to projects if missing.
Idempotent — safe to re-run.
"""

import logging
import sqlite3
import uuid
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Map project engagement_type to engagement type
TYPE_MAP = {
    "project": "project",
    "campaign": "project",  # campaigns are treated as projects
    "retainer": "retainer",
}

# Map project status to engagement state
STATE_MAP = {
    "active": "active",
    "completed": "completed",
    "on_hold": "paused",
    "cancelled": "cancelled",
    "archived": "completed",
}


def populate_engagements(db_path: str) -> dict[str, Any]:
    """Populate engagements from project data.

    For regular projects/campaigns: 1 engagement per project.
    For retainers: 1 engagement per (client_id, brand_id) group.

    Returns summary dict.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    now = datetime.now().isoformat()

    try:
        # Add engagement_id column if missing
        cols = [row[1] for row in conn.execute("PRAGMA table_info(projects)").fetchall()]
        if "engagement_id" not in cols:
            conn.execute("ALTER TABLE projects ADD COLUMN engagement_id TEXT")
            logger.info("Added engagement_id column to projects")

        # Clear existing engagements for idempotency
        conn.execute("DELETE FROM engagements")
        conn.execute("UPDATE projects SET engagement_id = NULL")

        # Fetch all projects
        projects = conn.execute(
            """SELECT id, name, client_id, brand_id, engagement_type, status,
                      asana_project_id, start_date
               FROM projects"""
        ).fetchall()

        created = 0
        linked = 0

        # Group retainers by (client_id, brand_id)
        retainer_groups: dict[tuple, list] = {}

        for proj in projects:
            eng_type = TYPE_MAP.get(proj["engagement_type"], "project")

            if eng_type == "retainer":
                key = (proj["client_id"], proj["brand_id"])
                retainer_groups.setdefault(key, []).append(proj)
            else:
                # Create one engagement per project/campaign
                eng_id = str(uuid.uuid4())
                state = STATE_MAP.get(proj["status"], "active")
                conn.execute(
                    """INSERT INTO engagements
                       (id, client_id, brand_id, name, type, state,
                        asana_project_gid, started_at, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        eng_id,
                        proj["client_id"],
                        proj["brand_id"],
                        proj["name"],
                        eng_type,
                        state,
                        proj["asana_project_id"],
                        proj["start_date"],
                        now,
                        now,
                    ),
                )
                conn.execute(
                    "UPDATE projects SET engagement_id = ? WHERE id = ?",
                    (eng_id, proj["id"]),
                )
                created += 1
                linked += 1

        # Create grouped retainer engagements
        for (client_id, brand_id), retainer_projects in retainer_groups.items():
            eng_id = str(uuid.uuid4())
            # Use first project name as engagement name
            names = [p["name"] for p in retainer_projects]
            eng_name = (
                f"Retainer: {names[0]}" if len(names) == 1 else f"Retainer ({len(names)} projects)"
            )

            # State: active if any project is active
            states = [STATE_MAP.get(p["status"], "active") for p in retainer_projects]
            state = "active" if "active" in states else states[0]

            # Use first project's asana GID
            asana_gid = retainer_projects[0]["asana_project_id"]
            start_date = min(
                (p["start_date"] for p in retainer_projects if p["start_date"]),
                default=None,
            )

            conn.execute(
                """INSERT INTO engagements
                   (id, client_id, brand_id, name, type, state,
                    asana_project_gid, started_at, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    eng_id,
                    client_id,
                    brand_id,
                    eng_name,
                    "retainer",
                    state,
                    asana_gid,
                    start_date,
                    now,
                    now,
                ),
            )
            created += 1

            for p in retainer_projects:
                conn.execute(
                    "UPDATE projects SET engagement_id = ? WHERE id = ?",
                    (eng_id, p["id"]),
                )
                linked += 1

        conn.commit()

        # Verify
        eng_count = conn.execute("SELECT COUNT(*) FROM engagements").fetchone()[0]
        unlinked = conn.execute(
            "SELECT COUNT(*) FROM projects WHERE engagement_id IS NULL"
        ).fetchone()[0]
        type_dist = dict(
            conn.execute("SELECT type, COUNT(*) FROM engagements GROUP BY type").fetchall()
        )

        result = {
            "engagements_created": eng_count,
            "projects_linked": linked,
            "projects_unlinked": unlinked,
            "type_distribution": type_dist,
        }
        logger.info(f"Populated engagements: {result}")
        return result

    finally:
        conn.close()
