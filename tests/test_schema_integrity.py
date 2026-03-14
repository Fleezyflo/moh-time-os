"""
Schema Integrity Tests — prove constraints survive the full lifecycle.

These tests verify that critical table invariants hold across:
  - fresh bootstrap (create_fresh)
  - converge on existing DB
  - converge on DB with weak pre-constraint schema (constraint drift)
  - table rebuild during constraint upgrade

If any test here fails, schema maintenance is silently weakening integrity.
"""

import sqlite3

import pytest

from lib import schema_engine

# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────


def _get_table_info(conn: sqlite3.Connection, table: str) -> list[tuple]:
    """Return PRAGMA table_info rows for a table.

    Each row: (cid, name, type, notnull, dflt_value, pk)
    """
    return conn.execute(f"PRAGMA table_info([{table}])").fetchall()


def _get_index_list(conn: sqlite3.Connection, table: str) -> list[tuple]:
    """Return PRAGMA index_list rows for a table.

    Each row: (seq, name, unique, origin, partial)
    """
    return conn.execute(f"PRAGMA index_list([{table}])").fetchall()


def _col_info(table_info: list[tuple], col_name: str) -> tuple | None:
    """Extract a specific column's info from PRAGMA table_info results."""
    for row in table_info:
        if row[1] == col_name:
            return row
    return None


def _has_unique_index_on(conn: sqlite3.Connection, table: str, col: str) -> bool:
    """Check if a UNIQUE index exists covering exactly the given column."""
    for idx_row in _get_index_list(conn, table):
        if idx_row[2]:  # unique flag
            idx_name = idx_row[1]
            idx_info = conn.execute(f"PRAGMA index_info([{idx_name}])").fetchall()
            cols = [r[2] for r in idx_info]
            if cols == [col]:
                return True
    return False


# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────


@pytest.fixture
def fresh_db():
    """In-memory DB created via create_fresh (canonical schema)."""
    conn = sqlite3.connect(":memory:")
    result = schema_engine.create_fresh(conn)
    assert not result["errors"], f"create_fresh errors: {result['errors']}"
    yield conn
    conn.close()


@pytest.fixture
def converged_db():
    """In-memory DB created via converge on empty DB."""
    conn = sqlite3.connect(":memory:")
    result = schema_engine.converge(conn)
    assert not result["errors"], f"converge errors: {result['errors']}"
    yield conn
    conn.close()


@pytest.fixture
def weak_schema_db():
    """In-memory DB with old weak api_keys schema (no NOT NULL, no UNIQUE).

    Simulates a database that was created before constraints were added
    to schema.py.
    """
    conn = sqlite3.connect(":memory:")
    # Create api_keys with the OLD weak schema (no NOT NULL, no UNIQUE, no CHECK)
    conn.execute("""
        CREATE TABLE api_keys (
            id TEXT PRIMARY KEY,
            key_hash TEXT,
            name TEXT,
            role TEXT,
            created_at TEXT,
            expires_at TEXT,
            last_used_at TEXT,
            is_active INTEGER DEFAULT 1,
            created_by TEXT
        )
    """)
    conn.commit()
    yield conn
    conn.close()


# ──────────────────────────────────────────────────────────────
# Test 1: Fresh DB has correct constraints on api_keys
# ──────────────────────────────────────────────────────────────


