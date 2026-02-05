#!/usr/bin/env python3
"""
Asana Full Sync — Proper hierarchy-aware sync.

Pulls: Workspace → Teams → Projects → Tasks
Links: Tasks → Projects → Clients (via mapping)

Usage:
    python3 -m lib.collectors.asana_sync sync        # Full sync
    python3 -m lib.collectors.asana_sync projects    # Sync projects only
    python3 -m lib.collectors.asana_sync tasks       # Sync tasks only
    python3 -m lib.collectors.asana_sync map         # Show unmapped projects
"""

import sys
import json
import sqlite3
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from engine.asana_client import asana_get, list_projects, list_tasks_in_project

# Config
WORKSPACE_GID = "1148006162435561"  # hrmny
DB_PATH = Path(__file__).parent.parent.parent / "data" / "state.db"

# Team classification
INTERNAL_TEAMS = {"Admin", "HR", "Majeed Board"}
CLIENT_TEAMS = {"POD (A)", "POD (B)", "POD (C)", "Client Servicing"}

# Client name patterns (regex) → client_id
# These catch common project naming patterns
CLIENT_PATTERNS = [
    (r"GARGASH|Mercedes.?Benz|MB\b|MBBC|Daimler", "c98d144b-79b6-4c21-a94f-1ebfea30aed7"),  # Gargash
    (r"SIXT", "sixt-001"),
    (r"Five.?Guys", "2244436a-3abc-4bb4-80e5-28d7e5b9ed11"),
    (r"Monoprix", "471533f7-6994-48db-9ffc-6889dae3e286"),
    (r"Geant|Géant", "471533f7-6994-48db-9ffc-6889dae3e286"),
    (r"Aswaaq", "471533f7-6994-48db-9ffc-6889dae3e286"),
    (r"Supercare", "supercare-001"),
    (r"Bin.?Sina", "binsina-001"),
    (r"Ankai", "ankai-001"),
    (r"ASICS", "0cdc4307-0775-4468-8519-7ee8592f563b"),
    (r"SSS\b|Sportsshoes", "26c3502e-446e-4c85-9efc-de417a093d03"),
    (r"Alfa.?Romeo", "alfa-romeo-001"),
    (r"Purple\b", "purple-001"),
    (r"GAC\b", "gac-001"),
]


def get_db():
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def infer_client_id(project_name: str, team_name: str) -> Optional[str]:
    """Infer client_id from project name or team."""
    # Check patterns
    for pattern, client_id in CLIENT_PATTERNS:
        if re.search(pattern, project_name, re.IGNORECASE):
            return client_id
    return None


def is_internal_project(project_name: str, team_name: str) -> bool:
    """Determine if project is internal."""
    if team_name in INTERNAL_TEAMS:
        return True
    
    internal_keywords = [
        "internal", "hrmny", "payroll", "hr ", "admin", "template",
        "onboarding", "timesheets", "equipment", "candidates", "receivables",
        "traffic:", "pipeline", "crm", "sonic unit"
    ]
    name_lower = project_name.lower()
    return any(kw in name_lower for kw in internal_keywords)


def sync_projects(conn: sqlite3.Connection, dry_run: bool = False) -> dict:
    """
    Sync all Asana projects to Time OS.
    
    Creates/updates:
    - projects table (Time OS projects)
    - asana_project_map (GID → project_id mapping)
    """
    cursor = conn.cursor()
    
    # Fetch all Asana projects
    print("Fetching Asana projects...")
    asana_projects = list_projects(
        WORKSPACE_GID, 
        opt_fields="name,archived,team,team.name,owner,owner.name"
    )
    print(f"Found {len(asana_projects)} Asana projects")
    
    stats = {"created": 0, "updated": 0, "mapped": 0, "skipped": 0}
    
    for ap in asana_projects:
        gid = ap["gid"]
        name = ap["name"]
        team = ap.get("team", {}).get("name", "")
        archived = ap.get("archived", False)
        
        if archived:
            stats["skipped"] += 1
            continue
        
        # Check if already mapped
        cursor.execute("SELECT project_id FROM asana_project_map WHERE asana_gid = ?", (gid,))
        existing = cursor.fetchone()
        
        if existing:
            # Already mapped, skip
            stats["skipped"] += 1
            continue
        
        # Determine project type
        is_internal = is_internal_project(name, team)
        client_id = None if is_internal else infer_client_id(name, team)
        
        # Generate project_id
        slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:40]
        project_id = f"asana-{slug}-{gid[-6:]}"
        
        # Check if project already exists by asana_project_id
        cursor.execute("SELECT id FROM projects WHERE asana_project_id = ?", (gid,))
        existing_proj = cursor.fetchone()
        
        if existing_proj:
            project_id = existing_proj["id"]
            stats["updated"] += 1
        else:
            # Create new project
            if not dry_run:
                cursor.execute("""
                    INSERT INTO projects (id, name, client_id, is_internal, asana_project_id, source, status)
                    VALUES (?, ?, ?, ?, ?, 'asana', 'active')
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        client_id = COALESCE(excluded.client_id, projects.client_id),
                        asana_project_id = excluded.asana_project_id,
                        updated_at = datetime('now')
                """, (project_id, name, client_id, 1 if is_internal else 0, gid))
            stats["created"] += 1
        
        # Add to mapping table
        if not dry_run:
            cursor.execute("""
                INSERT INTO asana_project_map (asana_gid, project_id, asana_name)
                VALUES (?, ?, ?)
                ON CONFLICT(asana_gid) DO UPDATE SET
                    project_id = excluded.project_id,
                    asana_name = excluded.asana_name
            """, (gid, project_id, name))
        stats["mapped"] += 1
    
    if not dry_run:
        conn.commit()
    
    return stats


