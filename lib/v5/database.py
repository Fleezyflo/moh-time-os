"""
Time OS V5 — Database Module

Provides database connection, transactions, and query helpers.
"""

import os
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from lib import paths

# Default database path
DEFAULT_DB_PATH = os.environ.get("TIME_OS_DB_PATH", str(paths.v5_db_path()))


class Database:
    """Database connection and query manager."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        """
        Initialize database manager.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._connection: sqlite3.Connection | None = None

        # Ensure data directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        """
        Get a database connection.

        Returns a new connection if none exists, or reuses existing one.
        Uses dict row factory for convenient column access.
        """
        if self._connection is None:
            self._connection = sqlite3.connect(self.db_path)
            self._connection.row_factory = self._dict_factory
            # Enable foreign keys
            self._connection.execute("PRAGMA foreign_keys = ON")
            # WAL mode for better concurrency
            self._connection.execute("PRAGMA journal_mode = WAL")
        return self._connection

    @staticmethod
    def _dict_factory(cursor: sqlite3.Cursor, row: tuple) -> dict[str, Any]:
        """Row factory that returns dicts instead of tuples."""
        return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

    def close(self) -> None:
        """Close the database connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager for database transactions.

        Commits on success, rolls back on exception.

        Usage:
            with db.transaction() as conn:
                conn.execute("INSERT INTO ...")
        """
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    @contextmanager
    def cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        """
        Context manager for database cursor.

        Usage:
            with db.cursor() as cur:
                cur.execute("SELECT ...")
                results = cur.fetchall()
        """
        conn = self.get_connection()
        cur = conn.cursor()
        try:
            yield cur
        finally:
            cur.close()

    # =========================================================================
    # Query Helpers
    # =========================================================================

    def execute(self, sql: str, params: tuple | dict | None = None) -> sqlite3.Cursor:
        """
        Execute a SQL statement.

        Args:
            sql: SQL statement
            params: Query parameters (tuple for ?, dict for :name)

        Returns:
            Cursor for the executed query
        """
        conn = self.get_connection()
        if params is None:
            return conn.execute(sql)
        return conn.execute(sql, params)

    def execute_many(self, sql: str, params_list: list[tuple | dict]) -> sqlite3.Cursor:
        """
        Execute a SQL statement for multiple parameter sets.

        Args:
            sql: SQL statement
            params_list: List of parameter tuples/dicts

        Returns:
            Cursor for the executed query
        """
        conn = self.get_connection()
        return conn.executemany(sql, params_list)

    def fetch_one(self, sql: str, params: tuple | dict | None = None) -> dict[str, Any] | None:
        """
        Execute query and return first row as dict.

        Args:
            sql: SQL query
            params: Query parameters

        Returns:
            First row as dict, or None if no results
        """
        cursor = self.execute(sql, params)
        return cursor.fetchone()

    def fetch_all(self, sql: str, params: tuple | dict | None = None) -> list[dict[str, Any]]:
        """
        Execute query and return all rows as list of dicts.

        Args:
            sql: SQL query
            params: Query parameters

        Returns:
            List of rows as dicts
        """
        cursor = self.execute(sql, params)
        return cursor.fetchall()

    def fetch_value(self, sql: str, params: tuple | dict | None = None) -> Any:
        """
        Execute query and return single value from first row.

        Args:
            sql: SQL query
            params: Query parameters

        Returns:
            First column of first row, or None
        """
        row = self.fetch_one(sql, params)
        if row is None:
            return None
        # Get first value from dict
        return next(iter(row.values())) if row else None

    def fetch_column(
        self, sql: str, params: tuple | dict | None = None, column: str = None
    ) -> list[Any]:
        """
        Execute query and return single column as list.

        Args:
            sql: SQL query
            params: Query parameters
            column: Column name to extract (default: first column)

        Returns:
            List of values from the specified column
        """
        rows = self.fetch_all(sql, params)
        if not rows:
            return []

        if column is None:
            column = list(rows[0].keys())[0]

        return [row[column] for row in rows]

    def insert(self, table: str, data: dict[str, Any], or_replace: bool = False) -> str:
        """
        Insert a row and return the ID.

        Args:
            table: Table name
            data: Dict of column names to values
            or_replace: If True, use INSERT OR REPLACE

        Returns:
            ID of inserted row (assumes 'id' column)
        """
        columns = list(data.keys())
        placeholders = ", ".join(["?" for _ in columns])
        column_names = ", ".join(columns)

        verb = "INSERT OR REPLACE" if or_replace else "INSERT"
        sql = f"{verb} INTO {table} ({column_names}) VALUES ({placeholders})"

        with self.transaction() as conn:
            conn.execute(sql, tuple(data.values()))

        return data.get("id")

    def update(
        self,
        table: str,
        data: dict[str, Any],
        where: str,
        where_params: tuple | list = (),
    ) -> int:
        """
        Update rows matching condition.

        Args:
            table: Table name
            data: Dict of column names to new values
            where: WHERE clause (without 'WHERE' keyword)
            where_params: Parameters for WHERE clause

        Returns:
            Number of rows updated
        """
        set_clause = ", ".join([f"{col} = ?" for col in data])
        sql = f"UPDATE {table} SET {set_clause} WHERE {where}"

        params = list(data.values()) + list(where_params)

        with self.transaction() as conn:
            cursor = conn.execute(sql, params)
            return cursor.rowcount

    def delete(self, table: str, where: str, where_params: tuple | list = ()) -> int:
        """
        Delete rows matching condition.

        Args:
            table: Table name
            where: WHERE clause (without 'WHERE' keyword)
            where_params: Parameters for WHERE clause

        Returns:
            Number of rows deleted
        """
        sql = f"DELETE FROM {table} WHERE {where}"

        with self.transaction() as conn:
            cursor = conn.execute(sql, list(where_params))
            return cursor.rowcount

    def exists(self, table: str, where: str, where_params: tuple | list = ()) -> bool:
        """
        Check if any rows match condition.

        Args:
            table: Table name
            where: WHERE clause (without 'WHERE' keyword)
            where_params: Parameters for WHERE clause

        Returns:
            True if at least one row matches
        """
        sql = f"SELECT 1 FROM {table} WHERE {where} LIMIT 1"
        result = self.fetch_one(sql, tuple(where_params))
        return result is not None

    def count(self, table: str, where: str = "1=1", where_params: tuple | list = ()) -> int:
        """
        Count rows matching condition.

        Args:
            table: Table name
            where: WHERE clause (default: all rows)
            where_params: Parameters for WHERE clause

        Returns:
            Number of matching rows
        """
        sql = f"SELECT COUNT(*) as cnt FROM {table} WHERE {where}"
        result = self.fetch_one(sql, tuple(where_params))
        return result["cnt"] if result else 0

    # =========================================================================
    # Batch Operations
    # =========================================================================

    def insert_many(self, table: str, rows: list[dict[str, Any]], or_replace: bool = False) -> int:
        """
        Insert multiple rows efficiently.

        Args:
            table: Table name
            rows: List of dicts with column names to values
            or_replace: If True, use INSERT OR REPLACE

        Returns:
            Number of rows inserted
        """
        if not rows:
            return 0

        columns = list(rows[0].keys())
        placeholders = ", ".join(["?" for _ in columns])
        column_names = ", ".join(columns)

        verb = "INSERT OR REPLACE" if or_replace else "INSERT"
        sql = f"{verb} INTO {table} ({column_names}) VALUES ({placeholders})"

        params_list = [tuple(row[col] for col in columns) for row in rows]

        with self.transaction() as conn:
            conn.executemany(sql, params_list)
            return len(rows)

    # =========================================================================
    # Schema Inspection
    # =========================================================================

    def table_exists(self, table: str) -> bool:
        """Check if a table exists."""
        sql = "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?"
        result = self.fetch_one(sql, (table,))
        return result is not None

    def get_tables(self) -> list[str]:
        """Get list of all tables."""
        sql = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        return self.fetch_column(sql)

    def get_columns(self, table: str) -> list[dict[str, Any]]:
        """Get column info for a table."""
        sql = f"PRAGMA table_info({table})"
        return self.fetch_all(sql)


# Global database instance (can be overridden)
_db: Database | None = None


def get_db(db_path: str = None) -> Database:
    """
    Get the global database instance.

    Args:
        db_path: Optional path to database (only used on first call)

    Returns:
        Database instance
    """
    global _db
    if _db is None:
        _db = Database(db_path or DEFAULT_DB_PATH)
    return _db


def set_db(db: Database) -> None:
    """
    Set the global database instance.

    Args:
        db: Database instance to use globally
    """
    global _db
    _db = db


def close_db() -> None:
    """Close the global database connection."""
    global _db
    if _db is not None:
        _db.close()
        _db = None
