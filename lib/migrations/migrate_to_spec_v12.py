#!/usr/bin/env python3
"""
Migration to MASTER_SPEC.md §12 - EXACT COMPLIANCE

This script rebuilds ALL tables to match §12 exactly:
- Column names, types, defaults as specified
- CHECK constraints as specified
- FOREIGN KEY declarations as specified
- Indexes as specified

Legacy columns are preserved AFTER §12 columns.
All runtime code must use §12 column names.
"""

import logging
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from lib import paths

logger = logging.getLogger(__name__)


DB_PATH = paths.db_path()
BACKUP_DIR = paths.data_dir() / "backups"


def backup_db() -> Path:
    """Create timestamped backup."""
    BACKUP_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"moh_time_os.db.pre_v12.{ts}"
    shutil.copy(DB_PATH, backup_path)
    logger.info(f"✓ Backup: {backup_path}")
    return backup_path


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def drop_all_views(conn):
    """Drop all views before table modifications."""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='view'")
    views = [r[0] for r in cursor.fetchall()]
    for v in views:
        cursor.execute(f"DROP VIEW IF EXISTS {v}")
    logger.info(f"✓ Dropped views: {views}")
    return views


def migrate_tasks(conn):
    """Migrate tasks to §12 schema."""
    cursor = conn.cursor()

    # Count before
    cursor.execute("SELECT COUNT(*) FROM tasks")
    before = cursor.fetchone()[0]

    # §12 tasks schema + legacy columns
    # Note: FOREIGN KEY constraints must come after ALL column definitions
    cursor.execute("""
        CREATE TABLE tasks_v12 (
            -- §12 REQUIRED COLUMNS (exact order, names, types, constraints)
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
            -- LEGACY COLUMNS (preserved for collector compatibility)
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
            -- §12 FOREIGN KEYS (must be at end after all columns)
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (brand_id) REFERENCES brands(id),
            FOREIGN KEY (client_id) REFERENCES clients(id),
            FOREIGN KEY (assignee_id) REFERENCES team_members(id)
        )
    """)

    # Migrate data
    cursor.execute("""
        INSERT INTO tasks_v12 (
            id, source, source_id, title, notes, status,
            project_id, brand_id, client_id,
            project_link_status, client_link_status,
            assignee_id, assignee_raw, lane, due_date, duration_min,
            created_at, updated_at,
            project, priority, due_time, assignee, tags, dependencies,
            blockers, context, synced_at, urgency, impact, sensitivity,
            effort_min, effort_max, waiting_for, deadline_type, dedupe_key,
            conflict_markers, delegated_by, delegated_at, assignee_name,
            priority_reasons, is_supervised, last_activity_at, stale_days,
            scheduled_block_id
        )
        SELECT
            id, source, source_id, title, notes,
            CASE WHEN status IN ('done', 'completed') THEN 'done'
                 WHEN status = 'archived' THEN 'archived'
                 WHEN status = 'pending' THEN 'active'
                 ELSE COALESCE(status, 'active') END,
            project_id, brand_id, client_id,
            COALESCE(project_link_status, 'unlinked'),
            COALESCE(client_link_status, 'unlinked'),
            assignee_id,
            COALESCE(assignee_raw, assignee_name, assignee),
            COALESCE(lane, 'ops'),
            due_date,
            COALESCE(duration_min, 60),
            COALESCE(created_at, datetime('now')),
            COALESCE(updated_at, datetime('now')),
            project, priority, due_time, assignee, tags, dependencies,
            blockers, context, synced_at, urgency, impact, sensitivity,
            effort_min, effort_max, waiting_for, deadline_type, dedupe_key,
            conflict_markers, delegated_by, delegated_at, assignee_name,
            priority_reasons, is_supervised, last_activity_at, stale_days,
            scheduled_block_id
        FROM tasks
    """)

    cursor.execute("DROP TABLE tasks")
    cursor.execute("ALTER TABLE tasks_v12 RENAME TO tasks")

    # §12 indexes
    cursor.execute("CREATE INDEX idx_tasks_project ON tasks(project_id)")
    cursor.execute("CREATE INDEX idx_tasks_client ON tasks(client_id)")
    cursor.execute("CREATE INDEX idx_tasks_project_link_status ON tasks(project_link_status)")
    cursor.execute("CREATE INDEX idx_tasks_client_link_status ON tasks(client_link_status)")
    cursor.execute("CREATE INDEX idx_tasks_assignee ON tasks(assignee_id)")

    cursor.execute("SELECT COUNT(*) FROM tasks")
    after = cursor.fetchone()[0]
    logger.info(f"✓ tasks: {before} → {after}")
    assert before == after, f"Row count mismatch: {before} vs {after}"


