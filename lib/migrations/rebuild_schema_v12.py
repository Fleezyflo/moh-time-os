"""
Schema Rebuild Migration - Align with MASTER_SPEC.md §12

This script rebuilds tables to match §12 exactly, including:
- CHECK constraints
- Column name corrections (from_address→from_email, etc.)
- Missing columns (updated_at on communications)
- Proper defaults

SQLite requires DROP+CREATE for adding CHECK constraints.
Data is preserved via temporary tables.
"""

import logging
import sqlite3
from datetime import datetime

from lib import paths

logger = logging.getLogger(__name__)


DB_PATH = paths.db_path()
BACKUP_DIR = paths.data_dir() / "backups"


def backup_db():
    """Create backup before migration."""
    BACKUP_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"moh_time_os.db.pre_v12_rebuild.{timestamp}"

    import shutil

    shutil.copy(DB_PATH, backup_path)
    logger.info(f"Backup created: {backup_path}")
    return backup_path


def rebuild_tasks(conn):
    """Rebuild tasks table to match §12."""
    cursor = conn.cursor()

    # Check current row count
    cursor.execute("SELECT COUNT(*) FROM tasks")
    count_before = cursor.fetchone()[0]
    logger.info(f"Tasks before: {count_before}")
    # Create new table with §12 schema
    cursor.execute("""
        CREATE TABLE tasks_new (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            source_id TEXT,
            title TEXT NOT NULL,
            notes TEXT,
            status TEXT DEFAULT 'active',
            project_id TEXT,
            brand_id TEXT,
            client_id TEXT,
            project_link_status TEXT DEFAULT 'unlinked'
                CHECK (project_link_status IN ('linked', 'partial', 'unlinked')),
            client_link_status TEXT DEFAULT 'unlinked'
                CHECK (client_link_status IN ('linked', 'unlinked', 'n/a')),
            assignee_id TEXT,
            assignee_raw TEXT,
            lane TEXT DEFAULT 'ops',
            due_date TEXT,
            duration_min INTEGER DEFAULT 60,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            -- Legacy columns preserved for collector compatibility
            project TEXT,
            priority INTEGER DEFAULT 50,
            due_time TEXT,
            assignee TEXT,
            tags TEXT,
            dependencies TEXT,
            blockers TEXT,
            context TEXT,
            synced_at TEXT,
            urgency TEXT DEFAULT 'medium',
            impact TEXT DEFAULT 'medium',
            sensitivity TEXT,
            effort_min INTEGER,
            effort_max INTEGER,
            waiting_for TEXT,
            deadline_type TEXT DEFAULT 'soft',
            dedupe_key TEXT,
            conflict_markers TEXT,
            delegated_by TEXT,
            delegated_at TEXT,
            assignee_name TEXT,
            priority_reasons TEXT,
            is_supervised INTEGER DEFAULT 0,
            last_activity_at TEXT,
            stale_days INTEGER DEFAULT 0,
            scheduled_block_id TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (brand_id) REFERENCES brands(id),
            FOREIGN KEY (client_id) REFERENCES clients(id),
            FOREIGN KEY (assignee_id) REFERENCES team_members(id)
        )
    """)

    # Copy data - map old columns to new
    cursor.execute("""
        INSERT INTO tasks_new
        SELECT
            id, source, source_id, title, notes,
            CASE WHEN status IN ('done', 'completed') THEN 'done'
                 WHEN status = 'archived' THEN 'archived'
                 ELSE 'active' END as status,
            project_id, brand_id, client_id,
            COALESCE(project_link_status, 'unlinked'),
            COALESCE(client_link_status, 'unlinked'),
            assignee_id,
            COALESCE(assignee_name, assignee) as assignee_raw,
            lane,
            due_date,
            COALESCE(duration_min, 60),
            COALESCE(created_at, datetime('now')),
            COALESCE(updated_at, datetime('now')),
            -- Legacy columns
            project, priority, due_time, assignee, tags, dependencies,
            blockers, context, synced_at, urgency, impact, sensitivity,
            effort_min, effort_max, waiting_for, deadline_type, dedupe_key,
            conflict_markers, delegated_by, delegated_at, assignee_name,
            priority_reasons, is_supervised, last_activity_at, stale_days,
            scheduled_block_id
        FROM tasks
    """)

    # Drop old, rename new
    cursor.execute("DROP TABLE tasks")
    cursor.execute("ALTER TABLE tasks_new RENAME TO tasks")

    # Recreate indexes
    cursor.execute("CREATE INDEX idx_tasks_project ON tasks(project_id)")
    cursor.execute("CREATE INDEX idx_tasks_client ON tasks(client_id)")
    cursor.execute("CREATE INDEX idx_tasks_project_link_status ON tasks(project_link_status)")
    cursor.execute("CREATE INDEX idx_tasks_client_link_status ON tasks(client_link_status)")
    cursor.execute("CREATE INDEX idx_tasks_assignee ON tasks(assignee_id)")
    cursor.execute("CREATE INDEX idx_tasks_status ON tasks(status)")
    cursor.execute("CREATE INDEX idx_tasks_due ON tasks(due_date)")
    cursor.execute("CREATE INDEX idx_tasks_lane ON tasks(lane)")

    # Verify count
    cursor.execute("SELECT COUNT(*) FROM tasks")
    count_after = cursor.fetchone()[0]
    logger.info(f"Tasks after: {count_after}")
    if count_before != count_after:
        raise Exception(f"Row count mismatch! Before: {count_before}, After: {count_after}")

    return count_after


