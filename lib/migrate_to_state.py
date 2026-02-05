#!/usr/bin/env python3
"""
Migrate v2.db data to state.db for unified database.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(__file__).parent.parent / "data"
V2_DB = DATA_DIR / "moh_time_os_v2.db"
STATE_DB = DATA_DIR / "state.db"


def migrate():
    """Run full migration from v2.db to state.db."""
    print("Starting migration from v2.db to state.db...")
    
    v2_conn = sqlite3.connect(V2_DB)
    v2_conn.row_factory = sqlite3.Row
    state_conn = sqlite3.connect(STATE_DB)
    state_conn.row_factory = sqlite3.Row
    
    try:
        # 1. Create clients table in state.db if not exists
        print("\n1. Creating clients table...")
        state_conn.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                tier TEXT CHECK (tier IN ('A', 'B', 'C')),
                type TEXT,
                financial_annual_value REAL,
                financial_ar_outstanding REAL,
                financial_ar_aging TEXT,
                financial_payment_pattern TEXT,
                relationship_health TEXT,
                relationship_trend TEXT,
                relationship_last_interaction TEXT,
                relationship_notes TEXT,
                contacts_json TEXT,
                active_projects_json TEXT,
                xero_contact_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        state_conn.commit()
        print("   ✓ Clients table ready")
        
        # 2. Migrate clients
        print("\n2. Migrating clients...")
        v2_clients = v2_conn.execute("SELECT * FROM clients").fetchall()
        migrated_clients = 0
        for client in v2_clients:
            try:
                state_conn.execute("""
                    INSERT OR REPLACE INTO clients 
                    (id, name, tier, type, financial_annual_value, financial_ar_outstanding,
                     financial_ar_aging, financial_payment_pattern, relationship_health,
                     relationship_trend, relationship_last_interaction, relationship_notes,
                     contacts_json, active_projects_json, xero_contact_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    client['id'], client['name'], client['tier'], client['type'],
                    client['financial_annual_value'], client['financial_ar_outstanding'],
                    client['financial_ar_aging'], client['financial_payment_pattern'],
                    client['relationship_health'], client['relationship_trend'],
                    client['relationship_last_interaction'], client['relationship_notes'],
                    client['contacts_json'], client['active_projects_json'],
                    client['xero_contact_id'], client['created_at'], client['updated_at']
                ))
                migrated_clients += 1
            except Exception as e:
                print(f"   ! Error migrating client {client['id']}: {e}")
        state_conn.commit()
        print(f"   ✓ Migrated {migrated_clients} clients")
        
        # 3. Migrate items to tasks (if not already there)
        print("\n3. Migrating items to tasks...")
        v2_items = v2_conn.execute("SELECT * FROM items WHERE status != 'done'").fetchall()
        migrated_items = 0
        for row in v2_items:
            item = dict(row)  # Convert Row to dict
            task_id = f"v2_{item['id']}"
            # Check if already exists
            existing = state_conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if existing:
                continue
            try:
                state_conn.execute("""
                    INSERT INTO tasks 
                    (id, source, source_id, title, status, priority, due_date, assignee,
                     project, lane, urgency, impact, deadline_type, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    task_id, 'v2_migration', item['id'], item['what'],
                    'pending' if item['status'] == 'open' else item['status'],
                    50,  # default priority
                    item.get('due'), item['owner'], item.get('project_id'),
                    item.get('lane', 'ops'), item.get('urgency', 'medium'),
                    item.get('impact', 'medium'), item.get('deadline_type', 'soft'),
                    item['created_at'], item['updated_at']
                ))
                migrated_items += 1
            except Exception as e:
                print(f"   ! Error migrating item {item['id']}: {e}")
        state_conn.commit()
        print(f"   ✓ Migrated {migrated_items} items to tasks")
        
        # 4. Update projects table with v2 data
        print("\n4. Updating projects...")
        v2_projects = v2_conn.execute("SELECT * FROM projects").fetchall()
        updated_projects = 0
        for row in v2_projects:
            proj = dict(row)
            existing = state_conn.execute("SELECT id FROM projects WHERE id = ?", (proj['id'],)).fetchone()
            if existing:
                # Update existing
                state_conn.execute("""
                    UPDATE projects SET 
                        name = ?, status = ?, health = ?, owner = ?, deadline = ?
                    WHERE id = ?
                """, (proj['name'], proj.get('status', 'active'), proj.get('health', 'green'),
                      proj.get('owner'), proj.get('deadline'), proj['id']))
            else:
                # Insert new
                state_conn.execute("""
                    INSERT INTO projects 
                    (id, source, name, status, health, owner, deadline)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (proj['id'], 'v2_migration', proj['name'], proj.get('status', 'active'),
                      proj.get('health', 'green'), proj.get('owner'), proj.get('deadline')))
            updated_projects += 1
        state_conn.commit()
        print(f"   ✓ Updated {updated_projects} projects")
        
        # 5. Migrate people
        print("\n5. Migrating people...")
        v2_people = v2_conn.execute("SELECT * FROM people").fetchall()
        migrated_people = 0
        for row in v2_people:
            person = dict(row)
            existing = state_conn.execute("SELECT id FROM people WHERE id = ?", (person['id'],)).fetchone()
            if existing:
                continue
            try:
                state_conn.execute("""
                    INSERT INTO people 
                    (id, name, email, phone, company, role, is_internal)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    person['id'], person['name'], person.get('email'), person.get('phone'),
                    person.get('company'), person.get('role'),
                    1 if person.get('type') == 'internal' else 0
                ))
                migrated_people += 1
            except Exception as e:
                print(f"   ! Error migrating person {person['id']}: {e}")
        state_conn.commit()
        print(f"   ✓ Migrated {migrated_people} people")
        
        # Summary
        print("\n" + "="*50)
        print("Migration complete!")
        print("="*50)
        
        # Verify counts
        clients_count = state_conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        tasks_count = state_conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        projects_count = state_conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        people_count = state_conn.execute("SELECT COUNT(*) FROM people").fetchone()[0]
        
        print(f"\nstate.db now contains:")
        print(f"  - {clients_count} clients")
        print(f"  - {tasks_count} tasks")
        print(f"  - {projects_count} projects")
        print(f"  - {people_count} people")
        
    finally:
        v2_conn.close()
        state_conn.close()


if __name__ == "__main__":
    migrate()
