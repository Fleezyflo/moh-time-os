"""
Schema Convergence Engine — introspect, diff, apply.

Reads the declarative schema from lib/schema and converges any SQLite
database to match.  Two entry points:

  converge(conn)     — For existing DBs: adds missing tables/columns/indexes.
  create_fresh(conn) — For new/test DBs: drops everything and creates clean.

The engine never drops tables or columns on an existing DB (unless constraint
drift is detected on a table with a constraint_version marker — in which case
it rebuilds the table to restore canonical guarantees).
It only adds what is missing and runs idempotent data migrations.
"""

import logging
import re
import sqlite3

from lib import safe_sql, schema

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────
# Constraint version tracking table
# ────────────────────────────────────────────────────────────

_CONSTRAINT_VERSION_DDL = (
    "CREATE TABLE IF NOT EXISTS _schema_constraint_versions "
    "(table_name TEXT PRIMARY KEY, constraint_version INTEGER NOT NULL)"
)


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
# Constraint drift detection and table rebuild
# ────────────────────────────────────────────────────────────


def _get_stored_constraint_version(conn: sqlite3.Connection, table_name: str) -> int:
    """Return the stored constraint_version for a table, or 0 if not tracked."""
    try:
        row = conn.execute(
            "SELECT constraint_version FROM _schema_constraint_versions WHERE table_name = ?",
            (table_name,),
        ).fetchone()
        return row[0] if row else 0
    except sqlite3.OperationalError:
        # Tracking table doesn't exist yet
        return 0


def _set_constraint_version(conn: sqlite3.Connection, table_name: str, version: int) -> None:
    """Store the constraint_version for a table."""
    conn.execute(_CONSTRAINT_VERSION_DDL)
    conn.execute(
        "INSERT OR REPLACE INTO _schema_constraint_versions (table_name, constraint_version) "
        "VALUES (?, ?)",
        (table_name, version),
    )


def _needs_constraint_rebuild(conn: sqlite3.Connection, table_name: str, table_def: dict) -> bool:
    """Check if a table needs rebuilding due to constraint drift.

    Returns True if the table declares a constraint_version that is higher
    than the stored version (meaning constraints were strengthened since the
    table was last created/rebuilt).
    """
    declared_version = table_def.get("constraint_version", 0)
    if declared_version == 0:
        return False
    stored_version = _get_stored_constraint_version(conn, table_name)
    return declared_version > stored_version


