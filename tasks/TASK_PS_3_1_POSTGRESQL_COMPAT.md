# PS-3.1: PostgreSQL Compatibility Layer

## Objective
Abstract the database layer so the system can run on both SQLite (development) and PostgreSQL (production) via a configuration switch.

## Context
`lib/db.py` (772 lines) is SQLite-specific: direct `sqlite3` imports, SQLite-only functions, `VACUUM` calls, WAL mode. PostgreSQL offers concurrent writes, better query planning, and production-grade reliability. Building the abstraction now means future migration is a config change, not a rewrite.

## Implementation

### DB Abstraction Layer
```python
# lib/db/engine.py
import os

def get_engine():
    db_type = os.environ.get("MOH_DB_ENGINE", "sqlite")
    if db_type == "sqlite":
        return SQLiteEngine(os.environ.get("MOH_DB_PATH", "data/moh_time_os.db"))
    elif db_type == "postgresql":
        return PostgreSQLEngine(os.environ.get("MOH_DB_URL"))
    raise ValueError(f"Unknown DB engine: {db_type}")

class DBEngine(Protocol):
    def execute(self, query: str, params: tuple = ()) -> Any: ...
    def executemany(self, query: str, params: list[tuple]) -> Any: ...
    def fetchone(self, query: str, params: tuple = ()) -> dict | None: ...
    def fetchall(self, query: str, params: tuple = ()) -> list[dict]: ...
    def transaction(self) -> ContextManager: ...
```

### SQL Compatibility
Handle SQLite vs PostgreSQL dialect differences:
```python
# lib/db/compat.py
class SQLCompat:
    def __init__(self, engine_type: str):
        self.engine_type = engine_type

    def upsert(self, table: str, columns: list, conflict_column: str) -> str:
        if self.engine_type == "sqlite":
            return f"INSERT OR REPLACE INTO {table} ..."
        return f"INSERT INTO {table} ... ON CONFLICT ({conflict_column}) DO UPDATE ..."

    def now(self) -> str:
        if self.engine_type == "sqlite":
            return "datetime('now')"
        return "NOW()"

    def boolean(self, value: bool) -> str:
        if self.engine_type == "sqlite":
            return "1" if value else "0"
        return "TRUE" if value else "FALSE"
```

### Migration System
- Schema migrations must be dialect-aware
- Use CREATE TABLE IF NOT EXISTS (works in both)
- Avoid SQLite-specific: `AUTOINCREMENT` → `SERIAL` in PG, `TEXT` for dates → `TIMESTAMP` in PG
- Migration runner checks engine type and applies appropriate SQL

### What Changes in lib/db.py
- Replace direct `sqlite3.connect()` with `get_engine()`
- Replace `cursor.execute()` with `engine.execute()`
- Replace `VACUUM` with engine-specific maintenance
- Replace WAL mode setup with engine-specific configuration

## Validation
- [ ] All tests pass with SQLite engine (no regressions)
- [ ] DB engine switchable via `MOH_DB_ENGINE` env var
- [ ] Migrations run correctly on both engines
- [ ] SQL compatibility layer handles dialect differences
- [ ] PostgreSQL engine connects and executes basic CRUD (if PG available for testing)

## Files Created/Modified
- New: `lib/db/engine.py` — engine abstraction
- New: `lib/db/compat.py` — SQL dialect compatibility
- `lib/db.py` → refactor to use engine abstraction
- All files importing from `lib/db.py` — update to use new interface

## Estimated Effort
Large — ~400 lines, significant refactor touching many files
