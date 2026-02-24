"""
Schema Convergence Engine — introspect, diff, apply.

Reads the declarative schema from lib/schema and converges any SQLite
database to match.  Two entry points:

  converge(conn)     — For existing DBs: adds missing tables/columns/indexes.
  create_fresh(conn) — For new/test DBs: drops everything and creates clean.

The engine never drops tables or columns on an existing DB.
It only adds what is missing and runs idempotent data migrations.
"""

import logging
import re
import sqlite3

from lib import schema

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────
# SQLite ALTER TABLE column-safety
# ────────────────────────────────────────────────────────────

# Clauses that are valid in CREATE TABLE but not in ALTER TABLE ADD COLUMN
_STRIP_PATTERNS = [
    re.compile(r"\bPRIMARY\s+KEY\b", re.IGNORECASE),
    re.compile(r"\bAUTOINCREMENT\b", re.IGNORECASE),
    re.compile(r"\bUNIQUE\b", re.IGNORECASE),
    re.compile(r"\bREFERENCES\s+\w+\s*\([^)]*\)", re.IGNORECASE),
    re.compile(r"\bFOREIGN\s+KEY\b", re.IGNORECASE),
    re.compile(r"\bCHECK\s*\([^)]*\)", re.IGNORECASE),
]


def make_alter_safe(col_def: str) -> str:
    """
    Transform a CREATE TABLE column definition into one safe for
    ALTER TABLE ADD COLUMN.

    SQLite restrictions on ALTER TABLE ADD COLUMN:
      - Cannot be PRIMARY KEY or AUTOINCREMENT
      - Cannot have UNIQUE constraint
      - Cannot have REFERENCES / FOREIGN KEY
      - Cannot have CHECK constraint
      - NOT NULL requires a DEFAULT (unless default is NULL)
    """
    safe = col_def
    for pattern in _STRIP_PATTERNS:
        safe = pattern.sub("", safe)

    # Collapse multiple spaces
    safe = re.sub(r"\s{2,}", " ", safe).strip()

    # NOT NULL without DEFAULT → add DEFAULT ''
    has_not_null = re.search(r"\bNOT\s+NULL\b", safe, re.IGNORECASE)
    has_default = re.search(r"\bDEFAULT\b", safe, re.IGNORECASE)
    if has_not_null and not has_default:
        safe = safe + " DEFAULT ''"

    return safe


# ────────────────────────────────────────────────────────────
# Introspection helpers
# ────────────────────────────────────────────────────────────


def _get_existing_tables(conn: sqlite3.Connection) -> dict[str, str]:
    """Return {name: type} for all objects in sqlite_master.

    type is 'table' or 'view'.
    """
    cursor = conn.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view')")
    return {row[0]: row[1] for row in cursor.fetchall()}


def _get_existing_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """Return set of column names for a table/view."""
    try:
        cursor = conn.execute(f"PRAGMA table_info([{table}])")  # nosec B608
        return {row[1] for row in cursor.fetchall()}
    except sqlite3.OperationalError:
        return set()


def _get_existing_indexes(conn: sqlite3.Connection) -> set[str]:
    """Return set of existing index names."""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND name NOT LIKE 'sqlite_%'"
    )
    return {row[0] for row in cursor.fetchall()}


# ────────────────────────────────────────────────────────────
# Build CREATE TABLE SQL from schema declaration
# ────────────────────────────────────────────────────────────


def _build_create_sql(table_name: str, table_def: dict) -> str:
    """Build a CREATE TABLE IF NOT EXISTS statement from schema declaration."""
    parts = []
    for col_name, col_ddl in table_def["columns"]:
        parts.append(f"    {col_name} {col_ddl}")
    # Table-level UNIQUE constraints (optional)
    for unique_cols in table_def.get("unique", []):
        cols_str = ", ".join(unique_cols)
        parts.append(f"    UNIQUE({cols_str})")
    body = ",\n".join(parts)
    return f"CREATE TABLE IF NOT EXISTS [{table_name}] (\n{body}\n)"