class TestFreshDBConstraints:
    """Verify api_keys constraints exist after create_fresh."""

    def test_key_hash_not_null(self, fresh_db):
        info = _col_info(_get_table_info(fresh_db, "api_keys"), "key_hash")
        assert info is not None, "key_hash column missing"
        assert info[3] == 1, "key_hash should be NOT NULL"

    def test_name_not_null(self, fresh_db):
        info = _col_info(_get_table_info(fresh_db, "api_keys"), "name")
        assert info is not None, "name column missing"
        assert info[3] == 1, "name should be NOT NULL"

    def test_role_not_null(self, fresh_db):
        info = _col_info(_get_table_info(fresh_db, "api_keys"), "role")
        assert info is not None, "role column missing"
        assert info[3] == 1, "role should be NOT NULL"

    def test_created_at_not_null(self, fresh_db):
        info = _col_info(_get_table_info(fresh_db, "api_keys"), "created_at")
        assert info is not None, "created_at column missing"
        assert info[3] == 1, "created_at should be NOT NULL"

    def test_is_active_not_null(self, fresh_db):
        info = _col_info(_get_table_info(fresh_db, "api_keys"), "is_active")
        assert info is not None, "is_active column missing"
        assert info[3] == 1, "is_active should be NOT NULL"

    def test_key_hash_unique(self, fresh_db):
        assert _has_unique_index_on(fresh_db, "api_keys", "key_hash"), (
            "key_hash should have a UNIQUE index"
        )

    def test_rejects_null_key_hash(self, fresh_db):
        with pytest.raises(sqlite3.IntegrityError):
            fresh_db.execute(
                "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
                "VALUES ('k1', NULL, 'test', 'viewer', '2025-01-01T00:00:00Z', 1)"
            )

    def test_rejects_null_name(self, fresh_db):
        with pytest.raises(sqlite3.IntegrityError):
            fresh_db.execute(
                "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
                "VALUES ('k1', 'hash1', NULL, 'viewer', '2025-01-01T00:00:00Z', 1)"
            )

    def test_rejects_null_role(self, fresh_db):
        with pytest.raises(sqlite3.IntegrityError):
            fresh_db.execute(
                "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
                "VALUES ('k1', 'hash1', 'test', NULL, '2025-01-01T00:00:00Z', 1)"
            )

    def test_rejects_invalid_role(self, fresh_db):
        with pytest.raises(sqlite3.IntegrityError):
            fresh_db.execute(
                "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
                "VALUES ('k1', 'hash1', 'test', 'superadmin', '2025-01-01T00:00:00Z', 1)"
            )

    def test_rejects_duplicate_key_hash(self, fresh_db):
        fresh_db.execute(
            "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
            "VALUES ('k1', 'hash1', 'test1', 'viewer', '2025-01-01T00:00:00Z', 1)"
        )
        with pytest.raises(sqlite3.IntegrityError):
            fresh_db.execute(
                "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
                "VALUES ('k2', 'hash1', 'test2', 'viewer', '2025-01-01T00:00:00Z', 1)"
            )

    def test_accepts_valid_row(self, fresh_db):
        """Sanity check — a valid row inserts without error."""
        fresh_db.execute(
            "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
            "VALUES ('k1', 'hash1', 'test', 'admin', '2025-01-01T00:00:00Z', 1)"
        )
        row = fresh_db.execute("SELECT * FROM api_keys WHERE id = 'k1'").fetchone()
        assert row is not None


# ──────────────────────────────────────────────────────────────
# Test 2: Converge on empty DB produces same constraints as fresh
# ──────────────────────────────────────────────────────────────


class TestConvergedDBConstraints:
    """Verify converge on empty DB produces identical constraints to fresh."""

    def test_key_hash_not_null(self, converged_db):
        info = _col_info(_get_table_info(converged_db, "api_keys"), "key_hash")
        assert info is not None
        assert info[3] == 1, "key_hash should be NOT NULL after converge"

    def test_role_not_null(self, converged_db):
        info = _col_info(_get_table_info(converged_db, "api_keys"), "role")
        assert info is not None
        assert info[3] == 1, "role should be NOT NULL after converge"

    def test_key_hash_unique(self, converged_db):
        assert _has_unique_index_on(converged_db, "api_keys", "key_hash")

    def test_rejects_null_key_hash(self, converged_db):
        with pytest.raises(sqlite3.IntegrityError):
            converged_db.execute(
                "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
                "VALUES ('k1', NULL, 'test', 'viewer', '2025-01-01T00:00:00Z', 1)"
            )

    def test_rejects_duplicate_key_hash(self, converged_db):
        converged_db.execute(
            "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
            "VALUES ('k1', 'hash1', 'test1', 'viewer', '2025-01-01T00:00:00Z', 1)"
        )
        with pytest.raises(sqlite3.IntegrityError):
            converged_db.execute(
                "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
                "VALUES ('k2', 'hash1', 'test2', 'viewer', '2025-01-01T00:00:00Z', 1)"
            )

    def test_rejects_invalid_role(self, converged_db):
        with pytest.raises(sqlite3.IntegrityError):
            converged_db.execute(
                "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
                "VALUES ('k1', 'hash1', 'test', 'superadmin', '2025-01-01T00:00:00Z', 1)"
            )


# ──────────────────────────────────────────────────────────────
# Test 3: Converge on weak schema DB rebuilds with correct constraints
# ──────────────────────────────────────────────────────────────


