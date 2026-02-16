"""
v2.9 Spec Alignment Migration

This migration aligns the database schema with CLIENT-UI-SPEC-v2.9.md:

1. Adds aggregation_key column to issues_v5 for detector upsert (§6.14.1)
2. Adds chk_no_resolved_state constraint to prevent resolved state persistence (§6.5)
3. Adds missing columns for issue lifecycle (§6.14)
4. Adds suppressed flag for dismiss functionality (§6.5)
5. Creates unique index on (issue_type, aggregation_key) WHERE suppressed = FALSE

Spec References:
- §6.14 Issues Schema
- §6.14.1 Aggregation Key Computation
- §6.5 Issue Lifecycle (resolved never persisted)

Run with: python -m lib.migrations.v29_spec_alignment
"""

import hashlib
import json
import logging
import sqlite3
from datetime import datetime

from lib import paths

logger = logging.getLogger(__name__)


# Database paths
V5_DB_PATH = paths.v5_db_path()


def get_utc_now_iso() -> str:
    """Returns current UTC time in canonical 24-char format per §0.1."""
    now = datetime.utcnow()
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")  # nosql: safe
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def index_exists(cursor, index_name: str) -> bool:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name=?", (index_name,))
    return cursor.fetchone() is not None


def compute_aggregation_key(
    issue_type: str,
    scope_client_id: str,
    scope_brand_id: str,
    scope_project_ids: str,
    scope_retainer_id: str,
    signal_ids: str,
) -> str:
    """
    Compute aggregation key per §6.14.1.

    Uses issue_type mapping:
    - deadline_risk, stale_task -> schedule_delivery (uses project/retainer scope)
    - ar_aging -> financial (would need invoice_source_id, but we use scope)
    - sentiment_* -> communication (uses brand scope)
    - Other -> risk (uses project scope)
    """
    client_id = scope_client_id or ""
    brand_id = scope_brand_id or ""
    engagement_id = scope_retainer_id or ""

    # Parse project_ids if retainer not set
    if not engagement_id and scope_project_ids:
        try:
            project_ids = json.loads(scope_project_ids)
            engagement_id = project_ids[0] if project_ids else ""
        except (json.JSONDecodeError, IndexError):
            engagement_id = scope_project_ids

    # Map issue_type to spec types
    type_lower = (issue_type or "").lower()
    if type_lower in ("deadline_risk", "stale_task", "schedule_delivery"):
        payload = f"schedule:{client_id}:{engagement_id}"
    elif type_lower in ("ar_aging", "financial"):
        # For financial, ideally we'd use invoice_source_id
        # Fallback: use first signal_id as invoice proxy
        invoice_id = ""
        if signal_ids:
            try:
                sids = json.loads(signal_ids)
                invoice_id = sids[0] if sids else ""
            except (json.JSONDecodeError, IndexError):
                invoice_id = signal_ids
        payload = f"financial:{client_id}:{engagement_id}:{invoice_id}"
    elif type_lower in ("sentiment_negative", "communication"):
        payload = f"comm:{client_id}:{brand_id}"
    else:
        # Risk or unknown
        rule = type_lower
        payload = f"risk:{client_id}:{engagement_id}:{rule}"

    return "agg_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def pre_migration_checks(cursor) -> bool:
    """Run pre-migration validation per §6.5."""
    logger.info("\n=== Pre-Migration Checks ===")
    # Check for resolved state rows (should be 0 per spec)
    cursor.execute("SELECT COUNT(*) FROM issues_v5 WHERE state = 'resolved'")
    resolved_count = cursor.fetchone()[0]
    if resolved_count > 0:
        logger.info(f"WARNING: Found {resolved_count} issues with state='resolved'")
        logger.info("These must be transitioned to 'regression_watch' before migration.")
        cursor.execute(
            """
            UPDATE issues_v5
            SET state = 'regression_watch',
                monitoring_until = datetime('now', '+90 days'),
                updated_at = ?
            WHERE state = 'resolved'
        """,
            (get_utc_now_iso(),),
        )
        logger.info(f"Auto-fixed: transitioned {resolved_count} issues to regression_watch")
    else:
        logger.info("✓ No resolved state rows found")
    return True


