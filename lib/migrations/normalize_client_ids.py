"""
Client ID Normalization Migration

Normalizes all client_id references across the database to use consistent
slug-based IDs that match the clients table.

Run: python -m lib.migrations.normalize_client_ids
"""

import logging
import re
import sqlite3
from datetime import datetime

from lib.store import DB_PATH

logger = logging.getLogger(__name__)


def get_db():
    """Get a direct database connection."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn


def slugify(name: str) -> str:
    """Convert name to slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:50]  # Limit length


def run_migration():
    """Run the client ID normalization migration."""
    conn = get_db()
    cursor = conn.cursor()

    results = {
        "tasks_updated": 0,
        "clients_created": 0,
        "mappings": {},
        "orphan_ids": [],
    }

    logger.info("Starting client ID normalization...")
    # Step 1: Get all unique client_ids from tasks
    cursor.execute("""
        SELECT DISTINCT client_id,
               (SELECT title FROM tasks t2 WHERE t2.client_id = t1.client_id LIMIT 1) as sample_title
        FROM tasks t1
        WHERE client_id IS NOT NULL AND client_id != ''
    """)
    task_client_ids = cursor.fetchall()
    logger.info(f"Found {len(task_client_ids)} unique client_ids in tasks")
    # Step 2: Get existing clients
    cursor.execute("SELECT id, name FROM clients")
    clients = cursor.fetchall()
    client_by_name_lower = {row[1].lower().strip(): row[0] for row in clients}
    client_ids = {row[0] for row in clients}
    logger.info(f"Found {len(clients)} existing clients")
    # Step 3: For each unique client_id, determine the correct mapping
    for row in task_client_ids:
        old_id = row[0]
        sample_title = row[1] or ""

        # Already valid?
        if old_id in client_ids:
            results["mappings"][old_id] = old_id
            continue

        # Extract client name from task title (pattern: "ClientName: Task Description")
        match = re.match(r"^([^:]+):", sample_title)
        if match:
            potential_name = match.group(1).strip()
            potential_name_lower = potential_name.lower()

            # Try exact match
            if potential_name_lower in client_by_name_lower:
                new_id = client_by_name_lower[potential_name_lower]
                results["mappings"][old_id] = new_id
                logger.info(f"  Mapped {old_id[:20]}... → {new_id} (exact match)")
                continue

            # Try partial match
            matched = False
            for client_name, client_id in client_by_name_lower.items():
                if (
                    potential_name_lower in client_name
                    or client_name in potential_name_lower
                ):
                    results["mappings"][old_id] = client_id
                    logger.info(
                        f"  Mapped {old_id[:20]}... → {client_id} (partial match)"
                    )
                    matched = True
                    break

            if matched:
                continue

            # Create new client from title prefix
            new_slug = slugify(potential_name)

            # Check if slug already exists
            cursor.execute("SELECT id FROM clients WHERE id = ?", (new_slug,))
            if not cursor.fetchone():
                cursor.execute(
                    """
                    INSERT INTO clients (id, name, tier, relationship_health, created_at, updated_at)
                    VALUES (?, ?, 'C', 50, ?, ?)
                """,
                    (
                        new_slug,
                        potential_name,
                        datetime.now().isoformat(),
                        datetime.now().isoformat(),
                    ),
                )
                results["clients_created"] += 1
                logger.info(f"  Created client: {new_slug} ({potential_name})")
            results["mappings"][old_id] = new_slug
            client_ids.add(new_slug)
            client_by_name_lower[potential_name_lower] = new_slug
        else:
            # Can't determine client from title
            results["orphan_ids"].append(old_id)
            logger.info(f"  Orphan client_id (no title pattern): {old_id[:30]}...")
    # Step 4: Apply mappings
    for old_id, new_id in results["mappings"].items():
        if old_id != new_id:
            cursor.execute("SELECT COUNT(*) FROM tasks WHERE client_id = ?", (old_id,))
            count = cursor.fetchone()[0]

            cursor.execute(
                "UPDATE tasks SET client_id = ? WHERE client_id = ?", (new_id, old_id)
            )
            results["tasks_updated"] += count
            logger.info(f"  Updated {count} tasks: {old_id[:20]}... → {new_id}")
    conn.commit()

    logger.info("\n=== Migration Complete ===")
    logger.info(f"Tasks updated: {results['tasks_updated']}")
    logger.info(f"Clients created: {results['clients_created']}")
    logger.info(f"Mappings created: {len(results['mappings'])}")
    logger.info(f"Orphan IDs (unmapped): {len(results['orphan_ids'])}")
    return results