class TestConstraintDriftRebuild:
    """Verify converge detects weak schema and rebuilds with constraints."""

    def test_weak_db_allows_null_key_hash_before_converge(self, weak_schema_db):
        """Prove the weakness exists before converge fixes it."""
        weak_schema_db.execute(
            "INSERT INTO api_keys (id, key_hash, name, role, created_at) "
            "VALUES ('k1', NULL, 'test', 'viewer', '2025-01-01T00:00:00Z')"
        )
        row = weak_schema_db.execute("SELECT * FROM api_keys WHERE id = 'k1'").fetchone()
        assert row is not None, "Weak schema should allow NULL key_hash"

    def test_converge_rebuilds_weak_table(self, weak_schema_db):
        """Converge detects constraint drift and rebuilds."""
        result = schema_engine.converge(weak_schema_db)
        rebuilds = result.get("constraint_rebuilds", [])
        rebuilt_tables = [r["table"] for r in rebuilds]
        assert "api_keys" in rebuilt_tables, (
            "api_keys should be rebuilt when constraint_version is behind"
        )

    def test_after_converge_rejects_null_key_hash(self, weak_schema_db):
        """After converge, NULL key_hash is rejected."""
        schema_engine.converge(weak_schema_db)
        with pytest.raises(sqlite3.IntegrityError):
            weak_schema_db.execute(
                "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
                "VALUES ('k1', NULL, 'test', 'viewer', '2025-01-01T00:00:00Z', 1)"
            )

    def test_after_converge_rejects_duplicate_key_hash(self, weak_schema_db):
        """After converge, duplicate key_hash is rejected."""
        schema_engine.converge(weak_schema_db)
        weak_schema_db.execute(
            "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
            "VALUES ('k1', 'hash1', 'test1', 'viewer', '2025-01-01T00:00:00Z', 1)"
        )
        with pytest.raises(sqlite3.IntegrityError):
            weak_schema_db.execute(
                "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
                "VALUES ('k2', 'hash1', 'test2', 'viewer', '2025-01-01T00:00:00Z', 1)"
            )

    def test_after_converge_rejects_invalid_role(self, weak_schema_db):
        """After converge, invalid role values are rejected."""
        schema_engine.converge(weak_schema_db)
        with pytest.raises(sqlite3.IntegrityError):
            weak_schema_db.execute(
                "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
                "VALUES ('k1', 'hash1', 'test', 'superadmin', '2025-01-01T00:00:00Z', 1)"
            )

    def test_rebuild_preserves_valid_data(self, weak_schema_db):
        """Valid rows survive the constraint rebuild."""
        # Insert valid data before converge
        weak_schema_db.execute(
            "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
            "VALUES ('k1', 'hash1', 'test', 'viewer', '2025-01-01T00:00:00Z', 1)"
        )
        weak_schema_db.execute(
            "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
            "VALUES ('k2', 'hash2', 'test2', 'admin', '2025-01-02T00:00:00Z', 1)"
        )
        weak_schema_db.commit()

        schema_engine.converge(weak_schema_db)

        rows = weak_schema_db.execute("SELECT id FROM api_keys ORDER BY id").fetchall()
        ids = [r[0] for r in rows]
        assert ids == ["k1", "k2"], f"Valid rows should survive rebuild, got {ids}"

    def test_rebuild_rejects_invalid_data(self, weak_schema_db):
        """Invalid rows (NULL in NOT NULL columns) are rejected and quarantined."""
        # Insert a valid row and an invalid row
        weak_schema_db.execute(
            "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
            "VALUES ('valid', 'hash1', 'test', 'viewer', '2025-01-01T00:00:00Z', 1)"
        )
        weak_schema_db.execute(
            "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
            "VALUES ('invalid', NULL, 'test', 'viewer', '2025-01-01T00:00:00Z', 1)"
        )
        weak_schema_db.commit()

        result = schema_engine.converge(weak_schema_db)

        # Check rebuild stats
        rebuilds = result.get("constraint_rebuilds", [])
        api_keys_rebuild = next(r for r in rebuilds if r["table"] == "api_keys")
        assert api_keys_rebuild["rows_before"] == 2
        assert api_keys_rebuild["rows_after"] == 1
        assert api_keys_rebuild["rows_rejected"] == 1

        # Only the valid row remains in api_keys
        rows = weak_schema_db.execute("SELECT id FROM api_keys").fetchall()
        assert [r[0] for r in rows] == ["valid"]

    def test_rebuild_quarantines_rejected_rows(self, weak_schema_db):
        """Rejected rows are preserved in a quarantine table, not silently destroyed."""
        weak_schema_db.execute(
            "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
            "VALUES ('good', 'hash1', 'test', 'viewer', '2025-01-01T00:00:00Z', 1)"
        )
        weak_schema_db.execute(
            "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
            "VALUES ('bad_null_hash', NULL, 'test', 'viewer', '2025-01-01T00:00:00Z', 1)"
        )
        weak_schema_db.execute(
            "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
            "VALUES ('bad_role', 'hash2', 'test', 'superadmin', '2025-01-01T00:00:00Z', 1)"
        )
        weak_schema_db.commit()

        result = schema_engine.converge(weak_schema_db)

        # Verify quarantine table exists and contains the rejected rows
        rebuilds = result.get("constraint_rebuilds", [])
        api_rebuild = next(r for r in rebuilds if r["table"] == "api_keys")
        assert api_rebuild["quarantine_table"] == "_quarantine_api_keys"
        assert api_rebuild["rows_rejected"] == 2

        # Verify rejected IDs are identified
        assert sorted(api_rebuild["rejected_ids"]) == ["bad_null_hash", "bad_role"]

        # Verify quarantine table actually contains the data
        q_rows = weak_schema_db.execute(
            "SELECT id FROM _quarantine_api_keys ORDER BY id"
        ).fetchall()
        assert [r[0] for r in q_rows] == ["bad_null_hash", "bad_role"]

        # Verify quarantine preserves full row data for recovery
        q_full = weak_schema_db.execute(
            "SELECT id, key_hash, role FROM _quarantine_api_keys WHERE id = 'bad_role'"
        ).fetchone()
        assert q_full is not None
        assert q_full[1] == "hash2"
        assert q_full[2] == "superadmin"

    def test_rebuild_no_quarantine_when_no_rejections(self, weak_schema_db):
        """When all rows are valid, no quarantine table is created."""
        weak_schema_db.execute(
            "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
            "VALUES ('k1', 'hash1', 'test', 'viewer', '2025-01-01T00:00:00Z', 1)"
        )
        weak_schema_db.commit()

        result = schema_engine.converge(weak_schema_db)
        rebuilds = result.get("constraint_rebuilds", [])
        api_rebuild = next(r for r in rebuilds if r["table"] == "api_keys")
        assert api_rebuild["rows_rejected"] == 0
        assert api_rebuild["quarantine_table"] is None


