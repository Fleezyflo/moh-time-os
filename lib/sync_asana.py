"""
Asana → Projects & Items sync.

Imports projects from Asana workspace.
Imports overdue tasks as Items.
Attempts to match projects to clients via fuzzy matching.
"""

import logging
from datetime import date, timedelta
from typing import Any

from engine.asana_client import list_projects, list_tasks_in_project, list_workspaces
from lib.entities import create_project, find_client, find_project, update_project
from lib.items import create_item
from lib.store import get_connection, now_iso

logger = logging.getLogger(__name__)

log = logging.getLogger("moh_time_os.sync_asana")

# hrmny.co workspace GID (cached from previous discovery)
HRMNY_WORKSPACE_GID = None


def get_workspace_gid() -> str:
    """Get hrmny.co workspace GID."""
    global HRMNY_WORKSPACE_GID

    if HRMNY_WORKSPACE_GID:
        return HRMNY_WORKSPACE_GID

    workspaces = list_workspaces()
    for ws in workspaces:
        if "hrmny" in ws.get("name", "").lower():
            HRMNY_WORKSPACE_GID = ws["gid"]
            return HRMNY_WORKSPACE_GID

    # Fallback to first workspace
    if workspaces:
        HRMNY_WORKSPACE_GID = workspaces[0]["gid"]
        return HRMNY_WORKSPACE_GID

    raise RuntimeError("No Asana workspace found")


def extract_client_name(project_name: str) -> str | None:
    """
    Try to extract client name from project name.

    Common patterns:
    - "ClientName - Project Name"
    - "ClientName: Project Name"
    - "ClientName | Project Name"
    - "[ClientName] Project Name"
    """
    # Try common separators
    for sep in [" - ", ": ", " | ", " – "]:
        if sep in project_name:
            parts = project_name.split(sep, 1)
            if len(parts) >= 1:
                return parts[0].strip()

    # Try bracket pattern
    if project_name.startswith("["):
        end = project_name.find("]")
        if end > 0:
            return project_name[1:end].strip()

    return None


def match_project_to_client(project_name: str) -> str | None:
    """
    Try to match a project to a client.
    Returns client_id if match found.
    """
    # Try to extract client name from project name
    extracted = extract_client_name(project_name)
    if extracted:
        client = find_client(extracted)
        if client:
            return client.id

    # Try matching the whole project name
    client = find_client(project_name)
    if client:
        return client.id

    # Try first word (often client abbreviation)
    first_word = project_name.split()[0] if project_name else None
    if first_word and len(first_word) >= 2:
        client = find_client(first_word)
        if client:
            return client.id

    return None


def sync_asana_projects() -> tuple[int, int, int, int, list[str]]:
    """
    Sync projects from Asana.

    Returns:
        (created, updated, matched_to_client, skipped, errors)
    """
    log.info("Starting Asana projects sync...")

    created = 0
    updated = 0
    matched = 0
    skipped = 0
    errors = []

    try:
        workspace_gid = get_workspace_gid()
        log.info(f"Using workspace: {workspace_gid}")

        # Fetch all active projects with owner, due_on, and custom fields
        log.info("Fetching Asana projects...")
        projects = list_projects(
            workspace_gid,
            archived=False,
            opt_fields="name,due_on,start_on,owner,owner.name,current_status,current_status.text",
        )
        log.info(f"Found {len(projects)} active projects")

        for proj in projects:
            try:
                proj_gid = proj.get("gid")
                name = proj.get("name", "").strip()
                due_on = proj.get("due_on")  # Asana project due date (YYYY-MM-DD)
                proj.get("start_on")  # Asana project start date

                # Extract owner
                owner_data = proj.get("owner") or {}
                owner_name = owner_data.get("name") if owner_data else None

                # Extract status from current_status
                status_data = proj.get("current_status") or {}
                status_data.get("text", "") if status_data else ""

                if not name:
                    skipped += 1
                    continue

                # Check if project exists by name (since we cleaned up)
                existing = find_project(name=name)

                # Try to match to client
                client_id = match_project_to_client(name)
                if client_id:
                    matched += 1

                if existing:
                    # Update project with all Asana data
                    updates = {"updated_at": now_iso()}
                    if not existing.client_id and client_id:
                        updates["client_id"] = client_id
                    if due_on:
                        updates["deadline"] = due_on
                    if owner_name:
                        updates["owner"] = owner_name
                    if proj_gid:
                        updates["source_id"] = proj_gid
                        updates["source"] = "asana"
                    update_project(existing.id, **updates)
                    updated += 1
                else:
                    # Create new project with all data
                    create_project(
                        name=name,
                        source="asana",
                        source_id=proj_gid,
                        client_id=client_id,
                        status="active",
                        deadline=due_on,
                        owner=owner_name,
                    )
                    created += 1

            except Exception as e:
                errors.append(f"Project {proj.get('name', 'Unknown')}: {e}")
                log.error(f"Error syncing project {proj.get('name')}: {e}")

        log.info(
            f"Asana projects sync complete: {created} created, {updated} updated, {matched} matched to clients"
        )

    except Exception as e:
        errors.append(f"Sync failed: {e}")
        log.error(f"Asana projects sync failed: {e}")

    return created, updated, matched, skipped, errors


