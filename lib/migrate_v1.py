"""Migrate items from v1 database to v2."""

import sqlite3
import os
from typing import Dict, Any

from .store import now_iso
from .entities import find_client, find_project, find_person
from .items import create_item

V1_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "moh_time_os.db")


def migrate_v1_items(dry_run: bool = True) -> Dict[str, Any]:
    """
    Migrate open items from v1 to v2.
    
    Args:
        dry_run: If True, don't actually create items, just report what would be done.
    
    Returns:
        Summary of migration.
    """
    result = {
        'total_v1': 0,
        'migrated': 0,
        'skipped': 0,
        'errors': [],
        'items': [],
    }
    
    if not os.path.exists(V1_DB_PATH):
        result['errors'].append("V1 database not found")
        return result
    
    conn = sqlite3.connect(V1_DB_PATH)
    conn.row_factory = sqlite3.Row
    
    try:
        # Get open items from v1
        rows = conn.execute("""
            SELECT 
                i.id, i.what, i.status, i.owner, i.due,
                i.client_id, i.project_id,
                c.name as client_name,
                p.name as project_name
            FROM items i
            LEFT JOIN clients c ON i.client_id = c.id
            LEFT JOIN projects p ON i.project_id = p.id
            WHERE i.status = 'open'
            ORDER BY i.due NULLS LAST
        """).fetchall()
        
        result['total_v1'] = len(rows)
        
        for row in rows:
            try:
                what = row['what']
                owner = row['owner'] or 'me'
                due = row['due']
                
                # Try to find matching entities in v2
                client_id = None
                project_id = None
                
                if row['client_name']:
                    client = find_client(name=row['client_name'])
                    if client:
                        client_id = client.id
                
                if row['project_name']:
                    project = find_project(name=row['project_name'])
                    if project:
                        project_id = project.id
                
                item_info = {
                    'what': what,
                    'owner': owner,
                    'due': due,
                    'client': row['client_name'],
                    'project': row['project_name'],
                    'client_linked': bool(client_id),
                    'project_linked': bool(project_id),
                }
                result['items'].append(item_info)
                
                if not dry_run:
                    create_item(
                        what=what,
                        owner=owner,
                        due=due,
                        client_id=client_id,
                        project_id=project_id,
                        source_type='migration',
                        source_ref=f"v1:{row['id']}",
                    )
                
                result['migrated'] += 1
                
            except Exception as e:
                result['errors'].append(f"{row['what'][:30]}: {str(e)}")
                result['skipped'] += 1
        
    finally:
        conn.close()
    
    return result


def print_migration_preview():
    """Print preview of what would be migrated."""
    result = migrate_v1_items(dry_run=True)
    
    print(f"V1 open items: {result['total_v1']}")
    print(f"Would migrate: {result['migrated']}")
    print(f"Errors: {len(result['errors'])}")
    print()
    
    if result['items']:
        print("Items to migrate:")
        for item in result['items'][:20]:
            linked = []
            if item['client_linked']:
                linked.append('C')
            if item['project_linked']:
                linked.append('P')
            link_str = f"[{','.join(linked)}]" if linked else "[unlinked]"
            
            due_str = f" (due {item['due']})" if item['due'] else ""
            print(f"  • {item['what'][:50]}{due_str} {link_str}")
        
        if len(result['items']) > 20:
            print(f"  ... and {len(result['items']) - 20} more")


def run_migration():
    """Run the actual migration."""
    print("Running migration (for real)...")
    result = migrate_v1_items(dry_run=False)
    
    print(f"Migrated: {result['migrated']}")
    print(f"Errors: {len(result['errors'])}")
    
    if result['errors']:
        print("\nErrors:")
        for err in result['errors'][:10]:
            print(f"  • {err}")


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--run':
        run_migration()
    else:
        print_migration_preview()