# ──────────────────────────────────────────────────────────────
# Test 3b: COALESCE fail-closed policy for is_active
# ──────────────────────────────────────────────────────────────


class TestCoalesceFailClosed:
    """Verify that NULL is_active defaults to 0 (inactive), not 1 (active).

    This is the fail-closed direction: unknown active status → inactive.
    """

    def test_null_is_active_becomes_inactive_after_rebuild(self):
        """A row with NULL is_active in weak schema becomes is_active=0 after rebuild."""
        conn = sqlite3.connect(":memory:")
        conn.execute("""
            CREATE TABLE api_keys (
                id TEXT PRIMARY KEY,
                key_hash TEXT,
                name TEXT,
                role TEXT,
                created_at TEXT,
                expires_at TEXT,
                last_used_at TEXT,
                is_active INTEGER,
                created_by TEXT
            )
        """)
        # Insert row with NULL is_active — all other required fields valid
        conn.execute(
            "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
            "VALUES ('k1', 'hash1', 'test', 'viewer', '2025-01-01T00:00:00Z', NULL)"
        )
        conn.commit()

        schema_engine.converge(conn)

        row = conn.execute("SELECT is_active FROM api_keys WHERE id = 'k1'").fetchone()
        assert row is not None, "Row should survive rebuild (all required fields valid)"
        assert row[0] == 0, f"NULL is_active must become 0 (inactive/fail-closed), got {row[0]}"
        conn.close()

    def test_explicit_active_survives_rebuild(self):
        """A row with is_active=1 stays active after rebuild."""
        conn = sqlite3.connect(":memory:")
        conn.execute("""
            CREATE TABLE api_keys (
                id TEXT PRIMARY KEY,
                key_hash TEXT,
                name TEXT,
                role TEXT,
                created_at TEXT,
                expires_at TEXT,
                last_used_at TEXT,
                is_active INTEGER DEFAULT 1,
                created_by TEXT
            )
        """)
        conn.execute(
            "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
            "VALUES ('k1', 'hash1', 'test', 'admin', '2025-01-01T00:00:00Z', 1)"
        )
        conn.commit()

        schema_engine.converge(conn)

        row = conn.execute("SELECT is_active FROM api_keys WHERE id = 'k1'").fetchone()
        assert row is not None
        assert row[0] == 1, "Explicit is_active=1 must survive rebuild unchanged"
        conn.close()

    def test_explicit_inactive_survives_rebuild(self):
        """A row with is_active=0 stays inactive after rebuild."""
        conn = sqlite3.connect(":memory:")
        conn.execute("""
            CREATE TABLE api_keys (
                id TEXT PRIMARY KEY,
                key_hash TEXT,
                name TEXT,
                role TEXT,
                created_at TEXT,
                expires_at TEXT,
                last_used_at TEXT,
                is_active INTEGER DEFAULT 1,
                created_by TEXT
            )
        """)
        conn.execute(
            "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
            "VALUES ('k1', 'hash1', 'test', 'admin', '2025-01-01T00:00:00Z', 0)"
        )
        conn.commit()

        schema_engine.converge(conn)

        row = conn.execute("SELECT is_active FROM api_keys WHERE id = 'k1'").fetchone()
        assert row is not None
        assert row[0] == 0, "Explicit is_active=0 must survive rebuild unchanged"
        conn.close()