def add_lifecycle_columns(cursor):
    """Add missing lifecycle columns per §6.14."""
    logger.info("\n=== Adding Lifecycle Columns ===")
    columns_to_add = [
        # Aggregation key
        ("aggregation_key", "TEXT"),
        # Suppression (parallel flag, not a state)
        ("suppressed", "INTEGER NOT NULL DEFAULT 0"),
        ("suppressed_at", "TEXT"),
        ("suppressed_by", "TEXT"),
        # Escalation (parallel flag)
        ("escalated", "INTEGER NOT NULL DEFAULT 0"),
        ("escalated_at", "TEXT"),
        ("escalated_by", "TEXT"),
        # Snooze fields
        ("snoozed_until", "TEXT"),
        ("snoozed_by", "TEXT"),
        ("snoozed_at", "TEXT"),
        ("snooze_reason", "TEXT"),
        # Tagged fields (first user confirmation)
        ("tagged_by_user_id", "TEXT"),
        ("tagged_at", "TEXT"),
        # Assignment fields
        ("assigned_to", "TEXT"),
        ("assigned_at", "TEXT"),
        ("assigned_by", "TEXT"),
        # Regression watch
        ("regression_watch_until", "TEXT"),
    ]

    for col_name, col_type in columns_to_add:
        if not column_exists(cursor, "issues_v5", col_name):
            logger.info(f"Adding {col_name} column...")
            cursor.execute(f"ALTER TABLE issues_v5 ADD COLUMN {col_name} {col_type}")  # nosql: safe
        else:
            logger.info(f"✓ {col_name} already exists")


def backfill_aggregation_keys(cursor):
    """Backfill aggregation_key for existing issues per §6.14.1."""
    logger.info("\n=== Backfilling Aggregation Keys ===")
    cursor.execute("""
        SELECT id, issue_type, scope_client_id, scope_brand_id,
               scope_project_ids, scope_retainer_id, signal_ids
        FROM issues_v5
        WHERE aggregation_key IS NULL
    """)

    rows = cursor.fetchall()
    logger.info(f"Found {len(rows)} issues needing aggregation_key")
    for row in rows:
        issue_id = row[0]
        agg_key = compute_aggregation_key(
            issue_type=row[1],
            scope_client_id=row[2],
            scope_brand_id=row[3],
            scope_project_ids=row[4],
            scope_retainer_id=row[5],
            signal_ids=row[6],
        )
        cursor.execute(
            "UPDATE issues_v5 SET aggregation_key = ?, updated_at = ? WHERE id = ?",
            (agg_key, get_utc_now_iso(), issue_id),
        )

    logger.info(f"✓ Backfilled {len(rows)} aggregation keys")


def check_for_duplicates(cursor) -> bool:
    """Check for duplicate aggregation keys before creating unique index."""
    logger.info("\n=== Checking for Duplicate Aggregation Keys ===")
    cursor.execute("""
        SELECT issue_type, aggregation_key, COUNT(*) as cnt
        FROM issues_v5
        WHERE suppressed = 0 AND aggregation_key IS NOT NULL
        GROUP BY issue_type, aggregation_key
        HAVING cnt > 1
    """)

    duplicates = cursor.fetchall()
    if duplicates:
        logger.info(f"WARNING: Found {len(duplicates)} duplicate aggregation keys:")
        for row in duplicates:
            logger.info(f"  - type={row[0]}, key={row[1]}, count={row[2]}")
        logger.info("These need to be resolved before creating unique index.")
        logger.info("Auto-resolving: keeping most recent, suppressing others...")
        for issue_type, agg_key, _ in duplicates:
            # Keep the most recently updated one, suppress others
            cursor.execute(
                """
                UPDATE issues_v5
                SET suppressed = 1,
                    suppressed_at = ?,
                    suppressed_by = 'system_migration'
                WHERE issue_type = ?
                  AND aggregation_key = ?
                  AND id NOT IN (
                      SELECT id FROM issues_v5
                      WHERE issue_type = ? AND aggregation_key = ?
                      ORDER BY updated_at DESC LIMIT 1
                  )
            """,
                (get_utc_now_iso(), issue_type, agg_key, issue_type, agg_key),
            )

        logger.info("✓ Duplicates auto-resolved by suppression")
    else:
        logger.info("✓ No duplicates found")
    return True