# ────────────────────────────────────────────────────────────
# converge — the main entry point for existing databases
# ────────────────────────────────────────────────────────────


def converge(conn: sqlite3.Connection) -> dict:
    """
    Converge an existing database to match schema.TABLES.

    Algorithm:
      1. Introspect sqlite_master for existing tables/views.
      2. For each declared table:
         a. If name exists as a VIEW → skip entirely (views managed separately).
         b. If table missing → CREATE TABLE.
         c. If table exists → PRAGMA table_info, ADD COLUMN for each missing column.
      3. Create missing indexes (skip indexes on views).
      4. Run idempotent data migrations.
      5. Set PRAGMA user_version.

    Returns a results dict for logging.
    """
    results = {
        "tables_created": [],
        "columns_added": [],
        "indexes_created": [],
        "data_migrations_run": [],
        "skipped_views": [],
        "errors": [],
    }

    existing_objects = _get_existing_tables(conn)
    existing_indexes = _get_existing_indexes(conn)

    # ── Phase 1: Tables and columns ──────────────────────────

    for table_name, table_def in schema.TABLES.items():
        obj_type = existing_objects.get(table_name)

        # Skip views — they exist in the live DB and must not be overwritten
        if obj_type == "view":
            results["skipped_views"].append(table_name)
            continue

        if obj_type is None:
            # Table does not exist → create it
            # But if schema marks it skip_if_view, check if there is a
            # view by this name (already handled above, but defensive)
            create_sql = _build_create_sql(table_name, table_def)
            try:
                conn.execute(create_sql)
                results["tables_created"].append(table_name)
                logger.info("schema_engine: created table %s", table_name)
            except sqlite3.OperationalError as e:
                err = f"CREATE TABLE {table_name}: {e}"
                results["errors"].append(err)
                logger.warning("schema_engine: %s", err)
        else:
            # Table exists → check for missing columns
            existing_cols = _get_existing_columns(conn, table_name)
            for col_name, col_ddl in table_def["columns"]:
                if col_name in existing_cols:
                    continue

                safe_ddl = make_alter_safe(col_ddl)
                try:
                    conn.execute(
                        f"ALTER TABLE [{table_name}] ADD COLUMN [{col_name}] {safe_ddl}"  # nosec B608
                    )
                    col_ref = f"{table_name}.{col_name}"
                    results["columns_added"].append(col_ref)
                    logger.info("schema_engine: added column %s", col_ref)
                except sqlite3.OperationalError as e:
                    err = f"ADD COLUMN {table_name}.{col_name}: {e}"
                    results["errors"].append(err)
                    logger.warning("schema_engine: %s", err)

    # ── Phase 2: Indexes ─────────────────────────────────────

    # Refresh object list after table creation
    existing_objects = _get_existing_tables(conn)

    for idx_name, idx_table, idx_cols, idx_where in schema.INDEXES:
        if idx_name in existing_indexes:
            continue

        # Skip index if target is a view
        if existing_objects.get(idx_table) == "view":
            continue

        # Skip index if target table doesn't exist
        if idx_table not in existing_objects:
            continue

        where_clause = f" WHERE {idx_where}" if idx_where else ""
        sql = f"CREATE INDEX IF NOT EXISTS [{idx_name}] ON [{idx_table}]({idx_cols}){where_clause}"
        try:
            conn.execute(sql)  # nosec B608
            results["indexes_created"].append(idx_name)
        except sqlite3.OperationalError as e:
            err = f"CREATE INDEX {idx_name}: {e}"
            results["errors"].append(err)
            logger.warning("schema_engine: %s", err)

    # ── Phase 3: Data migrations ─────────────────────────────

    for table, target_col, source_expr, where_cond in schema.DATA_MIGRATIONS:
        if table not in existing_objects:
            continue
        if existing_objects[table] == "view":
            continue

        # Only run if both source and target columns exist
        cols = _get_existing_columns(conn, table)
        if target_col not in cols:
            continue
        # source_expr might be a column name or an expression; check simple case
        if source_expr in schema.TABLES.get(table, {}).get("columns_set", set()):
            if source_expr not in cols:
                continue

        sql = f"UPDATE [{table}] SET [{target_col}] = [{source_expr}] WHERE {where_cond}"  # noqa: S608  # nosec B608
        try:
            cursor = conn.execute(sql)
            if cursor.rowcount > 0:
                migration_ref = f"{table}.{target_col} <- {source_expr}"
                results["data_migrations_run"].append(f"{migration_ref} ({cursor.rowcount} rows)")
                logger.info(
                    "schema_engine: data migration %s updated %d rows",
                    migration_ref,
                    cursor.rowcount,
                )
        except sqlite3.OperationalError as e:
            err = f"DATA MIGRATION {table}.{target_col}: {e}"
            results["errors"].append(err)
            logger.warning("schema_engine: %s", err)

    # ── Phase 4: Schema version ──────────────────────────────

    conn.execute(f"PRAGMA user_version = {schema.SCHEMA_VERSION}")  # nosec B608

    results["schema_version"] = schema.SCHEMA_VERSION
    return results