def sync_overdue_tasks() -> tuple[int, int, list[str]]:
    """
    Sync overdue tasks from Asana as Items.

    Only imports tasks that:
    - Have a due date in the past
    - Are not completed
    - Don't already exist as items (by source_ref)

    Returns:
        (created, skipped, errors)
    """
    log.info("Starting Asana overdue tasks sync...")

    created = 0
    skipped = 0
    errors = []

    today = date.today().isoformat()
    sixty_days_ago = (date.today() - timedelta(days=60)).isoformat()

    try:
        workspace_gid = get_workspace_gid()

        # Get all active projects
        projects = list_projects(workspace_gid, archived=False)
        log.info(f"Scanning {len(projects)} projects for overdue tasks...")

        for proj in projects:
            try:
                proj_gid = proj.get("gid")
                proj_name = proj.get("name", "")

                # Get incomplete tasks
                tasks = list_tasks_in_project(proj_gid, completed=False)

                for task in tasks:
                    due_on = task.get("due_on")

                    # Skip if no due date or not overdue
                    if not due_on or due_on >= today:
                        continue

                    # Skip if more than 60 days overdue (stale task)
                    if due_on < sixty_days_ago:
                        continue

                    task_gid = task.get("gid")
                    task_name = task.get("name", "").strip()

                    if not task_name:
                        continue

                    # Check if already imported
                    with get_connection() as conn:
                        existing = conn.execute(
                            "SELECT id FROM items WHERE source_ref = ?", (task_gid,)
                        ).fetchone()

                    if existing:
                        skipped += 1
                        continue

                    # Get assignee
                    assignee = task.get("assignee")
                    owner = assignee.get("name") if assignee else "unassigned"

                    # Try to find matching project in our system
                    our_project = find_project(asana_id=proj_gid)
                    project_id = our_project.id if our_project else None
                    client_id = our_project.client_id if our_project else None

                    # Get client name for context
                    client_name = None
                    if client_id:
                        from lib.entities import get_client

                        client = get_client(client_id)
                        client_name = client.name if client else None

                    # Create item
                    create_item(
                        what=task_name,
                        owner=owner,
                        due=due_on,
                        client_id=client_id,
                        client_name=client_name,
                        project_id=project_id,
                        project_name=proj_name,
                        source_type="asana",
                        source_ref=task_gid,
                        captured_by="sync",
                    )
                    created += 1

            except Exception as e:
                errors.append(f"Project {proj.get('name', 'Unknown')}: {e}")

        log.info(
            f"Overdue tasks sync complete: {created} created, {skipped} already existed"
        )

    except Exception as e:
        errors.append(f"Sync failed: {e}")
        log.error(f"Overdue tasks sync failed: {e}")

    return created, skipped, errors


def get_project_stats() -> dict[str, Any]:
    """Get summary statistics on projects."""
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]

        linked = conn.execute(
            "SELECT COUNT(*) FROM projects WHERE client_id IS NOT NULL"
        ).fetchone()[0]

        from_asana = conn.execute(
            "SELECT COUNT(*) FROM projects WHERE source = 'asana'"
        ).fetchone()[0]

        by_status = conn.execute("""
            SELECT status, COUNT(*) as count
            FROM projects
            GROUP BY status
            ORDER BY count DESC
        """).fetchall()

    return {
        "total": total,
        "linked_to_client": linked,
        "unlinked": total - linked,
        "from_asana": from_asana,
        "by_status": {r[0]: r[1] for r in by_status},
    }


def get_unlinked_projects(limit: int = 20) -> list[dict]:
    """Get projects not linked to a client."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, name, status
            FROM projects
            WHERE client_id IS NULL
            ORDER BY name
            LIMIT ?
        """,
            (limit,),
        ).fetchall()

    return [{"id": r[0], "name": r[1], "status": r[2]} for r in rows]


def run_full_sync() -> dict[str, Any]:
    """Run complete Asana sync (projects + overdue tasks)."""
    results = {}

    # Sync projects
    created, updated, matched, skipped, errors = sync_asana_projects()
    results["projects"] = {
        "created": created,
        "updated": updated,
        "matched_to_client": matched,
        "skipped": skipped,
        "errors": len(errors),
    }

    # Sync overdue tasks
    created, skipped, errors = sync_overdue_tasks()
    results["overdue_tasks"] = {
        "created": created,
        "skipped": skipped,
        "errors": len(errors),
    }

    # Get stats
    results["stats"] = get_project_stats()

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    logger.info("=== Asana Full Sync ===\n")
    results = run_full_sync()

    logger.info("\n--- Projects ---")
    p = results["projects"]
    logger.info(f"  Created: {p['created']}")
    logger.info(f"  Updated: {p['updated']}")
    logger.info(f"  Matched to client: {p['matched_to_client']}")
    logger.info(f"  Skipped: {p['skipped']}")
    logger.info(f"  Errors: {p['errors']}")
    logger.info("\n--- Overdue Tasks ---")
    t = results["overdue_tasks"]
    logger.info(f"  Imported as items: {t['created']}")
    logger.info(f"  Already existed: {t['skipped']}")
    logger.info(f"  Errors: {t['errors']}")
    logger.info("\n--- Stats ---")
    s = results["stats"]
    logger.info(f"  Total projects: {s['total']}")
    logger.info(f"  Linked to client: {s['linked_to_client']}")
    logger.info(f"  Unlinked: {s['unlinked']}")
    logger.info(f"  By status: {s['by_status']}")
    # Show some unlinked projects
    unlinked = get_unlinked_projects(10)
    if unlinked:
        logger.info(f"\n--- Sample Unlinked Projects ({len(unlinked)}) ---")
        for p in unlinked:
            logger.info(f"  - {p['name']}")
