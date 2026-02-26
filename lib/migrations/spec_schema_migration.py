"""
Spec Schema Migration - Align database with MASTER_SPEC.md §12

This migration:
1. Adds missing columns to tasks (project_id, brand_id, project_link_status, client_link_status)
2. Adds missing columns to projects (brand_id, is_internal, type)
3. Creates missing tables (brands, client_identities, invoices, team_members, resolution_queue, pending_actions, asana maps)
4. Creates required indexes

Run with: python -m lib.migrations.spec_schema_migration
"""

import logging
import sqlite3

from lib import paths

logger = logging.getLogger(__name__)


DB_PATH = paths.db_path()


def column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def table_exists(cursor, table: str) -> bool:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cursor.fetchone() is not None


def index_exists(cursor, index_name: str) -> bool:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name=?", (index_name,))
    return cursor.fetchone() is not None


def migrate_tasks(cursor):
    """Add missing columns to tasks table."""
    logger.info("\n=== Migrating tasks table ===")
    # Add project_id (FK to projects) - currently have 'project' as TEXT
    if not column_exists(cursor, "tasks", "project_id"):
        logger.info("Adding project_id column...")
        cursor.execute("ALTER TABLE tasks ADD COLUMN project_id TEXT")
    else:
        logger.info("project_id already exists")
    # Add brand_id
    if not column_exists(cursor, "tasks", "brand_id"):
        logger.info("Adding brand_id column...")
        cursor.execute("ALTER TABLE tasks ADD COLUMN brand_id TEXT")
    else:
        logger.info("brand_id already exists")
    # Add project_link_status
    if not column_exists(cursor, "tasks", "project_link_status"):
        logger.info("Adding project_link_status column...")
        cursor.execute("ALTER TABLE tasks ADD COLUMN project_link_status TEXT DEFAULT 'unlinked'")
    else:
        logger.info("project_link_status already exists")
    # Add client_link_status
    if not column_exists(cursor, "tasks", "client_link_status"):
        logger.info("Adding client_link_status column...")
        cursor.execute("ALTER TABLE tasks ADD COLUMN client_link_status TEXT DEFAULT 'unlinked'")
    else:
        logger.info("client_link_status already exists")
    # Create indexes
    indexes = [
        (
            "idx_tasks_project",
            "CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id)",
        ),
        (
            "idx_tasks_project_link_status",
            "CREATE INDEX IF NOT EXISTS idx_tasks_project_link_status ON tasks(project_link_status)",
        ),
        (
            "idx_tasks_client_link_status",
            "CREATE INDEX IF NOT EXISTS idx_tasks_client_link_status ON tasks(client_link_status)",
        ),
        (
            "idx_tasks_client",
            "CREATE INDEX IF NOT EXISTS idx_tasks_client ON tasks(client_id)",
        ),
        (
            "idx_tasks_assignee",
            "CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(assignee_id)",
        ),
    ]
    for idx_name, sql in indexes:
        if not index_exists(cursor, idx_name):
            logger.info(f"Creating index {idx_name}...")
            cursor.execute(sql)
        else:
            logger.info(f"Index {idx_name} already exists")


def migrate_projects(cursor):
    """Add missing columns to projects table."""
    logger.info("\n=== Migrating projects table ===")
    # Add brand_id
    if not column_exists(cursor, "projects", "brand_id"):
        logger.info("Adding brand_id column...")
        cursor.execute("ALTER TABLE projects ADD COLUMN brand_id TEXT")
    else:
        logger.info("brand_id already exists")
    # Add is_internal
    if not column_exists(cursor, "projects", "is_internal"):
        logger.info("Adding is_internal column...")
        cursor.execute("ALTER TABLE projects ADD COLUMN is_internal INTEGER NOT NULL DEFAULT 0")
    else:
        logger.info("is_internal already exists")
    # Add type
    if not column_exists(cursor, "projects", "type"):
        logger.info("Adding type column...")
        cursor.execute("ALTER TABLE projects ADD COLUMN type TEXT NOT NULL DEFAULT 'project'")
    else:
        logger.info("type already exists")


def migrate_clients(cursor):
    """Ensure clients table has health_score."""
    logger.info("\n=== Migrating clients table ===")
    if not column_exists(cursor, "clients", "health_score"):
        logger.info("Adding health_score column...")
        cursor.execute("ALTER TABLE clients ADD COLUMN health_score REAL")
    else:
        logger.info("health_score already exists")