# ────────────────────────────────────────────────────────────
# create_fresh — for new databases and test fixtures
# ────────────────────────────────────────────────────────────


def create_fresh(conn: sqlite3.Connection) -> dict:
    """
    Create all tables from scratch in an empty database.

    Drops ALL existing tables and views first.  Use only for:
      - Brand-new databases
      - Test fixtures (fixture_db.py)

    Does NOT run data migrations (no data to migrate in a fresh DB).
    """
    results = {"tables_created": [], "indexes_created": [], "errors": []}

    # Drop everything (order matters for foreign keys)
    cursor = conn.execute(
        "SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view') "
        "AND name NOT LIKE 'sqlite_%'"
    )
    existing = cursor.fetchall()

    # Drop views first, then tables
    for name, obj_type in existing:
        if obj_type == "view":
            conn.execute(f"DROP VIEW IF EXISTS [{name}]")  # nosec B608
    for name, obj_type in existing:
        if obj_type == "table":
            conn.execute(f"DROP TABLE IF EXISTS [{name}]")  # nosec B608

    # Create all tables
    for table_name, table_def in schema.TABLES.items():
        # For fresh DB, skip tables marked as skip_if_view — they need
        # their VIEW created, not a table. But since we don't have the
        # legacy data to view from, just create the table.
        create_sql = _build_create_sql(table_name, table_def)
        try:
            conn.execute(create_sql)
            results["tables_created"].append(table_name)
        except sqlite3.OperationalError as e:
            err = f"CREATE TABLE {table_name}: {e}"
            results["errors"].append(err)
            logger.warning("schema_engine: create_fresh %s", err)

    # Create all indexes (no views in fresh DB, so no skipping needed)
    for idx_name, idx_table, idx_cols, idx_where in schema.INDEXES:
        where_clause = f" WHERE {idx_where}" if idx_where else ""
        sql = f"CREATE INDEX IF NOT EXISTS [{idx_name}] ON [{idx_table}]({idx_cols}){where_clause}"
        try:
            conn.execute(sql)  # nosec B608
            results["indexes_created"].append(idx_name)
        except sqlite3.OperationalError as e:
            err = f"CREATE INDEX {idx_name}: {e}"
            results["errors"].append(err)
            logger.warning("schema_engine: create_fresh index %s", err)

    # Set schema version
    conn.execute(f"PRAGMA user_version = {schema.SCHEMA_VERSION}")  # nosec B608

    results["schema_version"] = schema.SCHEMA_VERSION
    return results
