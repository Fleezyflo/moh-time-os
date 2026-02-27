"""
State Store - The central nervous system of MOH TIME OS.
All components read from and write to this single source of truth.
"""

import json
import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from lib import db as db_module
from lib import paths, safe_sql

logger = logging.getLogger(__name__)


class StateStore:
    """
    Central state store. SQLite for persistence, in-memory cache for speed.
    Every component connects through here. No exceptions.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, db_path: str = None):
        """Singleton - one store, one truth."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: str = None):
        if self._initialized:
            return

        # Use centralized DB path resolution
        self.db_path = db_path or db_module.get_db_path_str()
        paths.data_dir()  # ensures directory exists

        logger.info("StateStore initializing with DB: %s", self.db_path)

        self._cache: dict[str, Any] = {}
        self._cache_timestamps: dict[str, datetime] = {}

        # Schema convergence — schema_engine creates/migrates all tables
        db_module.ensure_migrations()

        self._initialized = True

        logger.info("StateStore ready, DB path: %s", self.db_path)

    @contextmanager
    def _get_conn(self):
        """Thread-safe connection context."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")  # Enable FK enforcement
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ==================== CRUD Operations ====================

    def insert(self, table: str, data: dict) -> str:
        """Insert a row. Returns ID."""
        db_module.validate_identifier(table)
        columns = list(data.keys())
        for col in columns:
            db_module.validate_identifier(col)
        values = [json.dumps(v) if isinstance(v, dict | list) else v for v in data.values()]

        with self._get_conn() as conn:
            sql = safe_sql.insert_or_replace(table, columns)
            conn.execute(sql, values)

        return data.get("id", "")

    def insert_many(self, table: str, items: list[dict]) -> int:
        """Insert multiple rows. Returns count."""
        if not items:
            return 0

        db_module.validate_identifier(table)
        columns = list(items[0].keys())
        for col in columns:
            db_module.validate_identifier(col)

        sql = safe_sql.insert_or_replace(table, columns)

        with self._get_conn() as conn:
            for item in items:
                values = [json.dumps(v) if isinstance(v, dict | list) else v for v in item.values()]
                conn.execute(sql, values)

        return len(items)

    def get(self, table: str, id: str) -> dict | None:
        """Get a single row by ID."""
        db_module.validate_identifier(table)
        with self._get_conn() as conn:
            sql = safe_sql.select(table, where="id = ?")
            row = conn.execute(sql, [id]).fetchone()
            return dict(row) if row else None

    def update(self, table: str, id: str, data: dict) -> bool:
        """Update a row."""
        if not data:
            return False

        db_module.validate_identifier(table)
        for k in data:
            db_module.validate_identifier(k)
        values = [json.dumps(v) if isinstance(v, dict | list) else v for v in data.values()]
        values.append(id)

        with self._get_conn() as conn:
            sql = safe_sql.update(table, list(data.keys()))
            result = conn.execute(sql, values)
            return result.rowcount > 0

    def delete(self, table: str, id: str) -> bool:
        """Delete a row."""
        db_module.validate_identifier(table)
        with self._get_conn() as conn:
            sql = safe_sql.delete(table)
            result = conn.execute(sql, [id])
            return result.rowcount > 0

    def query(self, sql: str, params: list = None) -> list[dict]:
        """Execute raw query. Returns list of dicts."""
        with self._get_conn() as conn:
            rows = conn.execute(sql, params or []).fetchall()
            return [dict(row) for row in rows]

    def count(self, table: str, where: str = None, params: list = None) -> int:
        """Count rows."""
        db_module.validate_identifier(table)
        sql = safe_sql.select_count(table, where=where)

        with self._get_conn() as conn:
            row = conn.execute(sql, params or []).fetchone()
            return row["c"] if row else 0

    # ==================== Cache Operations ====================

    def set_cache(self, key: str, value: Any, ttl_seconds: int = 300):
        """Set cache value."""
        self._cache[key] = value
        self._cache_timestamps[key] = datetime.now()

        # Also persist to disk for recovery
        cache_path = Path(self.db_path).parent / "cache" / f"{key}.json"
        cache_path.parent.mkdir(exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump({"value": value, "timestamp": datetime.now().isoformat()}, f)

    def get_cache(self, key: str, max_age_seconds: int = 300) -> Any | None:
        """Get cache value if not expired."""
        if key in self._cache:
            timestamp = self._cache_timestamps.get(key)
            if timestamp:
                age = (datetime.now() - timestamp).total_seconds()
                if age < max_age_seconds:
                    return self._cache[key]

        # Try disk cache
        cache_path = Path(self.db_path).parent / "cache" / f"{key}.json"
        if cache_path.exists():
            with open(cache_path) as f:
                data = json.load(f)
                timestamp = datetime.fromisoformat(data["timestamp"])
                age = (datetime.now() - timestamp).total_seconds()
                if age < max_age_seconds:
                    self._cache[key] = data["value"]
                    self._cache_timestamps[key] = timestamp
                    return data["value"]

        return None

    def clear_cache(self, key: str = None):
        """Clear cache."""
        if key:
            self._cache.pop(key, None)
            self._cache_timestamps.pop(key, None)
        else:
            self._cache.clear()
            self._cache_timestamps.clear()

    # ==================== Convenience Methods ====================

    def get_pending_tasks(self, limit: int = 50) -> list[dict]:
        """Get pending tasks ordered by priority."""
        return self.query(
            "SELECT * FROM tasks WHERE status != 'done' "
            "ORDER BY priority DESC, due_date ASC LIMIT ?",
            [limit],
        )

    def get_upcoming_events(self, hours: int = 24) -> list[dict]:
        """Get upcoming events."""
        return self.query(
            """SELECT * FROM events
               WHERE datetime(start_time) >= datetime('now')
               AND datetime(start_time) <= datetime('now', '+' || ? || ' hours')
               ORDER BY start_time""",
            [hours],
        )

    def get_pending_decisions(self) -> list[dict]:
        """Get decisions awaiting approval."""
        return self.query("SELECT * FROM decisions WHERE approved IS NULL ORDER BY created_at DESC")

    def get_pending_actions(self) -> list[dict]:
        """Get actions ready to execute."""
        return self.query("SELECT * FROM actions WHERE status = 'approved' ORDER BY created_at")

    def get_active_insights(self) -> list[dict]:
        """Get non-expired insights."""
        return self.query(
            """SELECT * FROM insights
               WHERE (expires_at IS NULL OR datetime(expires_at) > datetime('now'))
               ORDER BY created_at DESC"""
        )

    def update_sync_state(self, source: str, success: bool, items: int = 0, error: str = None):
        """Update sync state for a source."""
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO sync_state
                (source, last_sync, last_success, items_synced, error)
                VALUES (?, ?, ?, ?, ?)
            """,
                [source, now, now if success else None, items, error],
            )

    def get_sync_states(self) -> dict[str, dict]:
        """Get all sync states."""
        rows = self.query("SELECT * FROM sync_state")
        return {row["source"]: row for row in rows}


# Singleton accessor
_store: StateStore | None = None


def get_store(db_path: str = None) -> StateStore:
    """Get the singleton state store."""
    global _store
    if _store is None:
        _store = StateStore(db_path)
    return _store
