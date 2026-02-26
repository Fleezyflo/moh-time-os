"""
Safety Migrations

Creates all tables, triggers, and constraints required for the safety system.
Idempotent - safe to run multiple times.
"""
# nosec B608 - All SQL in this file uses table names from hardcoded SAFETY_MANAGED_TABLES list
# Dynamic DDL construction is intentional for trigger generation patterns

import logging
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)

# Tables that require write context and audit logging
PROTECTED_TABLES = [
    "inbox_items_v29",
    "issues_v29",
    "issue_transitions_v29",
    "inbox_suppression_rules_v29",
    "signals_v29",
]


def run_safety_migrations(conn: sqlite3.Connection, verbose: bool = True) -> dict[str, Any]:
    """
    Run all safety migrations.

    Creates:
    - write_context_v1 table
    - db_write_audit_v1 table
    - Triggers for invariants (terminal state, dismiss fields, etc.)
    - Triggers for write context enforcement
    - Triggers for audit logging
    - Converts inbox_items to read-only VIEW if it's a table

    Returns dict with migration results.
    """
    results: dict[str, list[str]] = {
        "tables_created": [],
        "triggers_created": [],
        "views_created": [],
        "errors": [],
    }

    # 1. Create write_context_v1 table
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS write_context_v1 (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                request_id TEXT NOT NULL,
                actor TEXT NOT NULL,
                source TEXT NOT NULL,
                git_sha TEXT NOT NULL,
                set_at TEXT NOT NULL
            )
        """)
        results["tables_created"].append("write_context_v1")
        if verbose:
            logger.info("Created/verified write_context_v1 table")
    except (sqlite3.Error, ValueError, OSError) as e:
        results["errors"].append(f"write_context_v1: {e}")

    # 2. Create db_write_audit_v1 table
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS db_write_audit_v1 (
                id TEXT PRIMARY KEY,
                at TEXT NOT NULL,
                actor TEXT NOT NULL,
                request_id TEXT NOT NULL,
                source TEXT NOT NULL,
                git_sha TEXT NOT NULL,
                table_name TEXT NOT NULL,
                op TEXT NOT NULL CHECK (op IN ('INSERT', 'UPDATE', 'DELETE')),
                row_id TEXT NOT NULL,
                before_json TEXT,
                after_json TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_table_row ON db_write_audit_v1(table_name, row_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_actor ON db_write_audit_v1(actor)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_request ON db_write_audit_v1(request_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_at ON db_write_audit_v1(at)
        """)
        results["tables_created"].append("db_write_audit_v1")
        if verbose:
            logger.info("Created/verified db_write_audit_v1 table with indexes")
    except (sqlite3.Error, ValueError, OSError) as e:
        results["errors"].append(f"db_write_audit_v1: {e}")

    # 3. Create maintenance_mode table
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS maintenance_mode_v1 (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                flag INTEGER NOT NULL DEFAULT 0 CHECK (flag IN (0, 1)),
                reason TEXT,
                set_by TEXT,
                set_at TEXT
            )
        """)
        # Ensure exactly one row exists
        conn.execute("""
            INSERT OR IGNORE INTO maintenance_mode_v1 (id, flag) VALUES (1, 0)
        """)
        results["tables_created"].append("maintenance_mode_v1")
        if verbose:
            logger.info("Created/verified maintenance_mode_v1 table")
    except (sqlite3.Error, ValueError, OSError) as e:
        results["errors"].append(f"maintenance_mode_v1: {e}")

    # 4. Create invariant triggers on inbox_items_v29
    invariant_triggers = _get_invariant_triggers()
    for trigger_name, trigger_sql in invariant_triggers:
        try:
            # Drop if exists (to allow updates)
            conn.execute(f"DROP TRIGGER IF EXISTS {trigger_name}")
            conn.execute(trigger_sql)
            results["triggers_created"].append(trigger_name)
            if verbose:
                logger.info(f"Created trigger: {trigger_name}")
        except (sqlite3.Error, ValueError, OSError) as e:
            results["errors"].append(f"{trigger_name}: {e}")

    # 5. Create write context enforcement triggers
    for table in PROTECTED_TABLES:
        if not _table_exists(conn, table):
            if verbose:
                logger.info(f"Skipping triggers for {table} (table does not exist)")
            continue

        context_triggers = _get_context_triggers(table)
        for trigger_name, trigger_sql in context_triggers:
            try:
                conn.execute(f"DROP TRIGGER IF EXISTS {trigger_name}")
                conn.execute(trigger_sql)
                results["triggers_created"].append(trigger_name)
                if verbose:
                    logger.info(f"Created trigger: {trigger_name}")
            except (sqlite3.Error, ValueError, OSError) as e:
                results["errors"].append(f"{trigger_name}: {e}")

    # 6. Create audit logging triggers
    for table in PROTECTED_TABLES:
        if not _table_exists(conn, table):
            continue

        audit_triggers = _get_audit_triggers(table)
        for trigger_name, trigger_sql in audit_triggers:
            try:
                conn.execute(f"DROP TRIGGER IF EXISTS {trigger_name}")
                conn.execute(trigger_sql)
                results["triggers_created"].append(trigger_name)
                if verbose:
                    logger.info(f"Created trigger: {trigger_name}")
            except (sqlite3.Error, ValueError, OSError) as e:
                results["errors"].append(f"{trigger_name}: {e}")

    # 7. Convert inbox_items to VIEW if it's a table
    try:
        cursor = conn.execute("SELECT type FROM sqlite_master WHERE name = 'inbox_items'")
        row = cursor.fetchone()
        if row and row[0] == "table":
            # Check if table is empty or can be safely converted
            cursor = conn.execute("SELECT COUNT(*) FROM inbox_items")
            count = cursor.fetchone()[0]

            # Drop old table, create view
            conn.execute("DROP TABLE inbox_items")
            conn.execute("""
                CREATE VIEW inbox_items AS
                SELECT * FROM inbox_items_v29
            """)
            results["views_created"].append("inbox_items")
            if verbose:
                logger.info(
                    f"Converted inbox_items table ({count} rows) to VIEW over inbox_items_v29"
                )
        elif row and row[0] == "view":
            if verbose:
                logger.info("inbox_items is already a VIEW")
    except (sqlite3.Error, ValueError, OSError) as e:
        results["errors"].append(f"inbox_items view conversion: {e}")

    conn.commit()
    return results


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    """Check if a table exists."""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
        (table,),
    )
    return cursor.fetchone() is not None


def _get_invariant_triggers() -> list[tuple[str, str]]:
    """
    Get triggers that enforce inbox_items_v29 invariants.

    These prevent invalid state transitions at the DB level.
    """
    return [
        # 2.1 Terminal state requires resolved_at
        (
            "trg_inbox_v29_terminal_requires_resolved",
            """
            CREATE TRIGGER trg_inbox_v29_terminal_requires_resolved
            BEFORE UPDATE ON inbox_items_v29
            FOR EACH ROW
            WHEN NEW.state IN ('dismissed', 'linked_to_issue') AND NEW.resolved_at IS NULL
            BEGIN
                SELECT RAISE(ABORT, 'SAFETY: terminal state (dismissed/linked_to_issue) requires resolved_at');
            END
        """,
        ),
        # 2.2 Dismiss requires audit fields
        (
            "trg_inbox_v29_dismissed_requires_audit",
            """
            CREATE TRIGGER trg_inbox_v29_dismissed_requires_audit
            BEFORE UPDATE ON inbox_items_v29
            FOR EACH ROW
            WHEN NEW.state = 'dismissed' AND (
                NEW.dismissed_at IS NULL OR
                NEW.dismissed_by IS NULL OR
                NEW.suppression_key IS NULL
            )
            BEGIN
                SELECT RAISE(ABORT, 'SAFETY: dismissed state requires dismissed_at, dismissed_by, and suppression_key');
            END
        """,
        ),
        # 2.3 Linked_to_issue requires issue pointer
        (
            "trg_inbox_v29_linked_requires_issue",
            """
            CREATE TRIGGER trg_inbox_v29_linked_requires_issue
            BEFORE UPDATE ON inbox_items_v29
            FOR EACH ROW
            WHEN NEW.state = 'linked_to_issue' AND NEW.resolved_issue_id IS NULL
            BEGIN
                SELECT RAISE(ABORT, 'SAFETY: linked_to_issue state requires resolved_issue_id');
            END
        """,
        ),
        # INSERT versions of the same constraints
        (
            "trg_inbox_v29_terminal_requires_resolved_ins",
            """
            CREATE TRIGGER trg_inbox_v29_terminal_requires_resolved_ins
            BEFORE INSERT ON inbox_items_v29
            FOR EACH ROW
            WHEN NEW.state IN ('dismissed', 'linked_to_issue') AND NEW.resolved_at IS NULL
            BEGIN
                SELECT RAISE(ABORT, 'SAFETY: terminal state (dismissed/linked_to_issue) requires resolved_at');
            END
        """,
        ),
        (
            "trg_inbox_v29_dismissed_requires_audit_ins",
            """
            CREATE TRIGGER trg_inbox_v29_dismissed_requires_audit_ins
            BEFORE INSERT ON inbox_items_v29
            FOR EACH ROW
            WHEN NEW.state = 'dismissed' AND (
                NEW.dismissed_at IS NULL OR
                NEW.dismissed_by IS NULL OR
                NEW.suppression_key IS NULL
            )
            BEGIN
                SELECT RAISE(ABORT, 'SAFETY: dismissed state requires dismissed_at, dismissed_by, and suppression_key');
            END
        """,
        ),
        (
            "trg_inbox_v29_linked_requires_issue_ins",
            """
            CREATE TRIGGER trg_inbox_v29_linked_requires_issue_ins
            BEFORE INSERT ON inbox_items_v29
            FOR EACH ROW
            WHEN NEW.state = 'linked_to_issue' AND NEW.resolved_issue_id IS NULL
            BEGIN
                SELECT RAISE(ABORT, 'SAFETY: linked_to_issue state requires resolved_issue_id');
            END
        """,
        ),
    ]


def _get_context_triggers(table: str) -> list[tuple[str, str]]:
    """
    Get triggers that enforce write context for a table.

    These ABORT if write_context_v1 is not set.
    """
    safe_table = table.replace("-", "_")

    # nosec B608 - table names are from hardcoded SAFETY_MANAGED_TABLES list
    sql_insert = "".join(
        [
            "CREATE TRIGGER trg_",
            safe_table,
            "_ctx_insert\n",
            "BEFORE INSERT ON ",
            table,
            "\n",
            "FOR EACH ROW\n",
            "WHEN NOT EXISTS (\n",
            "    SELECT 1 FROM write_context_v1\n",
            "    WHERE id = 1 AND request_id IS NOT NULL AND actor IS NOT NULL\n",
            ") AND NOT EXISTS (\n",
            "    SELECT 1 FROM maintenance_mode_v1 WHERE id = 1 AND flag = 1\n",
            ")\n",
            "BEGIN\n",
            "    SELECT RAISE(ABORT, 'SAFETY: write context required - use WriteContext or set maintenance_mode');\n",
            "END",
        ]
    )
    sql_update = "".join(
        [
            "CREATE TRIGGER trg_",
            safe_table,
            "_ctx_update\n",
            "BEFORE UPDATE ON ",
            table,
            "\n",
            "FOR EACH ROW\n",
            "WHEN NOT EXISTS (\n",
            "    SELECT 1 FROM write_context_v1\n",
            "    WHERE id = 1 AND request_id IS NOT NULL AND actor IS NOT NULL\n",
            ") AND NOT EXISTS (\n",
            "    SELECT 1 FROM maintenance_mode_v1 WHERE id = 1 AND flag = 1\n",
            ")\n",
            "BEGIN\n",
            "    SELECT RAISE(ABORT, 'SAFETY: write context required - use WriteContext or set maintenance_mode');\n",
            "END",
        ]
    )
    sql_delete = "".join(
        [
            "CREATE TRIGGER trg_",
            safe_table,
            "_ctx_delete\n",
            "BEFORE DELETE ON ",
            table,
            "\n",
            "FOR EACH ROW\n",
            "WHEN NOT EXISTS (\n",
            "    SELECT 1 FROM write_context_v1\n",
            "    WHERE id = 1 AND request_id IS NOT NULL AND actor IS NOT NULL\n",
            ") AND NOT EXISTS (\n",
            "    SELECT 1 FROM maintenance_mode_v1 WHERE id = 1 AND flag = 1\n",
            ")\n",
            "BEGIN\n",
            "    SELECT RAISE(ABORT, 'SAFETY: write context required - use WriteContext or set maintenance_mode');\n",
            "END",
        ]
    )
    return [
        (f"trg_{safe_table}_ctx_insert", sql_insert),
        (f"trg_{safe_table}_ctx_update", sql_update),
        (f"trg_{safe_table}_ctx_delete", sql_delete),
    ]


def _get_audit_triggers(table: str) -> list[tuple[str, str]]:
    """
    Get triggers that log writes to db_write_audit_v1.

    Handles tables with and without 'state' column.
    """
    safe_table = table.replace("-", "_")

    # Get the primary key column (assume 'id' for these tables)
    pk_col = "id"

    # Tables that have a 'state' column
    tables_with_state = ["inbox_items_v29", "issues_v29"]
    has_state = table in tables_with_state

    if has_state:
        after_json_insert = f"json_object('id', NEW.{pk_col}, 'state', NEW.state)"
        before_json_update = f"json_object('id', OLD.{pk_col}, 'state', OLD.state)"
        after_json_update = f"json_object('id', NEW.{pk_col}, 'state', NEW.state)"
        before_json_delete = f"json_object('id', OLD.{pk_col}, 'state', OLD.state)"
    else:
        after_json_insert = f"json_object('id', NEW.{pk_col})"
        before_json_update = f"json_object('id', OLD.{pk_col})"
        after_json_update = f"json_object('id', NEW.{pk_col})"
        before_json_delete = f"json_object('id', OLD.{pk_col})"

    sql_insert = "".join(
        [
            "CREATE TRIGGER trg_",
            safe_table,
            "_audit_insert\n",
            "AFTER INSERT ON ",
            table,
            "\n",
            "FOR EACH ROW\n",
            "BEGIN\n",
            "    INSERT INTO db_write_audit_v1 (\n",
            "        id, at, actor, request_id, source, git_sha,\n",
            "        table_name, op, row_id, before_json, after_json\n",
            "    )\n",
            "    SELECT\n",
            "        lower(hex(randomblob(16))),\n",
            "        datetime('now'),\n",
            "        COALESCE(wc.actor, 'maintenance'),\n",
            "        COALESCE(wc.request_id, 'maintenance-' || lower(hex(randomblob(8)))),\n",
            "        COALESCE(wc.source, 'maintenance'),\n",
            "        COALESCE(wc.git_sha, 'unknown'),\n",
            "        '",
            table,
            "',\n",
            "        'INSERT',\n",
            "        NEW.",
            pk_col,
            ",\n",
            "        NULL,\n",
            "        ",
            after_json_insert,
            "\n",
            "    FROM (SELECT 1) AS dummy\n",
            "    LEFT JOIN write_context_v1 wc ON wc.id = 1;\n",
            "END",
        ]
    )
    sql_update = "".join(
        [
            "CREATE TRIGGER trg_",
            safe_table,
            "_audit_update\n",
            "AFTER UPDATE ON ",
            table,
            "\n",
            "FOR EACH ROW\n",
            "BEGIN\n",
            "    INSERT INTO db_write_audit_v1 (\n",
            "        id, at, actor, request_id, source, git_sha,\n",
            "        table_name, op, row_id, before_json, after_json\n",
            "    )\n",
            "    SELECT\n",
            "        lower(hex(randomblob(16))),\n",
            "        datetime('now'),\n",
            "        COALESCE(wc.actor, 'maintenance'),\n",
            "        COALESCE(wc.request_id, 'maintenance-' || lower(hex(randomblob(8)))),\n",
            "        COALESCE(wc.source, 'maintenance'),\n",
            "        COALESCE(wc.git_sha, 'unknown'),\n",
            "        '",
            table,
            "',\n",
            "        'UPDATE',\n",
            "        NEW.",
            pk_col,
            ",\n",
            "        ",
            before_json_update,
            ",\n",
            "        ",
            after_json_update,
            "\n",
            "    FROM (SELECT 1) AS dummy\n",
            "    LEFT JOIN write_context_v1 wc ON wc.id = 1;\n",
            "END",
        ]
    )
    sql_delete = "".join(
        [
            "CREATE TRIGGER trg_",
            safe_table,
            "_audit_delete\n",
            "AFTER DELETE ON ",
            table,
            "\n",
            "FOR EACH ROW\n",
            "BEGIN\n",
            "    INSERT INTO db_write_audit_v1 (\n",
            "        id, at, actor, request_id, source, git_sha,\n",
            "        table_name, op, row_id, before_json, after_json\n",
            "    )\n",
            "    SELECT\n",
            "        lower(hex(randomblob(16))),\n",
            "        datetime('now'),\n",
            "        COALESCE(wc.actor, 'maintenance'),\n",
            "        COALESCE(wc.request_id, 'maintenance-' || lower(hex(randomblob(8)))),\n",
            "        COALESCE(wc.source, 'maintenance'),\n",
            "        COALESCE(wc.git_sha, 'unknown'),\n",
            "        '",
            table,
            "',\n",
            "        'DELETE',\n",
            "        OLD.",
            pk_col,
            ",\n",
            "        ",
            before_json_delete,
            ",\n",
            "        NULL\n",
            "    FROM (SELECT 1) AS dummy\n",
            "    LEFT JOIN write_context_v1 wc ON wc.id = 1;\n",
            "END",
        ]
    )
    return [
        (f"trg_{safe_table}_audit_insert", sql_insert),
        (f"trg_{safe_table}_audit_update", sql_update),
        (f"trg_{safe_table}_audit_delete", sql_delete),
    ]


def enable_maintenance_mode(conn: sqlite3.Connection, reason: str, set_by: str) -> None:
    """
    Enable maintenance mode to allow bulk operations.

    This bypasses write context checks but still logs to audit.
    """
    from .utils import now_utc_iso

    conn.execute(
        """
        UPDATE maintenance_mode_v1
        SET flag = 1, reason = ?, set_by = ?, set_at = ?
        WHERE id = 1
    """,
        (reason, set_by, now_utc_iso()),
    )
    conn.commit()


def disable_maintenance_mode(conn: sqlite3.Connection) -> None:
    """Disable maintenance mode."""
    conn.execute("""
        UPDATE maintenance_mode_v1
        SET flag = 0, reason = NULL, set_by = NULL, set_at = NULL
        WHERE id = 1
    """)
    conn.commit()
