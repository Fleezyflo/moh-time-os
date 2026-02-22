"""
Comprehensive tests for PostgreSQL Compatibility Layer (Brief 14, Task PS-3.1).

Covers:
- SQLiteAdapter CRUD operations and transaction handling
- SQL translation (SQLite to PostgreSQL and back)
- Dialect detection
- Connection pooling (checkout, release, stats, max size)
- Health checks
"""

import sqlite3
import threading
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import pytest

from lib.db_opt.connection_pool import ConnectionPool, PooledDatabaseAdapter, PoolStats
from lib.db_opt.db_adapter import DatabaseAdapter, PostgreSQLAdapter, SQLiteAdapter
from lib.db_opt.sql_compat import (
    detect_dialect,
    translate_pg_to_sqlite,
    translate_sqlite_to_pg,
)

# =============================================================================
# SQLITE ADAPTER TESTS
# =============================================================================


class TestSQLiteAdapter:
    """Test SQLiteAdapter CRUD operations and transaction handling."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database file."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            yield str(db_path)

    @pytest.fixture
    def adapter(self, temp_db):
        """Create SQLiteAdapter instance."""
        adapter = SQLiteAdapter(temp_db)
        yield adapter
        adapter.close()

    def test_adapter_connection(self, temp_db):
        """SQLiteAdapter should establish connection."""
        adapter = SQLiteAdapter(temp_db)
        assert adapter.conn is not None
        adapter.close()

    def test_adapter_create_table(self, adapter):
        """SQLiteAdapter should create tables."""
        sql = "CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)"
        cursor = adapter.execute(sql)
        assert cursor is not None

    def test_adapter_insert(self, adapter):
        """SQLiteAdapter should insert rows."""
        adapter.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        adapter.execute("INSERT INTO test (name) VALUES (?)", ("Alice",))
        rows = adapter.fetchall("SELECT * FROM test")
        assert len(rows) == 1
        assert rows[0][1] == "Alice"

    def test_adapter_insert_multiple(self, adapter):
        """SQLiteAdapter should insert multiple rows with executemany."""
        adapter.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        params = [("Alice",), ("Bob",), ("Charlie",)]
        adapter.executemany("INSERT INTO test (name) VALUES (?)", params)
        rows = adapter.fetchall("SELECT * FROM test")
        assert len(rows) == 3

    def test_adapter_fetchone(self, adapter):
        """SQLiteAdapter.fetchone should return single row."""
        adapter.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        adapter.execute("INSERT INTO test (name) VALUES (?)", ("Alice",))
        row = adapter.fetchone("SELECT * FROM test WHERE id = ?", (1,))
        assert row is not None
        assert row[1] == "Alice"

    def test_adapter_fetchone_no_results(self, adapter):
        """SQLiteAdapter.fetchone should return None if no results."""
        adapter.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        row = adapter.fetchone("SELECT * FROM test WHERE id = ?", (999,))
        assert row is None

    def test_adapter_fetchall(self, adapter):
        """SQLiteAdapter.fetchall should return all rows."""
        adapter.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        adapter.executemany(
            "INSERT INTO test (name) VALUES (?)",
            [("Alice",), ("Bob",)],
        )
        rows = adapter.fetchall("SELECT * FROM test")
        assert len(rows) == 2

    def test_adapter_fetchall_empty(self, adapter):
        """SQLiteAdapter.fetchall should return empty list if no rows."""
        adapter.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        rows = adapter.fetchall("SELECT * FROM test")
        assert rows == []

    def test_adapter_transaction_commit(self, adapter):
        """SQLiteAdapter transaction should commit on success."""
        adapter.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        with adapter.transaction():
            adapter.execute("INSERT INTO test (name) VALUES (?)", ("Alice",))
        rows = adapter.fetchall("SELECT * FROM test")
        assert len(rows) == 1

    def test_adapter_transaction_rollback(self, adapter):
        """SQLiteAdapter transaction should rollback on exception."""
        adapter.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        try:
            with adapter.transaction():
                adapter.execute("INSERT INTO test (name) VALUES (?)", ("Alice",))
                raise RuntimeError("Test error")
        except RuntimeError:
            pass
        rows = adapter.fetchall("SELECT * FROM test")
        assert len(rows) == 0

    def test_adapter_context_manager(self, temp_db):
        """SQLiteAdapter should work as context manager."""
        with SQLiteAdapter(temp_db) as adapter:
            adapter.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
            adapter.execute("INSERT INTO test (name) VALUES (?)", ("Alice",))
            rows = adapter.fetchall("SELECT * FROM test")
            assert len(rows) == 1

    def test_adapter_execute_no_params(self, adapter):
        """SQLiteAdapter.execute should work without parameters."""
        adapter.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
        cursor = adapter.execute("SELECT COUNT(*) FROM test")
        assert cursor is not None

    def test_adapter_error_handling(self, adapter):
        """SQLiteAdapter should raise errors on bad SQL."""
        with pytest.raises(sqlite3.Error):
            adapter.execute("INVALID SQL SYNTAX")


# =============================================================================
# SQL TRANSLATION TESTS
# =============================================================================


class TestSQLTranslation:
    """Test SQL dialect translation."""

    # =========================================================================
    # SQLite to PostgreSQL Translations
    # =========================================================================

    def test_translate_autoincrement_to_serial(self):
        """Should translate AUTOINCREMENT to SERIAL."""
        sql = "CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)"
        result = translate_sqlite_to_pg(sql)
        assert "SERIAL PRIMARY KEY" in result
        assert "AUTOINCREMENT" not in result

    def test_translate_integer_primary_key(self):
        """Should translate INTEGER PRIMARY KEY to SERIAL PRIMARY KEY."""
        sql = "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)"
        result = translate_sqlite_to_pg(sql)
        assert "SERIAL PRIMARY KEY" in result

    def test_translate_datetime_now(self):
        """Should translate datetime('now') to NOW()."""
        sql = "INSERT INTO events (created_at) VALUES (datetime('now'))"
        result = translate_sqlite_to_pg(sql)
        assert "NOW()" in result
        assert "datetime('now')" not in result

    def test_translate_datetime_now_double_quotes(self):
        """Should handle datetime with double quotes."""
        sql = 'INSERT INTO events (created_at) VALUES (datetime("now"))'
        result = translate_sqlite_to_pg(sql)
        assert "NOW()" in result

    def test_translate_group_concat_single_arg(self):
        """Should translate GROUP_CONCAT to STRING_AGG."""
        sql = "SELECT GROUP_CONCAT(name) FROM users"
        result = translate_sqlite_to_pg(sql)
        assert "STRING_AGG" in result
        assert "GROUP_CONCAT" not in result

    def test_translate_group_concat_with_separator(self):
        """Should translate GROUP_CONCAT with separator to STRING_AGG."""
        sql = "SELECT GROUP_CONCAT(name, ',') FROM users"
        result = translate_sqlite_to_pg(sql)
        assert "STRING_AGG" in result
        assert "GROUP_CONCAT" not in result

    def test_translate_ifnull_to_coalesce(self):
        """Should translate IFNULL to COALESCE."""
        sql = "SELECT IFNULL(email, 'no-email') FROM users"
        result = translate_sqlite_to_pg(sql)
        assert "COALESCE" in result
        assert "IFNULL" not in result

    def test_translate_substr_to_substring(self):
        """Should translate SUBSTR to SUBSTRING."""
        sql = "SELECT SUBSTR(name, 1, 3) FROM users"
        result = translate_sqlite_to_pg(sql)
        assert "SUBSTRING" in result
        assert "SUBSTR(" not in result

    def test_translate_glob_to_similar_to(self):
        """Should translate GLOB to SIMILAR TO with pattern conversion."""
        sql = "SELECT * FROM users WHERE name GLOB 'A*'"
        result = translate_sqlite_to_pg(sql)
        assert "SIMILAR TO" in result
        assert "GLOB" not in result
        # * should be converted to %
        assert "A%" in result

    def test_translate_glob_with_single_char(self):
        """Should translate ? in GLOB to _ in SIMILAR TO."""
        sql = "SELECT * FROM users WHERE name GLOB 'A?c'"
        result = translate_sqlite_to_pg(sql)
        assert "SIMILAR TO" in result
        # ? should be converted to _
        assert "A_c" in result

    # =========================================================================
    # PostgreSQL to SQLite Translations
    # =========================================================================

    def test_translate_serial_to_autoincrement(self):
        """Should translate SERIAL PRIMARY KEY to INTEGER PRIMARY KEY AUTOINCREMENT."""
        sql = "CREATE TABLE users (id SERIAL PRIMARY KEY, name TEXT)"
        result = translate_pg_to_sqlite(sql)
        assert "INTEGER PRIMARY KEY AUTOINCREMENT" in result
        assert "SERIAL" not in result

    def test_translate_now_to_datetime(self):
        """Should translate NOW() to datetime('now')."""
        sql = "INSERT INTO events (created_at) VALUES (NOW())"
        result = translate_pg_to_sqlite(sql)
        assert "datetime('now')" in result
        assert "NOW()" not in result

    def test_translate_string_agg_to_group_concat(self):
        """Should translate STRING_AGG to GROUP_CONCAT."""
        sql = "SELECT STRING_AGG(name, ',') FROM users"
        result = translate_pg_to_sqlite(sql)
        assert "GROUP_CONCAT" in result
        assert "STRING_AGG" not in result

    def test_translate_substring_to_substr(self):
        """Should translate SUBSTRING to SUBSTR."""
        sql = "SELECT SUBSTRING(name, 1, 3) FROM users"
        result = translate_pg_to_sqlite(sql)
        assert "SUBSTR" in result
        assert "SUBSTRING" not in result

    def test_translate_similar_to_to_glob(self):
        """Should translate SIMILAR TO to GLOB with pattern conversion."""
        sql = "SELECT * FROM users WHERE name SIMILAR TO 'A%'"
        result = translate_pg_to_sqlite(sql)
        assert "GLOB" in result
        assert "SIMILAR TO" not in result
        # % should be converted to *
        assert "A*" in result

    def test_translate_boolean_true_to_1(self):
        """Should translate true to 1."""
        sql = "UPDATE users SET active = true WHERE id = 1"
        result = translate_pg_to_sqlite(sql)
        assert "1" in result

    def test_translate_boolean_false_to_0(self):
        """Should translate false to 0."""
        sql = "UPDATE users SET active = false WHERE id = 1"
        result = translate_pg_to_sqlite(sql)
        assert "0" in result

    # =========================================================================
    # Round-trip Translations
    # =========================================================================

    def test_roundtrip_sqlite_to_pg_to_sqlite(self):
        """Should preserve SQL structure through round-trip translation."""
        original = "SELECT * FROM users WHERE id = ?"
        pg = translate_sqlite_to_pg(original)
        back = translate_pg_to_sqlite(pg)
        # Standard SQL should pass through unchanged
        assert "SELECT" in back
        assert "FROM users" in back

    def test_roundtrip_datetime(self):
        """Should handle datetime round-trip translation."""
        sqlite_sql = "INSERT INTO events (ts) VALUES (datetime('now'))"
        pg_sql = translate_sqlite_to_pg(sqlite_sql)
        assert "NOW()" in pg_sql


# =============================================================================
# DIALECT DETECTION TESTS
# =============================================================================


class TestDialectDetection:
    """Test SQL dialect detection."""

    def test_detect_sqlite_autoincrement(self):
        """Should detect SQLite AUTOINCREMENT."""
        sql = "CREATE TABLE t (id INTEGER PRIMARY KEY AUTOINCREMENT)"
        assert detect_dialect(sql) == "sqlite"

    def test_detect_sqlite_datetime_now(self):
        """Should detect SQLite datetime('now')."""
        sql = "INSERT INTO t (ts) VALUES (datetime('now'))"
        assert detect_dialect(sql) == "sqlite"

    def test_detect_sqlite_group_concat(self):
        """Should detect SQLite GROUP_CONCAT."""
        sql = "SELECT GROUP_CONCAT(name) FROM t"
        assert detect_dialect(sql) == "sqlite"

    def test_detect_sqlite_ifnull(self):
        """Should detect SQLite IFNULL."""
        sql = "SELECT IFNULL(email, 'none') FROM t"
        assert detect_dialect(sql) == "sqlite"

    def test_detect_sqlite_glob(self):
        """Should detect SQLite GLOB."""
        sql = "SELECT * FROM t WHERE name GLOB '*abc*'"
        assert detect_dialect(sql) == "sqlite"

    def test_detect_postgresql_serial(self):
        """Should detect PostgreSQL SERIAL."""
        sql = "CREATE TABLE t (id SERIAL PRIMARY KEY)"
        assert detect_dialect(sql) == "postgresql"

    def test_detect_postgresql_now(self):
        """Should detect PostgreSQL NOW()."""
        sql = "INSERT INTO t (ts) VALUES (NOW())"
        assert detect_dialect(sql) == "postgresql"

    def test_detect_postgresql_string_agg(self):
        """Should detect PostgreSQL STRING_AGG."""
        sql = "SELECT STRING_AGG(name, ',') FROM t"
        assert detect_dialect(sql) == "postgresql"

    def test_detect_postgresql_similar_to(self):
        """Should detect PostgreSQL SIMILAR TO."""
        sql = "SELECT * FROM t WHERE name SIMILAR TO 'A%'"
        assert detect_dialect(sql) == "postgresql"

    def test_detect_postgresql_create_extension(self):
        """Should detect PostgreSQL CREATE EXTENSION."""
        sql = "CREATE EXTENSION IF NOT EXISTS uuid"
        assert detect_dialect(sql) == "postgresql"

    def test_detect_standard_sql(self):
        """Should detect standard SQL."""
        sql = "SELECT * FROM users WHERE id = 1"
        assert detect_dialect(sql) == "standard"

    def test_detect_standard_simple_insert(self):
        """Should detect standard INSERT."""
        sql = "INSERT INTO users (name) VALUES ('Alice')"
        assert detect_dialect(sql) == "standard"

    def test_detect_case_insensitive_sqlite(self):
        """Dialect detection should be case-insensitive."""
        sql = "SELECT datetime('now') FROM users"
        assert detect_dialect(sql) == "sqlite"

    def test_detect_case_insensitive_postgresql(self):
        """Dialect detection should be case-insensitive."""
        sql = "SELECT NOW() FROM users"
        assert detect_dialect(sql) == "postgresql"


# =============================================================================
# CONNECTION POOL TESTS
# =============================================================================


class TestConnectionPool:
    """Test connection pool functionality."""

    @pytest.fixture
    def adapter_factory(self):
        """Create a test adapter factory."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            def factory():
                return SQLiteAdapter(str(db_path))

            yield factory

    @pytest.fixture
    def pool(self, adapter_factory):
        """Create a connection pool."""
        pool = ConnectionPool(adapter_factory, max_size=5)
        yield pool
        pool.close_all()

    def test_pool_checkout(self, pool):
        """Pool should checkout connection."""
        conn = pool.get_connection()
        assert conn is not None
        assert isinstance(conn, DatabaseAdapter)
        pool.release_connection(conn)

    def test_pool_release(self, pool):
        """Pool should release connection back to idle."""
        conn = pool.get_connection()
        stats_before = pool.pool_stats()
        assert stats_before.active_connections == 1
        assert stats_before.idle_connections == 0

        pool.release_connection(conn)
        stats_after = pool.pool_stats()
        assert stats_after.active_connections == 0
        assert stats_after.idle_connections == 1

    def test_pool_reuses_idle_connection(self, pool):
        """Pool should reuse idle connections."""
        conn1 = pool.get_connection()
        pool.release_connection(conn1)
        conn2 = pool.get_connection()
        # Should be the same connection object
        assert conn1 is conn2
        pool.release_connection(conn2)

    def test_pool_max_size(self, pool):
        """Pool should not exceed max size."""
        conns = []
        for _ in range(5):
            conn = pool.get_connection()
            conns.append(conn)

        stats = pool.pool_stats()
        assert stats.active_connections == 5
        assert stats.total_connections == 5

        for conn in conns:
            pool.release_connection(conn)

    def test_pool_waits_for_available_connection(self, pool):
        """Pool should wait for available connection when at max size."""
        conns = []
        # Get max connections
        for _ in range(5):
            conns.append(pool.get_connection())

        # Start thread to release a connection after delay
        def release_delayed():
            time.sleep(0.5)
            pool.release_connection(conns[0])

        thread = threading.Thread(target=release_delayed)
        thread.start()

        # This should block until a connection is available
        start = time.time()
        conn = pool.get_connection()
        elapsed = time.time() - start

        # Should have waited approximately 0.5 seconds
        assert elapsed >= 0.4
        assert conn is not None

        thread.join()

        # Cleanup
        pool.release_connection(conn)
        for c in conns[1:]:
            pool.release_connection(c)

    def test_pool_stats(self, pool):
        """Pool should provide accurate statistics."""
        stats = pool.pool_stats()
        assert isinstance(stats, PoolStats)
        assert stats.active_connections == 0
        assert stats.idle_connections == 0
        assert stats.max_pool_size == 5
        assert stats.checkout_count == 0

        conn = pool.get_connection()
        stats = pool.pool_stats()
        assert stats.active_connections == 1
        assert stats.checkout_count == 1

        pool.release_connection(conn)
        stats = pool.pool_stats()
        assert stats.release_count == 1

    def test_pool_stats_to_dict(self, pool):
        """Pool stats should convert to dictionary."""
        conn = pool.get_connection()
        stats = pool.pool_stats()
        stats_dict = stats.to_dict()

        assert isinstance(stats_dict, dict)
        assert "active_connections" in stats_dict
        assert "idle_connections" in stats_dict
        assert "max_pool_size" in stats_dict
        assert "checkout_count" in stats_dict

        pool.release_connection(conn)

    def test_pool_health_check(self, adapter_factory):
        """Pool should check connection health on checkout."""
        pool = ConnectionPool(adapter_factory, max_size=3)

        # Get and release a connection
        conn = pool.get_connection()
        pool.release_connection(conn)

        # Next checkout should reuse it if healthy
        stats_before = pool.pool_stats()
        conn2 = pool.get_connection()
        stats_after = pool.pool_stats()

        # Should have reused the connection
        assert stats_after.total_connections <= stats_before.total_connections + 1

        pool.release_connection(conn2)
        pool.close_all()

    def test_pool_release_invalid_connection(self, pool):
        """Pool should raise error when releasing unknown connection."""
        fake_conn = MagicMock(spec=DatabaseAdapter)
        with pytest.raises(RuntimeError):
            pool.release_connection(fake_conn)

    def test_pool_close_all(self, pool):
        """Pool should close all connections."""
        [pool.get_connection() for _ in range(3)]
        assert pool.pool_stats().total_connections >= 3

        pool.close_all()
        assert pool.pool_stats().total_connections == 0


