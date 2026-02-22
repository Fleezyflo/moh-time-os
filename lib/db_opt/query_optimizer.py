"""
Query Optimization Utilities — Batch Loading & Analysis

Provides tools for:
- BatchLoader: Collects IDs and performs single IN queries
- prefetch_related: Bulk-load related data
- explain_query: EXPLAIN wrapper for query analysis
- QueryStats: Track query performance metrics

Used to eliminate N+1 query patterns in API endpoints.
"""

import logging
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class QueryStats:
    """Track query performance metrics."""

    query_count: int = 0
    total_time_ms: float = 0.0
    slowest_query_ms: float = 0.0
    slowest_query_sql: str = ""
    queries: list[dict] = field(default_factory=list)

    def add_query(self, sql: str, duration_ms: float) -> None:
        """Record a query execution."""
        self.query_count += 1
        self.total_time_ms += duration_ms
        if duration_ms > self.slowest_query_ms:
            self.slowest_query_ms = duration_ms
            self.slowest_query_sql = sql[:100]
        self.queries.append({"sql": sql[:200], "duration_ms": round(duration_ms, 2)})

    def to_dict(self) -> dict:
        """Convert stats to dict for JSON serialization."""
        return {
            "query_count": self.query_count,
            "total_time_ms": round(self.total_time_ms, 2),
            "slowest_query_ms": round(self.slowest_query_ms, 2),
            "slowest_query_sql": self.slowest_query_sql,
            "avg_query_ms": (
                round(self.total_time_ms / self.query_count, 2) if self.query_count > 0 else 0
            ),
        }


class BatchLoader:
    """
    Collects IDs and performs single bulk IN query instead of N individual queries.

    Usage:
        loader = BatchLoader(conn, "users", "id", ["name", "email"])
        loader.add_id("user1")
        loader.add_id("user2")
        user_map = loader.get_map()  # Single query: SELECT id, name, email FROM users WHERE id IN (?, ?)
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        table: str,
        id_column: str,
        columns: list[str],
    ):
        """Initialize batch loader."""
        self.conn = conn
        self.table = table
        self.id_column = id_column
        self.columns = columns
        self.ids: set = set()
        self.loaded = False
        self._cache: dict = {}

    def add_id(self, id_value: Any) -> None:
        """Add an ID to batch load."""
        if not self.loaded:
            self.ids.add(id_value)

    def add_ids(self, ids: list[Any]) -> None:
        """Add multiple IDs to batch load."""
        if not self.loaded:
            self.ids.update(ids)

    def get_map(self) -> dict[Any, dict]:
        """
        Load all collected IDs in a single query, return map of id -> row dict.

        Returns empty dict if no IDs collected.
        """
        if self.loaded:
            return self._cache

        if not self.ids:
            self.loaded = True
            return {}

        # Build parameterized IN query
        placeholders = ",".join("?" * len(self.ids))
        column_list = ", ".join([self.id_column] + self.columns)

        sql = f"""
            SELECT {column_list}
            FROM {self.table}
            WHERE {self.id_column} IN ({placeholders})
        """

        try:
            cursor = self.conn.execute(sql, list(self.ids))
            for row in cursor.fetchall():
                row_dict = dict(row)
                id_val = row_dict[self.id_column]
                self._cache[id_val] = row_dict
            self.loaded = True
            return self._cache
        except sqlite3.Error as e:
            logger.error(f"BatchLoader failed for {self.table}: {e}")
            self.loaded = True
            return {}

    def get(self, id_value: Any, default: dict | None = None) -> dict | None:
        """Get single row by ID (performs load on first call)."""
        return self.get_map().get(id_value, default)


def prefetch_related(
    conn: sqlite3.Connection,
    table: str,
    ids: list[Any],
    id_column: str = "id",
    columns: list[str] | None = None,
) -> dict[Any, dict]:
    """
    Bulk-load related data in a single query.

    Args:
        conn: Database connection
        table: Table to query
        ids: IDs to fetch
        id_column: Column name for ID matching
        columns: Columns to select (default: all)

    Returns:
        Map of {id: row_dict}

    Usage:
        projects = prefetch_related(conn, "projects", client_ids, id_column="client_id")
        for client_id in client_ids:
            project = projects.get(client_id)
    """
    if not ids:
        return {}

    if columns is None:
        columns = ["*"]

    column_list = ", ".join(columns)
    placeholders = ",".join("?" * len(ids))

    sql = f"""
        SELECT {id_column}, {column_list}
        FROM {table}
        WHERE {id_column} IN ({placeholders})
    """

    try:
        cursor = conn.execute(sql, ids)
        result = {}
        for row in cursor.fetchall():
            row_dict = dict(row)
            id_val = row_dict[id_column]
            # Support both single and multi-row results
            if id_val not in result:
                result[id_val] = row_dict
            else:
                # Convert to list if multiple rows for same ID
                if not isinstance(result[id_val], list):
                    result[id_val] = [result[id_val]]
                result[id_val].append(row_dict)
        return result
    except sqlite3.Error as e:
        logger.error(f"prefetch_related failed for {table}: {e}")
        return {}


def explain_query(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    """
    Get EXPLAIN QUERY PLAN for a query.

    Returns list of dicts with: addr, opcode, p1, p2, p3, p4, p5, comment

    Usage:
        plan = explain_query(conn, "SELECT * FROM users WHERE id = ?", (123,))
        for step in plan:
            print(f"{step['opcode']}: {step['comment']}")
    """
    explain_sql = f"EXPLAIN QUERY PLAN {sql}"
    try:
        cursor = conn.execute(explain_sql, params)
        cols = [col[0] for col in cursor.description]
        return [dict(zip(cols, row, strict=False)) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logger.error(f"EXPLAIN failed: {e}")
        return []


def analyze_query_performance(
    conn: sqlite3.Connection, sql: str, params: tuple = (), iterations: int = 3
) -> dict:
    """
    Run query multiple times and measure performance.

    Args:
        conn: Database connection
        sql: SQL query
        params: Query parameters
        iterations: Number of times to run

    Returns:
        Dict with: avg_ms, min_ms, max_ms, total_ms, row_count
    """
    times = []
    row_count = 0

    for _ in range(iterations):
        start = time.time()
        cursor = conn.execute(sql, params)
        rows = cursor.fetchall()
        duration = (time.time() - start) * 1000
        times.append(duration)
        row_count = len(rows)

    return {
        "avg_ms": round(sum(times) / len(times), 2),
        "min_ms": round(min(times), 2),
        "max_ms": round(max(times), 2),
        "total_ms": round(sum(times), 2),
        "row_count": row_count,
        "iterations": iterations,
    }