def migrate_communications(conn):
    """Migrate communications to §12 schema."""
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM communications")
    before = cursor.fetchone()[0]

    cursor.execute("""
        CREATE TABLE communications_v12 (
            -- §12 REQUIRED COLUMNS
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
            -- LEGACY COLUMNS
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
            -- §12 FOREIGN KEY (must be at end)
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )
    """)

    # Check if old table has from_email or from_address
    cursor.execute("PRAGMA table_info(communications)")
    cols = {r["name"] for r in cursor.fetchall()}
    from_col = "from_email" if "from_email" in cols else "from_address"
    to_col = "to_emails" if "to_emails" in cols else "to_addresses"

    cursor.execute(f"""
        INSERT INTO communications_v12 (
            id, source, source_id, thread_id,
            from_email, from_domain, to_emails,
            subject, snippet, body_text, content_hash, received_at,
            client_id, link_status, processed, created_at, updated_at,
            priority, requires_response, response_deadline, sentiment,
            labels, sensitivity, stakeholder_tier, lane, is_vip, from_name,
            is_unread, is_starred, is_important, priority_reasons,
            response_urgency, expected_response_by, processed_at, action_taken,
            linked_task_id, age_hours
        )
        SELECT
            id, source, source_id, thread_id,
            {from_col}, from_domain, {to_col},
            subject, snippet, body_text, content_hash, received_at,
            client_id, COALESCE(link_status, 'unlinked'), processed,
            COALESCE(created_at, datetime('now')), datetime('now'),
            priority, requires_response, response_deadline, sentiment,
            labels, sensitivity, stakeholder_tier, lane, is_vip, from_name,
            is_unread, is_starred, is_important, priority_reasons,
            response_urgency, expected_response_by, processed_at, action_taken,
            linked_task_id, age_hours
        FROM communications
    """)

    cursor.execute("DROP TABLE communications")
    cursor.execute("ALTER TABLE communications_v12 RENAME TO communications")

    # §12 indexes
    cursor.execute("CREATE INDEX idx_communications_client ON communications(client_id)")
    cursor.execute("CREATE INDEX idx_communications_processed ON communications(processed)")
    cursor.execute("CREATE INDEX idx_communications_content_hash ON communications(content_hash)")
    cursor.execute("CREATE INDEX idx_communications_from_email ON communications(from_email)")
    cursor.execute("CREATE INDEX idx_communications_from_domain ON communications(from_domain)")

    cursor.execute("SELECT COUNT(*) FROM communications")
    after = cursor.fetchone()[0]
    logger.info(f"✓ communications: {before} → {after}")
    assert before == after