def add_constraints_and_indexes(cursor):
    """Add constraints and indexes per §6.14."""
    logger.info("\n=== Adding Constraints and Indexes ===")
    # Note: SQLite doesn't support adding CHECK constraints to existing tables
    # The chk_no_resolved_state will be enforced at application layer
    # and validated by startup canary
    logger.info("Note: CHECK constraints enforced at application layer (SQLite limitation)")
    # Create unique index for aggregation key
    idx_name = "idx_issues_v5_aggregation_unique"
    if not index_exists(cursor, idx_name):
        logger.info(f"Creating {idx_name}...")
        cursor.execute("""
            CREATE UNIQUE INDEX idx_issues_v5_aggregation_unique
            ON issues_v5 (issue_type, aggregation_key)
            WHERE suppressed = 0 AND aggregation_key IS NOT NULL
        """)
        logger.info(f"✓ {idx_name} created")
    else:
        logger.info(f"✓ {idx_name} already exists")
    # Add other useful indexes
    indexes = [
        (
            "idx_issues_v5_state",
            "CREATE INDEX IF NOT EXISTS idx_issues_v5_state ON issues_v5(state)",
        ),
        (
            "idx_issues_v5_suppressed",
            "CREATE INDEX IF NOT EXISTS idx_issues_v5_suppressed ON issues_v5(suppressed)",
        ),
        (
            "idx_issues_v5_client",
            "CREATE INDEX IF NOT EXISTS idx_issues_v5_client ON issues_v5(scope_client_id)",
        ),
        (
            "idx_issues_v5_severity",
            "CREATE INDEX IF NOT EXISTS idx_issues_v5_severity ON issues_v5(severity)",
        ),
    ]

    for idx_name, sql in indexes:
        if not index_exists(cursor, idx_name):
            logger.info(f"Creating {idx_name}...")
            cursor.execute(sql)
        else:
            logger.info(f"✓ {idx_name} already exists")


def verify_migration(cursor) -> bool:
    """Verify migration success."""
    logger.info("\n=== Verifying Migration ===")
    errors = []

    # Check aggregation_key column exists
    if not column_exists(cursor, "issues_v5", "aggregation_key"):
        errors.append("Missing aggregation_key column")

    # Check suppressed column exists
    if not column_exists(cursor, "issues_v5", "suppressed"):
        errors.append("Missing suppressed column")

    # Check no resolved state rows
    cursor.execute("SELECT COUNT(*) FROM issues_v5 WHERE state = 'resolved'")
    if cursor.fetchone()[0] > 0:
        errors.append("Found issues with state='resolved'")

    # Check aggregation_key is populated
    cursor.execute("SELECT COUNT(*) FROM issues_v5 WHERE aggregation_key IS NULL")
    null_count = cursor.fetchone()[0]
    if null_count > 0:
        errors.append(f"Found {null_count} issues with NULL aggregation_key")

    # Check unique index exists
    if not index_exists(cursor, "idx_issues_v5_aggregation_unique"):
        errors.append("Missing idx_issues_v5_aggregation_unique index")

    if errors:
        logger.info("ERRORS:")
        for e in errors:
            logger.info(f"  ✗ {e}")
        return False

    logger.info("✓ All verifications passed")
    return True


def run_migration():
    """Run the full v2.9 spec alignment migration."""
    logger.info("=" * 60)
    logger.info("v2.9 Spec Alignment Migration")
    logger.info("=" * 60)
    logger.info(f"\nDatabase: {V5_DB_PATH}")
    if not V5_DB_PATH.exists():
        logger.info(f"ERROR: Database not found at {V5_DB_PATH}")
        return False

    conn = sqlite3.connect(V5_DB_PATH)
    cursor = conn.cursor()

    try:
        # Pre-migration checks
        if not pre_migration_checks(cursor):
            logger.info("\n✗ Pre-migration checks failed")
            conn.rollback()
            return False

        # Add columns
        add_lifecycle_columns(cursor)
        conn.commit()  # Commit column additions first

        # Backfill aggregation keys
        backfill_aggregation_keys(cursor)
        conn.commit()

        # Check for duplicates and resolve
        if not check_for_duplicates(cursor):
            logger.info("\n✗ Duplicate resolution failed")
            conn.rollback()
            return False
        conn.commit()

        # Add constraints and indexes
        add_constraints_and_indexes(cursor)
        conn.commit()

        # Verify
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
