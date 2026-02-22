"""
Centralized Database Access for MOH TIME OS.

Single source of truth for:
- DB path resolution
- Connection factory
- Schema migrations
- Startup validation

ALL code must use this module for DB access. No direct sqlite3.connect() elsewhere.
"""

import logging
import re
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from lib import paths

logger = logging.getLogger(__name__)

# ============================================================
# SQL IDENTIFIER VALIDATION
# ============================================================

_SAFE_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def validate_identifier(name: str) -> str:
    """Validate that *name* is a safe SQL identifier (table or column name).

    Returns the name unchanged if valid; raises ``ValueError`` otherwise.
    This prevents SQL injection via dynamic identifier interpolation.
    """
    if not _SAFE_IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return name


# Schema version - increment when adding migrations
SCHEMA_VERSION = 10

# ============================================================
# REQUIRED TABLES - Create if missing
# ============================================================
REQUIRED_TABLES = {
    "clients": """
        CREATE TABLE IF NOT EXISTS clients (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            tier TEXT CHECK (tier IN ('A', 'B', 'C')),
            type TEXT,
            financial_annual_value REAL,
            financial_ar_outstanding REAL,
            financial_ar_aging TEXT,
            financial_payment_pattern TEXT,
            relationship_health TEXT CHECK (relationship_health IN
                ('excellent', 'good', 'fair', 'poor', 'critical')),
            relationship_trend TEXT CHECK (relationship_trend IN
                ('improving', 'stable', 'declining')),
            relationship_last_interaction TEXT,
            relationship_notes TEXT,
            contacts_json TEXT,
            active_projects_json TEXT,
            xero_contact_id TEXT,
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
    """,
    "events": """
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            source TEXT,
            source_id TEXT,
            title TEXT,
            start_at TEXT,
            end_at TEXT,
            location TEXT,
            attendees TEXT,
            status TEXT DEFAULT 'confirmed',
            prep_required TEXT,
            prep_notes TEXT,
            context TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """,
    "invoices": """
        CREATE TABLE IF NOT EXISTS invoices (
            id TEXT PRIMARY KEY,
            source_id TEXT,
            client_id TEXT,
            client_name TEXT,
            status TEXT DEFAULT 'pending',
            total REAL,
            amount_due REAL,
            currency TEXT DEFAULT 'AED',
            issued_at TEXT,
            due_at TEXT,
            paid_at TEXT,
            aging_bucket TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """,
}

