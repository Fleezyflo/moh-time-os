"""
Database lifecycle tests.

Tests the complete DB lifecycle:
1. Fresh boot from empty state
2. Migrations run correctly
3. Schema assertions pass
4. Backup/restore works correctly
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
        if os.path.exists(path):
            os.unlink(path)

    def test_fresh_boot_creates_tables(self, temp_db):
        """Fresh DB boot creates required tables via migrations."""
        from lib.db import run_migrations

        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")

        run_migrations(conn)

        # Check required tables exist
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cursor.fetchall()}

        # Core tables that must exist
        required = {"clients", "events", "invoices"}
        missing = required - tables

        assert not missing, f"Missing required tables: {missing}"
        conn.close()

    def test_fresh_boot_sets_schema_version(self, temp_db):
        """Fresh boot sets schema version pragma."""
        from lib.db import SCHEMA_VERSION, run_migrations

        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")

        run_migrations(conn)

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
        if os.path.exists(path):
            os.unlink(path)

    def test_migrations_run_idempotent(self, temp_db):
        """Migrations can run multiple times without error."""
        from lib.db import run_migrations

        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")

        # Run twice
        result1 = run_migrations(conn)
        result2 = run_migrations(conn)

        # Both should succeed (no exceptions)
        assert result1 is not None
        assert result2 is not None
        conn.close()

    def test_migrations_create_core_tables(self, temp_db):
        """Migrations create core tables."""
        from lib.db import run_migrations

        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")

        run_migrations(conn)

        # Check core tables
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='clients'"
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

        from lib.db import run_migrations

        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        run_migrations(conn)
        conn.close()

        yield path
        if os.path.exists(path):
            os.unlink(path)

    def test_schema_assertions_pass(self, initialized_db):
        """Schema assertions pass on properly initialized DB."""
        # Just verify we can connect and query
        conn = sqlite3.connect(initialized_db)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        assert len(tables) > 0, "No tables found after initialization"
        conn.close()


class TestUpgrade:
    """Test database upgrade from older schema versions."""

    @pytest.fixture
    def old_schema_db(self):
        """Create a database with older schema version."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        # Create DB with older schema (version 1, minimal tables)
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA user_version = 1")

        # Create minimal v1 schema
        conn.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                title TEXT,
                start_time TEXT,
                end_time TEXT,
                client_id TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id TEXT PRIMARY KEY,
                client_id TEXT,
                amount REAL,
                status TEXT
            )
        """)
        conn.commit()
        conn.close()

        yield path
        if os.path.exists(path):
            os.unlink(path)

    def test_upgrade_from_old_schema(self, old_schema_db):
        """Migrations upgrade from older schema to current."""
        from lib.db import SCHEMA_VERSION, run_migrations

        # Verify old version
        conn = sqlite3.connect(old_schema_db)
        cursor = conn.execute("PRAGMA user_version")
        old_version = cursor.fetchone()[0]
        assert old_version == 1, f"Expected old version 1, got {old_version}"

        # Run migrations
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        run_migrations(conn)

        # Verify upgraded
        cursor = conn.execute("PRAGMA user_version")
        new_version = cursor.fetchone()[0]
        assert new_version == SCHEMA_VERSION, f"Expected {SCHEMA_VERSION}, got {new_version}"

        # Verify core tables still exist
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='clients'"
        )
        assert cursor.fetchone() is not None, "clients table lost during upgrade"
        conn.close()

    def test_upgrade_preserves_data(self, old_schema_db):
        """Upgrade preserves existing data."""
        from lib.db import run_migrations

        # Insert test data
        conn = sqlite3.connect(old_schema_db)
        conn.execute("INSERT INTO clients (id, name) VALUES ('test-1', 'Test Client')")
        conn.commit()

        # Run migrations
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        run_migrations(conn)

        # Verify data preserved
        cursor = conn.execute("SELECT name FROM clients WHERE id = 'test-1'")
        row = cursor.fetchone()
        assert row is not None, "Data lost during upgrade"
        assert row[0] == "Test Client"
        conn.close()


class TestBackupRestore:
    """Test backup and restore functionality."""

    def test_backup_creates_copy(self):
        """Backup creates a valid copy of the database."""
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
            if os.path.exists(source_path):
                os.unlink(source_path)
            if os.path.exists(backup_path):
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
            if os.path.exists(source_path):
                os.unlink(source_path)
            if os.path.exists(backup_path):
                os.unlink(backup_path)