def rebuild_communications(conn):
    """Rebuild communications table to match §12."""
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM communications")
    count_before = cursor.fetchone()[0]
    logger.info(f"Communications before: {count_before}")
    # Create new table with §12 schema
    cursor.execute("""
        CREATE TABLE communications_new (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            source_id TEXT,
            thread_id TEXT,
            from_email TEXT,
            from_domain TEXT,
            to_emails TEXT,
            subject TEXT,
            snippet TEXT,
            body_text TEXT,
            content_hash TEXT,
            received_at TEXT,
            client_id TEXT,
            link_status TEXT DEFAULT 'unlinked' CHECK (link_status IN ('linked', 'unlinked')),
            processed INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            -- Legacy columns preserved
            priority INTEGER DEFAULT 50,
            requires_response INTEGER DEFAULT 0,
            response_deadline TEXT,
            sentiment TEXT,
            labels TEXT,
            sensitivity TEXT,
            stakeholder_tier TEXT DEFAULT 'significant',
            lane TEXT,
            is_vip INTEGER DEFAULT 0,
            from_name TEXT,
            is_unread INTEGER DEFAULT 0,
            is_starred INTEGER DEFAULT 0,
            is_important INTEGER DEFAULT 0,
            priority_reasons TEXT,
            response_urgency TEXT,
            expected_response_by TEXT,
            processed_at TEXT,
            action_taken TEXT,
            linked_task_id TEXT,
            age_hours REAL,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )
    """)

    # Copy data - rename columns
    cursor.execute("""
        INSERT INTO communications_new
        SELECT
            id, source, source_id, thread_id,
            from_address as from_email,
            from_domain,
            to_addresses as to_emails,
            subject, snippet, body_text, content_hash, received_at,
            client_id,
            COALESCE(link_status, 'unlinked'),
            processed,
            COALESCE(created_at, datetime('now')),
            datetime('now') as updated_at,
            -- Legacy
            priority, requires_response, response_deadline, sentiment,
            labels, sensitivity, stakeholder_tier, lane, is_vip, from_name,
            is_unread, is_starred, is_important, priority_reasons,
            response_urgency, expected_response_by, processed_at, action_taken,
            linked_task_id, age_hours
        FROM communications
    """)

    cursor.execute("DROP TABLE communications")
    cursor.execute("ALTER TABLE communications_new RENAME TO communications")

    # Recreate indexes
    cursor.execute("CREATE INDEX idx_communications_client ON communications(client_id)")
    cursor.execute("CREATE INDEX idx_communications_processed ON communications(processed)")
    cursor.execute("CREATE INDEX idx_communications_content_hash ON communications(content_hash)")
    cursor.execute("CREATE INDEX idx_communications_from_email ON communications(from_email)")
    cursor.execute("CREATE INDEX idx_communications_from_domain ON communications(from_domain)")

    cursor.execute("SELECT COUNT(*) FROM communications")
    count_after = cursor.fetchone()[0]
    logger.info(f"Communications after: {count_after}")
    if count_before != count_after:
        raise Exception(f"Row count mismatch! Before: {count_before}, After: {count_after}")

    return count_after


