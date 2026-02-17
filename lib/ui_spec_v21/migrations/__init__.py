"""
Migration Runner — Time OS UI Spec v2.1

Applies all migrations idempotently.
Creates tables, indexes, and constraints per spec.
"""

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


MIGRATIONS_DIR = Path(__file__).parent


def get_migration_files() -> list[Path]:
    """Get all SQL migration files in order."""
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def run_migrations(conn: sqlite3.Connection, verbose: bool = True) -> list[str]:
    """
    Run all migrations idempotently.

    Returns list of applied migration names.
    """
    applied = []

    for migration_file in get_migration_files():
        if verbose:
            logger.info(f"Applying migration: {migration_file.name}")
        sql = migration_file.read_text()

        try:
            conn.executescript(sql)
            applied.append(migration_file.name)
            if verbose:
                logger.info(f"  ✓ {migration_file.name} applied")
        except sqlite3.Error as e:
            if verbose:
                logger.info(f"  ⚠ {migration_file.name}: {e}")
    # Apply constraint triggers (SQLite doesn't support CHECK constraints added via ALTER)
    apply_constraint_triggers(conn, verbose)

    # Apply unique partial indexes
    apply_unique_indexes(conn, verbose)

    conn.commit()
    return applied


def apply_constraint_triggers(conn: sqlite3.Connection, verbose: bool = True):
    """
    Apply constraint validation via triggers.

    SQLite CHECK constraints can't be added to existing tables,
    so we use triggers for validation on INSERT/UPDATE.

    Spec: 6.13 Integrity constraints
    """
    if verbose:
        logger.info("Applying constraint triggers...")
    triggers = [
        # chk_underlying_exclusive
        """
        CREATE TRIGGER IF NOT EXISTS trg_inbox_underlying_exclusive_insert
        BEFORE INSERT ON inbox_items_v29
        FOR EACH ROW
        WHEN NOT ((NEW.underlying_issue_id IS NOT NULL) != (NEW.underlying_signal_id IS NOT NULL))
        BEGIN
            SELECT RAISE(ABORT, 'Constraint violation: exactly one of underlying_issue_id or underlying_signal_id must be set');
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS trg_inbox_underlying_exclusive_update
        BEFORE UPDATE ON inbox_items_v29
        FOR EACH ROW
        WHEN NOT ((NEW.underlying_issue_id IS NOT NULL) != (NEW.underlying_signal_id IS NOT NULL))
        BEGIN
            SELECT RAISE(ABORT, 'Constraint violation: exactly one of underlying_issue_id or underlying_signal_id must be set');
        END;
        """,
        # chk_type_issue_mapping
        """
        CREATE TRIGGER IF NOT EXISTS trg_inbox_type_issue_mapping_insert
        BEFORE INSERT ON inbox_items_v29
        FOR EACH ROW
        WHEN NEW.type = 'issue' AND (NEW.underlying_issue_id IS NULL OR NEW.underlying_signal_id IS NOT NULL)
        BEGIN
            SELECT RAISE(ABORT, 'Constraint violation: type=issue requires underlying_issue_id and no underlying_signal_id');
        END;
        """,
        # chk_type_signal_mapping
        """
        CREATE TRIGGER IF NOT EXISTS trg_inbox_type_signal_mapping_insert
        BEFORE INSERT ON inbox_items_v29
        FOR EACH ROW
        WHEN NEW.type IN ('flagged_signal', 'orphan', 'ambiguous')
             AND (NEW.underlying_signal_id IS NULL OR NEW.underlying_issue_id IS NOT NULL)
        BEGIN
            SELECT RAISE(ABORT, 'Constraint violation: signal types require underlying_signal_id and no underlying_issue_id');
        END;
        """,
        # chk_snooze_requires_until
        """
        CREATE TRIGGER IF NOT EXISTS trg_inbox_snooze_requires_until_insert
        BEFORE INSERT ON inbox_items_v29
        FOR EACH ROW
        WHEN NEW.state = 'snoozed' AND NEW.snooze_until IS NULL
        BEGIN
            SELECT RAISE(ABORT, 'Constraint violation: snoozed state requires snooze_until');
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS trg_inbox_snooze_requires_until_update
        BEFORE UPDATE ON inbox_items_v29
        FOR EACH ROW
        WHEN NEW.state = 'snoozed' AND NEW.snooze_until IS NULL
        BEGIN
            SELECT RAISE(ABORT, 'Constraint violation: snoozed state requires snooze_until');
        END;
        """,
        # chk_dismissed_requires_key
        """
        CREATE TRIGGER IF NOT EXISTS trg_inbox_dismissed_requires_key_insert
        BEFORE INSERT ON inbox_items_v29
        FOR EACH ROW
        WHEN NEW.state = 'dismissed' AND NEW.suppression_key IS NULL
        BEGIN
            SELECT RAISE(ABORT, 'Constraint violation: dismissed state requires suppression_key');
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS trg_inbox_dismissed_requires_key_update
        BEFORE UPDATE ON inbox_items_v29
        FOR EACH ROW
        WHEN NEW.state = 'dismissed' AND NEW.suppression_key IS NULL
        BEGIN
            SELECT RAISE(ABORT, 'Constraint violation: dismissed state requires suppression_key');
        END;
        """,
        # chk_terminal_requires_resolved
        """
        CREATE TRIGGER IF NOT EXISTS trg_inbox_terminal_requires_resolved_insert
        BEFORE INSERT ON inbox_items_v29
        FOR EACH ROW
        WHEN NEW.state IN ('dismissed', 'linked_to_issue') AND NEW.resolved_at IS NULL
        BEGIN
            SELECT RAISE(ABORT, 'Constraint violation: terminal states require resolved_at');
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS trg_inbox_terminal_requires_resolved_update
        BEFORE UPDATE ON inbox_items_v29
        FOR EACH ROW
        WHEN NEW.state IN ('dismissed', 'linked_to_issue') AND NEW.resolved_at IS NULL
        BEGIN
            SELECT RAISE(ABORT, 'Constraint violation: terminal states require resolved_at');
        END;
        """,
        # chk_linked_requires_issue
        """
        CREATE TRIGGER IF NOT EXISTS trg_inbox_linked_requires_issue_insert
        BEFORE INSERT ON inbox_items_v29
        FOR EACH ROW
        WHEN NEW.state = 'linked_to_issue' AND NEW.resolved_issue_id IS NULL
        BEGIN
            SELECT RAISE(ABORT, 'Constraint violation: linked_to_issue state requires resolved_issue_id');
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS trg_inbox_linked_requires_issue_update
        BEFORE UPDATE ON inbox_items_v29
        FOR EACH ROW
        WHEN NEW.state = 'linked_to_issue' AND NEW.resolved_issue_id IS NULL
        BEGIN
            SELECT RAISE(ABORT, 'Constraint violation: linked_to_issue state requires resolved_issue_id');
        END;
        """,
        # chk_dismissed_requires_audit
        """
        CREATE TRIGGER IF NOT EXISTS trg_inbox_dismissed_requires_audit_insert
        BEFORE INSERT ON inbox_items_v29
        FOR EACH ROW
        WHEN NEW.state = 'dismissed' AND (NEW.dismissed_at IS NULL OR NEW.dismissed_by IS NULL)
        BEGIN
            SELECT RAISE(ABORT, 'Constraint violation: dismissed state requires dismissed_at and dismissed_by');
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS trg_inbox_dismissed_requires_audit_update
        BEFORE UPDATE ON inbox_items_v29
        FOR EACH ROW
        WHEN NEW.state = 'dismissed' AND (NEW.dismissed_at IS NULL OR NEW.dismissed_by IS NULL)
        BEGIN
            SELECT RAISE(ABORT, 'Constraint violation: dismissed state requires dismissed_at and dismissed_by');
        END;
        """,
    ]

    for trigger_sql in triggers:
        try:
            conn.execute(trigger_sql)
        except sqlite3.Error as e:
            if verbose:
                logger.info(f"  ⚠ Trigger: {e}")


