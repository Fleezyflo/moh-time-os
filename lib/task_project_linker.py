"""
Task-project linker — links orphaned tasks to projects using multiple strategies.

Priority order: Asana GID match > project map > name match.
Also cascades client_id from projects to tasks.

All DB access goes through StateStore: reads via ``store.query()``, writes via
``store.execute_write()``. No raw ``sqlite3`` connections (the writes are
set-based UPDATEs with subqueries, so they go through execute_write rather than
the per-row ``store.update()`` helper).
"""

import logging
from datetime import datetime, timezone
from typing import Any

from lib.state_store import StateStore

logger = logging.getLogger(__name__)


def _resolve_store(db_path: str | None, store: StateStore | None) -> StateStore:
    """Return the provided store, or construct one from db_path (or the default)."""
    if store is not None:
        return store
    return StateStore(db_path) if db_path else StateStore()


def link_by_asana_gid(
    db_path: str | None = None, dry_run: bool = False, store: StateStore | None = None
) -> int:
    """Link tasks to projects by matching Asana project names.

    Tasks from Asana have a project name in the `project` field; projects have a
    matching `name`. We link source='asana' tasks whose project name matches.
    """
    s = _resolve_store(db_path, store)
    now = datetime.now(timezone.utc).isoformat()

    count = s.query(
        """SELECT COUNT(*) AS c FROM tasks t
           JOIN projects p ON LOWER(TRIM(t.project)) = LOWER(TRIM(p.name))
           WHERE t.project_id IS NULL
             AND t.project IS NOT NULL AND t.project != ''
             AND t.source = 'asana'"""
    )[0]["c"]

    if not dry_run and count > 0:
        s.execute_write(
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
            [now],
        )

    logger.info(f"link_by_asana_gid: {'would link' if dry_run else 'linked'} {count} tasks")
    return count


def link_by_map(
    db_path: str | None = None, dry_run: bool = False, store: StateStore | None = None
) -> int:
    """Link tasks using asana_project_map explicit mappings."""
    s = _resolve_store(db_path, store)
    now = datetime.now(timezone.utc).isoformat()

    # asana_project_map schema: asana_gid, project_id, asana_name, created_at
    count = s.query(
        """SELECT COUNT(*) AS c FROM tasks t
           JOIN asana_project_map m ON LOWER(TRIM(t.project)) = LOWER(TRIM(m.asana_name))
           JOIN projects p ON p.asana_project_id = m.asana_gid
           WHERE t.project_id IS NULL"""
    )[0]["c"]

    if not dry_run and count > 0:
        s.execute_write(
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
            [now],
        )

    logger.info(f"link_by_map: {'would link' if dry_run else 'linked'} {count} tasks")
    return count


def link_by_name(
    db_path: str | None = None, dry_run: bool = False, store: StateStore | None = None
) -> int:
    """Link tasks by matching project name to projects.name (case-insensitive)."""
    s = _resolve_store(db_path, store)
    now = datetime.now(timezone.utc).isoformat()

    count = s.query(
        """SELECT COUNT(*) AS c FROM tasks t
           JOIN projects p ON LOWER(TRIM(t.project)) = LOWER(TRIM(p.name))
           WHERE t.project_id IS NULL
             AND t.project IS NOT NULL AND t.project != ''"""
    )[0]["c"]

    if not dry_run and count > 0:
        s.execute_write(
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
            [now],
        )

    logger.info(f"link_by_name: {'would link' if dry_run else 'linked'} {count} tasks")
    return count


def cascade_client_ids(
    db_path: str | None = None, dry_run: bool = False, store: StateStore | None = None
) -> int:
    """Cascade client_id from projects to tasks.

    For tasks that have a project_id but no client_id, copy the project's client_id.
    """
    s = _resolve_store(db_path, store)
    now = datetime.now(timezone.utc).isoformat()

    count = s.query(
        """SELECT COUNT(*) AS c FROM tasks t
           JOIN projects p ON t.project_id = p.id
           WHERE (t.client_id IS NULL OR t.client_id = '')
             AND p.client_id IS NOT NULL"""
    )[0]["c"]

    if not dry_run and count > 0:
        s.execute_write(
            """UPDATE tasks SET
                   client_id = (SELECT p.client_id FROM projects p
                                WHERE p.id = tasks.project_id),
                   updated_at = ?
               WHERE (client_id IS NULL OR client_id = '')
                 AND project_id IS NOT NULL
                 AND EXISTS (SELECT 1 FROM projects p
                             WHERE p.id = tasks.project_id
                               AND p.client_id IS NOT NULL)""",
            [now],
        )

    logger.info(f"cascade_client_ids: {'would update' if dry_run else 'updated'} {count} tasks")
    return count


def link_all(
    db_path: str | None = None, dry_run: bool = False, store: StateStore | None = None
) -> dict[str, Any]:
    """Run all linking strategies in priority order, then cascade client_ids.

    Returns summary dict.
    """
    s = _resolve_store(db_path, store)

    before_linked = s.query("SELECT COUNT(*) AS c FROM tasks WHERE project_id IS NOT NULL")[0]["c"]
    before_clients = s.query("SELECT COUNT(*) AS c FROM tasks WHERE client_id IS NOT NULL")[0]["c"]

    gid_count = link_by_asana_gid(dry_run=dry_run, store=s)
    map_count = link_by_map(dry_run=dry_run, store=s)
    name_count = link_by_name(dry_run=dry_run, store=s)
    client_count = cascade_client_ids(dry_run=dry_run, store=s)

    after_linked = s.query("SELECT COUNT(*) AS c FROM tasks WHERE project_id IS NOT NULL")[0]["c"]
    after_clients = s.query("SELECT COUNT(*) AS c FROM tasks WHERE client_id IS NOT NULL")[0]["c"]
    projects_with_tasks = s.query(
        "SELECT COUNT(DISTINCT project_id) AS c FROM tasks WHERE project_id IS NOT NULL"
    )[0]["c"]

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