def rebuild_projects(conn):
    """Rebuild projects table to match §12."""
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM projects")
    count_before = cursor.fetchone()[0]
    logger.info(f"Projects before: {count_before}")
    cursor.execute("""
        CREATE TABLE projects_new (
            id TEXT PRIMARY KEY,
            brand_id TEXT,
            client_id TEXT,
            is_internal INTEGER NOT NULL DEFAULT 0,
            name TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT 'project' CHECK (type IN ('project', 'retainer')),
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            -- Legacy columns
            source TEXT,
            source_id TEXT,
            health TEXT DEFAULT 'green',
            owner TEXT,
            deadline TEXT,
            tasks_total INTEGER DEFAULT 0,
            tasks_done INTEGER DEFAULT 0,
            blockers TEXT,
            next_milestone TEXT,
            context TEXT,
            involvement_type TEXT DEFAULT 'mixed',
            aliases TEXT,
            recognizers TEXT,
            lane_mapping TEXT,
            routing_rules TEXT,
            delegation_policy TEXT,
            reporting_cadence TEXT DEFAULT 'weekly',
            sensitivity_profile TEXT,
            enrollment_evidence TEXT,
            enrolled_at TEXT,
            health_reasons TEXT,
            owner_id TEXT,
            owner_name TEXT,
            lane TEXT,
            client TEXT,
            days_to_deadline INTEGER,
            tasks_completed INTEGER DEFAULT 0,
            tasks_overdue INTEGER DEFAULT 0,
            tasks_blocked INTEGER DEFAULT 0,
            completion_pct REAL DEFAULT 0,
            velocity_trend TEXT,
            next_milestone_date TEXT,
            last_activity_at TEXT,
            enrollment_status TEXT,
            rule_bundles TEXT,
            start_date TEXT,
            target_end_date TEXT,
            value REAL,
            stakes TEXT,
            description TEXT,
            milestones TEXT,
            team TEXT,
            asana_project_id TEXT,
            proposed_at TEXT,
            FOREIGN KEY (brand_id) REFERENCES brands(id),
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )
    """)

    cursor.execute("""
        INSERT INTO projects_new
        SELECT
            id, brand_id, client_id, is_internal, name,
            COALESCE(type, 'project'),
            status,
            COALESCE(created_at, datetime('now')),
            COALESCE(updated_at, datetime('now')),
            -- Legacy
            source, source_id, health, owner, deadline, tasks_total, tasks_done,
            blockers, next_milestone, context, involvement_type, aliases,
            recognizers, lane_mapping, routing_rules, delegation_policy,
            reporting_cadence, sensitivity_profile, enrollment_evidence,
            enrolled_at, health_reasons, owner_id, owner_name, lane, client,
            days_to_deadline, tasks_completed, tasks_overdue, tasks_blocked,
            completion_pct, velocity_trend, next_milestone_date, last_activity_at,
            enrollment_status, rule_bundles, start_date, target_end_date, value,
            stakes, description, milestones, team, asana_project_id, proposed_at
        FROM projects
    """)

    cursor.execute("DROP TABLE projects")
    cursor.execute("ALTER TABLE projects_new RENAME TO projects")

    cursor.execute("CREATE INDEX idx_projects_status ON projects(status)")
    cursor.execute("CREATE INDEX idx_projects_brand ON projects(brand_id)")
    cursor.execute("CREATE INDEX idx_projects_client ON projects(client_id)")

    cursor.execute("SELECT COUNT(*) FROM projects")
    count_after = cursor.fetchone()[0]
    logger.info(f"Projects after: {count_after}")
    if count_before != count_after:
        raise Exception("Row count mismatch!")

    return count_after