def migrate_communications(cursor):
    """Ensure communications table has required columns."""
    logger.info("\n=== Migrating communications table ===")
    if not column_exists(cursor, "communications", "from_domain"):
        logger.info("Adding from_domain column...")
        cursor.execute("ALTER TABLE communications ADD COLUMN from_domain TEXT")
    else:
        logger.info("from_domain already exists")
    if not column_exists(cursor, "communications", "link_status"):
        logger.info("Adding link_status column...")
        cursor.execute("ALTER TABLE communications ADD COLUMN link_status TEXT DEFAULT 'unlinked'")
    else:
        logger.info("link_status already exists")
    if not column_exists(cursor, "communications", "content_hash"):
        logger.info("Adding content_hash column...")
        cursor.execute("ALTER TABLE communications ADD COLUMN content_hash TEXT")
    else:
        logger.info("content_hash already exists")
    if not column_exists(cursor, "communications", "client_id"):
        logger.info("Adding client_id column...")
        cursor.execute("ALTER TABLE communications ADD COLUMN client_id TEXT")
    else:
        logger.info("client_id already exists")
    # Create indexes (only if column exists)
    if column_exists(cursor, "communications", "client_id"):
        if not index_exists(cursor, "idx_communications_client"):
            logger.info("Creating index idx_communications_client...")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_communications_client ON communications(client_id)"
            )

    if not index_exists(cursor, "idx_communications_from_domain"):
        logger.info("Creating index idx_communications_from_domain...")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_communications_from_domain ON communications(from_domain)"
        )

    if not index_exists(cursor, "idx_communications_content_hash"):
        logger.info("Creating index idx_communications_content_hash...")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_communications_content_hash ON communications(content_hash)"
        )


def create_brands_table(cursor):
    """Create brands table if not exists."""
    logger.info("\n=== Creating brands table ===")
    if table_exists(cursor, "brands"):
        logger.info("brands table already exists")
        return

    cursor.execute("""
        CREATE TABLE brands (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (client_id) REFERENCES clients(id),
            UNIQUE(client_id, name)
        )
    """)
    logger.info("brands table created")


def create_client_identities_table(cursor):
    """Create client_identities table if not exists."""
    logger.info("\n=== Creating client_identities table ===")
    if table_exists(cursor, "client_identities"):
        logger.info("client_identities table already exists")
        return

    cursor.execute("""
        CREATE TABLE client_identities (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
            client_id TEXT NOT NULL,
            identity_type TEXT NOT NULL CHECK (identity_type IN ('email', 'domain')),
            identity_value TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (client_id) REFERENCES clients(id),
            UNIQUE(identity_type, identity_value)
        )
    """)
    logger.info("client_identities table created")