def populate_project_client_links():
    """Ensure every project is linked to a client."""
    conn = get_db()
    cursor = conn.cursor()

    results = {"linked": 0, "created": 0, "failed": []}

    logger.info("\nPopulating project-client links...")
    # Get all projects
    cursor.execute("SELECT id, name FROM projects")
    projects = cursor.fetchall()

    # Get all clients
    cursor.execute("SELECT id, name FROM clients")
    clients = cursor.fetchall()
    client_by_name = {row[1].lower(): row[0] for row in clients}
    client_by_id = {row[0]: row[1] for row in clients}

    for project_id, project_name in projects:
        # Already linked?
        cursor.execute(
            "SELECT 1 FROM client_projects WHERE project_id = ?", (project_id,)
        )
        if cursor.fetchone():
            logger.info(f"  {project_id}: already linked")
            continue

        matched_client = None

        # Strategy 1: Project ID prefix (ret-sixt → sixt)
        if project_id.startswith("ret-"):
            client_slug = project_id[4:]  # Remove 'ret-'

            # Find client with this slug or name
            for cid, cname in client_by_id.items():
                if cid.lower() == client_slug or cname.lower() == client_slug:
                    matched_client = cid
                    break

            # Try partial name match
            if not matched_client:
                for cname, cid in client_by_name.items():
                    if client_slug in cname or cname.startswith(client_slug):
                        matched_client = cid
                        break

        # Strategy 2: Project name contains client name
        if not matched_client:
            project_name_lower = project_name.lower()
            for cname, cid in client_by_name.items():
                if cname in project_name_lower or project_name_lower.startswith(cname):
                    matched_client = cid
                    break

        if matched_client:
            cursor.execute(
                """
                INSERT OR IGNORE INTO client_projects (client_id, project_id)
                VALUES (?, ?)
            """,
                (matched_client, project_id),
            )
            results["linked"] += 1
            logger.info(f"  {project_id} → {matched_client}")
        else:
            results["failed"].append(project_id)
            logger.info(f"  {project_id}: NO MATCH FOUND")
    conn.commit()

    logger.info(f"\nLinked: {results['linked']}, Failed: {len(results['failed'])}")
    return results


def propagate_client_to_tasks():
    """Propagate client_id from project to tasks that don't have one."""
    conn = get_db()
    cursor = conn.cursor()

    logger.info("\nPropagating client_id from projects to tasks...")
    # Find tasks with project but no client_id
    cursor.execute("""
        UPDATE tasks
        SET client_id = (
            SELECT cp.client_id
            FROM client_projects cp
            WHERE cp.project_id = tasks.project
        )
        WHERE (client_id IS NULL OR client_id = '')
        AND project IS NOT NULL
        AND project != ''
        AND EXISTS (
            SELECT 1 FROM client_projects cp WHERE cp.project_id = tasks.project
        )
    """)

    updated = cursor.rowcount
    conn.commit()

    logger.info(f"Updated {updated} tasks with client_id from project")
    return {"tasks_updated": updated}


def validate_integrity():
    """Validate data integrity after migration."""
    conn = get_db()
    cursor = conn.cursor()

    issues = []

    logger.info("\nValidating data integrity...")
    # Check 1: Orphan client_ids in tasks
    cursor.execute("""
        SELECT COUNT(DISTINCT client_id)
        FROM tasks t
        WHERE client_id IS NOT NULL
        AND client_id != ''
        AND NOT EXISTS (SELECT 1 FROM clients c WHERE c.id = t.client_id)
    """)
    count = cursor.fetchone()[0]
    if count > 0:
        issues.append(f"Orphan client_ids in tasks: {count}")
    logger.info(f"  Orphan client_ids: {count}")
    # Check 2: Projects without client links
    cursor.execute("""
        SELECT COUNT(*)
        FROM projects p
        WHERE NOT EXISTS (SELECT 1 FROM client_projects cp WHERE cp.project_id = p.id)
    """)
    count = cursor.fetchone()[0]
    if count > 0:
        issues.append(f"Unlinked projects: {count}")
    logger.info(f"  Unlinked projects: {count}")
    # Check 3: Coverage metrics
    cursor.execute("SELECT COUNT(*) FROM tasks")
    total_tasks = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM tasks WHERE client_id IS NOT NULL AND client_id != ''"
    )
    tasks_with_client = cursor.fetchone()[0]

    coverage = round(tasks_with_client / total_tasks * 100, 1) if total_tasks > 0 else 0
    logger.info(
        f"  Task-client coverage: {coverage}% ({tasks_with_client}/{total_tasks})"
    )
    cursor.execute("SELECT COUNT(*) FROM projects")
    total_projects = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT project_id) FROM client_projects")
    linked_projects = cursor.fetchone()[0]

    project_coverage = (
        round(linked_projects / total_projects * 100, 1) if total_projects > 0 else 0
    )
    logger.info(
        f"  Project-client coverage: {project_coverage}% ({linked_projects}/{total_projects})"
    )
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "task_client_coverage": coverage,
        "project_link_coverage": project_coverage,
    }


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("CLIENT ID NORMALIZATION MIGRATION")
    logger.info("=" * 60)
    # Step 1: Normalize client IDs
    norm_results = run_migration()

    # Step 2: Populate project-client links
    link_results = populate_project_client_links()

    # Step 3: Propagate client to tasks
    prop_results = propagate_client_to_tasks()

    # Step 4: Validate
    validation = validate_integrity()

    logger.info("\n" + "=" * 60)
    logger.info("FINAL RESULTS")
    logger.info("=" * 60)
    logger.info(f"Data valid: {validation['valid']}")
    logger.info(f"Task-client coverage: {validation['task_client_coverage']}%")
    logger.info(f"Project-link coverage: {validation['project_link_coverage']}%")
    if validation["issues"]:
        logger.info(f"Issues: {validation['issues']}")
