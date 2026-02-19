"""
Determinism Guard Tests.

These tests verify that:
1. Live DB access is blocked
2. Cassettes are valid and deterministic
3. Fixture DB works correctly

Run with: pytest tests/test_determinism_guards.py -v
"""

import sqlite3
import pytest
from pathlib import Path

from tests.fixtures import create_fixture_db, guard_no_live_db


class TestLiveDBGuard:
    """Verify live database access is blocked."""

    def test_live_db_path_blocked(self):
        """Direct access to live DB path raises RuntimeError."""
        with pytest.raises(RuntimeError, match="DETERMINISM VIOLATION"):
            sqlite3.connect("data/moh_time_os.db")

    def test_absolute_live_db_path_blocked(self):
        """Absolute path to live DB is also blocked."""
        from tests.conftest import LIVE_DB_ABSOLUTE
        with pytest.raises(RuntimeError, match="DETERMINISM VIOLATION"):
            sqlite3.connect(str(LIVE_DB_ABSOLUTE))

    def test_memory_db_allowed(self):
        """In-memory databases are allowed."""
        conn = sqlite3.connect(":memory:")
        conn.execute("SELECT 1")
        conn.close()

    def test_temp_db_allowed(self, tmp_path):
        """Temp databases are allowed."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("SELECT 1")
        conn.close()

    def test_fixture_db_allowed(self, tmp_path):
        """Fixture databases are allowed."""
        conn = create_fixture_db(":memory:")
        cursor = conn.execute("SELECT COUNT(*) FROM clients")
        count = cursor.fetchone()[0]
        assert count > 0, "Fixture DB should have seeded clients"
        conn.close()

    def test_uri_format_live_db_blocked(self):
        """SQLite URI format (file:/path?mode=ro) to live DB is blocked."""
        from tests.conftest import LIVE_DB_ABSOLUTE
        uri = f"file:{LIVE_DB_ABSOLUTE}?mode=ro"
        with pytest.raises(RuntimeError, match="DETERMINISM VIOLATION"):
            sqlite3.connect(uri, uri=True)

    def test_home_db_path_blocked(self):
        """HOME path (~/.moh_time_os/data/moh_time_os.db) is blocked."""
        from tests.conftest import HOME_DB_ABSOLUTE
        with pytest.raises(RuntimeError, match="DETERMINISM VIOLATION"):
            sqlite3.connect(str(HOME_DB_ABSOLUTE))


class TestSQLiteSiblingFilesBlocked:
    """
    Regression tests for SQLite sibling files (-wal, -shm, -journal).

    SQLite creates these files alongside the main .db file. Any access to them
    also indicates live DB usage and must be blocked.
    """

    def test_wal_file_blocked(self):
        """WAL file access is blocked."""
        with pytest.raises(RuntimeError, match="DETERMINISM VIOLATION"):
            sqlite3.connect("data/moh_time_os.db-wal")

    def test_shm_file_blocked(self):
        """SHM file access is blocked."""
        with pytest.raises(RuntimeError, match="DETERMINISM VIOLATION"):
            sqlite3.connect("data/moh_time_os.db-shm")

    def test_journal_file_blocked(self):
        """Journal file access is blocked."""
        with pytest.raises(RuntimeError, match="DETERMINISM VIOLATION"):
            sqlite3.connect("data/moh_time_os.db-journal")

    def test_absolute_wal_file_blocked(self):
        """Absolute path to WAL file is blocked."""
        from tests.conftest import LIVE_DB_ABSOLUTE
        with pytest.raises(RuntimeError, match="DETERMINISM VIOLATION"):
            sqlite3.connect(f"{LIVE_DB_ABSOLUTE}-wal")

    def test_home_wal_file_blocked(self):
        """HOME WAL file is blocked."""
        from tests.conftest import HOME_DB_ABSOLUTE
        with pytest.raises(RuntimeError, match="DETERMINISM VIOLATION"):
            sqlite3.connect(f"{HOME_DB_ABSOLUTE}-wal")


class TestURIFormatBlocked:
    """
    Regression tests for SQLite URI format variations.

    SQLite accepts file: URIs with query params. All variations must be blocked.
    """

    def test_uri_relative_path_blocked(self):
        """URI with relative path is blocked."""
        with pytest.raises(RuntimeError, match="DETERMINISM VIOLATION"):
            sqlite3.connect("file:data/moh_time_os.db", uri=True)

    def test_uri_absolute_path_blocked(self):
        """URI with absolute path is blocked."""
        from tests.conftest import LIVE_DB_ABSOLUTE
        with pytest.raises(RuntimeError, match="DETERMINISM VIOLATION"):
            sqlite3.connect(f"file:{LIVE_DB_ABSOLUTE}", uri=True)

    def test_uri_with_mode_ro_blocked(self):
        """URI with ?mode=ro query param is blocked."""
        with pytest.raises(RuntimeError, match="DETERMINISM VIOLATION"):
            sqlite3.connect("file:data/moh_time_os.db?mode=ro", uri=True)

    def test_uri_with_cache_shared_blocked(self):
        """URI with ?cache=shared query param is blocked."""
        with pytest.raises(RuntimeError, match="DETERMINISM VIOLATION"):
            sqlite3.connect("file:data/moh_time_os.db?cache=shared", uri=True)

    def test_uri_with_multiple_params_blocked(self):
        """URI with multiple query params is blocked."""
        with pytest.raises(RuntimeError, match="DETERMINISM VIOLATION"):
            sqlite3.connect("file:data/moh_time_os.db?mode=ro&cache=shared", uri=True)


class TestDbapi2BypassClosed:
    """
    Regression tests for sqlite3.dbapi2.connect bypass.

    This was a critical bypass where code could use sqlite3.dbapi2.connect
    instead of sqlite3.connect to avoid the guard.
    """

    def test_dbapi2_connect_blocked(self):
        """sqlite3.dbapi2.connect is also guarded."""
        with pytest.raises(RuntimeError, match="DETERMINISM VIOLATION"):
            sqlite3.dbapi2.connect("data/moh_time_os.db")

    def test_dbapi2_absolute_path_blocked(self):
        """sqlite3.dbapi2.connect with absolute path is blocked."""
        from tests.conftest import LIVE_DB_ABSOLUTE
        with pytest.raises(RuntimeError, match="DETERMINISM VIOLATION"):
            sqlite3.dbapi2.connect(str(LIVE_DB_ABSOLUTE))

    def test_dbapi2_uri_blocked(self):
        """sqlite3.dbapi2.connect with URI is blocked."""
        with pytest.raises(RuntimeError, match="DETERMINISM VIOLATION"):
            sqlite3.dbapi2.connect("file:data/moh_time_os.db?mode=ro", uri=True)

    def test_dbapi2_memory_allowed(self):
        """sqlite3.dbapi2.connect to :memory: is allowed."""
        conn = sqlite3.dbapi2.connect(":memory:")
        conn.execute("SELECT 1")
        conn.close()


class TestTildeExpansionBlocked:
    """
    Regression tests for tilde expansion in paths.

    Paths like ~/.moh_time_os/data/moh_time_os.db must be blocked.
    """

    def test_tilde_home_db_blocked(self):
        """Tilde path to HOME DB is blocked."""
        with pytest.raises(RuntimeError, match="DETERMINISM VIOLATION"):
            sqlite3.connect("~/.moh_time_os/data/moh_time_os.db")

    def test_tilde_home_wal_blocked(self):
        """Tilde path to HOME WAL file is blocked."""
        with pytest.raises(RuntimeError, match="DETERMINISM VIOLATION"):
            sqlite3.connect("~/.moh_time_os/data/moh_time_os.db-wal")


class TestGuardNoLiveDbFunction:
    """Test the guard_no_live_db helper function."""

    def test_raises_on_live_path(self):
        """guard_no_live_db raises on live DB path."""
        with pytest.raises(RuntimeError, match="DETERMINISM VIOLATION"):
            guard_no_live_db("data/moh_time_os.db")

    def test_passes_on_fixture_path(self, tmp_path):
        """guard_no_live_db allows fixture paths."""
        fixture_path = tmp_path / "fixture.db"
        guard_no_live_db(str(fixture_path))  # Should not raise


class TestFilesystemProbeGuard:
    """
    Regression tests for filesystem probe guards.

    These catch stat/lstat/exists calls on live DB paths, not just sqlite3.connect.
    This is critical because module import can trigger path resolution that probes
    for default DB locations.
    """

    def test_path_exists_on_live_db_blocked(self):
        """Path.exists() on live DB path raises RuntimeError."""
        from tests.conftest import LIVE_DB_ABSOLUTE
        with pytest.raises(RuntimeError, match="DETERMINISM VIOLATION.*live DB path probed"):
            LIVE_DB_ABSOLUTE.exists()

    def test_path_exists_on_home_db_blocked(self):
        """Path.exists() on home DB path raises RuntimeError."""
        from tests.conftest import HOME_DB_ABSOLUTE
        with pytest.raises(RuntimeError, match="DETERMINISM VIOLATION.*live DB path probed"):
            HOME_DB_ABSOLUTE.exists()

    def test_os_stat_on_live_db_blocked(self):
        """os.stat() on live DB path raises RuntimeError."""
        import os
        from tests.conftest import LIVE_DB_ABSOLUTE
        with pytest.raises(RuntimeError, match="DETERMINISM VIOLATION.*live DB path probed"):
            os.stat(str(LIVE_DB_ABSOLUTE))

    def test_os_lstat_on_live_db_blocked(self):
        """os.lstat() on live DB path raises RuntimeError."""
        import os
        from tests.conftest import LIVE_DB_ABSOLUTE
        with pytest.raises(RuntimeError, match="DETERMINISM VIOLATION.*live DB path probed"):
            os.lstat(str(LIVE_DB_ABSOLUTE))

    def test_path_stat_on_live_db_blocked(self):
        """Path.stat() on live DB path raises RuntimeError."""
        from tests.conftest import LIVE_DB_ABSOLUTE
        with pytest.raises(RuntimeError, match="DETERMINISM VIOLATION.*live DB path probed"):
            LIVE_DB_ABSOLUTE.stat()

    def test_temp_path_operations_allowed(self, tmp_path):
        """Filesystem operations on temp paths are allowed."""
        import os
        test_file = tmp_path / "test.db"
        test_file.touch()  # Create the file

        # These should all work without raising
        assert test_file.exists()
        os.stat(str(test_file))
        os.lstat(str(test_file))
        test_file.stat()

    def test_query_engine_import_does_not_probe(self):
        """
        QueryEngine can be imported without probing live DB paths.

        This is a regression test for the import-time DEFAULT_DB_PATH issue.
        The module should use lazy initialization to avoid filesystem probes.
        """
        # If we got here without error, the guard didn't fire during import
        from lib.query_engine import QueryEngine, get_default_db_path

        # QueryEngine class should be importable
        assert QueryEngine is not None

        # get_default_db_path should exist but NOT have been called yet
        # (we can't easily test this without more mocking, but the import succeeded
        # which means no probes happened)


class TestCassetteValidation:
    """Test cassette infrastructure."""

    def test_cassettes_valid(self, validated_cassettes):
        """All cassettes pass validation (expiry, redaction, sorted keys)."""
        # validated_cassettes fixture runs validation and fails if issues
        assert validated_cassettes is True

    def test_cassette_has_expiry(self):
        """Cassettes require expiry metadata."""
        from lib.collectors.recorder import CassetteEntry

        entry = CassetteEntry(
            request_method="GET",
            request_url="https://api.example.com/test",
            request_headers={},
            request_body=None,
            response_status=200,
            response_headers={},
            response_body="{}",
            recorded_at="2024-01-01T00:00:00Z",
            expires_at="2024-02-01T00:00:00Z",
        )

        assert entry.expires_at is not None
        assert entry.recorded_at is not None

    def test_redact_secrets(self):
        """Secret redaction works."""
        from lib.collectors.recorder import redact_secrets

        text = '{"access_token": "secret123", "data": "visible"}'
        result = redact_secrets(text)

        assert "secret123" not in result
        assert "[REDACTED]" in result
        assert '"data": "visible"' in result


class TestFixtureDB:
    """Test fixture database infrastructure."""

    def test_creates_all_tables(self):
        """Fixture DB has all required tables."""
        conn = create_fixture_db(":memory:")

        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {t[0] for t in tables}

        required = {"clients", "brands", "projects", "invoices", "people", "tasks", "communications"}
        assert required.issubset(table_names), f"Missing tables: {required - table_names}"

    def test_has_seeded_data(self):
        """Fixture DB is seeded with deterministic data."""
        conn = create_fixture_db(":memory:")

        # Check clients exist
        client_count = conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        assert client_count > 0, "Expected seeded clients"

        # Check brands exist
        brand_count = conn.execute("SELECT COUNT(*) FROM brands").fetchone()[0]
        assert brand_count > 0, "Expected seeded brands"

        # Check projects exist
        project_count = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        assert project_count > 0, "Expected seeded projects"

    def test_deterministic_counts(self):
        """Fixture DB has deterministic counts matching golden expectations."""
        from tests.fixtures.fixture_db import load_seed_data

        seed = load_seed_data()
        expected_clients = len(seed.get("clients", []))
        expected_brands = len(seed.get("brands", []))

        conn = create_fixture_db(":memory:")
        actual_clients = conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        actual_brands = conn.execute("SELECT COUNT(*) FROM brands").fetchone()[0]

        assert actual_clients == expected_clients, "Client count mismatch"
        assert actual_brands == expected_brands, "Brand count mismatch"