# ──────────────────────────────────────────────────────────────
# Test 3c: Index verification after rebuild
# ──────────────────────────────────────────────────────────────


class TestIndexSurvival:
    """Verify indexes are recreated after constraint rebuild."""

    def test_key_hash_index_exists_after_rebuild(self):
        """The idx_api_keys_key_hash index is created after rebuild."""
        conn = sqlite3.connect(":memory:")
        # Create weak schema (no index)
        conn.execute("""
            CREATE TABLE api_keys (
                id TEXT PRIMARY KEY,
                key_hash TEXT,
                name TEXT,
                role TEXT,
                created_at TEXT,
                expires_at TEXT,
                last_used_at TEXT,
                is_active INTEGER DEFAULT 1,
                created_by TEXT
            )
        """)
        conn.commit()

        result = schema_engine.converge(conn)
        assert not result["errors"], f"converge errors: {result['errors']}"

        # Phase 2 of converge creates indexes after Phase 0.5 rebuild
        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_api_keys_key_hash'"
        ).fetchone()
        assert indexes is not None, "idx_api_keys_key_hash should exist after converge"
        conn.close()

    def test_unique_constraint_survives_rebuild(self):
        """UNIQUE(key_hash) from table definition survives rebuild."""
        conn = sqlite3.connect(":memory:")
        conn.execute("""
            CREATE TABLE api_keys (
                id TEXT PRIMARY KEY,
                key_hash TEXT,
                name TEXT,
                role TEXT,
                created_at TEXT,
                expires_at TEXT,
                last_used_at TEXT,
                is_active INTEGER DEFAULT 1,
                created_by TEXT
            )
        """)
        conn.commit()

        schema_engine.converge(conn)

        assert _has_unique_index_on(conn, "api_keys", "key_hash"), (
            "UNIQUE(key_hash) should exist after rebuild"
        )
        conn.close()


# ──────────────────────────────────────────────────────────────
# Test 4: Idempotent converge — second run is a no-op
# ──────────────────────────────────────────────────────────────


class TestConvergeIdempotent:
    """Verify running converge twice doesn't break anything."""

    def test_double_converge_no_errors(self):
        conn = sqlite3.connect(":memory:")
        result1 = schema_engine.converge(conn)
        assert not result1["errors"]

        result2 = schema_engine.converge(conn)
        assert not result2["errors"]
        # Second run should not rebuild api_keys (version already stored)
        rebuilds = result2.get("constraint_rebuilds", [])
        rebuilt_tables = [r["table"] for r in rebuilds]
        assert "api_keys" not in rebuilt_tables, "Second converge should not rebuild api_keys"
        conn.close()

    def test_constraints_survive_double_converge(self):
        conn = sqlite3.connect(":memory:")
        schema_engine.converge(conn)
        schema_engine.converge(conn)

        # Constraints should still hold
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
                "VALUES ('k1', NULL, 'test', 'viewer', '2025-01-01T00:00:00Z', 1)"
            )
        conn.close()


# ──────────────────────────────────────────────────────────────
# Test 5: Fresh vs converge parity
# ──────────────────────────────────────────────────────────────