def apply_unique_indexes(conn: sqlite3.Connection, verbose: bool = True):
    """
    Apply unique partial indexes.

    Spec: 6.13 Dedupe unique indexes
    """
    if verbose:
        logger.info("Applying unique partial indexes...")
    indexes = [
        # At most one active inbox item per underlying issue
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_inbox_items_unique_active_issue
        ON inbox_items (underlying_issue_id)
        WHERE underlying_issue_id IS NOT NULL AND state IN ('proposed', 'snoozed');
        """,
        # At most one active inbox item per underlying signal
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_inbox_items_unique_active_signal
        ON inbox_items (underlying_signal_id)
        WHERE underlying_signal_id IS NOT NULL AND state IN ('proposed', 'snoozed');
        """,
    ]

    for index_sql in indexes:
        try:
            conn.execute(index_sql)
            if verbose:
                logger.info("  ✓ Unique index applied")
        except sqlite3.Error as e:
            if verbose:
                logger.info(f"  ⚠ Index: {e}")


def create_database(db_path: str, verbose: bool = True) -> sqlite3.Connection:
    """
    Create database and run all migrations.
    """
    if verbose:
        logger.info(f"Creating database: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")

    run_migrations(conn, verbose)

    if verbose:
        logger.info("Database setup complete!")
    return conn


def migrate_existing(db_path: str, verbose: bool = True) -> list[str]:
    """
    Run migrations on existing database.
    """
    if verbose:
        logger.info(f"Migrating database: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")

    applied = run_migrations(conn, verbose)

    conn.close()
    return applied


if __name__ == "__main__":
    import sys

    from lib import paths

    db_path = sys.argv[1] if len(sys.argv) > 1 else str(paths.db_path())

    migrate_existing(db_path)
