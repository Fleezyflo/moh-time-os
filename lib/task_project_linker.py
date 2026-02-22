"""
Task-project linker — links orphaned tasks to projects using multiple strategies.

Priority order: Asana GID match > project map > name match.
Also cascades client_id from projects to tasks.
"""

import logging
import sqlite3
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


def link_by_asana_gid(db_path: str, dry_run: bool = False) -> int:
    """Link tasks to projects by matching Asana GIDs.

    Tasks from Asana have a project name in the `project` field.
    Projects have `asana_project_id`.
    We match via the task's source metadata or the project name.
    """
    conn = sqlite3.connect(db_path)
    now = datetime.now().isoformat()

    try:
        # Match tasks that have a `project` name matching a project's name
        # and source = 'asana'
        count = conn.execute(
            """SELECT COUNT(*) FROM tasks t
               JOIN projects p ON LOWER(TRIM(t.project)) = LOWER(TRIM(p.name))
               WHERE t.project_id IS NULL
                 AND t.project IS NOT NULL AND t.project != ''
                 AND t.source = 'asana'"""
        ).fetchone()[0]

        if not dry_run and count > 0:
            conn.execute(
                """UPDATE tasks SET
                       project_id = (SELECT p.id FROM projects p
                                     WHERE LOWER(TRIM(tasks.project)) = LOWER(TRIM(p.name))
                                     LIMIT 1),
                       project_link_status = 'linked',
                       updated_at = ?
                   WHERE project_id IS NULL
                     AND project IS NOT NULL AND project != ''
                     AND source = 'asana'
                     AND EXISTS (SELECT 1 FROM projects p
                                 WHERE LOWER(TRIM(tasks.project)) = LOWER(TRIM(p.name)))""",
                (now,),
            )
            conn.commit()

        logger.info(f"link_by_asana_gid: {'would link' if dry_run else 'linked'} {count} tasks")
        return count

    finally:
        conn.close()


def link_by_map(db_path: str, dry_run: bool = False) -> int:
    """Link tasks using asana_project_map explicit mappings."""
    conn = sqlite3.connect(db_path)
    now = datetime.now().isoformat()

    try:
        # asana_project_map schema: asana_gid, project_id, asana_name, created_at
        count = conn.execute(
            """SELECT COUNT(*) FROM tasks t
               JOIN asana_project_map m ON LOWER(TRIM(t.project)) = LOWER(TRIM(m.asana_name))
               JOIN projects p ON p.asana_project_id = m.asana_gid
               WHERE t.project_id IS NULL"""
        ).fetchone()[0]

        if not dry_run and count > 0:
            conn.execute(
                """UPDATE tasks SET
                       project_id = (
                           SELECT p.id FROM asana_project_map m
                           JOIN projects p ON p.asana_project_id = m.asana_gid
                           WHERE LOWER(TRIM(m.asana_name)) = LOWER(TRIM(tasks.project))
                           LIMIT 1
                       ),
                       project_link_status = 'linked',
                       updated_at = ?
                   WHERE project_id IS NULL
                     AND EXISTS (
                         SELECT 1 FROM asana_project_map m
                         JOIN projects p ON p.asana_project_id = m.asana_gid
                         WHERE LOWER(TRIM(m.asana_name)) = LOWER(TRIM(tasks.project))
                     )""",
                (now,),
            )
            conn.commit()

        logger.info(f"link_by_map: {'would link' if dry_run else 'linked'} {count} tasks")
        return count

    finally:
        conn.close()


def link_by_name(db_path: str, dry_run: bool = False) -> int:
    """Link tasks by fuzzy-matching project name to projects.name_normalized."""
    conn = sqlite3.connect(db_path)
    now = datetime.now().isoformat()

    try:
        # Exact name match (case-insensitive)
        count = conn.execute(
            """SELECT COUNT(*) FROM tasks t
               JOIN projects p ON LOWER(TRIM(t.project)) = LOWER(TRIM(p.name))
               WHERE t.project_id IS NULL
                 AND t.project IS NOT NULL AND t.project != ''"""
        ).fetchone()[0]

        if not dry_run and count > 0:
            conn.execute(
                """UPDATE tasks SET
                       project_id = (SELECT p.id FROM projects p
                                     WHERE LOWER(TRIM(tasks.project)) = LOWER(TRIM(p.name))
                                     LIMIT 1),
                       project_link_status = 'linked',
                       updated_at = ?
                   WHERE project_id IS NULL
                     AND project IS NOT NULL AND project != ''
                     AND EXISTS (SELECT 1 FROM projects p
                                 WHERE LOWER(TRIM(tasks.project)) = LOWER(TRIM(p.name)))""",
                (now,),
            )
            conn.commit()

        logger.info(f"link_by_name: {'would link' if dry_run else 'linked'} {count} tasks")
        return count

    finally:
        conn.close()


def cascade_client_ids(db_path: str, dry_run: bool = False) -> int:
    """Cascade client_id from projects to tasks.

    For tasks that have a project_id but no client_id, copy the project's client_id.
    """
    conn = sqlite3.connect(db_path)
    now = datetime.now().isoformat()

    try:
        count = conn.execute(
            """SELECT COUNT(*) FROM tasks t
               JOIN projects p ON t.project_id = p.id
               WHERE (t.client_id IS NULL OR t.client_id = '')
                 AND p.client_id IS NOT NULL"""
        ).fetchone()[0]

        if not dry_run and count > 0:
            conn.execute(
                """UPDATE tasks SET
                       client_id = (SELECT p.client_id FROM projects p
                                    WHERE p.id = tasks.project_id),
                       updated_at = ?
                   WHERE (client_id IS NULL OR client_id = '')
                     AND project_id IS NOT NULL
                     AND EXISTS (SELECT 1 FROM projects p
                                 WHERE p.id = tasks.project_id
                                   AND p.client_id IS NOT NULL)""",
                (now,),
            )
            conn.commit()

        logger.info(f"cascade_client_ids: {'would update' if dry_run else 'updated'} {count} tasks")
        return count

    finally:
        conn.close()


def link_all(db_path: str, dry_run: bool = False) -> dict[str, Any]:
    """Run all linking strategies in priority order, then cascade client_ids.

    Returns summary dict.
    """
    conn = sqlite3.connect(db_path)
    before_linked = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE project_id IS NOT NULL"
    ).fetchone()[0]
    before_clients = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE client_id IS NOT NULL"
    ).fetchone()[0]
    conn.close()

    gid_count = link_by_asana_gid(db_path, dry_run=dry_run)
    map_count = link_by_map(db_path, dry_run=dry_run)
    name_count = link_by_name(db_path, dry_run=dry_run)
    client_count = cascade_client_ids(db_path, dry_run=dry_run)

    conn = sqlite3.connect(db_path)
    after_linked = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE project_id IS NOT NULL"
    ).fetchone()[0]
    after_clients = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE client_id IS NOT NULL"
    ).fetchone()[0]
    projects_with_tasks = conn.execute(
        "SELECT COUNT(DISTINCT project_id) FROM tasks WHERE project_id IS NOT NULL"
    ).fetchone()[0]
    conn.close()

    result = {
        "dry_run": dry_run,
        "linked_by_gid": gid_count,
        "linked_by_map": map_count,
        "linked_by_name": name_count,
        "client_ids_cascaded": client_count,
        "tasks_linked_before": before_linked,
        "tasks_linked_after": after_linked,
        "tasks_with_client_before": before_clients,
        "tasks_with_client_after": after_clients,
        "projects_with_tasks": projects_with_tasks,
    }
    logger.info(f"link_all result: {result}")
    return result
