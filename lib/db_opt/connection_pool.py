"""
Connection Pooling for Database Adapters.

Provides thread-safe connection pooling for SQLite and PostgreSQL.

Features:
- Configurable pool size (default 10)
- Connection health checks on checkout
- Pool statistics tracking
- Thread-safe operations with Lock
- For SQLite: manages concurrent reader connections
- Automatic connection recycling

Classes:
- PoolStats: Statistics for pool health
- ConnectionPool: Thread-safe connection pool manager
"""

import logging
import sqlite3
import threading
import time
from dataclasses import dataclass
from typing import Optional

from lib.db_opt.db_adapter import DatabaseAdapter, SQLiteAdapter

logger = logging.getLogger(__name__)


@dataclass
class PoolStats:
    """Statistics for connection pool health."""

    active_connections: int
    idle_connections: int
    total_connections: int
    max_pool_size: int
    wait_time_ms: float = 0.0
    checkout_count: int = 0
    release_count: int = 0

    def to_dict(self) -> dict:
        """Convert stats to dictionary."""
        return {
            "active_connections": self.active_connections,
            "idle_connections": self.idle_connections,
            "total_connections": self.total_connections,
            "max_pool_size": self.max_pool_size,
            "wait_time_ms": round(self.wait_time_ms, 2),
            "checkout_count": self.checkout_count,
            "release_count": self.release_count,
        }


class ConnectionPool:
    """
    Thread-safe connection pool manager.

    Manages a pool of database connections, handling checkout/release,
    health checks, and statistics.
    """

    def __init__(
        self,
        adapter_factory,
        max_size: int = 10,
        health_check_timeout: float = 5.0,
    ):
        """
        Initialize connection pool.

        Args:
            adapter_factory: Callable that returns DatabaseAdapter instance
            max_size: Maximum number of connections in pool (default 10)
            health_check_timeout: Timeout for health checks in seconds
        """
        self.adapter_factory = adapter_factory
        self.max_size = max_size
        self.health_check_timeout = health_check_timeout

        self._lock = threading.Lock()
        self._idle: list[DatabaseAdapter] = []
        self._active: set[DatabaseAdapter] = set()

        self.checkout_count = 0
        self.release_count = 0
        self.total_wait_time_ms = 0.0

    def get_connection(self) -> DatabaseAdapter:
        """
        Get a connection from the pool.

        Returns an idle connection if available, creates a new one if under max_size,
        or waits for one to be released.

        Raises:
            RuntimeError: If connection cannot be obtained

        Returns:
            DatabaseAdapter instance
        """
        start_time = time.time()
        max_wait = 30.0  # 30 second maximum wait

        with self._lock:
            # Try to get an idle connection
            while len(self._idle) == 0 and len(self._active) >= self.max_size:
                # Release lock and wait for a connection
                self._lock.release()
                time.sleep(0.1)

                # Check if we've exceeded max wait
                elapsed = time.time() - start_time
                if elapsed > max_wait:
                    logger.error(
                        f"ConnectionPool.get_connection: exceeded max wait time ({max_wait}s)"
                    )
                    raise RuntimeError(f"Could not obtain connection within {max_wait}s")

                self._lock.acquire()

            # Get idle connection or create new one
            if self._idle:
                conn = self._idle.pop()
                # Health check
                if not self._is_healthy(conn):
                    logger.warning("ConnectionPool: unhealthy connection discarded")
                    conn = self.adapter_factory()
            else:
                conn = self.adapter_factory()

            self._active.add(conn)
            self.checkout_count += 1

            # Record wait time
            wait_time = (time.time() - start_time) * 1000
            self.total_wait_time_ms += wait_time

            logger.debug(
                f"ConnectionPool: checked out connection "
                f"(active={len(self._active)}, idle={len(self._idle)})"
            )

            return conn

    def release_connection(self, conn: DatabaseAdapter) -> None:
        """
        Return a connection to the pool.

        Args:
            conn: DatabaseAdapter instance to return

        Raises:
            RuntimeError: If connection not in active set
        """
        with self._lock:
            if conn not in self._active:
                logger.error("ConnectionPool.release_connection: connection not in active set")
                raise RuntimeError("Connection not in active pool")

            self._active.remove(conn)

            # Health check before returning to idle
            if self._is_healthy(conn):
                self._idle.append(conn)
            else:
                logger.warning("ConnectionPool: unhealthy connection not returned to pool")
                self._close_connection(conn)

            self.release_count += 1

            logger.debug(
                f"ConnectionPool: released connection "
                f"(active={len(self._active)}, idle={len(self._idle)})"
            )

    def pool_stats(self) -> PoolStats:
        """
        Get current pool statistics.

        Returns:
            PoolStats with current pool health metrics
        """
        with self._lock:
            avg_wait = (
                self.total_wait_time_ms / self.checkout_count if self.checkout_count > 0 else 0.0
            )

            return PoolStats(
                active_connections=len(self._active),
                idle_connections=len(self._idle),
                total_connections=len(self._active) + len(self._idle),
                max_pool_size=self.max_size,
                wait_time_ms=avg_wait,
                checkout_count=self.checkout_count,
                release_count=self.release_count,
            )

    def close_all(self) -> None:
        """Close all connections in the pool."""
        with self._lock:
            for conn in self._active:
                self._close_connection(conn)
            for conn in self._idle:
                self._close_connection(conn)

            self._active.clear()
            self._idle.clear()

            logger.debug("ConnectionPool: all connections closed")

    def _is_healthy(self, conn: DatabaseAdapter) -> bool:
        """
        Check if connection is healthy.

        For SQLiteAdapter, runs a simple query.

        Args:
            conn: DatabaseAdapter to check

        Returns:
            True if healthy, False otherwise
        """
        if isinstance(conn, SQLiteAdapter):
            try:
                # Simple health check: execute a no-op query
                conn.execute("SELECT 1")
                return True
            except Exception as e:
                logger.warning(f"ConnectionPool: health check failed: {e}")
                return False

        # Default: assume healthy
        return True

    def _close_connection(self, conn: DatabaseAdapter) -> None:
        """
        Close a connection.

        Args:
            conn: DatabaseAdapter to close
        """
        try:
            if isinstance(conn, SQLiteAdapter):
                conn.close()
            logger.debug("ConnectionPool: connection closed")
        except Exception as e:
            logger.error(f"ConnectionPool: error closing connection: {e}")


