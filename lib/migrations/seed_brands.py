"""
Seed Brands Migration - Create brands from existing project names

Per MASTER_SPEC.md §1.1:
- Brand is REQUIRED for non-internal projects
- Brand assignment is manual-only (but we can seed initial data)

This migration:
1. Creates brands for each client based on project names
2. Links projects to those brands
"""

import sqlite3
import re
from pathlib import Path
from typing import Dict, Set

DB_PATH = Path(__file__).parent.parent.parent / "data" / "state.db"


def slugify(name: str) -> str:
    """Convert name to slug."""
    # Remove special chars, lowercase, replace spaces with dashes
    slug = re.sub(r'[^\w\s-]', '', name.lower())
    slug = re.sub(r'[\s_]+', '-', slug)
    return slug.strip('-')


def extract_brand_name(project_name: str) -> str:
    """Extract brand name from project name."""
    # Remove common suffixes
    name = project_name
    for suffix in [' Monthly', ' Retainer', ' Campaign', ' Project', ': Activation', ': Film']:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    return name.strip()


def run_migration():
    """Create brands and link projects."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("=== Seeding Brands ===\n")
    
    # Get all non-internal projects without brand_id
    cursor.execute("""
        SELECT id, name, client_id 
        FROM projects 
        WHERE is_internal = 0 AND brand_id IS NULL AND client_id IS NOT NULL
    """)
    projects = cursor.fetchall()
    
    if not projects:
        print("No projects need brand linking.")
        conn.close()
        return
    
    print(f"Found {len(projects)} projects needing brands.\n")
    
    # Track brands by client_id to avoid duplicates
    brands_by_client: Dict[str, Dict[str, str]] = {}  # client_id -> {brand_name: brand_id}
    
    for project in projects:
        client_id = project['client_id']
        project_name = project['name']
        brand_name = extract_brand_name(project_name)
        
        if client_id not in brands_by_client:
            brands_by_client[client_id] = {}
        
        # Check if brand already exists for this client
        if brand_name not in brands_by_client[client_id]:
            # Check database
            cursor.execute("""
                SELECT id FROM brands WHERE client_id = ? AND name = ?
            """, [client_id, brand_name])
            existing = cursor.fetchone()
            
            if existing:
                brands_by_client[client_id][brand_name] = existing['id']
                print(f"  Found existing brand: {brand_name} ({existing['id']})")
            else:
                # Create new brand
                brand_id = f"brand-{slugify(brand_name)}"
                
                # Ensure unique
                cursor.execute("SELECT id FROM brands WHERE id = ?", [brand_id])
                if cursor.fetchone():
                    brand_id = f"{brand_id}-{client_id[:8]}"
                
                cursor.execute("""
                    INSERT INTO brands (id, client_id, name, created_at)
                    VALUES (?, ?, ?, datetime('now'))
                """, [brand_id, client_id, brand_name])
                
                brands_by_client[client_id][brand_name] = brand_id
                print(f"  Created brand: {brand_name} ({brand_id}) for client {client_id[:8]}...")
    
    print(f"\nLinking projects to brands...\n")
    
    # Link projects to brands
    linked = 0
    for project in projects:
        client_id = project['client_id']
        project_name = project['name']
        brand_name = extract_brand_name(project_name)
        
        brand_id = brands_by_client.get(client_id, {}).get(brand_name)
        if brand_id:
            cursor.execute("""
                UPDATE projects SET brand_id = ?, updated_at = datetime('now')
                WHERE id = ?
            """, [brand_id, project['id']])
            linked += 1
            print(f"  Linked: {project['id']} → {brand_id}")
    
    conn.commit()
    print(f"\n✓ Linked {linked} projects to brands")
    
    # Verify
    cursor.execute("""
        SELECT COUNT(*) as c FROM projects WHERE is_internal = 0 AND brand_id IS NULL
    """)
    remaining = cursor.fetchone()['c']
    print(f"  Remaining without brand: {remaining}")
    
    conn.close()


if __name__ == "__main__":
    run_migration()