# ============================================================
# COLLECTOR EXPANSION TABLES - New tables for full API coverage
# ============================================================
COLLECTOR_EXPANSION_TABLES = {
    "asana_custom_fields": """
        CREATE TABLE IF NOT EXISTS asana_custom_fields (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            task_id TEXT,
            field_name TEXT NOT NULL,
            field_type TEXT NOT NULL,
            text_value TEXT,
            number_value REAL,
            enum_value TEXT,
            date_value TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "asana_subtasks": """
        CREATE TABLE IF NOT EXISTS asana_subtasks (
            id TEXT PRIMARY KEY,
            parent_task_id TEXT NOT NULL,
            name TEXT NOT NULL,
            assignee_id TEXT,
            assignee_name TEXT,
            completed INTEGER DEFAULT 0,
            due_on TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "asana_sections": """
        CREATE TABLE IF NOT EXISTS asana_sections (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            sort_order INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "asana_stories": """
        CREATE TABLE IF NOT EXISTS asana_stories (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            type TEXT NOT NULL,
            text TEXT,
            created_by TEXT,
            created_at TEXT NOT NULL
        )
    """,
    "asana_task_dependencies": """
        CREATE TABLE IF NOT EXISTS asana_task_dependencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            depends_on_task_id TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(task_id, depends_on_task_id)
        )
    """,
    "asana_portfolios": """
        CREATE TABLE IF NOT EXISTS asana_portfolios (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            owner_id TEXT,
            owner_name TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "asana_goals": """
        CREATE TABLE IF NOT EXISTS asana_goals (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            owner_id TEXT,
            owner_name TEXT,
            status TEXT,
            due_on TEXT,
            html_notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "asana_attachments": """
        CREATE TABLE IF NOT EXISTS asana_attachments (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            name TEXT NOT NULL,
            download_url TEXT,
            host TEXT,
            size_bytes INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "gmail_participants": """
        CREATE TABLE IF NOT EXISTS gmail_participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT NOT NULL,
            role TEXT NOT NULL,
            email TEXT NOT NULL,
            name TEXT
        )
    """,
    "gmail_attachments": """
        CREATE TABLE IF NOT EXISTS gmail_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            mime_type TEXT,
            size_bytes INTEGER,
            attachment_id TEXT
        )
    """,
    "gmail_labels": """
        CREATE TABLE IF NOT EXISTS gmail_labels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT NOT NULL,
            label_id TEXT NOT NULL,
            label_name TEXT
        )
    """,
    "calendar_attendees": """
        CREATE TABLE IF NOT EXISTS calendar_attendees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL,
            email TEXT NOT NULL,
            display_name TEXT,
            response_status TEXT,
            organizer INTEGER DEFAULT 0,
            self INTEGER DEFAULT 0
        )
    """,
    "calendar_recurrence_rules": """
        CREATE TABLE IF NOT EXISTS calendar_recurrence_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL,
            rrule TEXT NOT NULL
        )
    """,
    "chat_reactions": """
        CREATE TABLE IF NOT EXISTS chat_reactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT NOT NULL,
            emoji TEXT NOT NULL,
            user_id TEXT,
            user_name TEXT
        )
    """,
    "chat_attachments": """
        CREATE TABLE IF NOT EXISTS chat_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT NOT NULL,
            name TEXT,
            content_type TEXT,
            source_uri TEXT,
            thumbnail_uri TEXT
        )
    """,
    "chat_space_metadata": """
        CREATE TABLE IF NOT EXISTS chat_space_metadata (
            space_id TEXT PRIMARY KEY,
            display_name TEXT,
            space_type TEXT,
            threaded INTEGER DEFAULT 0,
            member_count INTEGER,
            created_time TEXT,
            last_synced TEXT
        )
    """,
    "chat_space_members": """
        CREATE TABLE IF NOT EXISTS chat_space_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            space_id TEXT NOT NULL,
            member_id TEXT NOT NULL,
            display_name TEXT,
            email TEXT,
            role TEXT,
            UNIQUE(space_id, member_id)
        )
    """,
    "xero_line_items": """
        CREATE TABLE IF NOT EXISTS xero_line_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id TEXT NOT NULL,
            description TEXT,
            quantity REAL,
            unit_amount REAL,
            line_amount REAL,
            tax_type TEXT,
            tax_amount REAL,
            account_code TEXT,
            tracking_category TEXT,
            tracking_option TEXT
        )
    """,
    "xero_contacts": """
        CREATE TABLE IF NOT EXISTS xero_contacts (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            account_number TEXT,
            tax_number TEXT,
            is_supplier INTEGER DEFAULT 0,
            is_customer INTEGER DEFAULT 0,
            default_currency TEXT,
            outstanding_balance REAL,
            overdue_balance REAL,
            last_synced TEXT
        )
    """,
    "xero_credit_notes": """
        CREATE TABLE IF NOT EXISTS xero_credit_notes (
            id TEXT PRIMARY KEY,
            contact_id TEXT,
            date TEXT,
            status TEXT,
            total REAL,
            currency_code TEXT,
            remaining_credit REAL,
            allocated_amount REAL,
            last_synced TEXT
        )
    """,
    "xero_bank_transactions": """
        CREATE TABLE IF NOT EXISTS xero_bank_transactions (
            id TEXT PRIMARY KEY,
            type TEXT,
            contact_id TEXT,
            date TEXT,
            status TEXT,
            total REAL,
            currency_code TEXT,
            reference TEXT,
            last_synced TEXT
        )
    """,
    "xero_tax_rates": """
        CREATE TABLE IF NOT EXISTS xero_tax_rates (
            name TEXT PRIMARY KEY,
            tax_type TEXT,
            effective_rate REAL,
            status TEXT
        )
    """,
}

# ============================================================
# REQUIRED COLUMNS - Add if missing
# ============================================================
REQUIRED_COLUMNS = {
    "tasks": [
        ("description", "TEXT DEFAULT ''"),
        ("project_id", "TEXT"),
        ("notes", "TEXT"),
        ("completed_at", "TEXT"),
        ("priority_reasons", "TEXT"),
        ("section_id", "TEXT"),
        ("section_name", "TEXT"),
        ("subtask_count", "INTEGER DEFAULT 0"),
        ("has_dependencies", "INTEGER DEFAULT 0"),
        ("attachment_count", "INTEGER DEFAULT 0"),
        ("story_count", "INTEGER DEFAULT 0"),
        ("custom_fields_json", "TEXT"),
    ],
    "communications": [
        ("content_hash", "TEXT"),
        ("body_text_source", "TEXT"),
        ("body_text", "TEXT"),
        ("received_at", "TEXT"),
        ("sensitivity", "TEXT"),
        ("stakeholder_tier", "TEXT"),
        ("is_read", "INTEGER"),
        ("is_starred", "INTEGER"),
        ("importance", "TEXT"),
        ("has_attachments", "INTEGER DEFAULT 0"),
        ("attachment_count", "INTEGER DEFAULT 0"),
        ("label_ids", "TEXT"),
    ],
    "events": [
        ("prep_notes", "TEXT"),
        ("start_at", "TEXT"),
        ("end_at", "TEXT"),
        ("organizer_email", "TEXT"),
        ("organizer_name", "TEXT"),
        ("conference_url", "TEXT"),
        ("conference_type", "TEXT"),
        ("recurrence", "TEXT"),
        ("event_type", "TEXT"),
        ("calendar_id", "TEXT DEFAULT 'primary'"),
        ("attendee_count", "INTEGER DEFAULT 0"),
        ("accepted_count", "INTEGER DEFAULT 0"),
        ("declined_count", "INTEGER DEFAULT 0"),
    ],
    "invoices": [
        ("source_id", "TEXT"),
        ("total", "REAL"),
        ("currency", "TEXT DEFAULT 'AED'"),
        ("issued_at", "TEXT"),
        ("due_at", "TEXT"),
    ],
    "people": [
        ("type", "TEXT DEFAULT 'external'"),
    ],
    "projects": [
        ("enrollment_status", "TEXT DEFAULT 'enrolled'"),
        ("rule_bundles", "TEXT"),
        ("brand_id", "TEXT"),
    ],
    "proposals_v4": [
        ("scope_level", "TEXT DEFAULT 'project'"),
        ("scope_name", "TEXT"),
        ("client_id", "TEXT"),
        ("client_name", "TEXT"),
        ("client_tier", "TEXT"),
        ("brand_id", "TEXT"),
        ("brand_name", "TEXT"),
        ("engagement_type", "TEXT"),
        ("signal_summary_json", "TEXT"),
        ("score_breakdown_json", "TEXT"),
        ("affected_task_ids_json", "TEXT"),
    ],
    "signals": [
        ("resolved_at", "TEXT"),
        ("resolution", "TEXT"),
    ],
    "chat_messages": [
        ("thread_id", "TEXT"),
        ("thread_reply_count", "INTEGER DEFAULT 0"),
        ("reaction_count", "INTEGER DEFAULT 0"),
        ("has_attachment", "INTEGER DEFAULT 0"),
        ("attachment_count", "INTEGER DEFAULT 0"),
    ],
}

# ============================================================
# V29 SPEC SCHEMA - Tables for CLIENT-UI-SPEC-v2.9.md
# ============================================================
V29_SCHEMA_SQL = """
-- Issues table per §6.14
CREATE TABLE IF NOT EXISTS issues_v29 (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('financial', 'schedule_delivery', 'communication', 'risk')),
    state TEXT NOT NULL DEFAULT 'detected' CHECK (state IN (
        'detected', 'surfaced', 'snoozed', 'acknowledged', 'addressing',
        'awaiting_resolution', 'regression_watch', 'closed', 'regressed'
    )),
    severity TEXT NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),
    client_id TEXT NOT NULL,
    brand_id TEXT,
    engagement_id TEXT,
    title TEXT NOT NULL,
    evidence TEXT,
    evidence_version TEXT DEFAULT 'v1',
    aggregation_key TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    snoozed_until TEXT,
    snoozed_by TEXT,
    snoozed_at TEXT,
    snooze_reason TEXT,
    tagged_by_user_id TEXT,
    tagged_at TEXT,
    assigned_to TEXT,
    assigned_at TEXT,
    assigned_by TEXT,
    suppressed INTEGER NOT NULL DEFAULT 0,
    suppressed_at TEXT,
    suppressed_by TEXT,
    escalated INTEGER NOT NULL DEFAULT 0,
    escalated_at TEXT,
    escalated_by TEXT,
    regression_watch_until TEXT,
    closed_at TEXT,
    FOREIGN KEY (client_id) REFERENCES clients(id)
);

CREATE INDEX IF NOT EXISTS idx_issues_v29_client ON issues_v29(client_id);
CREATE INDEX IF NOT EXISTS idx_issues_v29_state ON issues_v29(state);
CREATE INDEX IF NOT EXISTS idx_issues_v29_severity ON issues_v29(severity);
CREATE INDEX IF NOT EXISTS idx_issues_v29_type ON issues_v29(type);

-- Issue transitions audit table
CREATE TABLE IF NOT EXISTS issue_transitions_v29 (
    id TEXT PRIMARY KEY,
    issue_id TEXT NOT NULL,
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    action TEXT,
    actor TEXT,
    reason TEXT,
    transitioned_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (issue_id) REFERENCES issues_v29(id)
);

CREATE INDEX IF NOT EXISTS idx_issue_transitions_v29_issue ON issue_transitions_v29(issue_id);

-- Inbox items table per §6.13
CREATE TABLE IF NOT EXISTS inbox_items_v29 (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('issue', 'flagged_signal', 'orphan', 'ambiguous')),
    state TEXT NOT NULL DEFAULT 'proposed' CHECK (state IN (
        'proposed', 'snoozed', 'linked_to_issue', 'dismissed'
    )),
    severity TEXT NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),
    proposed_at TEXT NOT NULL,
    last_refreshed_at TEXT NOT NULL,
    read_at TEXT,
    resurfaced_at TEXT,
    resolved_at TEXT,
    snooze_until TEXT,
    snoozed_by TEXT,
    snoozed_at TEXT,
    snooze_reason TEXT,
    dismissed_by TEXT,
    dismissed_at TEXT,
    dismiss_reason TEXT,
    suppression_key TEXT,
    underlying_issue_id TEXT,
    underlying_signal_id TEXT,
    resolved_issue_id TEXT,
    title TEXT NOT NULL,
    client_id TEXT,
    brand_id TEXT,
    engagement_id TEXT,
    evidence TEXT,
    evidence_version TEXT DEFAULT 'v1',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (underlying_issue_id) REFERENCES issues_v29(id),
    FOREIGN KEY (client_id) REFERENCES clients(id)
);

CREATE INDEX IF NOT EXISTS idx_inbox_items_v29_state ON inbox_items_v29(state);
CREATE INDEX IF NOT EXISTS idx_inbox_items_v29_type ON inbox_items_v29(type);
CREATE INDEX IF NOT EXISTS idx_inbox_items_v29_client ON inbox_items_v29(client_id);

-- Signals table per §6.15
CREATE TABLE IF NOT EXISTS signals_v29 (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    client_id TEXT,
    engagement_id TEXT,
    sentiment TEXT CHECK (sentiment IN ('good', 'neutral', 'bad')),
    signal_type TEXT,
    summary TEXT,
    observed_at TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    evidence TEXT,
    dismissed_at TEXT,
    dismissed_by TEXT,
    analysis_provider TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (client_id) REFERENCES clients(id)
);

CREATE INDEX IF NOT EXISTS idx_signals_v29_client ON signals_v29(client_id);
CREATE INDEX IF NOT EXISTS idx_signals_v29_source ON signals_v29(source, source_id);
CREATE INDEX IF NOT EXISTS idx_signals_v29_observed ON signals_v29(observed_at);

-- Suppression rules table
CREATE TABLE IF NOT EXISTS inbox_suppression_rules_v29 (
    id TEXT PRIMARY KEY,
    suppression_key TEXT NOT NULL UNIQUE,
    item_type TEXT NOT NULL,
    scope_client_id TEXT,
    scope_engagement_id TEXT,
    scope_source TEXT,
    scope_rule TEXT,
    reason TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_suppression_v29_key ON inbox_suppression_rules_v29(suppression_key);
CREATE INDEX IF NOT EXISTS idx_suppression_v29_expires ON inbox_suppression_rules_v29(expires_at);
"""

# ============================================================
# DB PATH RESOLUTION
# ============================================================


def get_db_path() -> Path:
    """
    Get the canonical DB path. ALL code must use this.

    Resolution order:
    1. MOH_TIME_OS_DB env var (explicit override)
    2. ~/.moh_time_os/data/moh_time_os.db (default via paths.db_path())
    """
    return paths.db_path()


def get_db_path_str() -> str:
    """Get DB path as string for sqlite3.connect()."""
    return str(get_db_path())


# ============================================================
# CONNECTION FACTORY
# ============================================================


@contextmanager
def get_connection(
    row_factory: bool = True,
) -> Generator[sqlite3.Connection, None, None]:
    """
    Get a database connection with proper setup.

    Usage:
        with get_connection() as conn:
            conn.execute(...)
    """
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    if row_factory:
        conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ============================================================
# SCHEMA INTROSPECTION
# ============================================================


def get_table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """Get existing column names for a table."""
    validate_identifier(table)
    try:
        cursor = conn.execute(f"PRAGMA table_info({table})")  # nosec B608 — validated above
        return {row[1] for row in cursor.fetchall()}
    except sqlite3.OperationalError:
        return set()


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    """Check if a table exists."""
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cursor.fetchone() is not None


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Get current schema version from PRAGMA user_version."""
    cursor = conn.execute("PRAGMA user_version")
    return cursor.fetchone()[0]


def set_schema_version(conn: sqlite3.Connection, version: int):
    """Set schema version via PRAGMA user_version."""
    if not isinstance(version, int) or version < 0:
        raise ValueError(f"Invalid schema version: {version!r}")
    conn.execute(f"PRAGMA user_version = {version}")  # nosec B608 — int-validated above


# ============================================================
# MIGRATION LOGIC
# ============================================================


def create_table_if_missing(conn: sqlite3.Connection, table: str, create_sql: str) -> bool:
    """Create a table if it doesn't exist. Returns True if created."""
    if table_exists(conn, table):
        return False
    try:
        conn.execute(create_sql)
        logger.info(f"Migration: created table {table}")
        return True
    except sqlite3.OperationalError as e:
        logger.warning(f"Failed to create table {table}: {e}")
        return False


def add_column_if_missing(
    conn: sqlite3.Connection, table: str, column: str, definition: str
) -> bool:
    """Add a column to a table if it doesn't exist. Returns True if added."""
    if not table_exists(conn, table):
        return False

    existing = get_table_columns(conn, table)
    if column in existing:
        return False

    validate_identifier(table)
    validate_identifier(column)
    # definition is a type spec like "TEXT DEFAULT ''" — not parameterizable in SQLite
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")  # nosec B608 — validated above
        logger.info(f"Migration: added column {table}.{column}")
        return True
    except sqlite3.OperationalError as e:
        logger.warning(f"Failed to add {table}.{column}: {e}")
        return False


def run_migrations(conn: sqlite3.Connection) -> dict:
    """
    Run all migrations idempotently inside a transaction.

    Returns dict with migration results.
    """
    previous_version = get_schema_version(conn)

    results = {
        "previous_version": previous_version,
        "target_version": SCHEMA_VERSION,
        "tables_created": [],
        "columns_added": [],
        "errors": [],
    }

    # Step 1: Create required tables
    for table, create_sql in REQUIRED_TABLES.items():
        try:
            if create_table_if_missing(conn, table, create_sql):
                results["tables_created"].append(table)
        except Exception as e:
            results["errors"].append(f"create {table}: {e}")

    # Step 1b: Create collector expansion tables
    for table, create_sql in COLLECTOR_EXPANSION_TABLES.items():
        try:
            if create_table_if_missing(conn, table, create_sql):
                results["tables_created"].append(table)
        except Exception as e:
            results["errors"].append(f"create {table}: {e}")

    # Step 2: Add required columns to existing tables
    for table, columns in REQUIRED_COLUMNS.items():
        for column, definition in columns:
            try:
                if add_column_if_missing(conn, table, column, definition):
                    results["columns_added"].append(f"{table}.{column}")
            except Exception as e:
                results["errors"].append(f"{table}.{column}: {e}")

    # Step 3: Create indexes
    indexes = [
        ("idx_tasks_project_id", "tasks", "project_id"),
        ("idx_communications_content_hash", "communications", "content_hash"),
        ("idx_invoices_status", "invoices", "status"),
        ("idx_invoices_due_at", "invoices", "due_at"),
        ("idx_events_start_at", "events", "start_at"),
        ("idx_asana_custom_fields_project", "asana_custom_fields", "project_id"),
        ("idx_asana_custom_fields_task", "asana_custom_fields", "task_id"),
        ("idx_asana_subtasks_parent_task", "asana_subtasks", "parent_task_id"),
        ("idx_asana_sections_project", "asana_sections", "project_id"),
        ("idx_asana_stories_task", "asana_stories", "task_id"),
        ("idx_asana_task_dependencies_task", "asana_task_dependencies", "task_id"),
        ("idx_asana_portfolios_owner", "asana_portfolios", "owner_id"),
        ("idx_asana_goals_owner", "asana_goals", "owner_id"),
        ("idx_asana_attachments_task", "asana_attachments", "task_id"),
        ("idx_gmail_participants_message", "gmail_participants", "message_id"),
        ("idx_gmail_attachments_message", "gmail_attachments", "message_id"),
        ("idx_gmail_labels_message", "gmail_labels", "message_id"),
        ("idx_calendar_attendees_event", "calendar_attendees", "event_id"),
        ("idx_calendar_recurrence_event", "calendar_recurrence_rules", "event_id"),
        ("idx_chat_reactions_message", "chat_reactions", "message_id"),
        ("idx_chat_attachments_message", "chat_attachments", "message_id"),
        ("idx_chat_space_members_space", "chat_space_members", "space_id"),
        ("idx_xero_line_items_invoice", "xero_line_items", "invoice_id"),
        ("idx_xero_contacts_name", "xero_contacts", "name"),
        ("idx_xero_credit_notes_contact", "xero_credit_notes", "contact_id"),
        ("idx_xero_bank_transactions_contact", "xero_bank_transactions", "contact_id"),
    ]

    for idx_name, table, columns in indexes:
        # All identifiers come from hardcoded list above
        validate_identifier(idx_name)
        validate_identifier(table)
        validate_identifier(columns)
        if table_exists(conn, table):
            try:
                conn.execute(
                    f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({columns})"  # nosec B608
                )
            except sqlite3.OperationalError:
                pass

    # Step 4: Run V29 spec schema (idempotent CREATE IF NOT EXISTS)
    # Execute statements individually to handle VIEWs gracefully
    try:
        for statement in V29_SCHEMA_SQL.split(";"):
            statement = statement.strip()
            if not statement:
                continue

            # Skip index creation on VIEWs
            if statement.upper().startswith("CREATE INDEX"):
                # Extract table name from "CREATE INDEX ... ON table_name(..."
                match = re.search(r"ON\s+(\w+)\s*\(", statement, re.IGNORECASE)
                if match:
                    target_table = match.group(1)
                    # Check if target is a VIEW
                    cursor = conn.execute(
                        "SELECT type FROM sqlite_master WHERE name = ?", (target_table,)
                    )
                    row = cursor.fetchone()
                    if row and row[0] == "view":
                        # Silently skip index creation on VIEWs
                        continue

            try:
                conn.execute(statement)
            except sqlite3.OperationalError:
                # Ignore errors for IF NOT EXISTS statements
                pass

        v29_tables = [
            "issues_v29",
            "issue_transitions_v29",
            "inbox_items_v29",
            "signals_v29",
            "inbox_suppression_rules_v29",
        ]
        for t in v29_tables:
            if table_exists(conn, t) and t not in results["tables_created"]:
                results["tables_created"].append(t)
    except Exception as e:
        results["errors"].append(f"v29 schema: {e}")

    # Step 5: Migration 9 - Create VIEWs for v29 tables if physical tables are empty
    # This allows endpoints querying v29 tables to work by selecting from legacy tables
    if previous_version < 9:
        try:
            # Check if issues_v29 is empty table (not a view)
            cursor = conn.execute("SELECT type FROM sqlite_master WHERE name = 'issues_v29'")
            row = cursor.fetchone()
            if row and row[0] == "table":
                cursor = conn.execute("SELECT COUNT(*) FROM issues_v29")
                if cursor.fetchone()[0] == 0:
                    # Empty table - safe to replace with VIEW
                    conn.execute("DROP TABLE issues_v29")
                    conn.execute("""
                        CREATE VIEW issues_v29 AS
                        SELECT
                            i.issue_id AS id,
                            CASE
                                WHEN lower(i.issue_type) LIKE '%ar%' OR lower(i.issue_type) LIKE '%payment%' OR lower(i.issue_type) LIKE '%invoice%' THEN 'financial'
                                WHEN lower(i.issue_type) LIKE '%deadline%' OR lower(i.issue_type) LIKE '%overdue%' OR lower(i.issue_type) LIKE '%delay%' THEN 'schedule_delivery'
                                WHEN lower(i.issue_type) LIKE '%communication%' OR lower(i.issue_type) LIKE '%response%' THEN 'communication'
                                ELSE 'risk'
                            END AS type,
                            CASE i.state
                                WHEN 'open' THEN 'surfaced'
                                WHEN 'monitoring' THEN 'acknowledged'
                                WHEN 'awaiting' THEN 'awaiting_resolution'
                                WHEN 'blocked' THEN 'addressing'
                                WHEN 'resolved' THEN 'closed'
                                ELSE 'surfaced'
                            END AS state,
                            CASE
                                WHEN i.priority >= 80 THEN 'critical'
                                WHEN i.priority >= 60 THEN 'high'
                                WHEN i.priority >= 40 THEN 'medium'
                                WHEN i.priority >= 20 THEN 'low'
                                ELSE 'info'
                            END AS severity,
                            COALESCE(
                                CASE WHEN i.primary_ref_type = 'client' THEN i.primary_ref_id END,
                                (SELECT t.client_id FROM tasks t WHERE t.id = i.primary_ref_id),
                                'unknown'
                            ) AS client_id,
                            NULL AS brand_id,
                            NULL AS engagement_id,
                            i.headline AS title,
                            COALESCE(i.scope_refs, '{}') AS evidence,
                            'v1' AS evidence_version,
                            i.issue_id AS aggregation_key,
                            COALESCE(i.opened_at, datetime('now')) AS created_at,
                            COALESCE(i.last_activity_at, datetime('now')) AS updated_at,
                            NULL AS snoozed_until, NULL AS snoozed_by, NULL AS snoozed_at, NULL AS snooze_reason,
                            NULL AS tagged_by_user_id, NULL AS tagged_at,
                            NULL AS assigned_to, NULL AS assigned_at, NULL AS assigned_by,
                            0 AS suppressed, NULL AS suppressed_at, NULL AS suppressed_by,
                            0 AS escalated, NULL AS escalated_at, NULL AS escalated_by,
                            NULL AS regression_watch_until,
                            i.closed_at
                        FROM issues i
                    """)
                    logger.info("Migration 9: Created issues_v29 VIEW from legacy issues table")

            # Check if signals_v29 is empty table
            cursor = conn.execute("SELECT type FROM sqlite_master WHERE name = 'signals_v29'")
            row = cursor.fetchone()
            if row and row[0] == "table":
                cursor = conn.execute("SELECT COUNT(*) FROM signals_v29")
                if cursor.fetchone()[0] == 0:
                    # Empty table - safe to replace with VIEW
                    conn.execute("DROP TABLE signals_v29")
                    conn.execute("""
                        CREATE VIEW signals_v29 AS
                        SELECT
                            s.signal_id AS id,
                            COALESCE(s.detector_id, 'unknown') AS source,
                            s.signal_id AS source_id,
                            CASE WHEN s.entity_ref_type = 'client' THEN s.entity_ref_id ELSE NULL END AS client_id,
                            NULL AS engagement_id,
                            CASE
                                WHEN lower(s.signal_type) LIKE '%positive%' OR lower(s.signal_type) LIKE '%good%' THEN 'good'
                                WHEN lower(s.signal_type) LIKE '%risk%' OR lower(s.signal_type) LIKE '%overdue%' OR lower(s.signal_type) LIKE '%negative%' THEN 'bad'
                                ELSE 'neutral'
                            END AS sentiment,
                            s.signal_type,
                            COALESCE(s.value, s.signal_type) AS summary,
                            COALESCE(s.detected_at, datetime('now')) AS observed_at,
                            COALESCE(s.detected_at, datetime('now')) AS ingested_at,
                            '{}' AS evidence,
                            s.resolved_at AS dismissed_at,
                            NULL AS dismissed_by,
                            NULL AS analysis_provider,
                            COALESCE(s.created_at, datetime('now')) AS created_at,
                            COALESCE(s.detected_at, datetime('now')) AS updated_at
                        FROM signals s
                    """)
                    logger.info("Migration 9: Created signals_v29 VIEW from legacy signals table")
        except Exception as e:
            results["errors"].append(f"migration 9 views: {e}")

    # Step 5: Update schema version only after success
    set_schema_version(conn, SCHEMA_VERSION)
    results["final_version"] = SCHEMA_VERSION

    return results


# ============================================================
# STARTUP ENTRY POINT
# ============================================================

_migrations_run = False


def run_startup_migrations() -> dict:
    """
    Run migrations at startup. Safe to call multiple times.
    Logs comprehensive startup info.
    """
    global _migrations_run

    db_path = get_db_path()

    # Log startup info
    logger.info("=" * 50)
    logger.info("MOH TIME OS Database Startup")
    logger.info("=" * 50)
    logger.info(f"Resolved DB path: {db_path}")
    logger.info(f"DB exists: {db_path.exists()}")
    logger.info(f"Target SCHEMA_VERSION: {SCHEMA_VERSION}")

    # Ensure parent directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with get_connection() as conn:
        version_before = get_schema_version(conn)
        logger.info(f"Current user_version: {version_before}")

        if version_before >= SCHEMA_VERSION and _migrations_run:
            logger.info("Migrations already applied, skipping")
            return {"status": "skipped", "version": version_before}

        # Run migrations
        results = run_migrations(conn)

        # Log what happened
        if results["tables_created"]:
            logger.info(f"Tables created: {results['tables_created']}")
        if results["columns_added"]:
            logger.info(f"Columns added: {results['columns_added']}")
        if results["errors"]:
            logger.warning(f"Migration errors: {results['errors']}")

        if not results["tables_created"] and not results["columns_added"]:
            logger.info("No migrations needed, schema up to date")

        # Confirm critical tables present
        if table_exists(conn, "clients"):
            logger.info("OK clients present")
        else:
            logger.error("MISSING clients table")

        if table_exists(conn, "inbox_items_v29"):
            logger.info("OK inbox_items_v29 present")
        else:
            logger.error("MISSING inbox_items_v29 table")

        logger.info(f"Final user_version: {results['final_version']}")
        logger.info("=" * 50)

        _migrations_run = True
        return results


def ensure_migrations():
    """Ensure migrations have been run. Called by StateStore and other entry points."""
    global _migrations_run
    if not _migrations_run:
        run_startup_migrations()
        _migrations_run = True


# ============================================================
# DEBUG INFO
# ============================================================


def get_db_info() -> dict:
    """
    Get detailed DB info for /api/debug/db endpoint.

    Returns dict with path, exists, size, version, table schemas.
    """
    db_path = get_db_path()
    info = {
        "resolved_db_path": str(db_path),
        "exists": db_path.exists(),
        "file_size": None,
        "sqlite_version": sqlite3.sqlite_version,
        "user_version": None,
        "target_schema_version": SCHEMA_VERSION,
        "tables": {},
    }

    if db_path.exists():
        info["file_size"] = db_path.stat().st_size

        with get_connection() as conn:
            info["user_version"] = get_schema_version(conn)

            # Get columns for required tables
            for table in [
                "tasks",
                "communications",
                "events",
                "invoices",
                "projects",
                "people",
            ]:
                if table_exists(conn, table):
                    info["tables"][table] = sorted(get_table_columns(conn, table))
                else:
                    info["tables"][table] = None  # Table doesn't exist

    return info