def create_team_members_table(cursor):
    """Create team_members table if not exists."""
    logger.info("\n=== Creating team_members table ===")
    if table_exists(cursor, "team_members"):
        logger.info("team_members table already exists")
        return

    cursor.execute("""
        CREATE TABLE team_members (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            asana_gid TEXT,
            default_lane TEXT DEFAULT 'ops',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    logger.info("team_members table created")


def create_invoices_table(cursor):
    """Create invoices table if not exists."""
    logger.info("\n=== Creating invoices table ===")
    if table_exists(cursor, "invoices"):
        logger.info("invoices table already exists")
        return

    cursor.execute("""
        CREATE TABLE invoices (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            external_id TEXT NOT NULL,
            client_id TEXT,
            client_name TEXT,
            brand_id TEXT,
            project_id TEXT,
            amount REAL NOT NULL,
            currency TEXT NOT NULL,
            issue_date TEXT NOT NULL,
            due_date TEXT,
            status TEXT NOT NULL CHECK (status IN ('draft', 'sent', 'paid', 'overdue', 'void')),
            paid_date TEXT,
            aging_bucket TEXT CHECK (aging_bucket IN ('current', '1-30', '31-60', '61-90', '90+', NULL)),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (client_id) REFERENCES clients(id),
            FOREIGN KEY (brand_id) REFERENCES brands(id),
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_client ON invoices(client_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status)")
    logger.info("invoices table created with indexes")


def create_resolution_queue_table(cursor):
    """Create resolution_queue table if not exists."""
    logger.info("\n=== Creating resolution_queue table ===")
    if table_exists(cursor, "resolution_queue"):
        logger.info("resolution_queue table already exists")
        return

    cursor.execute("""
        CREATE TABLE resolution_queue (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            issue_type TEXT NOT NULL,
            priority INTEGER NOT NULL DEFAULT 2,
            context TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at TEXT,
            resolved_at TEXT,
            resolved_by TEXT,
            resolution_action TEXT,
            UNIQUE(entity_type, entity_id, issue_type)
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_resolution_queue_pending
        ON resolution_queue(priority, created_at)
        WHERE resolved_at IS NULL
    """)
    logger.info("resolution_queue table created with index")


def create_pending_actions_table(cursor):
    """Create pending_actions table if not exists."""
    logger.info("\n=== Creating pending_actions table ===")
    if table_exists(cursor, "pending_actions"):
        logger.info("pending_actions table already exists")
        return

    cursor.execute("""
        CREATE TABLE pending_actions (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
            idempotency_key TEXT UNIQUE NOT NULL,
            action_type TEXT NOT NULL,
            entity_type TEXT,
            entity_id TEXT,
            payload TEXT NOT NULL,
            risk_level TEXT NOT NULL,
            approval_mode TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            proposed_at TEXT NOT NULL DEFAULT (datetime('now')),
            proposed_by TEXT,
            decided_at TEXT,
            decided_by TEXT,
            executed_at TEXT,
            execution_result TEXT,
            expires_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_pending_actions_status ON pending_actions(status)"
    )
    logger.info("pending_actions table created with index")


def create_asana_maps(cursor):
    """Create Asana mapping tables if not exist."""
    logger.info("\n=== Creating Asana mapping tables ===")
    if not table_exists(cursor, "asana_project_map"):
        cursor.execute("""
            CREATE TABLE asana_project_map (
                asana_gid TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                asana_name TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
        """)
        logger.info("asana_project_map table created")
    else:
        logger.info("asana_project_map already exists")
    if not table_exists(cursor, "asana_user_map"):
        cursor.execute("""
            CREATE TABLE asana_user_map (
                asana_gid TEXT PRIMARY KEY,
                team_member_id TEXT NOT NULL,
                asana_name TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (team_member_id) REFERENCES team_members(id)
            )
        """)
        logger.info("asana_user_map table created")
    else:
        logger.info("asana_user_map already exists")


def verify_schema(cursor):
    """Verify schema matches spec requirements."""
    logger.info("\n=== Verifying Schema ===")
    errors = []

    # Check tasks columns
    required_task_cols = [
        "id",
        "project_id",
        "brand_id",
        "client_id",
        "project_link_status",
        "client_link_status",
    ]
    cursor.execute("PRAGMA table_info(tasks)")
    task_cols = [row[1] for row in cursor.fetchall()]
    for col in required_task_cols:
        if col not in task_cols:
            errors.append(f"tasks missing column: {col}")

    # Verify NO is_internal on tasks
    if "is_internal" in task_cols:
        errors.append("tasks should NOT have is_internal column (per spec)")

    # Check projects columns
    required_project_cols = ["id", "brand_id", "client_id", "is_internal", "type"]
    cursor.execute("PRAGMA table_info(projects)")
    project_cols = [row[1] for row in cursor.fetchall()]
    for col in required_project_cols:
        if col not in project_cols:
            errors.append(f"projects missing column: {col}")

    # Check required tables exist
    required_tables = [
        "brands",
        "client_identities",
        "invoices",
        "team_members",
        "resolution_queue",
        "pending_actions",
        "asana_project_map",
        "asana_user_map",
    ]
    for table in required_tables:
        if not table_exists(cursor, table):
            errors.append(f"missing table: {table}")

    if errors:
        logger.info("ERRORS FOUND:")
        for e in errors:
            logger.info(f"  - {e}")
        return False
    logger.info("All schema requirements verified ✓")
    return True


def run_migration():
    """Run the full migration."""
    logger.info(f"Connecting to {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Migrate existing tables
        migrate_tasks(cursor)
        migrate_projects(cursor)
        migrate_clients(cursor)
        migrate_communications(cursor)

        # Create missing tables
        create_brands_table(cursor)
        create_client_identities_table(cursor)
        create_team_members_table(cursor)
        create_invoices_table(cursor)
        create_resolution_queue_table(cursor)
        create_pending_actions_table(cursor)
        create_asana_maps(cursor)

        # Verify
        success = verify_schema(cursor)

        if success:
            conn.commit()
            logger.info("\n✓ Migration committed successfully")
        else:
            conn.rollback()
            logger.info("\n✗ Migration rolled back due to errors")
            return False

    except (sqlite3.Error, ValueError, OSError) as e:
        conn.rollback()
        logger.info(f"\n✗ Migration failed: {e}")
        raise
    finally:
        conn.close()

    return True


if __name__ == "__main__":
    run_migration()
