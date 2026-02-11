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