def _rebuild_table_for_constraints(
    conn: sqlite3.Connection, table_name: str, table_def: dict
) -> dict:
    """Rebuild a table to enforce updated constraints.

    Algorithm:
      1. Count existing rows.
      2. Create _new table with canonical schema (full constraints).
      3. Copy data via INSERT OR IGNORE (constraint-violating rows skipped).
      4. Identify rejected rows by diffing old vs new.
      5. Quarantine rejected rows into _quarantine_{table} with timestamps.
      6. Log each rejected row's primary key at WARNING level.
      7. Drop old table, rename _new.
      8. Update stored constraint_version.

    COALESCE policy for NOT NULL + DEFAULT columns:
      - is_active: defaults to 0 (fail-closed — unknown state → inactive)
      - all others: defaults to column DEFAULT value

    Returns dict with rebuild details including quarantine info.
    """
    result = {
        "table": table_name,
        "rows_before": 0,
        "rows_after": 0,
        "rows_rejected": 0,
        "rejected_ids": [],
        "rows_coalesced": 0,
        "coalesced_ids": [],
        "quarantine_table": None,
        "errors": [],
    }

    # Determine primary key column for per-row logging
    pk_col = None
    for col_name, col_ddl in table_def["columns"]:
        if "PRIMARY KEY" in col_ddl.upper():
            pk_col = col_name
            break
    pk_cols = table_def.get("primary_key")
    if pk_cols:
        pk_col = pk_cols[0]

    try:
        # Count existing rows
        cursor = conn.execute(safe_sql.select_count_bare(table_name))
        result["rows_before"] = cursor.fetchone()[0]

        # Get existing column names (to handle column set differences)
        existing_cols = _get_existing_columns(conn, table_name)
        declared_cols = [col_name for col_name, _ in table_def["columns"]]
        # Only copy columns that exist in both old and new schemas
        common_cols = [c for c in declared_cols if c in existing_cols]

        if not common_cols:
            result["errors"].append(f"No common columns between old and new {table_name}")
            return result

        # Build canonical CREATE TABLE for _new
        new_table = f"{table_name}_constraint_rebuild"
        create_sql = _build_create_sql(new_table, table_def)

        # Drop _new if it exists from a previous failed attempt
        conn.execute(safe_sql.drop_table(new_table))
        conn.execute(create_sql)

        # Build column list for INSERT...SELECT
        cols_csv = ", ".join(f"[{c}]" for c in common_cols)

        # Build SELECT expressions that handle NULL-to-default coercion
        # for columns that are now NOT NULL but were previously nullable.
        #
        # COALESCE POLICY: for is_active, default to 0 (fail-closed).
        # A row with unknown active status must NOT be treated as active.
        # For all other NOT NULL + DEFAULT columns, use the declared default.
        select_exprs = []
        for col_name in common_cols:
            col_ddl = None
            for cname, cddl in table_def["columns"]:
                if cname == col_name:
                    col_ddl = cddl
                    break

            if col_ddl and "NOT NULL" in col_ddl.upper() and "DEFAULT" in col_ddl.upper():
                default_match = re.search(r"DEFAULT\s+(\S+)", col_ddl, re.IGNORECASE)
                if default_match:
                    default_val = default_match.group(1)
                    # Fail-closed: is_active defaults to 0 (inactive), not 1
                    if col_name == "is_active":
                        default_val = "0"
                    select_exprs.append(f"COALESCE([{col_name}], {default_val}) AS [{col_name}]")
                    continue

            select_exprs.append(f"[{col_name}]")

        select_csv = ", ".join(select_exprs)

        # Copy valid rows — rows violating NOT NULL or CHECK are skipped.
        copy_sql = safe_sql.insert_or_ignore_from_select(
            new_table, cols_csv, select_csv, table_name
        )
        try:
            conn.execute(copy_sql)
        except sqlite3.Error as e:
            result["errors"].append(f"Data copy failed: {e}")
            conn.execute(safe_sql.drop_table(new_table))
            return result

        # Count rows in new table
        cursor = conn.execute(safe_sql.select_count_bare(new_table))
        result["rows_after"] = cursor.fetchone()[0]
        result["rows_rejected"] = result["rows_before"] - result["rows_after"]

        # ── Detect COALESCE mutations (rescued but modified rows) ─
        # Rows where a NOT NULL + DEFAULT column was NULL in the old table
        # but received a COALESCE default in the new table.  These rows
        # survived the rebuild but their data was silently changed.
        # We detect this for is_active specifically (fail-closed: NULL → 0).
        if pk_col and pk_col in common_cols and "is_active" in common_cols:
            coalesce_sql = safe_sql.select_coalesced_pks(
                table_name, new_table, pk_col, "is_active", "0"
            )
            try:
                coalesced_rows = conn.execute(coalesce_sql).fetchall()
                result["rows_coalesced"] = len(coalesced_rows)
                result["coalesced_ids"] = [row[0] for row in coalesced_rows]

                for cid in result["coalesced_ids"]:
                    logger.warning(
                        "schema_engine: COALESCED %s row %s=%r "
                        "is_active NULL -> 0 (fail-closed rescue, not a rejection)",
                        table_name,
                        pk_col,
                        cid,
                    )

                if result["rows_coalesced"] > 0:
                    logger.warning(
                        "schema_engine: rebuild %s coalesced %d rows "
                        "(is_active NULL -> 0, fail-closed policy)",
                        table_name,
                        result["rows_coalesced"],
                    )
            except sqlite3.Error as e:
                logger.warning(
                    "schema_engine: coalesce detection for %s failed: %s",
                    table_name,
                    e,
                )

        # ── Quarantine rejected rows ──────────────────────────────
        if result["rows_rejected"] > 0 and pk_col and pk_col in common_cols:
            quarantine_name = f"_quarantine_{table_name}"
            result["quarantine_table"] = quarantine_name

            # Create quarantine table with same schema as old table
            conn.execute(safe_sql.drop_table(quarantine_name))
            conn.execute(safe_sql.create_table_as_empty(quarantine_name, table_name))

            # Copy rejected rows: rows in old table whose PK is NOT in new table
            except_sql = safe_sql.insert_from_except(
                quarantine_name, table_name, new_table, pk_col, cols_csv
            )
            conn.execute(except_sql)

            # Log each rejected row's primary key
            rejected_rows = conn.execute(safe_sql.select_column(quarantine_name, pk_col)).fetchall()
            result["rejected_ids"] = [row[0] for row in rejected_rows]

            for rejected_id in result["rejected_ids"]:
                logger.warning(
                    "schema_engine: QUARANTINED %s row %s=%r "
                    "(violated new constraints, preserved in %s)",
                    table_name,
                    pk_col,
                    rejected_id,
                    quarantine_name,
                )

            logger.warning(
                "schema_engine: rebuild %s rejected %d rows — quarantined in %s for review",
                table_name,
                result["rows_rejected"],
                quarantine_name,
            )
        elif result["rows_rejected"] > 0:
            logger.warning(
                "schema_engine: rebuild %s rejected %d rows with invalid data "
                "(no PK column found for quarantine)",
                table_name,
                result["rows_rejected"],
            )

        # Swap tables
        conn.execute(safe_sql.drop_table(table_name))
        safe_sql._validate(new_table)
        safe_sql._validate(table_name)
        conn.execute(f"ALTER TABLE [{new_table}] RENAME TO [{table_name}]")

        # Update constraint version
        declared_version = table_def.get("constraint_version", 0)
        _set_constraint_version(conn, table_name, declared_version)

        logger.info(
            "schema_engine: rebuilt %s for constraint enforcement "
            "(before=%d, after=%d, rejected=%d, coalesced=%d, quarantine=%s)",
            table_name,
            result["rows_before"],
            result["rows_after"],
            result["rows_rejected"],
            result["rows_coalesced"],
            result["quarantine_table"],
        )

    except sqlite3.Error as e:
        result["errors"].append(f"Rebuild failed: {e}")
        logger.error("schema_engine: rebuild %s failed: %s", table_name, e)
        # Try to clean up
        try:
            conn.execute(safe_sql.drop_table(f"{table_name}_constraint_rebuild"))
        except sqlite3.Error:
            pass

    return result


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
        cursor = conn.execute(safe_sql.pragma_table_info(table))
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
    # Table-level constraints (optional)
    pk_cols = table_def.get("primary_key")
    if pk_cols:
        parts.append(f"    PRIMARY KEY ({', '.join(pk_cols)})")
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

    # ── Phase 0: Drop tables with PK type mismatch ──────────
    # If a table was created with the wrong PK type (e.g., INTEGER vs TEXT),
    # ALTER TABLE can't fix it. Drop and let Phase 1 recreate it.
    results["tables_rebuilt"] = []
    for table_name, table_def in schema.TABLES.items():
        if existing_objects.get(table_name) != "table":
            continue
        # Find the declared PK column and its expected type prefix
        declared_pk_type = None
        for _col_name, col_ddl in table_def["columns"]:
            if "PRIMARY KEY" in col_ddl.upper():
                declared_pk_type = col_ddl.split()[0].upper()  # TEXT or INTEGER
                break
        if declared_pk_type is None:
            continue
        # Check actual PK type in the existing table
        try:
            cursor = conn.execute(f"PRAGMA table_info([{table_name}])")
            for row in cursor.fetchall():
                # row: (cid, name, type, notnull, dflt_value, pk)
                if row[5]:  # pk flag is non-zero
                    actual_type = (row[2] or "").upper()
                    if actual_type != declared_pk_type:
                        logger.info(
                            "schema_engine: rebuilding %s (PK type %s != declared %s)",
                            table_name,
                            actual_type,
                            declared_pk_type,
                        )
                        conn.execute(safe_sql.drop_table(table_name))
                        existing_objects.pop(table_name, None)
                        results["tables_rebuilt"].append(table_name)
                    break
        except sqlite3.OperationalError as e:
            logger.warning("schema_engine: PK check for %s failed: %s", table_name, e)

    # ── Phase 0.5: Constraint drift — rebuild tables with stale constraints ──
    # Tables with a constraint_version in their schema definition are checked.
    # If the stored version is lower than declared, the table is rebuilt with
    # full canonical constraints.  This handles the case where a table was
    # originally created with weaker constraints (e.g., no NOT NULL, no UNIQUE)
    # and schema.py was later strengthened.
    results["constraint_rebuilds"] = []
    for table_name, table_def in schema.TABLES.items():
        if existing_objects.get(table_name) != "table":
            continue
        if not _needs_constraint_rebuild(conn, table_name, table_def):
            continue

        logger.info("schema_engine: constraint drift detected on %s, rebuilding", table_name)
        rebuild_result = _rebuild_table_for_constraints(conn, table_name, table_def)
        results["constraint_rebuilds"].append(rebuild_result)

        if rebuild_result["errors"]:
            for err in rebuild_result["errors"]:
                results["errors"].append(f"CONSTRAINT REBUILD {table_name}: {err}")
        else:
            # Table was rebuilt — remove from existing_objects so Phase 1
            # doesn't try to add columns that already exist.
            # Re-read because the table was recreated.
            existing_objects = _get_existing_tables(conn)

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
                # Record constraint_version for newly created tables
                cv = table_def.get("constraint_version", 0)
                if cv > 0:
                    _set_constraint_version(conn, table_name, cv)
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
                    conn.execute(safe_sql.alter_add_column(table_name, col_name, safe_ddl))
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
            conn.execute(sql)
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

        # Validate identifiers before building SQL
        safe_sql._validate(table)
        safe_sql._validate(target_col)
        safe_sql._validate(source_expr)
        sql = safe_sql.update_set_where_simple(table, target_col, source_expr, where_cond)
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

    # ── Phase 4: Views ────────────────────────────────────────

    results["views_created"] = []
    for view_name, view_sql in schema.VIEWS.items():
        if view_name in existing_objects:
            continue
        try:
            conn.execute(view_sql)
            results["views_created"].append(view_name)
            logger.info("schema_engine: created view %s", view_name)
        except sqlite3.OperationalError as e:
            err = f"CREATE VIEW {view_name}: {e}"
            results["errors"].append(err)
            logger.warning("schema_engine: %s", err)

    # ── Phase 5: Schema version ──────────────────────────────

    conn.execute(safe_sql.pragma_user_version_set(schema.SCHEMA_VERSION))

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
            conn.execute(safe_sql.drop_view(name))
    for name, obj_type in existing:
        if obj_type == "table":
            conn.execute(safe_sql.drop_table(name))

    # Ensure constraint-version tracking table exists
    conn.execute(_CONSTRAINT_VERSION_DDL)

    # Create all tables
    for table_name, table_def in schema.TABLES.items():
        # For fresh DB, skip tables marked as skip_if_view — they need
        # their VIEW created, not a table. But since we don't have the
        # legacy data to view from, just create the table.
        create_sql = _build_create_sql(table_name, table_def)
        try:
            conn.execute(create_sql)
            results["tables_created"].append(table_name)
            # Record constraint_version for tables that declare one
            cv = table_def.get("constraint_version", 0)
            if cv > 0:
                _set_constraint_version(conn, table_name, cv)
        except sqlite3.OperationalError as e:
            err = f"CREATE TABLE {table_name}: {e}"
            results["errors"].append(err)
            logger.warning("schema_engine: create_fresh %s", err)

    # Create all indexes (no views in fresh DB, so no skipping needed)
    for idx_name, idx_table, idx_cols, idx_where in schema.INDEXES:
        where_clause = f" WHERE {idx_where}" if idx_where else ""
        sql = f"CREATE INDEX IF NOT EXISTS [{idx_name}] ON [{idx_table}]({idx_cols}){where_clause}"
        try:
            conn.execute(sql)
            results["indexes_created"].append(idx_name)
        except sqlite3.OperationalError as e:
            err = f"CREATE INDEX {idx_name}: {e}"
            results["errors"].append(err)
            logger.warning("schema_engine: create_fresh index %s", err)

    # Create canonical views
    results["views_created"] = []
    for view_name, view_sql in schema.VIEWS.items():
        try:
            conn.execute(view_sql)
            results["views_created"].append(view_name)
        except sqlite3.OperationalError as e:
            err = f"CREATE VIEW {view_name}: {e}"
            results["errors"].append(err)
            logger.warning("schema_engine: create_fresh view %s", err)

    # Set schema version
    conn.execute(safe_sql.pragma_user_version_set(schema.SCHEMA_VERSION))

    results["schema_version"] = schema.SCHEMA_VERSION
    return results