def sync_tasks(conn: sqlite3.Connection, limit_projects: int = None) -> dict:
    """
    Sync tasks from Asana with proper project linking.
    
    Uses asana_project_map to link tasks → projects → clients.
    """
    cursor = conn.cursor()
    
    # Get all mapped projects
    cursor.execute("""
        SELECT apm.asana_gid, apm.project_id, apm.asana_name, p.client_id
        FROM asana_project_map apm
        LEFT JOIN projects p ON p.id = apm.project_id
    """)
    mappings = {row["asana_gid"]: dict(row) for row in cursor.fetchall()}
    
    if not mappings:
        print("No project mappings found. Run 'sync projects' first.")
        return {"error": "no mappings"}
    
    print(f"Found {len(mappings)} mapped projects")
    
    stats = {"synced": 0, "created": 0, "updated": 0, "errors": 0}
    project_gids = list(mappings.keys())
    
    if limit_projects:
        project_gids = project_gids[:limit_projects]
    
    for i, gid in enumerate(project_gids):
        mapping = mappings[gid]
        project_id = mapping["project_id"]
        client_id = mapping["client_id"]
        project_name = mapping["asana_name"]
        
        print(f"[{i+1}/{len(project_gids)}] {project_name}...", end=" ", flush=True)
        
        try:
            tasks = list_tasks_in_project(gid, completed=False)
            print(f"{len(tasks)} tasks")
            
            for task in tasks:
                task_gid = task["gid"]
                task_id = f"asana-{task_gid}"
                
                assignee = task.get("assignee")
                assignee_name = assignee.get("name") if assignee else None
                assignee_gid = assignee.get("gid") if assignee else None
                
                cursor.execute("""
                    INSERT INTO tasks (
                        id, source, source_id, title, status,
                        project_id, client_id, project,
                        assignee_raw, assignee_id,
                        due_date, project_link_status, client_link_status
                    ) VALUES (?, 'asana', ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        title = excluded.title,
                        project_id = excluded.project_id,
                        client_id = COALESCE(excluded.client_id, tasks.client_id),
                        project = excluded.project,
                        assignee_raw = excluded.assignee_raw,
                        assignee_id = excluded.assignee_id,
                        due_date = excluded.due_date,
                        project_link_status = excluded.project_link_status,
                        client_link_status = excluded.client_link_status,
                        updated_at = datetime('now')
                """, (
                    task_id, task_gid, task["name"],
                    project_id, client_id, project_name,
                    assignee_name, assignee_gid,
                    task.get("due_on"),
                    "linked",
                    "linked" if client_id else "unlinked"
                ))
                stats["synced"] += 1
            
            conn.commit()
            
        except Exception as e:
            print(f"ERROR: {e}")
            stats["errors"] += 1
    
    return stats


def show_unmapped(conn: sqlite3.Connection):
    """Show projects that need client mapping."""
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT apm.asana_gid, apm.asana_name, p.client_id, p.is_internal
        FROM asana_project_map apm
        JOIN projects p ON p.id = apm.project_id
        WHERE p.client_id IS NULL AND p.is_internal = 0
        ORDER BY apm.asana_name
    """)
    
    unmapped = cursor.fetchall()
    
    if not unmapped:
        print("All non-internal projects are mapped to clients!")
        return
    
    print(f"\n{len(unmapped)} projects need client mapping:\n")
    for row in unmapped:
        print(f"  {row['asana_gid']}: {row['asana_name']}")
    
    print("\nTo map, add entries to CLIENT_PATTERNS in this file or run:")
    print("  UPDATE projects SET client_id = '<client_id>' WHERE asana_project_id = '<gid>';")


def show_stats(conn: sqlite3.Connection):
    """Show sync statistics."""
    cursor = conn.cursor()
    
    # Project stats
    cursor.execute("SELECT COUNT(*) FROM asana_project_map")
    mapped_projects = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM projects WHERE source = 'asana'")
    asana_projects = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM projects p
        JOIN asana_project_map apm ON apm.project_id = p.id
        WHERE p.client_id IS NOT NULL
    """)
    with_client = cursor.fetchone()[0]
    
    # Task stats
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE source = 'asana'")
    total_tasks = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE source = 'asana' AND project_id IS NOT NULL")
    linked_tasks = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE source = 'asana' AND client_id IS NOT NULL")
    tasks_with_client = cursor.fetchone()[0]
    
    print("\n=== Asana Sync Stats ===")
    print(f"Mapped projects:     {mapped_projects}")
    print(f"  → with client:     {with_client}")
    print(f"Tasks from Asana:    {total_tasks}")
    print(f"  → project linked:  {linked_tasks} ({100*linked_tasks/total_tasks:.1f}%)" if total_tasks else "  → none")
    print(f"  → client linked:   {tasks_with_client} ({100*tasks_with_client/total_tasks:.1f}%)" if total_tasks else "  → none")


if __name__ == "__main__":
    import sys
    
    cmd = sys.argv[1] if len(sys.argv) > 1 else "sync"
    conn = get_db()
    
    if cmd == "projects":
        stats = sync_projects(conn)
        print(f"\nProjects: {stats}")
        
    elif cmd == "tasks":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
        stats = sync_tasks(conn, limit_projects=limit)
        print(f"\nTasks: {stats}")
        
    elif cmd == "sync":
        print("=== FULL SYNC ===\n")
        print("--- Projects ---")
        p_stats = sync_projects(conn)
        print(f"Result: {p_stats}\n")
        
        print("--- Tasks ---")
        t_stats = sync_tasks(conn)
        print(f"Result: {t_stats}\n")
        
        show_stats(conn)
        
    elif cmd == "map":
        show_unmapped(conn)
        
    elif cmd == "stats":
        show_stats(conn)
        
    else:
        print(__doc__)
    
    conn.close()