class TestFreshConvergeParity:
    """Verify fresh DB and converged DB enforce the same constraints."""

    def _get_constraint_profile(self, conn: sqlite3.Connection) -> dict:
        """Build a comparable constraint profile for api_keys.

        Includes metadata (NOT NULL, PK, UNIQUE) AND behavioral probes
        for CHECK constraints that PRAGMA table_info cannot expose.
        """
        info = _get_table_info(conn, "api_keys")

        # Behavioral probe: does CHECK(role IN (...)) reject invalid roles?
        check_rejects_invalid_role = False
        try:
            conn.execute(
                "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
                "VALUES ('__probe__', '__probe__', '__probe__', 'EVIL_ROLE', "
                "'2025-01-01T00:00:00Z', 1)"
            )
            # If we get here, CHECK is missing — roll back the probe row
            conn.execute("DELETE FROM api_keys WHERE id = '__probe__'")
        except sqlite3.IntegrityError:
            check_rejects_invalid_role = True

        return {
            "columns": {row[1]: {"notnull": row[3], "pk": row[5]} for row in info},
            "has_unique_key_hash": _has_unique_index_on(conn, "api_keys", "key_hash"),
            "check_rejects_invalid_role": check_rejects_invalid_role,
        }

    def test_fresh_and_converge_have_same_constraints(self):
        fresh = sqlite3.connect(":memory:")
        schema_engine.create_fresh(fresh)

        converged = sqlite3.connect(":memory:")
        schema_engine.converge(converged)

        fresh_profile = self._get_constraint_profile(fresh)
        converge_profile = self._get_constraint_profile(converged)

        assert fresh_profile == converge_profile, (
            f"Fresh and converged schemas differ:\n"
            f"  Fresh:     {fresh_profile}\n"
            f"  Converged: {converge_profile}"
        )

        fresh.close()
        converged.close()

    def test_fresh_and_post_drift_converge_have_same_constraints(self):
        """After fixing constraint drift, schema matches fresh."""
        fresh = sqlite3.connect(":memory:")
        schema_engine.create_fresh(fresh)

        # Simulate old weak schema
        drifted = sqlite3.connect(":memory:")
        drifted.execute("""
            CREATE TABLE api_keys (
                id TEXT PRIMARY KEY,
                key_hash TEXT,
                name TEXT,
                role TEXT,
                created_at TEXT,
                expires_at TEXT,
                last_used_at TEXT,
                is_active INTEGER DEFAULT 1,
                created_by TEXT
            )
        """)
        schema_engine.converge(drifted)

        fresh_profile = self._get_constraint_profile(fresh)
        drifted_profile = self._get_constraint_profile(drifted)

        assert fresh_profile == drifted_profile, (
            f"Post-drift converge doesn't match fresh:\n"
            f"  Fresh:   {fresh_profile}\n"
            f"  Drifted: {drifted_profile}"
        )

        fresh.close()
        drifted.close()


# ──────────────────────────────────────────────────────────────
# Test 6: NULL handling in KeyManager read paths
# ──────────────────────────────────────────────────────────────


try:
    from lib.security.key_manager import _row_to_key_info

    _HAS_KEY_MANAGER = True
except ImportError:
    _HAS_KEY_MANAGER = False

_skip_key_manager = pytest.mark.skipif(
    not _HAS_KEY_MANAGER,
    reason="key_manager dependencies (fastapi) not installed",
)


@_skip_key_manager
class TestKeyManagerNullHandling:
    """Verify KeyManager read paths handle corrupt NULL data safely."""

    def test_row_to_key_info_rejects_null_role(self):
        row = ("id1", "name1", None, "2025-01-01", None, None, 1, None)
        result = _row_to_key_info(row)
        assert result is None, "NULL role should be rejected"

    def test_row_to_key_info_rejects_null_name(self):
        row = ("id1", None, "viewer", "2025-01-01", None, None, 1, None)
        result = _row_to_key_info(row)
        assert result is None, "NULL name should be rejected"

    def test_row_to_key_info_rejects_null_id(self):
        row = (None, "name1", "viewer", "2025-01-01", None, None, 1, None)
        result = _row_to_key_info(row)
        assert result is None, "NULL id should be rejected"

    def test_row_to_key_info_rejects_invalid_role(self):
        row = ("id1", "name1", "superadmin", "2025-01-01", None, None, 1, None)
        result = _row_to_key_info(row)
        assert result is None, "Invalid role should be rejected"

    def test_row_to_key_info_accepts_valid_row(self):
        row = ("id1", "name1", "viewer", "2025-01-01", None, None, 1, None)
        result = _row_to_key_info(row)
        assert result is not None
        assert result.id == "id1"
        assert result.name == "name1"
        assert result.role.value == "viewer"

    def test_row_to_key_info_handles_null_is_active(self):
        row = ("id1", "name1", "admin", "2025-01-01", None, None, None, None)
        result = _row_to_key_info(row)
        assert result is not None
        assert result.is_active is False, "NULL is_active should default to False"


# ──────────────────────────────────────────────────────────────
# Test 7: COALESCE mutation visibility (D1 fix)
# ──────────────────────────────────────────────────────────────


