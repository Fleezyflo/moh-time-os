"""
v2.9 Inbox Schema Migration

Creates inbox_items table with v2.9 fields from CLIENT-UI-SPEC-v2.9.md §6.13.

This migration:
1. Creates inbox_items table with all v2.9 columns
2. Creates inbox_suppression_rules table (§1.8)
3. Creates issue_transitions table (§6.5)
4. Creates necessary indexes and constraints

Spec References:
- §6.13 Inbox Items Data Model
- §1.8 Dismiss Action / Suppression
- §0.5 Attention Age
- §6.5 Issue Lifecycle (transitions)

Run with: python -m lib.migrations.v29_inbox_schema
"""

import logging
import sqlite3
from datetime import datetime

from lib import paths

logger = logging.getLogger(__name__)


# Database path
DB_PATH = paths.db_path()


def get_utc_now_iso() -> str:
    """Returns current UTC time in canonical 24-char format per §0.1."""
    now = datetime.utcnow()
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def table_exists(cursor, table: str) -> bool:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cursor.fetchone() is not None


def column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def index_exists(cursor, index_name: str) -> bool:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name=?", (index_name,))
    return cursor.fetchone() is not None


def create_inbox_items_table(cursor):
    """Create inbox_items table per §6.13."""
    logger.info("\n=== Creating inbox_items table ===")
    if table_exists(cursor, "inbox_items"):
        logger.info("inbox_items table already exists, checking for missing columns...")
        # Add v2.9 columns if missing
        v29_columns = [
            ("resurfaced_at", "TEXT"),
            ("last_refreshed_at", "TEXT"),
            ("resolution_reason", "TEXT"),
        ]
        for col_name, col_type in v29_columns:
            if not column_exists(cursor, "inbox_items", col_name):
                logger.info(f"  Adding {col_name} column...")
                cursor.execute(f"ALTER TABLE inbox_items ADD COLUMN {col_name} {col_type}")
            else:
                logger.info(f"  ✓ {col_name} already exists")
        return

    cursor.execute("""
        CREATE TABLE inbox_items (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL CHECK (type IN ('issue', 'flagged_signal', 'orphan', 'ambiguous')),
            state TEXT NOT NULL DEFAULT 'proposed' CHECK (state IN ('proposed', 'snoozed', 'dismissed', 'linked_to_issue')),
            severity TEXT NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),

            -- Timestamps
            proposed_at TEXT NOT NULL,
            last_refreshed_at TEXT NOT NULL,
            read_at TEXT,
            resurfaced_at TEXT,
            resolved_at TEXT,

            -- Snooze (populated when state = 'snoozed')
            snooze_until TEXT,
            snoozed_by TEXT,
            snoozed_at TEXT,
            snooze_reason TEXT,

            -- Dismissal (populated when state = 'dismissed')
            dismissed_by TEXT,
            dismissed_at TEXT,
            dismiss_reason TEXT,
            suppression_key TEXT,

            -- Underlying entity (exactly one of these is set)
            underlying_issue_id TEXT,
            underlying_signal_id TEXT,

            -- Resolution (populated when state = 'linked_to_issue')
            resolved_issue_id TEXT,
            resolution_reason TEXT CHECK (resolution_reason IS NULL OR resolution_reason IN (
                'tag', 'assign', 'issue_snoozed_directly', 'issue_resolved_directly',
                'issue_closed_directly', 'issue_acknowledged_directly',
                'issue_assigned_directly', 'superseded'
            )),

            -- Scoping (nullable per type)
            client_id TEXT,
            brand_id TEXT,
            engagement_id TEXT,

            -- Metadata
            title TEXT NOT NULL,
            evidence TEXT NOT NULL,
            evidence_version TEXT NOT NULL DEFAULT 'v1',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    logger.info("✓ inbox_items table created")


def create_inbox_indexes(cursor):
    """Create indexes for inbox_items per §6.13."""
    logger.info("\n=== Creating inbox_items indexes ===")
    indexes = [
        (
            "idx_inbox_items_state",
            "CREATE INDEX IF NOT EXISTS idx_inbox_items_state ON inbox_items(state)",
        ),
        (
            "idx_inbox_items_type",
            "CREATE INDEX IF NOT EXISTS idx_inbox_items_type ON inbox_items(type)",
        ),
        (
            "idx_inbox_items_client",
            "CREATE INDEX IF NOT EXISTS idx_inbox_items_client ON inbox_items(client_id)",
        ),
        (
            "idx_inbox_items_proposed",
            "CREATE INDEX IF NOT EXISTS idx_inbox_items_proposed ON inbox_items(proposed_at)",
        ),
        (
            "idx_inbox_items_suppression",
            "CREATE INDEX IF NOT EXISTS idx_inbox_items_suppression ON inbox_items(suppression_key)",
        ),
        (
            "idx_inbox_items_severity",
            "CREATE INDEX IF NOT EXISTS idx_inbox_items_severity ON inbox_items(severity)",
        ),
        (
            "idx_inbox_items_resolved",
            "CREATE INDEX IF NOT EXISTS idx_inbox_items_resolved ON inbox_items(resolved_at)",
        ),
        (
            "idx_inbox_items_underlying_issue",
            "CREATE INDEX IF NOT EXISTS idx_inbox_items_underlying_issue ON inbox_items(underlying_issue_id)",
        ),
        (
            "idx_inbox_items_underlying_signal",
            "CREATE INDEX IF NOT EXISTS idx_inbox_items_underlying_signal ON inbox_items(underlying_signal_id)",
        ),
        (
            "idx_inbox_items_resurfaced",
            "CREATE INDEX IF NOT EXISTS idx_inbox_items_resurfaced ON inbox_items(resurfaced_at)",
        ),
    ]

    # Unique partial indexes for dedupe
    unique_indexes = [
        (
            "idx_inbox_items_unique_active_issue",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_inbox_items_unique_active_issue ON inbox_items (underlying_issue_id) WHERE underlying_issue_id IS NOT NULL AND state IN ('proposed', 'snoozed')",
        ),
        (
            "idx_inbox_items_unique_active_signal",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_inbox_items_unique_active_signal ON inbox_items (underlying_signal_id) WHERE underlying_signal_id IS NOT NULL AND state IN ('proposed', 'snoozed')",
        ),
    ]

    for idx_name, sql in indexes + unique_indexes:
        if not index_exists(cursor, idx_name):
            logger.info(f"Creating {idx_name}...")
            cursor.execute(sql)
        else:
            logger.info(f"✓ {idx_name} already exists")


def create_suppression_rules_table(cursor):
    """Create inbox_suppression_rules table per §1.8."""
    logger.info("\n=== Creating inbox_suppression_rules table ===")
    if table_exists(cursor, "inbox_suppression_rules"):
        logger.info("✓ inbox_suppression_rules table already exists")
        return

    cursor.execute("""
        CREATE TABLE inbox_suppression_rules (
            id TEXT PRIMARY KEY,
            suppression_key TEXT NOT NULL UNIQUE,
            item_type TEXT NOT NULL CHECK (item_type IN ('issue', 'flagged_signal', 'orphan', 'ambiguous')),
            issue_id TEXT,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT,
            reason TEXT
        )
    """)

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_suppression_rules_key_expires ON inbox_suppression_rules(suppression_key, expires_at)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_suppression_rules_expires ON inbox_suppression_rules(expires_at) WHERE expires_at IS NOT NULL"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_suppression_rules_issue ON inbox_suppression_rules(issue_id) WHERE issue_id IS NOT NULL"
    )

    logger.info("✓ inbox_suppression_rules table created with indexes")


def create_issue_transitions_table(cursor):
    """Create issue_transitions table per §6.5."""
    logger.info("\n=== Creating issue_transitions table ===")
    if table_exists(cursor, "issue_transitions"):
        logger.info("✓ issue_transitions table already exists")
        return

    cursor.execute("""
        CREATE TABLE issue_transitions (
            id TEXT PRIMARY KEY,
            issue_id TEXT NOT NULL,
            previous_state TEXT NOT NULL,
            new_state TEXT NOT NULL,
            transition_reason TEXT NOT NULL CHECK (transition_reason IN (
                'user', 'system_timer', 'system_signal', 'system_threshold',
                'system_aggregation', 'system_workflow'
            )),
            trigger_signal_id TEXT,
            trigger_rule TEXT,
            actor TEXT NOT NULL,
            actor_note TEXT,
            transitioned_at TEXT NOT NULL
        )
    """)

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_issue_transitions_issue ON issue_transitions(issue_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_issue_transitions_timestamp ON issue_transitions(transitioned_at)"
    )

    logger.info("✓ issue_transitions table created with indexes")


def create_inbox_triggers(cursor):
    """Create validation triggers for inbox_items per §6.13."""
    logger.info("\n=== Creating inbox_items triggers ===")
    triggers = [
        # chk_underlying_exclusive
        """
        CREATE TRIGGER IF NOT EXISTS trg_inbox_underlying_exclusive_insert
        BEFORE INSERT ON inbox_items
        FOR EACH ROW
        WHEN NOT ((NEW.underlying_issue_id IS NOT NULL) != (NEW.underlying_signal_id IS NOT NULL))
        BEGIN
            SELECT RAISE(ABORT, 'Constraint violation: exactly one of underlying_issue_id or underlying_signal_id must be set');
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS trg_inbox_underlying_exclusive_update
        BEFORE UPDATE ON inbox_items
        FOR EACH ROW
        WHEN NOT ((NEW.underlying_issue_id IS NOT NULL) != (NEW.underlying_signal_id IS NOT NULL))
        BEGIN
            SELECT RAISE(ABORT, 'Constraint violation: exactly one of underlying_issue_id or underlying_signal_id must be set');
        END
        """,
        # chk_type_issue_mapping
        """
        CREATE TRIGGER IF NOT EXISTS trg_inbox_type_issue_mapping_insert
        BEFORE INSERT ON inbox_items
        FOR EACH ROW
        WHEN NEW.type = 'issue' AND (NEW.underlying_issue_id IS NULL OR NEW.underlying_signal_id IS NOT NULL)
        BEGIN
            SELECT RAISE(ABORT, 'Constraint violation: type=issue requires underlying_issue_id and no underlying_signal_id');
        END
        """,
        # chk_snooze_requires_until
        """
        CREATE TRIGGER IF NOT EXISTS trg_inbox_snooze_requires_until_insert
        BEFORE INSERT ON inbox_items
        FOR EACH ROW
        WHEN NEW.state = 'snoozed' AND NEW.snooze_until IS NULL
        BEGIN
            SELECT RAISE(ABORT, 'Constraint violation: state=snoozed requires snooze_until');
        END
        """,
        # chk_terminal_requires_resolved
        """
        CREATE TRIGGER IF NOT EXISTS trg_inbox_terminal_requires_resolved_insert
        BEFORE INSERT ON inbox_items
        FOR EACH ROW
        WHEN NEW.state IN ('dismissed', 'linked_to_issue') AND NEW.resolved_at IS NULL
        BEGIN
            SELECT RAISE(ABORT, 'Constraint violation: terminal state requires resolved_at');
        END
        """,
        # chk_linked_requires_issue
        """
        CREATE TRIGGER IF NOT EXISTS trg_inbox_linked_requires_issue_insert
        BEFORE INSERT ON inbox_items
        FOR EACH ROW
        WHEN NEW.state = 'linked_to_issue' AND NEW.resolved_issue_id IS NULL
        BEGIN
            SELECT RAISE(ABORT, 'Constraint violation: state=linked_to_issue requires resolved_issue_id');
        END
        """,
    ]

    for trigger_sql in triggers:
        try:
            cursor.execute(trigger_sql)
        except Exception as e:
            if "already exists" not in str(e).lower():
                logger.info(f"  Warning: {e}")
    logger.info("✓ Triggers created")


def verify_migration(cursor) -> bool:
    """Verify migration success."""
    logger.info("\n=== Verifying Migration ===")
    errors = []

    # Check tables exist
    required_tables = ["inbox_items", "inbox_suppression_rules", "issue_transitions"]
    for table in required_tables:
        if not table_exists(cursor, table):
            errors.append(f"Missing table: {table}")

    # Check inbox_items columns
    required_columns = ["resurfaced_at", "last_refreshed_at", "resolution_reason"]
    for col in required_columns:
        if table_exists(cursor, "inbox_items") and not column_exists(cursor, "inbox_items", col):
            errors.append(f"Missing column inbox_items.{col}")

    if errors:
        logger.info("ERRORS:")
        for e in errors:
            logger.info(f"  ✗ {e}")
        return False

    logger.info("✓ All verifications passed")
    return True


def run_migration():
    """Run the full v2.9 inbox schema migration."""
    logger.info("=" * 60)
    logger.info("v2.9 Inbox Schema Migration")
    logger.info("=" * 60)
    logger.info(f"\nDatabase: {DB_PATH}")
    if not DB_PATH.exists():
        logger.info(f"ERROR: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        create_inbox_items_table(cursor)
        create_inbox_indexes(cursor)
        create_suppression_rules_table(cursor)
        create_issue_transitions_table(cursor)
        create_inbox_triggers(cursor)

        if not verify_migration(cursor):
            logger.info("\n✗ Migration verification failed")
            conn.rollback()
            return False

        conn.commit()
        logger.info(f"\n{'=' * 60}")
        logger.info("✓ Migration completed successfully")
        logger.info(f"{'=' * 60}")
        return True

    except Exception as e:
        conn.rollback()
        logger.info(f"\n✗ Migration failed: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    import sys

    success = run_migration()
    sys.exit(0 if success else 1)
