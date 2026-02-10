"""
State Store - The central nervous system of MOH TIME OS.
All components read from and write to this single source of truth.
"""

import json
import logging
import sqlite3
import threading
from contextlib import contextmanager, suppress
from datetime import datetime
from pathlib import Path
from typing import Any

from lib import db as db_module
from lib import paths

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

        logger.info(f"StateStore initializing with DB: {self.db_path}")

        self._cache: dict[str, Any] = {}
        self._cache_timestamps: dict[str, datetime] = {}

        self._init_schema()

        # Run centralized migrations
        db_module.ensure_migrations()

        # Also run legacy migrations for backward compatibility
        self._run_migrations()
        self._initialized = True

        logger.info(f"StateStore ready, DB path: {self.db_path}")

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

    def _init_schema(self):
        """Initialize all tables. This is the data model."""
        with self._get_conn() as conn:
            # Skip schema creation if core tables already exist (moh_time_os.db has V4 schema)
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'"
            )
            if cursor.fetchone():
                # Database already has tables, skip schema init
                return

            conn.executescript("""
                -- CORE ENTITIES

                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    source_id TEXT,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    priority INTEGER DEFAULT 50,
                    due_date TEXT,
                    due_time TEXT,
                    assignee TEXT,
                    project TEXT,
                    tags TEXT,
                    dependencies TEXT,
                    blockers TEXT,
                    context TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    synced_at TEXT
                );

                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    source_id TEXT,
                    title TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    location TEXT,
                    attendees TEXT,
                    status TEXT DEFAULT 'confirmed',
                    prep_required TEXT,
                    context TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS communications (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    source_id TEXT,
                    thread_id TEXT,
                    from_email TEXT,
                    to_emails TEXT,
                    subject TEXT,
                    snippet TEXT,
                    priority INTEGER DEFAULT 50,
                    requires_response INTEGER DEFAULT 0,
                    response_deadline TEXT,
                    sentiment TEXT,
                    labels TEXT,
                    processed INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS people (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT,
                    phone TEXT,
                    company TEXT,
                    role TEXT,
                    type TEXT DEFAULT 'external',  -- 'internal' or 'external'
                    relationship TEXT,
                    importance INTEGER DEFAULT 50,
                    last_contact TEXT,
                    contact_frequency_days INTEGER,
                    notes TEXT,
                    context TEXT
                );

                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    source TEXT,
                    source_id TEXT,
                    name TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    health TEXT DEFAULT 'green',
                    enrollment_status TEXT DEFAULT 'enrolled',
                    rule_bundles TEXT,
                    owner TEXT,
                    deadline TEXT,
                    tasks_total INTEGER DEFAULT 0,
                    tasks_done INTEGER DEFAULT 0,
                    blockers TEXT,
                    next_milestone TEXT,
                    context TEXT
                );

                -- INTELLIGENCE LAYER

                CREATE TABLE IF NOT EXISTS insights (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    confidence REAL DEFAULT 0.5,
                    data TEXT,
                    actionable INTEGER DEFAULT 0,
                    action_taken INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    expires_at TEXT
                );

                CREATE TABLE IF NOT EXISTS decisions (
                    id TEXT PRIMARY KEY,
                    domain TEXT NOT NULL,
                    decision_type TEXT NOT NULL,
                    description TEXT,
                    input_data TEXT,
                    options TEXT,
                    selected_option TEXT,
                    rationale TEXT,
                    confidence REAL DEFAULT 0.5,
                    requires_approval INTEGER DEFAULT 1,
                    approved INTEGER,
                    approved_at TEXT,
                    executed INTEGER DEFAULT 0,
                    executed_at TEXT,
                    outcome TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS notifications (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    priority TEXT NOT NULL DEFAULT 'normal',
                    title TEXT NOT NULL,
                    body TEXT,
                    action_url TEXT,
                    action_data TEXT,
                    channels TEXT,
                    sent_at TEXT,
                    read_at TEXT,
                    acted_on_at TEXT,
                    created_at TEXT NOT NULL
                );

                -- EXECUTION LAYER

                CREATE TABLE IF NOT EXISTS actions (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    target_system TEXT,
                    payload TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    requires_approval INTEGER DEFAULT 1,
                    approved_by TEXT,
                    approved_at TEXT,
                    executed_at TEXT,
                    result TEXT,
                    error TEXT,
                    retry_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                -- LEARNING LAYER

                CREATE TABLE IF NOT EXISTS feedback (
                    id TEXT PRIMARY KEY,
                    decision_id TEXT,
                    insight_id TEXT,
                    action_id TEXT,
                    feedback_type TEXT,
                    details TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS patterns (
                    id TEXT PRIMARY KEY,
                    domain TEXT NOT NULL,
                    pattern_type TEXT NOT NULL,
                    description TEXT,
                    data TEXT,
                    confidence REAL DEFAULT 0.5,
                    occurrences INTEGER DEFAULT 1,
                    last_seen TEXT,
                    created_at TEXT NOT NULL
                );

                -- SYSTEM

                CREATE TABLE IF NOT EXISTS cycle_logs (
                    id TEXT PRIMARY KEY,
                    cycle_number INTEGER,
                    phase TEXT,
                    data TEXT,
                    duration_ms REAL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sync_state (
                    source TEXT PRIMARY KEY,
                    last_sync TEXT,
                    last_success TEXT,
                    items_synced INTEGER DEFAULT 0,
                    error TEXT
                );

                -- CLIENT TRUTH (Tier 3)

                CREATE TABLE IF NOT EXISTS client_projects (
                    client_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    linked_at TEXT NOT NULL,
                    PRIMARY KEY (client_id, project_id),
                    FOREIGN KEY (client_id) REFERENCES clients(id),
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                );

                CREATE TABLE IF NOT EXISTS client_health_log (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    health_score INTEGER,
                    factors TEXT,
                    computed_at TEXT NOT NULL,
                    FOREIGN KEY (client_id) REFERENCES clients(id)
                );

                -- CAPACITY (Tier 2: Capacity Truth)

                CREATE TABLE IF NOT EXISTS capacity_lanes (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    display_name TEXT,
                    owner TEXT,
                    weekly_hours INTEGER DEFAULT 40,
                    buffer_pct REAL DEFAULT 0.2,
                    color TEXT DEFAULT '#6366f1',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS time_debt (
                    id TEXT PRIMARY KEY,
                    lane TEXT NOT NULL,
                    amount_min INTEGER NOT NULL,
                    reason TEXT,
                    source_task_id TEXT,
                    incurred_at TEXT NOT NULL,
                    resolved_at TEXT,
                    FOREIGN KEY (lane) REFERENCES capacity_lanes(id)
                );

                -- COMMITMENTS (§12 schema)

                CREATE TABLE IF NOT EXISTS commitments (
                    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
                    source_type TEXT NOT NULL DEFAULT 'communication',
                    source_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    type TEXT NOT NULL CHECK (type IN ('promise', 'request')),
                    confidence REAL,
                    deadline TEXT,
                    speaker TEXT,
                    target TEXT,
                    client_id TEXT,
                    task_id TEXT,
                    status TEXT DEFAULT 'open' CHECK (status IN ('open', 'fulfilled', 'broken', 'cancelled')),
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (source_id) REFERENCES communications(id),
                    FOREIGN KEY (client_id) REFERENCES clients(id),
                    FOREIGN KEY (task_id) REFERENCES tasks(id)
                );

                -- INDEXES

                CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
                CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(due_date);
                CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority DESC);
                CREATE INDEX IF NOT EXISTS idx_events_start ON events(start_time);
                CREATE INDEX IF NOT EXISTS idx_communications_priority ON communications(priority DESC);
                CREATE INDEX IF NOT EXISTS idx_notifications_created ON notifications(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_actions_status ON actions(status);
                CREATE INDEX IF NOT EXISTS idx_decisions_pending ON decisions(approved) WHERE approved IS NULL;
                CREATE INDEX IF NOT EXISTS idx_commitments_source ON commitments(source_id);
                CREATE INDEX IF NOT EXISTS idx_commitments_client ON commitments(client_id);
                CREATE INDEX IF NOT EXISTS idx_time_debt_lane ON time_debt(lane);
                CREATE INDEX IF NOT EXISTS idx_time_debt_unresolved ON time_debt(resolved_at) WHERE resolved_at IS NULL;
                CREATE INDEX IF NOT EXISTS idx_client_projects_client ON client_projects(client_id);
                CREATE INDEX IF NOT EXISTS idx_client_projects_project ON client_projects(project_id);
                CREATE INDEX IF NOT EXISTS idx_client_health_log_client ON client_health_log(client_id);
            """)

    def _run_migrations(self):
        """Run schema migrations for existing databases."""
        with self._get_conn() as conn:
            # Migration: Add 'type' column to people table (internal/external team filtering)
            try:
                conn.execute("SELECT type FROM people LIMIT 1")
            except sqlite3.OperationalError:
                try:
                    conn.execute(
                        "ALTER TABLE people ADD COLUMN type TEXT DEFAULT 'external'"
                    )
                except sqlite3.OperationalError:
                    pass  # Column may already exist or table doesn't exist

            # Migration: Add 'enrollment_status' column to projects table
            try:
                conn.execute("SELECT enrollment_status FROM projects LIMIT 1")
            except sqlite3.OperationalError:
                with suppress(sqlite3.OperationalError):
                    conn.execute(
                        "ALTER TABLE projects ADD COLUMN enrollment_status TEXT DEFAULT 'enrolled'"
                    )

            # Migration: Add 'rule_bundles' column to projects table
            try:
                conn.execute("SELECT rule_bundles FROM projects LIMIT 1")
            except sqlite3.OperationalError:
                with suppress(sqlite3.OperationalError):
                    conn.execute("ALTER TABLE projects ADD COLUMN rule_bundles TEXT")

            # Migration: Add 'completed_at' column to tasks table
            try:
                conn.execute("SELECT completed_at FROM tasks LIMIT 1")
            except sqlite3.OperationalError:
                with suppress(sqlite3.OperationalError):
                    conn.execute("ALTER TABLE tasks ADD COLUMN completed_at TEXT")

            # Migration: Add 'brand_id' column to projects table
            try:
                conn.execute("SELECT brand_id FROM projects LIMIT 1")
            except sqlite3.OperationalError:
                with suppress(sqlite3.OperationalError):
                    conn.execute("ALTER TABLE projects ADD COLUMN brand_id TEXT")

            # Migration: Add proposal hierarchy columns to proposals_v4 table
            proposal_columns = [
                ("scope_level", "TEXT DEFAULT 'project'"),
                ("scope_name", "TEXT"),
                ("client_id", "TEXT"),
                ("client_name", "TEXT"),
                ("client_tier", "TEXT"),
                ("brand_id", "TEXT"),
                ("brand_name", "TEXT"),
                ("engagement_type", "TEXT"),
                ("signal_summary_json", "TEXT"),
                ("score_breakdown_json", "TEXT"),
                ("affected_task_ids_json", "TEXT"),
            ]
            for col_name, col_def in proposal_columns:
                try:
                    conn.execute(f"SELECT {col_name} FROM proposals_v4 LIMIT 1")
                except sqlite3.OperationalError:
                    try:
                        conn.execute(
                            f"ALTER TABLE proposals_v4 ADD COLUMN {col_name} {col_def}"
                        )
                    except sqlite3.OperationalError:
                        pass  # Table may not exist or column exists

            # Migration: Add signal lifecycle columns to signals table
            signal_columns = [
                ("resolved_at", "TEXT"),
                ("resolution", "TEXT"),
            ]
            for col_name, col_def in signal_columns:
                try:
                    conn.execute(f"SELECT {col_name} FROM signals LIMIT 1")
                except sqlite3.OperationalError:
                    try:
                        conn.execute(
                            f"ALTER TABLE signals ADD COLUMN {col_name} {col_def}"
                        )
                    except sqlite3.OperationalError:
                        pass  # Table may not exist or column exists

            # Migration: Create indexes for proposal hierarchy
            with suppress(sqlite3.OperationalError):
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_proposals_hierarchy ON proposals_v4(client_id, brand_id, scope_level)"
                )

            with suppress(sqlite3.OperationalError):
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_signals_resolved ON signals(status, resolved_at)"
                )

            # Migration: Add 'description' column to tasks table
            self._add_column_if_missing(conn, "tasks", "description", "TEXT DEFAULT ''")

            # Migration: Add 'received_at' column to communications table
            self._add_column_if_missing(conn, "communications", "received_at", "TEXT")

    def _add_column_if_missing(
        self, conn, table: str, column: str, definition: str
    ) -> bool:
        """
        Add a column to a table if it doesn't exist.
        Uses PRAGMA table_info for detection, then ALTER TABLE ADD COLUMN.
        Returns True if column was added, False if already existed or table doesn't exist.
        """
        import logging

        logger = logging.getLogger(__name__)

        try:
            # Check if table exists
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            )
            if not cursor.fetchone():
                logger.debug(f"Migration skipped: table '{table}' does not exist")
                return False

            # Get existing columns
            cursor = conn.execute(f"PRAGMA table_info({table})")
            existing_columns = {row[1] for row in cursor.fetchall()}

            if column in existing_columns:
                logger.debug(f"Migration skipped: {table}.{column} already exists")
                return False

            # Add the column
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            logger.info(f"Migration applied: added {table}.{column} ({definition})")
            return True

        except sqlite3.OperationalError as e:
            logger.warning(f"Migration failed for {table}.{column}: {e}")
            return False

    # ==================== CRUD Operations ====================

    def insert(self, table: str, data: dict) -> str:
        """Insert a row. Returns ID."""
        columns = list(data.keys())
        placeholders = ["?" for _ in columns]
        values = [
            json.dumps(v) if isinstance(v, (dict, list)) else v for v in data.values()
        ]

        with self._get_conn() as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO {table} ({','.join(columns)}) VALUES ({','.join(placeholders)})",
                values,
            )

        return data.get("id", "")

    def insert_many(self, table: str, items: list[dict]) -> int:
        """Insert multiple rows. Returns count."""
        if not items:
            return 0

        columns = list(items[0].keys())
        placeholders = ["?" for _ in columns]

        with self._get_conn() as conn:
            for item in items:
                values = [
                    json.dumps(v) if isinstance(v, (dict, list)) else v
                    for v in item.values()
                ]
                conn.execute(
                    f"INSERT OR REPLACE INTO {table} ({','.join(columns)}) VALUES ({','.join(placeholders)})",
                    values,
                )

        return len(items)

    def get(self, table: str, id: str) -> dict | None:
        """Get a single row by ID."""
        with self._get_conn() as conn:
            row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", [id]).fetchone()
            return dict(row) if row else None

    def update(self, table: str, id: str, data: dict) -> bool:
        """Update a row."""
        if not data:
            return False

        sets = [f"{k} = ?" for k in data]
        values = [
            json.dumps(v) if isinstance(v, (dict, list)) else v for v in data.values()
        ]
        values.append(id)

        with self._get_conn() as conn:
            result = conn.execute(
                f"UPDATE {table} SET {','.join(sets)} WHERE id = ?", values
            )
            return result.rowcount > 0

    def delete(self, table: str, id: str) -> bool:
        """Delete a row."""
        with self._get_conn() as conn:
            result = conn.execute(f"DELETE FROM {table} WHERE id = ?", [id])
            return result.rowcount > 0

    def query(self, sql: str, params: list = None) -> list[dict]:
        """Execute raw query. Returns list of dicts."""
        with self._get_conn() as conn:
            rows = conn.execute(sql, params or []).fetchall()
            return [dict(row) for row in rows]

    def count(self, table: str, where: str = None, params: list = None) -> int:
        """Count rows."""
        sql = f"SELECT COUNT(*) as c FROM {table}"
        if where:
            sql += f" WHERE {where}"

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
            "SELECT * FROM tasks WHERE status != 'done' ORDER BY priority DESC, due_date ASC LIMIT ?",
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
        return self.query(
            "SELECT * FROM decisions WHERE approved IS NULL ORDER BY created_at DESC"
        )

    def get_pending_actions(self) -> list[dict]:
        """Get actions ready to execute."""
        return self.query(
            "SELECT * FROM actions WHERE status = 'approved' ORDER BY created_at"
        )

    def get_active_insights(self) -> list[dict]:
        """Get non-expired insights."""
        return self.query(
            """SELECT * FROM insights
               WHERE (expires_at IS NULL OR datetime(expires_at) > datetime('now'))
               ORDER BY created_at DESC"""
        )

    def update_sync_state(
        self, source: str, success: bool, items: int = 0, error: str = None
    ):
        """Update sync state for a source."""
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sync_state (source, last_sync, last_success, items_synced, error)
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