class TestCoalesceVisibility:
    """Verify COALESCE mutations are surfaced in rebuild results and logs."""

    def _make_weak_db_with_null_is_active(self):
        """Create a weak-schema DB with a row whose is_active is NULL."""
        conn = sqlite3.connect(":memory:")
        conn.execute("""
            CREATE TABLE api_keys (
                id TEXT PRIMARY KEY,
                key_hash TEXT,
                name TEXT,
                role TEXT,
                created_at TEXT,
                expires_at TEXT,
                last_used_at TEXT,
                is_active INTEGER,
                created_by TEXT
            )
        """)
        return conn

    def test_coalesced_row_appears_in_result(self):
        """Rebuild result includes rows_coalesced and coalesced_ids."""
        conn = self._make_weak_db_with_null_is_active()
        conn.execute(
            "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
            "VALUES ('k1', 'hash1', 'test', 'viewer', '2025-01-01T00:00:00Z', NULL)"
        )
        conn.commit()

        result = schema_engine.converge(conn)
        rebuilds = result.get("constraint_rebuilds", [])
        api_rebuild = next(r for r in rebuilds if r["table"] == "api_keys")

        assert api_rebuild["rows_coalesced"] == 1, (
            f"Expected 1 coalesced row, got {api_rebuild['rows_coalesced']}"
        )
        assert api_rebuild["coalesced_ids"] == ["k1"], (
            f"Expected coalesced_ids=['k1'], got {api_rebuild['coalesced_ids']}"
        )
        conn.close()

    def test_coalesced_row_not_counted_as_rejected(self):
        """A coalesced row is rescued, not rejected — rows_rejected must be 0."""
        conn = self._make_weak_db_with_null_is_active()
        conn.execute(
            "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
            "VALUES ('k1', 'hash1', 'test', 'viewer', '2025-01-01T00:00:00Z', NULL)"
        )
        conn.commit()

        result = schema_engine.converge(conn)
        rebuilds = result.get("constraint_rebuilds", [])
        api_rebuild = next(r for r in rebuilds if r["table"] == "api_keys")

        assert api_rebuild["rows_rejected"] == 0, "Coalesced rows must not be counted as rejected"
        assert api_rebuild["rows_coalesced"] == 1
        conn.close()

    def test_coalesced_row_logged_at_warning(self):
        """COALESCE mutation produces a WARNING log with the row's PK."""
        import logging

        conn = self._make_weak_db_with_null_is_active()
        conn.execute(
            "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
            "VALUES ('k1', 'hash1', 'test', 'viewer', '2025-01-01T00:00:00Z', NULL)"
        )
        conn.commit()

        log_records = []
        handler = logging.Handler()
        handler.emit = lambda record: log_records.append(record)
        handler.setLevel(logging.WARNING)
        logger = logging.getLogger("lib.schema_engine")
        logger.addHandler(handler)
        try:
            schema_engine.converge(conn)
        finally:
            logger.removeHandler(handler)

        coalesce_logs = [
            r for r in log_records if "COALESCED" in r.getMessage() and "k1" in r.getMessage()
        ]
        assert len(coalesce_logs) >= 1, (
            "Expected at least one WARNING log mentioning COALESCED and row PK 'k1'"
        )
        conn.close()

    def test_unchanged_valid_row_not_marked_coalesced(self):
        """A row with explicit is_active=1 must not appear in coalesced_ids."""
        conn = self._make_weak_db_with_null_is_active()
        conn.execute(
            "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
            "VALUES ('k1', 'hash1', 'test', 'viewer', '2025-01-01T00:00:00Z', 1)"
        )
        conn.commit()

        result = schema_engine.converge(conn)
        rebuilds = result.get("constraint_rebuilds", [])
        api_rebuild = next(r for r in rebuilds if r["table"] == "api_keys")

        assert api_rebuild["rows_coalesced"] == 0, (
            "Explicit is_active=1 must not be marked as coalesced"
        )
        assert api_rebuild["coalesced_ids"] == []
        conn.close()

    def test_mixed_coalesced_and_rejected(self):
        """A rebuild with both NULL-is_active and NULL-key_hash rows classifies each correctly."""
        conn = self._make_weak_db_with_null_is_active()
        # Row 1: valid, is_active=NULL → coalesced
        conn.execute(
            "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
            "VALUES ('coalesced_row', 'hash1', 'test', 'viewer', '2025-01-01T00:00:00Z', NULL)"
        )
        # Row 2: NULL key_hash → rejected
        conn.execute(
            "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
            "VALUES ('rejected_row', NULL, 'test', 'viewer', '2025-01-01T00:00:00Z', 1)"
        )
        # Row 3: fully valid → unchanged
        conn.execute(
            "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
            "VALUES ('valid_row', 'hash2', 'test', 'admin', '2025-01-01T00:00:00Z', 1)"
        )
        conn.commit()

        result = schema_engine.converge(conn)
        rebuilds = result.get("constraint_rebuilds", [])
        api_rebuild = next(r for r in rebuilds if r["table"] == "api_keys")

        assert api_rebuild["rows_before"] == 3
        assert api_rebuild["rows_after"] == 2, "coalesced_row + valid_row survive"
        assert api_rebuild["rows_rejected"] == 1
        assert api_rebuild["rejected_ids"] == ["rejected_row"]
        assert api_rebuild["rows_coalesced"] == 1
        assert api_rebuild["coalesced_ids"] == ["coalesced_row"]
        conn.close()