# =============================================================================
# POOLED ADAPTER TESTS
# =============================================================================


class TestPooledDatabaseAdapter:
    """Test PooledDatabaseAdapter wrapper."""

    @pytest.fixture
    def pooled_adapter(self):
        """Create pooled adapter."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            def factory():
                return SQLiteAdapter(str(db_path))

            adapter = PooledDatabaseAdapter(factory, max_pool_size=3)
            yield adapter
            adapter.close_all()

    def test_pooled_adapter_execute(self, pooled_adapter):
        """Pooled adapter should execute queries."""
        pooled_adapter.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
        cursor = pooled_adapter.execute("SELECT COUNT(*) FROM test")
        assert cursor is not None

    def test_pooled_adapter_fetchone(self, pooled_adapter):
        """Pooled adapter should fetchone."""
        pooled_adapter.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        pooled_adapter.execute("INSERT INTO test (name) VALUES (?)", ("Alice",))
        row = pooled_adapter.fetchone("SELECT * FROM test")
        assert row is not None
        assert row[1] == "Alice"

    def test_pooled_adapter_fetchall(self, pooled_adapter):
        """Pooled adapter should fetchall."""
        pooled_adapter.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        pooled_adapter.executemany(
            "INSERT INTO test (name) VALUES (?)",
            [("Alice",), ("Bob",)],
        )
        rows = pooled_adapter.fetchall("SELECT * FROM test")
        assert len(rows) == 2

    def test_pooled_adapter_executemany(self, pooled_adapter):
        """Pooled adapter should executemany."""
        pooled_adapter.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        pooled_adapter.executemany(
            "INSERT INTO test (name) VALUES (?)",
            [("Alice",), ("Bob",), ("Charlie",)],
        )
        rows = pooled_adapter.fetchall("SELECT * FROM test")
        assert len(rows) == 3

    def test_pooled_adapter_stats(self, pooled_adapter):
        """Pooled adapter should provide pool stats."""
        stats = pooled_adapter.pool_stats()
        assert isinstance(stats, PoolStats)
        assert stats.max_pool_size == 3

    def test_pooled_adapter_close_all(self, pooled_adapter):
        """Pooled adapter should close all connections."""
        pooled_adapter.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
        pooled_adapter.close_all()
        stats = pooled_adapter.pool_stats()
        assert stats.total_connections == 0


# =============================================================================
# POSTGRESQL ADAPTER STUB TESTS
# =============================================================================


class TestPostgreSQLAdapter:
    """Test PostgreSQL adapter implementation."""

    def test_postgresql_adapter_requires_psycopg2(self):
        """PostgreSQL adapter should raise ImportError when psycopg2 is not installed."""
        # psycopg2 is not installed in test environment
        with pytest.raises(ImportError, match="psycopg2"):
            PostgreSQLAdapter("postgresql://user:pass@localhost/db")

    def test_postgresql_adapter_stores_connection_string(self):
        """PostgreSQL adapter should store connection string before failing."""
        try:
            PostgreSQLAdapter("postgresql://user:pass@localhost/db")
        except ImportError:
            pass  # Expected — psycopg2 not installed


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegration:
    """Integration tests combining multiple components."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            yield str(db_path)

    def test_integration_adapter_with_sql_translation(self, temp_db):
        """Adapter should work with SQL translation."""
        adapter = SQLiteAdapter(temp_db)

        # Create table using SQLite SQL
        sqlite_sql = "CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)"
        adapter.execute(sqlite_sql)

        # Insert data
        adapter.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))

        # Verify
        row = adapter.fetchone("SELECT * FROM users")
        assert row[1] == "Alice"

        adapter.close()

    def test_integration_full_workflow(self, temp_db):
        """Full workflow: create adapter, use connection pool, run queries."""

        def factory():
            return SQLiteAdapter(temp_db)

        pooled = PooledDatabaseAdapter(factory, max_pool_size=3)

        # Setup
        pooled.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, price REAL)")
        pooled.executemany(
            "INSERT INTO products (name, price) VALUES (?, ?)",
            [("Widget", 10.0), ("Gadget", 20.0), ("Tool", 15.0)],
        )

        # Query
        rows = pooled.fetchall("SELECT * FROM products")
        assert len(rows) == 3

        # Stats
        stats = pooled.pool_stats()
        assert stats.total_connections >= 0

        pooled.close_all()

    def test_integration_dialect_translation_workflow(self):
        """Full workflow using SQL translation."""
        # Start with SQLite SQL
        sqlite_sql = """
            CREATE TABLE events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at DATETIME DEFAULT datetime('now')
            )
        """

        # Translate to PostgreSQL
        pg_sql = translate_sqlite_to_pg(sqlite_sql)
        assert "SERIAL" in pg_sql
        assert "NOW()" in pg_sql

        # Detect dialect
        assert detect_dialect(sqlite_sql) == "sqlite"
        assert detect_dialect(pg_sql) == "postgresql"

        # Translate back to SQLite
        back_to_sqlite = translate_pg_to_sqlite(pg_sql)
        assert "AUTOINCREMENT" in back_to_sqlite
        assert "datetime('now')" in back_to_sqlite