class PooledDatabaseAdapter:
    """
    Wrapper around DatabaseAdapter that uses connection pooling.

    Provides the same interface as DatabaseAdapter but with pooling benefits.
    """

    def __init__(
        self,
        adapter_factory,
        max_pool_size: int = 10,
    ):
        """
        Initialize pooled adapter.

        Args:
            adapter_factory: Callable that returns DatabaseAdapter
            max_pool_size: Maximum pool size
        """
        self.pool = ConnectionPool(adapter_factory, max_size=max_pool_size)

    def execute(self, sql: str, params=None):
        """Execute SQL using pooled connection."""
        conn = self.pool.get_connection()
        try:
            return conn.execute(sql, params)
        finally:
            self.pool.release_connection(conn)

    def executemany(self, sql: str, params_list):
        """Execute SQL many times using pooled connection."""
        conn = self.pool.get_connection()
        try:
            conn.executemany(sql, params_list)
        finally:
            self.pool.release_connection(conn)

    def fetchone(self, sql: str, params=None):
        """Fetch one row using pooled connection."""
        conn = self.pool.get_connection()
        try:
            return conn.fetchone(sql, params)
        finally:
            self.pool.release_connection(conn)

    def fetchall(self, sql: str, params=None):
        """Fetch all rows using pooled connection."""
        conn = self.pool.get_connection()
        try:
            return conn.fetchall(sql, params)
        finally:
            self.pool.release_connection(conn)

    def pool_stats(self) -> PoolStats:
        """Get pool statistics."""
        return self.pool.pool_stats()

    def close_all(self) -> None:
        """Close all pooled connections."""
        self.pool.close_all()