# ──────────────────────────────────────────────────────────────
# Test 8: CHECK constraint parity proof (D2 fix)
# ──────────────────────────────────────────────────────────────


class TestCheckConstraintParity:
    """Prove CHECK(role) enforcement across all three schema paths.

    The parity profile now includes a behavioral probe for CHECK constraints,
    but these tests make CHECK enforcement explicit and independent.
    """

    def test_fresh_rejects_invalid_role(self):
        """Fresh DB enforces CHECK(role IN (...))."""
        conn = sqlite3.connect(":memory:")
        schema_engine.create_fresh(conn)
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            conn.execute(
                "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
                "VALUES ('k1', 'h1', 'test', 'EVIL', '2025-01-01T00:00:00Z', 1)"
            )
        conn.close()

    def test_converge_created_rejects_invalid_role(self):
        """Converge-created DB enforces CHECK(role IN (...))."""
        conn = sqlite3.connect(":memory:")
        schema_engine.converge(conn)
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            conn.execute(
                "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
                "VALUES ('k1', 'h1', 'test', 'EVIL', '2025-01-01T00:00:00Z', 1)"
            )
        conn.close()

    def test_rebuilt_weak_rejects_invalid_role(self):
        """Rebuilt weak-schema DB enforces CHECK(role IN (...))."""
        conn = sqlite3.connect(":memory:")
        conn.execute("""
            CREATE TABLE api_keys (
                id TEXT PRIMARY KEY,
                key_hash TEXT,
                name TEXT,
                role TEXT,
                created_at TEXT,
                expires_at TEXT,
                last_used_at TEXT,
                is_active INTEGER DEFAULT 1,
                created_by TEXT
            )
        """)
        conn.commit()
        schema_engine.converge(conn)
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            conn.execute(
                "INSERT INTO api_keys (id, key_hash, name, role, created_at, is_active) "
                "VALUES ('k1', 'h1', 'test', 'EVIL', '2025-01-01T00:00:00Z', 1)"
            )
        conn.close()

    def test_parity_profile_includes_check_probe(self):
        """The parity profile's check_rejects_invalid_role field is True for all paths."""
        fresh = sqlite3.connect(":memory:")
        schema_engine.create_fresh(fresh)

        converged = sqlite3.connect(":memory:")
        schema_engine.converge(converged)

        rebuilt = sqlite3.connect(":memory:")
        rebuilt.execute("""
            CREATE TABLE api_keys (
                id TEXT PRIMARY KEY,
                key_hash TEXT,
                name TEXT,
                role TEXT,
                created_at TEXT,
                expires_at TEXT,
                last_used_at TEXT,
                is_active INTEGER DEFAULT 1,
                created_by TEXT
            )
        """)
        schema_engine.converge(rebuilt)

        # Use the same _get_constraint_profile logic from TestFreshConvergeParity
        parity = TestFreshConvergeParity()
        fresh_p = parity._get_constraint_profile(fresh)
        converged_p = parity._get_constraint_profile(converged)
        rebuilt_p = parity._get_constraint_profile(rebuilt)

        assert fresh_p["check_rejects_invalid_role"] is True, "Fresh DB must reject invalid roles"
        assert converged_p["check_rejects_invalid_role"] is True, (
            "Converge-created DB must reject invalid roles"
        )
        assert rebuilt_p["check_rejects_invalid_role"] is True, (
            "Rebuilt weak DB must reject invalid roles"
        )

        # Full profile equality
        assert fresh_p == converged_p, f"Fresh != Converged: {fresh_p} vs {converged_p}"
        assert fresh_p == rebuilt_p, f"Fresh != Rebuilt: {fresh_p} vs {rebuilt_p}"

        fresh.close()
        converged.close()
        rebuilt.close()
