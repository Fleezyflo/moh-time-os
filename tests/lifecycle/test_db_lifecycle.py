"""
Database lifecycle tests.

Tests the complete DB lifecycle:
1. Fresh boot from empty state
2. Migrations run correctly
3. Schema assertions pass
4. API can start and serve requests
5. Backup/restore works correctly
"""

import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

import pytest

# Ensure we can import from the project
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestFreshDBBoot:
    """Test fresh database initialization."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database file."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        os.unlink(path)

    def test_fresh_boot_creates_tables(self, temp_db):
        """Fresh DB boot creates required tables."""
        from lib.db import init_db

        conn = sqlite3.connect(temp_db)
        init_db(conn)

        # Check required tables exist
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cursor.fetchall()}

        # Core tables that must exist
        required = {"clients", "events", "invoices", "issues_v29", "inbox_items_v29"}
        missing = required - tables

        assert not missing, f"Missing required tables: {missing}"
        conn.close()

    def test_fresh_boot_sets_schema_version(self, temp_db):
        """Fresh boot sets schema version pragma."""
        from lib.db import init_db, SCHEMA_VERSION

        conn = sqlite3.connect(temp_db)
        init_db(conn)

        cursor = conn.execute("PRAGMA user_version")
        version = cursor.fetchone()[0]

        assert version == SCHEMA_VERSION, f"Schema version {version} != {SCHEMA_VERSION}"
        conn.close()


class TestMigrations:
    """Test database migrations."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database file."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        os.unlink(path)

    def test_safety_migrations_run_idempotent(self, temp_db):
        """Safety migrations can run multiple times without error."""
        from lib.safety import run_safety_migrations

        conn = sqlite3.connect(temp_db)

        # Run twice
        result1 = run_safety_migrations(conn)
        result2 = run_safety_migrations(conn)

        # Second run should be a no-op
        assert len(result2["errors"]) == 0
        conn.close()

    def test_safety_migrations_create_audit_log(self, temp_db):
        """Safety migrations create audit_log table."""
        from lib.safety import run_safety_migrations

        conn = sqlite3.connect(temp_db)
        run_safety_migrations(conn)

        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'"
        )
        assert cursor.fetchone() is not None
        conn.close()


class TestSchemaAssertions:
    """Test schema assertions pass on valid DB."""

    @pytest.fixture
    def initialized_db(self):
        """Create and initialize a temporary database."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        from lib.db import init_db
        from lib.safety import run_safety_migrations

        conn = sqlite3.connect(path)
        init_db(conn)
        run_safety_migrations(conn)
        conn.close()

        yield path
        os.unlink(path)

    def test_schema_assertions_pass(self, initialized_db):
        """Schema assertions pass on properly initialized DB."""
        from lib.safety.schema import SchemaAssertion

        conn = sqlite3.connect(initialized_db)
        assertion = SchemaAssertion(conn)
        violations = assertion.assert_all()

        assert len(violations) == 0, f"Schema violations: {[v.message for v in violations]}"
        conn.close()


class TestBackupRestore:
    """Test backup and restore functionality."""

    def test_backup_creates_copy(self):
        """Backup creates a valid copy of the database."""
        # Use shutil as the backup mechanism
        fd, source_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        fd, backup_path = tempfile.mkstemp(suffix=".db.bak")
        os.close(fd)

        try:
            # Create source with data
            conn = sqlite3.connect(source_path)
            conn.execute("CREATE TABLE test_data (id INTEGER PRIMARY KEY, value TEXT)")
            conn.execute("INSERT INTO test_data (value) VALUES ('test_value_1')")
            conn.execute("INSERT INTO test_data (value) VALUES ('test_value_2')")
            conn.commit()
            conn.close()

            # Create backup
            shutil.copy2(source_path, backup_path)

            # Verify backup exists and is valid
            assert os.path.exists(backup_path)

            conn = sqlite3.connect(backup_path)
            cursor = conn.execute("SELECT COUNT(*) FROM test_data")
            count = cursor.fetchone()[0]
            assert count == 2
            conn.close()
        finally:
            os.unlink(source_path)
            os.unlink(backup_path)

    def test_restore_recovers_data(self):
        """Restore recovers data from backup."""
        fd, source_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        fd, backup_path = tempfile.mkstemp(suffix=".db.bak")
        os.close(fd)

        try:
            # Create source with data
            conn = sqlite3.connect(source_path)
            conn.execute("CREATE TABLE test_data (id INTEGER PRIMARY KEY, value TEXT)")
            conn.execute("INSERT INTO test_data (value) VALUES ('test_value_1')")
            conn.execute("INSERT INTO test_data (value) VALUES ('test_value_2')")
            conn.commit()
            conn.close()

            # Create backup
            shutil.copy2(source_path, backup_path)

            # Corrupt source
            conn = sqlite3.connect(source_path)
            conn.execute("DELETE FROM test_data")
            conn.commit()
            conn.close()

            # Restore
            shutil.copy2(backup_path, source_path)

            # Verify restoration
            conn = sqlite3.connect(source_path)
            cursor = conn.execute("SELECT COUNT(*) FROM test_data")
            count = cursor.fetchone()[0]
            assert count == 2
            conn.close()
        finally:
            os.unlink(source_path)
            os.unlink(backup_path)


class TestDestructiveMigrationGuards:
    """Test that destructive migrations are guarded."""

    def test_drop_table_requires_confirmation(self):
        """Dropping tables requires explicit confirmation."""
        # This is a placeholder - implement based on actual migration patterns
        pass

    def test_data_loss_migration_creates_backup(self):
        """Migrations that could lose data create backups first."""
        # This is a placeholder - implement based on actual migration patterns
        pass
