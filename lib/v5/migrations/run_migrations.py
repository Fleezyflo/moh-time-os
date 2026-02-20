"""
Time OS V5 — Migration Runner

Handles database migrations for V5 schema.
"""

import logging
import re
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


class MigrationRunner:
    """Runs SQL migrations in order, tracking which have been applied."""

    def __init__(self, db_path: str):
        """
        Initialize migration runner.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.migrations_dir = Path(__file__).parent

    def get_connection(self) -> sqlite3.Connection:
        """Create a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def ensure_migrations_table(self, conn: sqlite3.Connection) -> None:
        """Create migrations tracking table if it doesn't exist."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS migrations (
                id TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT (datetime('now')),
                description TEXT
            )
        """)
        conn.commit()

    def get_applied_migrations(self, conn: sqlite3.Connection) -> list[str]:
        """Get list of already-applied migration IDs."""
        cursor = conn.execute("SELECT id FROM migrations ORDER BY id")
        return [row["id"] for row in cursor.fetchall()]

    def get_pending_migrations(self) -> list[tuple[str, Path]]:
        """
        Get list of pending migration files.

        Returns:
            List of (migration_id, file_path) tuples, sorted by ID
        """
        migration_files = []

        for file in self.migrations_dir.glob("*.sql"):
            # Extract migration ID from filename (e.g., "001_create_schema.sql" -> "001")
            match = re.match(r"^(\d+)_.*\.sql$", file.name)
            if match:
                migration_id = match.group(1)
                migration_files.append((migration_id, file))

        # Sort by migration ID
        migration_files.sort(key=lambda x: x[0])
        return migration_files

    def run_migration(self, conn: sqlite3.Connection, migration_id: str, file_path: Path) -> None:
        """
        Run a single migration file.

        Args:
            conn: Database connection
            migration_id: Migration identifier
            file_path: Path to SQL file
        """
        logger.info(f"Running migration {migration_id}: {file_path.name}")
        # Read SQL file
        sql = file_path.read_text()

        # Execute all statements
        try:
            conn.executescript(sql)

            # Record migration as applied
            conn.execute(
                "INSERT INTO migrations (id, description) VALUES (?, ?)",
                (migration_id, file_path.name),
            )
            conn.commit()
            logger.info(f"  ✓ Migration {migration_id} applied successfully")
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"Migration {migration_id} failed: {e}") from e

    def run_all(self, dry_run: bool = False) -> int:
        """
        Run all pending migrations.

        Args:
            dry_run: If True, only print what would be run

        Returns:
            Number of migrations applied
        """
        conn = self.get_connection()

        try:
            self.ensure_migrations_table(conn)

            applied = set(self.get_applied_migrations(conn))
            pending = self.get_pending_migrations()

            # Filter to only pending migrations
            to_run = [(mid, path) for mid, path in pending if mid not in applied]

            if not to_run:
                logger.info("No pending migrations.")
                return 0

            logger.info(f"Found {len(to_run)} pending migration(s):")
            for mid, path in to_run:
                logger.info(f"  - {mid}: {path.name}")
            if dry_run:
                logger.info("\nDry run mode - no changes made.")
                return 0

            # (newline for readability)

            for mid, path in to_run:
                self.run_migration(conn, mid, path)

            logger.info(f"\n✓ Applied {len(to_run)} migration(s)")
            return len(to_run)

        finally:
            conn.close()

    def rollback(self, migration_id: str) -> None:
        """
        Remove a migration from the tracking table.

        Note: This does NOT reverse the schema changes - that must be done manually
        or via a new migration.

        Args:
            migration_id: Migration ID to remove from tracking
        """
        conn = self.get_connection()

        try:
            cursor = conn.execute("DELETE FROM migrations WHERE id = ?", (migration_id,))

            if cursor.rowcount > 0:
                conn.commit()
                logger.info(f"✓ Removed migration {migration_id} from tracking")
                logger.info("  Note: Schema changes were NOT reversed")
            else:
                logger.info(f"Migration {migration_id} not found in tracking table")
        finally:
            conn.close()

    def status(self) -> None:
        """Print migration status."""
        conn = self.get_connection()

        try:
            self.ensure_migrations_table(conn)

            applied = self.get_applied_migrations(conn)
            pending = self.get_pending_migrations()

            logger.info("Migration Status")
            logger.info("=" * 50)
            logger.info(f"\nApplied ({len(applied)}):")
            if applied:
                cursor = conn.execute(
                    "SELECT id, applied_at, description FROM migrations ORDER BY id"
                )
                for row in cursor.fetchall():
                    logger.info(f"  ✓ {row['id']}: {row['description']} ({row['applied_at']})")
            else:
                logger.info("  (none)")
            {mid for mid, _ in pending}
            not_applied = [(mid, path) for mid, path in pending if mid not in applied]

            logger.info(f"\nPending ({len(not_applied)}):")
            if not_applied:
                for mid, path in not_applied:
                    logger.info(f"  ○ {mid}: {path.name}")
            else:
                logger.info("  (none)")
        finally:
            conn.close()


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Time OS V5 Migration Runner")
    parser.add_argument(
        "--db",
        default="time_os_v5.db",
        help="Path to SQLite database (default: time_os_v5.db)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print pending migrations without applying",
    )
    parser.add_argument("--status", action="store_true", help="Show migration status")
    parser.add_argument(
        "--rollback",
        metavar="ID",
        help="Remove migration ID from tracking (does not reverse schema)",
    )

    args = parser.parse_args()

    runner = MigrationRunner(args.db)

    if args.status:
        runner.status()
    elif args.rollback:
        runner.rollback(args.rollback)
    else:
        runner.run_all(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
