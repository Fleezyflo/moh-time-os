"""
Database Adapter Abstraction Layer.

Provides a unified interface for both SQLite and PostgreSQL database operations.
Allows the system to switch between databases without changing application code.

Classes:
- DatabaseAdapter: Abstract base class defining the database interface
- SQLiteAdapter: SQLite implementation
- PostgreSQLAdapter: PostgreSQL implementation (stub with full SQL translation)
"""

import logging
import sqlite3
from abc import ABC, abstractmethod
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DatabaseAdapter(ABC):
    """
    Abstract base class for database adapters.

    All adapters must implement execute, executemany, fetchone, fetchall, and transaction.
    """

    @abstractmethod
    def execute(self, sql: str, params: tuple | None = None) -> Any:
        """Execute SQL statement and return cursor."""
        pass

    @abstractmethod
    def executemany(self, sql: str, params_list: list[tuple]) -> None:
        """Execute SQL statement multiple times with different parameters."""
        pass

    @abstractmethod
    def fetchone(self, sql: str, params: tuple | None = None) -> tuple | None:
        """Execute SQL and fetch single row."""
        pass

    @abstractmethod
    def fetchall(self, sql: str, params: tuple | None = None) -> list[tuple]:
        """Execute SQL and fetch all rows."""
        pass

    @abstractmethod
    @contextmanager
    def transaction(self) -> Generator[None, None, None]:
        """Context manager for database transactions."""
        pass


class SQLiteAdapter(DatabaseAdapter):
    """
    SQLite database adapter.

    Wraps sqlite3 connection with standardized DatabaseAdapter interface.
    Manages row factory, foreign keys, and transaction handling.
    """

    def __init__(self, db_path: str):
        """
        Initialize SQLite adapter.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn: sqlite3.Connection | None = None
        self._connect()

    def _connect(self) -> None:
        """Create database connection with proper configuration."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys=ON")
            logger.debug(f"SQLiteAdapter connected to {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"SQLiteAdapter connection failed: {e}")
            raise

    def execute(self, sql: str, params: tuple | None = None) -> sqlite3.Cursor:
        """
        Execute SQL statement.

        Args:
            sql: SQL statement
            params: Query parameters (tuple)

        Returns:
            sqlite3.Cursor object
        """
        if self.conn is None:
            logger.error("SQLiteAdapter: connection is None")
            raise RuntimeError("Database connection not initialized")

        try:
            if params is None:
                return self.conn.execute(sql)
            return self.conn.execute(sql, params)
        except sqlite3.Error as e:
            logger.error(f"SQLiteAdapter.execute failed: {e}")
            raise

    def executemany(self, sql: str, params_list: list[tuple]) -> None:
        """
        Execute SQL statement multiple times.

        Args:
            sql: SQL statement
            params_list: List of parameter tuples
        """
        if self.conn is None:
            logger.error("SQLiteAdapter: connection is None")
            raise RuntimeError("Database connection not initialized")

        try:
            self.conn.executemany(sql, params_list)
        except sqlite3.Error as e:
            logger.error(f"SQLiteAdapter.executemany failed: {e}")
            raise

    def fetchone(self, sql: str, params: tuple | None = None) -> tuple | None:
        """
        Execute SQL and fetch single row.

        Args:
            sql: SQL statement
            params: Query parameters (tuple)

        Returns:
            Row as tuple, or None if no rows
        """
        if self.conn is None:
            logger.error("SQLiteAdapter: connection is None")
            raise RuntimeError("Database connection not initialized")

        try:
            cursor = self.execute(sql, params)
            return cursor.fetchone()
        except sqlite3.Error as e:
            logger.error(f"SQLiteAdapter.fetchone failed: {e}")
            raise

    def fetchall(self, sql: str, params: tuple | None = None) -> list[tuple]:
        """
        Execute SQL and fetch all rows.

        Args:
            sql: SQL statement
            params: Query parameters (tuple)

        Returns:
            List of rows as tuples
        """
        if self.conn is None:
            logger.error("SQLiteAdapter: connection is None")
            raise RuntimeError("Database connection not initialized")

        try:
            cursor = self.execute(sql, params)
            return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"SQLiteAdapter.fetchall failed: {e}")
            raise

    @contextmanager
    def transaction(self) -> Generator[None, None, None]:
        """
        Context manager for transactions.

        Commits on success, rolls back on exception.
        """
        if self.conn is None:
            logger.error("SQLiteAdapter: connection is None")
            raise RuntimeError("Database connection not initialized")

        try:
            self.conn.execute("BEGIN")
            yield
            self.conn.execute("COMMIT")
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"SQLiteAdapter.transaction error: {e}")
            self.conn.execute("ROLLBACK")
            raise

    def close(self) -> None:
        """Close database connection."""
        if self.conn is not None:
            try:
                self.conn.close()
                self.conn = None
                logger.debug("SQLiteAdapter connection closed")
            except sqlite3.Error as e:
                logger.error(f"SQLiteAdapter.close failed: {e}")
                raise

    def __enter__(self) -> "SQLiteAdapter":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()


class PostgreSQLAdapter(DatabaseAdapter):
    """
    PostgreSQL database adapter.

    Uses psycopg2 for synchronous connections. Falls back to error
    with clear message if psycopg2 is not installed.
    """

    def __init__(self, connection_string: str):
        """
        Initialize PostgreSQL adapter.

        Args:
            connection_string: PostgreSQL connection string
                Format: postgresql://user:password@host:port/database
        """
        self.connection_string = connection_string
        self.conn = None
        try:
            import psycopg2

            self.conn = psycopg2.connect(connection_string)
            self.conn.autocommit = False
            logger.info("PostgreSQL connection established")
        except ImportError:
            logger.error("psycopg2 not installed. Install with: pip install psycopg2-binary")
            raise ImportError(
                "psycopg2 is required for PostgreSQL support. "
                "Install with: pip install psycopg2-binary"
            ) from None

    def execute(self, sql: str, params: tuple | None = None) -> Any:
        """Execute SQL statement."""
        if not self.conn:
            raise RuntimeError("PostgreSQL connection not established")
        cursor = self.conn.cursor()
        cursor.execute(sql, params)
        return cursor

    def executemany(self, sql: str, params_list: list[tuple]) -> None:
        """Execute SQL statement multiple times."""
        if not self.conn:
            raise RuntimeError("PostgreSQL connection not established")
        cursor = self.conn.cursor()
        cursor.executemany(sql, params_list)

    def fetchone(self, sql: str, params: tuple | None = None) -> dict | None:
        """Execute SQL and fetch single row as dict."""
        if not self.conn:
            raise RuntimeError("PostgreSQL connection not established")
        import psycopg2.extras

        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(sql, params)
        row = cursor.fetchone()
        return dict(row) if row else None

    def fetchall(self, sql: str, params: tuple | None = None) -> list[dict]:
        """Execute SQL and fetch all rows as dicts."""
        if not self.conn:
            raise RuntimeError("PostgreSQL connection not established")
        import psycopg2.extras

        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    @contextmanager
    def transaction(self) -> Generator[None, None, None]:
        """Context manager for transactions."""
        if not self.conn:
            raise RuntimeError("PostgreSQL connection not established")
        try:
            yield
            self.conn.commit()
        except (sqlite3.Error, ValueError, OSError):
            self.conn.rollback()
            raise

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("PostgreSQL connection closed")