def drop_views(conn):
    """Drop views that depend on tables we're rebuilding."""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='view'")
    views = [row[0] for row in cursor.fetchall()]

    dropped = []
    for view in views:
        cursor.execute(f"DROP VIEW IF EXISTS {view}")
        dropped.append(view)

    logger.info(f"Dropped views: {dropped}")
    return dropped


def recreate_items_view(conn):
    """Recreate items view after table rebuild."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE VIEW items AS
        SELECT
            id,
            title AS what,
            CASE status
                WHEN 'pending' THEN 'open'
                WHEN 'completed' THEN 'done'
                ELSE status
            END AS status,
            assignee AS owner,
            assignee_id AS owner_id,
            NULL AS counterparty,
            NULL AS counterparty_id,
            due_date AS due,
            waiting_for AS waiting_since,
            client_id,
            project_id,
            context AS context_snapshot_json,
            NULL AS stakes,
            NULL AS history_context,
            source AS source_type,
            source_id AS source_ref,
            created_at AS captured_at,
            NULL AS resolution_outcome,
            NULL AS resolution_notes,
            NULL AS resolved_at,
            created_at,
            updated_at,
            lane,
            urgency,
            impact,
            deadline_type,
            effort_min,
            effort_max,
            dependencies,
            sensitivity AS sensitivity_flags,
            NULL AS recommended_action,
            dedupe_key,
            conflict_markers,
            NULL AS delegated_to,
            delegated_at
        FROM tasks
    """)
    logger.info("Recreated items view")


def run_migration():
    """Run full schema rebuild."""
    logger.info("=" * 60)
    logger.info("Schema Rebuild Migration to §12")
    logger.info("=" * 60)
    # Backup first
    backup_path = backup_db()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys=OFF")  # Disable during migration

    try:
        # Drop dependent views first
        logger.info("\nDropping dependent views...")
        drop_views(conn)

        logger.info("\nRebuilding tasks...")
        rebuild_tasks(conn)

        logger.info("\nRebuilding communications...")
        rebuild_communications(conn)

        logger.info("\nRebuilding projects...")
        rebuild_projects(conn)

        # Recreate views
        logger.info("\nRecreating views...")
        recreate_items_view(conn)

        conn.commit()
        logger.info("\n✓ Migration complete!")
        # Verify CHECK constraints exist
        logger.info("\nVerifying CHECK constraints...")
        cursor = conn.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE name='tasks'")
        tasks_sql = cursor.fetchone()[0]
        if "CHECK (project_link_status IN" in tasks_sql:
            logger.info("  ✓ tasks.project_link_status CHECK constraint exists")
        if "CHECK (client_link_status IN" in tasks_sql:
            logger.info("  ✓ tasks.client_link_status CHECK constraint exists")
        cursor.execute("SELECT sql FROM sqlite_master WHERE name='communications'")
        comms_sql = cursor.fetchone()[0]
        if "CHECK (link_status IN" in comms_sql:
            logger.info("  ✓ communications.link_status CHECK constraint exists")
        cursor.execute("SELECT sql FROM sqlite_master WHERE name='projects'")
        proj_sql = cursor.fetchone()[0]
        if "CHECK (type IN" in proj_sql:
            logger.info("  ✓ projects.type CHECK constraint exists")
    except (sqlite3.Error, ValueError, OSError) as e:
        conn.rollback()
        logger.info(f"\n✗ Migration failed: {e}")
        logger.info(f"  Restore from: {backup_path}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run_migration()