def migrate_projects(conn):
    """Migrate projects to §12 schema."""
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM projects")
    before = cursor.fetchone()[0]

    cursor.execute("""
        CREATE TABLE projects_v12 (
            -- §12 REQUIRED COLUMNS
            id TEXT PRIMARY KEY,
            brand_id TEXT,
            client_id TEXT,
            is_internal INTEGER NOT NULL DEFAULT 0,
            name TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT 'project' CHECK (type IN ('project', 'retainer')),
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            -- LEGACY COLUMNS
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
            -- §12 FOREIGN KEYS (must be at end)
            FOREIGN KEY (brand_id) REFERENCES brands(id),
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )
    """)

    cursor.execute("""
        INSERT INTO projects_v12
        SELECT
            id, brand_id, client_id, COALESCE(is_internal, 0), name,
            COALESCE(type, 'project'), COALESCE(status, 'active'),
            COALESCE(created_at, datetime('now')), COALESCE(updated_at, datetime('now')),
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
    cursor.execute("ALTER TABLE projects_v12 RENAME TO projects")

    # §12 has no explicit indexes for projects, but we add useful ones
    cursor.execute("CREATE INDEX idx_projects_brand ON projects(brand_id)")
    cursor.execute("CREATE INDEX idx_projects_client ON projects(client_id)")
    cursor.execute("CREATE INDEX idx_projects_status ON projects(status)")

    cursor.execute("SELECT COUNT(*) FROM projects")
    after = cursor.fetchone()[0]
    logger.info(f"✓ projects: {before} → {after}")
    assert before == after


def migrate_clients(conn):
    """Migrate clients to §12 schema."""
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM clients")
    before = cursor.fetchone()[0]

    cursor.execute("""
        CREATE TABLE clients_v12 (
            -- §12 REQUIRED COLUMNS
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            tier TEXT DEFAULT 'C',
            health_score REAL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            -- LEGACY COLUMNS
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
            xero_contact_id TEXT
        )
    """)

    cursor.execute("""
        INSERT INTO clients_v12
        SELECT
            id, name, COALESCE(tier, 'C'), health_score,
            COALESCE(created_at, datetime('now')), COALESCE(updated_at, datetime('now')),
            type, financial_annual_value, financial_ar_outstanding,
            financial_ar_aging, financial_payment_pattern, relationship_health,
            relationship_trend, relationship_last_interaction, relationship_notes,
            contacts_json, active_projects_json, xero_contact_id
        FROM clients
    """)

    cursor.execute("DROP TABLE clients")
    cursor.execute("ALTER TABLE clients_v12 RENAME TO clients")

    cursor.execute("SELECT COUNT(*) FROM clients")
    after = cursor.fetchone()[0]
    logger.info(f"✓ clients: {before} → {after}")
    assert before == after


def migrate_invoices(conn):
    """Migrate invoices to §12 schema."""
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM invoices")
    before = cursor.fetchone()[0]

    cursor.execute("""
        CREATE TABLE invoices_v12 (
            -- §12 REQUIRED COLUMNS
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

    if before > 0:
        cursor.execute("""
            INSERT INTO invoices_v12
            SELECT * FROM invoices
        """)

    cursor.execute("DROP TABLE invoices")
    cursor.execute("ALTER TABLE invoices_v12 RENAME TO invoices")

    # §12 indexes
    cursor.execute("CREATE INDEX idx_invoices_client ON invoices(client_id)")
    cursor.execute("CREATE INDEX idx_invoices_status ON invoices(status)")
    cursor.execute("""
        CREATE INDEX idx_invoices_ar ON invoices(status, paid_date)
        WHERE status IN ('sent', 'overdue') AND paid_date IS NULL
    """)

    cursor.execute("SELECT COUNT(*) FROM invoices")
    after = cursor.fetchone()[0]
    logger.info(f"✓ invoices: {before} → {after}")
    assert before == after


def migrate_commitments(conn):
    """Migrate commitments to §12 schema."""
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM commitments")
    before = cursor.fetchone()[0]

    cursor.execute("""
        CREATE TABLE commitments_v12 (
            -- §12 REQUIRED COLUMNS
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
            source_type TEXT NOT NULL DEFAULT 'communication',
            source_id TEXT NOT NULL,
            text TEXT NOT NULL,
            type TEXT NOT NULL CHECK (type IN ('promise', 'request')),
            confidence REAL,
            deadline TEXT,
            speaker TEXT,
            target TEXT,
            client_id TEXT,
            task_id TEXT,
            status TEXT DEFAULT 'open' CHECK (status IN ('open', 'fulfilled', 'broken', 'cancelled')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (source_id) REFERENCES communications(id),
            FOREIGN KEY (client_id) REFERENCES clients(id),
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    """)

    if before > 0:
        cursor.execute("""
            INSERT INTO commitments_v12
            SELECT * FROM commitments
        """)

    cursor.execute("DROP TABLE commitments")
    cursor.execute("ALTER TABLE commitments_v12 RENAME TO commitments")

    # §12 indexes
    cursor.execute("CREATE INDEX idx_commitments_source ON commitments(source_id)")
    cursor.execute("CREATE INDEX idx_commitments_client ON commitments(client_id)")

    cursor.execute("SELECT COUNT(*) FROM commitments")
    after = cursor.fetchone()[0]
    logger.info(f"✓ commitments: {before} → {after}")
    assert before == after


def ensure_spec_tables(conn):
    """Ensure all §12 tables exist (create if missing)."""
    cursor = conn.cursor()

    # brands - check and recreate if needed
    cursor.execute("SELECT sql FROM sqlite_master WHERE name='brands'")
    brands_sql = cursor.fetchone()
    if brands_sql and "UNIQUE(client_id, name)" not in brands_sql[0]:
        cursor.execute("SELECT COUNT(*) FROM brands")
        before = cursor.fetchone()[0]
        cursor.execute("""
            CREATE TABLE brands_v12 (
                id TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (client_id) REFERENCES clients(id),
                UNIQUE(client_id, name)
            )
        """)
        cursor.execute("INSERT OR IGNORE INTO brands_v12 SELECT * FROM brands")
        cursor.execute("DROP TABLE brands")
        cursor.execute("ALTER TABLE brands_v12 RENAME TO brands")
        cursor.execute("SELECT COUNT(*) FROM brands")
        after = cursor.fetchone()[0]
        logger.info(f"✓ brands: {before} → {after}")
    # client_identities
    cursor.execute("SELECT name FROM sqlite_master WHERE name='client_identities'")
    if not cursor.fetchone():
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
        logger.info("✓ client_identities: created")
    # team_members
    cursor.execute("SELECT name FROM sqlite_master WHERE name='team_members'")
    if not cursor.fetchone():
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
        logger.info("✓ team_members: created")
    # capacity_lanes
    cursor.execute("SELECT name FROM sqlite_master WHERE name='capacity_lanes'")
    if not cursor.fetchone():
        cursor.execute("""
            CREATE TABLE capacity_lanes (
                id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
                name TEXT UNIQUE NOT NULL,
                owner_id TEXT,
                weekly_hours REAL NOT NULL CHECK (weekly_hours > 0),
                buffer_pct REAL DEFAULT 20,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (owner_id) REFERENCES team_members(id)
            )
        """)
        logger.info("✓ capacity_lanes: created")
    # resolution_queue
    cursor.execute("SELECT sql FROM sqlite_master WHERE name='resolution_queue'")
    rq_sql = cursor.fetchone()
    if rq_sql and "UNIQUE(entity_type, entity_id, issue_type)" not in rq_sql[0]:
        cursor.execute("SELECT COUNT(*) FROM resolution_queue")
        before = cursor.fetchone()[0]
        cursor.execute("""
            CREATE TABLE resolution_queue_v12 (
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
            INSERT OR IGNORE INTO resolution_queue_v12
            SELECT id, entity_type, entity_id, issue_type, priority, context,
                   created_at, expires_at, resolved_at, resolved_by, resolution_action
            FROM resolution_queue
        """)
        cursor.execute("DROP TABLE resolution_queue")
        cursor.execute("ALTER TABLE resolution_queue_v12 RENAME TO resolution_queue")
        cursor.execute("""
            CREATE INDEX idx_resolution_queue_pending
            ON resolution_queue(priority, created_at)
            WHERE resolved_at IS NULL
        """)
        cursor.execute("SELECT COUNT(*) FROM resolution_queue")
        after = cursor.fetchone()[0]
        logger.info(f"✓ resolution_queue: {before} → {after}")
    # pending_actions
    cursor.execute("SELECT name FROM sqlite_master WHERE name='pending_actions'")
    if not cursor.fetchone():
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
        cursor.execute("CREATE INDEX idx_pending_actions_status ON pending_actions(status)")
        logger.info("✓ pending_actions: created")
    # asana_project_map
    cursor.execute("SELECT name FROM sqlite_master WHERE name='asana_project_map'")
    if not cursor.fetchone():
        cursor.execute("""
            CREATE TABLE asana_project_map (
                asana_gid TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                asana_name TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
        """)
        logger.info("✓ asana_project_map: created")
    # asana_user_map
    cursor.execute("SELECT name FROM sqlite_master WHERE name='asana_user_map'")
    if not cursor.fetchone():
        cursor.execute("""
            CREATE TABLE asana_user_map (
                asana_gid TEXT PRIMARY KEY,
                team_member_id TEXT NOT NULL,
                asana_name TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (team_member_id) REFERENCES team_members(id)
            )
        """)
        logger.info("✓ asana_user_map: created")


def recreate_items_view(conn):
    """Recreate items view using §12 column names."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE VIEW IF NOT EXISTS items AS
        SELECT
            id,
            title AS what,
            status,
            assignee_raw AS owner,
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
    logger.info("✓ items view: created")


def verify_schema(conn):
    """Verify §12 compliance."""
    cursor = conn.cursor()
    logger.info("\n" + "=" * 60)
    logger.info("§12 SCHEMA VERIFICATION")
    logger.info("=" * 60)
    checks = []

    # tasks checks
    cursor.execute("SELECT sql FROM sqlite_master WHERE name='tasks'")
    tasks_sql = cursor.fetchone()[0]
    checks.append(
        (
            "tasks.project_link_status CHECK",
            "CHECK (project_link_status IN" in tasks_sql,
        )
    )
    checks.append(("tasks.client_link_status CHECK", "CHECK (client_link_status IN" in tasks_sql))
    checks.append(("tasks FK project_id", "FOREIGN KEY (project_id)" in tasks_sql))
    checks.append(("tasks FK client_id", "FOREIGN KEY (client_id)" in tasks_sql))

    # communications checks
    cursor.execute("SELECT sql FROM sqlite_master WHERE name='communications'")
    comms_sql = cursor.fetchone()[0]
    checks.append(("communications.from_email exists", "from_email TEXT" in comms_sql))
    checks.append(("communications.to_emails exists", "to_emails TEXT" in comms_sql))
    checks.append(("communications.link_status CHECK", "CHECK (link_status IN" in comms_sql))

    # projects checks
    cursor.execute("SELECT sql FROM sqlite_master WHERE name='projects'")
    proj_sql = cursor.fetchone()[0]
    checks.append(("projects.type CHECK", "CHECK (type IN" in proj_sql))

    # invoices checks
    cursor.execute("SELECT sql FROM sqlite_master WHERE name='invoices'")
    inv_sql = cursor.fetchone()[0]
    checks.append(("invoices.status CHECK", "CHECK (status IN" in inv_sql))
    checks.append(("invoices.aging_bucket CHECK", "CHECK (aging_bucket IN" in inv_sql))

    # Print results
    for name, passed in checks:
        logger.info(f"  {name}: {'✓' if passed else '✗'}")
    all_passed = all(p for _, p in checks)
    logger.info(f"\nAll checks passed: {'✓' if all_passed else '✗'}")
    return all_passed


def run_migration():
    """Execute full migration."""
    logger.info("=" * 60)
    logger.info("MIGRATION TO MASTER_SPEC.md §12")
    logger.info("=" * 60)
    backup_path = backup_db()

    conn = get_conn()
    conn.execute("PRAGMA foreign_keys=OFF")

    try:
        drop_all_views(conn)

        migrate_tasks(conn)
        migrate_communications(conn)
        migrate_projects(conn)
        migrate_clients(conn)
        migrate_invoices(conn)
        migrate_commitments(conn)
        ensure_spec_tables(conn)
        recreate_items_view(conn)

        conn.commit()

        if verify_schema(conn):
            logger.info("\n✓ MIGRATION SUCCESSFUL")
        else:
            raise Exception("Schema verification failed")

    except Exception as e:
        conn.rollback()
        logger.info(f"\n✗ MIGRATION FAILED: {e}")
        logger.info(f"  Restore from: {backup_path}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run_migration()
