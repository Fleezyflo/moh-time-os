#!/usr/bin/env python3
"""
Migrate database to canonical schema from MOH_TIME_OS.md spec.

Adds missing fields to items table:
- lane (text)
- urgency (text: critical/high/medium/low/none)
- impact (text: critical/high/medium/low/none)
- deadline_type (text: hard/soft)
- effort_min (integer, minutes)
- effort_max (integer, minutes)
- dependencies (json list of item IDs)
- sensitivity_flags (json list)
- recommended_action (text)
- dedupe_key (text, unique)
- conflict_markers (json)
- delegated_to (text, person ID)
- delegated_at (text, ISO timestamp)
"""

from pathlib import Path
from .store import get_connection, db_exists


MIGRATION_SQL = """
-- Add missing columns (SQLite allows ADD COLUMN one at a time)

-- Lane
ALTER TABLE items ADD COLUMN lane TEXT DEFAULT 'ops';

-- Priority dimensions
ALTER TABLE items ADD COLUMN urgency TEXT DEFAULT 'medium';
ALTER TABLE items ADD COLUMN impact TEXT DEFAULT 'medium';

-- Deadline type
ALTER TABLE items ADD COLUMN deadline_type TEXT DEFAULT 'soft';

-- Effort estimate (range in minutes)
ALTER TABLE items ADD COLUMN effort_min INTEGER;
ALTER TABLE items ADD COLUMN effort_max INTEGER;

-- Dependencies (JSON array of item IDs)
ALTER TABLE items ADD COLUMN dependencies TEXT DEFAULT '[]';

-- Sensitivity flags (JSON array)
ALTER TABLE items ADD COLUMN sensitivity_flags TEXT DEFAULT '[]';

-- Recommended next action
ALTER TABLE items ADD COLUMN recommended_action TEXT;

-- Dedupe key for idempotent operations
ALTER TABLE items ADD COLUMN dedupe_key TEXT;

-- Conflict markers (JSON)
ALTER TABLE items ADD COLUMN conflict_markers TEXT DEFAULT '{}';

-- Delegation fields
ALTER TABLE items ADD COLUMN delegated_to TEXT;
ALTER TABLE items ADD COLUMN delegated_at TEXT;

-- Create index on dedupe_key
CREATE INDEX IF NOT EXISTS idx_items_dedupe_key ON items(dedupe_key);

-- Create index on lane
CREATE INDEX IF NOT EXISTS idx_items_lane ON items(lane);

-- Create index on status
CREATE INDEX IF NOT EXISTS idx_items_status ON items(status);
"""

# Map old statuses to new canonical statuses
STATUS_MIGRATION = {
    'open': 'planned',
    'waiting': 'waitingFor',
    'done': 'done',
    'cancelled': 'dropped',
}


def check_column_exists(conn, table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    cursor = conn.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def migrate():
    """Run migration to add canonical fields."""
    if not db_exists():
        print("Database does not exist. Run initial setup first.")
        return False
    
    with get_connection() as conn:
        # Check what columns already exist
        existing = []
        new_columns = [
            'lane', 'urgency', 'impact', 'deadline_type',
            'effort_min', 'effort_max', 'dependencies',
            'sensitivity_flags', 'recommended_action',
            'dedupe_key', 'conflict_markers',
            'delegated_to', 'delegated_at'
        ]
        
        for col in new_columns:
            if check_column_exists(conn, 'items', col):
                existing.append(col)
        
        if existing:
            print(f"Columns already exist: {existing}")
        
        # Add missing columns
        added = []
        for col in new_columns:
            if col in existing:
                continue
            
            try:
                if col == 'lane':
                    conn.execute("ALTER TABLE items ADD COLUMN lane TEXT DEFAULT 'ops'")
                elif col == 'urgency':
                    conn.execute("ALTER TABLE items ADD COLUMN urgency TEXT DEFAULT 'medium'")
                elif col == 'impact':
                    conn.execute("ALTER TABLE items ADD COLUMN impact TEXT DEFAULT 'medium'")
                elif col == 'deadline_type':
                    conn.execute("ALTER TABLE items ADD COLUMN deadline_type TEXT DEFAULT 'soft'")
                elif col == 'effort_min':
                    conn.execute("ALTER TABLE items ADD COLUMN effort_min INTEGER")
                elif col == 'effort_max':
                    conn.execute("ALTER TABLE items ADD COLUMN effort_max INTEGER")
                elif col == 'dependencies':
                    conn.execute("ALTER TABLE items ADD COLUMN dependencies TEXT DEFAULT '[]'")
                elif col == 'sensitivity_flags':
                    conn.execute("ALTER TABLE items ADD COLUMN sensitivity_flags TEXT DEFAULT '[]'")
                elif col == 'recommended_action':
                    conn.execute("ALTER TABLE items ADD COLUMN recommended_action TEXT")
                elif col == 'dedupe_key':
                    conn.execute("ALTER TABLE items ADD COLUMN dedupe_key TEXT")
                elif col == 'conflict_markers':
                    conn.execute("ALTER TABLE items ADD COLUMN conflict_markers TEXT DEFAULT '{}'")
                elif col == 'delegated_to':
                    conn.execute("ALTER TABLE items ADD COLUMN delegated_to TEXT")
                elif col == 'delegated_at':
                    conn.execute("ALTER TABLE items ADD COLUMN delegated_at TEXT")
                
                added.append(col)
                print(f"Added column: {col}")
            except Exception as e:
                print(f"Error adding {col}: {e}")
        
        # Create indexes
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_items_dedupe_key ON items(dedupe_key)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_items_lane ON items(lane)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_items_status ON items(status)")
            print("Created indexes")
        except Exception as e:
            print(f"Error creating indexes: {e}")
        
        # Note: Status migration skipped because of CHECK constraint
        # The old statuses (open, waiting, done, cancelled) are kept for now
        # A full table recreation would be needed to change the constraint
        print("Status migration skipped (CHECK constraint in place)")
        
        conn.commit()
        print(f"\nMigration complete. Added {len(added)} columns.")
        return True


def verify():
    """Verify migration was successful."""
    if not db_exists():
        print("Database does not exist")
        return False
    
    with get_connection() as conn:
        cursor = conn.execute("PRAGMA table_info(items)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        required = [
            'lane', 'urgency', 'impact', 'deadline_type',
            'effort_min', 'effort_max', 'dependencies',
            'sensitivity_flags', 'recommended_action',
            'dedupe_key', 'conflict_markers',
            'delegated_to', 'delegated_at'
        ]
        
        missing = [c for c in required if c not in columns]
        
        if missing:
            print(f"Missing columns: {missing}")
            return False
        
        print("All canonical columns present")
        print(f"Total columns: {len(columns)}")
        return True


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        verify()
    else:
        migrate()
        verify()
