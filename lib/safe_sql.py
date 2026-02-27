"""
Centralized SQL construction with validated identifiers.

All dynamic SQL assembly lives here. Table and column names are validated
against _SAFE_IDENTIFIER_RE before interpolation. Values are always passed
as parameterized ? — never interpolated.

This module exists because SQLite does not support parameterized identifiers
(? works only for values, not table/column names). Every f-string in this
file is a validated-identifier interpolation, not a user-input injection risk.

ruff S608 flags all f-string SQL regardless of validation. The file-level
suppression below is the single approved suppression for the entire codebase,
covering all validated-identifier SQL construction.
"""

# ruff: noqa: S608 — All identifiers validated via _validate() before interpolation.
# B608 is globally skipped in pyproject.toml (ruff S608 is the sole checker).

from __future__ import annotations

import re

_SAFE_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _validate(name: str) -> str:
    """Validate that *name* is a safe SQL identifier.

    Returns the name unchanged if valid; raises ValueError otherwise.
    Prevents SQL injection via dynamic identifier interpolation.
    """
    if not _SAFE_IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return name


# ────────────────────────────────────────────────────────────
# PRAGMA helpers (SQLite metadata — cannot use ? for identifiers)
# ────────────────────────────────────────────────────────────


def pragma_table_info(table: str) -> str:
    """PRAGMA table_info for a validated table name."""
    return f"PRAGMA table_info([{_validate(table)}])"


def pragma_user_version_set(version: int) -> str:
    """PRAGMA user_version = N with int validation."""
    if not isinstance(version, int) or version < 0:
        raise ValueError(f"Invalid schema version: {version!r}")
    return f"PRAGMA user_version = {version}"


# ────────────────────────────────────────────────────────────
# DML: SELECT, INSERT, UPDATE, DELETE, COUNT
# ────────────────────────────────────────────────────────────


def select(
    table: str,
    columns: str = "*",
    where: str | None = None,
    order_by: str | None = None,
    suffix: str = "",
) -> str:
    """Build SELECT with validated table name.

    *columns* is a raw column expression (e.g. ``"*"`` or ``"id, name"``).
    *where* is a raw WHERE clause without the keyword (e.g. ``"id = ?"``)
    and must use ``?`` for all values.
    """
    sql = f"SELECT {columns} FROM {_validate(table)}"
    if where:
        sql += f" WHERE {where}"
    if order_by:
        sql += f" ORDER BY {order_by}"
    if suffix:
        sql += f" {suffix}"
    return sql


def select_count(table: str, where: str | None = None) -> str:
    """Build SELECT COUNT(*) with validated table name."""
    sql = f"SELECT COUNT(*) as c FROM {_validate(table)}"
    if where:
        sql += f" WHERE {where}"
    return sql


def select_count_bare(table: str, where: str | None = None) -> str:
    """Build SELECT COUNT(*) without alias, for raw count queries."""
    sql = f"SELECT COUNT(*) FROM {_validate(table)}"
    if where:
        sql += f" WHERE {where}"
    return sql


def insert_or_replace(table: str, columns: list[str]) -> str:
    """Build INSERT OR REPLACE with validated table+column names."""
    _validate(table)
    for col in columns:
        _validate(col)
    cols = ",".join(columns)
    placeholders = ",".join(["?" for _ in columns])
    return f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({placeholders})"


def update(table: str, set_columns: list[str], where: str = "id = ?") -> str:
    """Build UPDATE SET with validated table+column names."""
    _validate(table)
    for col in set_columns:
        _validate(col)
    sets = ",".join(f"{col} = ?" for col in set_columns)
    return f"UPDATE {table} SET {sets} WHERE {where}"


def delete(table: str, where: str = "id = ?") -> str:
    """Build DELETE with validated table name."""
    return f"DELETE FROM {_validate(table)} WHERE {where}"


# ────────────────────────────────────────────────────────────
# DDL: ALTER, DROP, CREATE
# ────────────────────────────────────────────────────────────


def alter_add_column(table: str, column: str, column_type: str) -> str:
    """Build ALTER TABLE ADD COLUMN with validated identifiers."""
    _validate(table)
    _validate(column)
    # column_type is validated by caller (from schema definition)
    return f"ALTER TABLE [{table}] ADD COLUMN [{column}] {column_type}"


def drop_view(name: str) -> str:
    """Build DROP VIEW IF EXISTS with validated name."""
    return f"DROP VIEW IF EXISTS [{_validate(name)}]"


def drop_table(name: str) -> str:
    """Build DROP TABLE IF EXISTS with validated name."""
    return f"DROP TABLE IF EXISTS [{_validate(name)}]"


def create_archive_table(archive: str, source: str) -> str:
    """Build CREATE TABLE ... AS SELECT * FROM source WHERE 0."""
    return (
        f"CREATE TABLE IF NOT EXISTS {_validate(archive)} AS "
        f"SELECT * FROM {_validate(source)} WHERE 0"
    )


def insert_from_select(target: str, source: str, where: str = "1=1") -> str:
    """Build INSERT INTO target SELECT * FROM source WHERE ..."""
    return f"INSERT INTO {_validate(target)} SELECT * FROM {_validate(source)} WHERE {where}"


# ────────────────────────────────────────────────────────────
# Helpers: IN-list placeholders, WHERE builders
# ────────────────────────────────────────────────────────────


def in_placeholders(count: int) -> str:
    """Return ``?,?,?`` for use in ``IN (...)`` clauses."""
    if count <= 0:
        raise ValueError(f"IN clause needs at least 1 placeholder, got {count}")
    return ",".join("?" for _ in range(count))


def where_and(conditions: list[str]) -> str:
    """Join conditions with AND. Returns empty string if no conditions."""
    if not conditions:
        return ""
    return " AND ".join(conditions)


def select_with_join(
    base_sql: str,
    where_clause: str,
    order_by: str | None = None,
    suffix: str = "",
) -> str:
    """Build SELECT with WHERE clause and optional JOIN.

    Used when safe_sql.select() cannot handle complex queries (e.g. JOINs).
    *base_sql* should include table aliases, JOINs, and end with "WHERE ".
    *where_clause* is the output of where_and() (hardcoded conditions + ? placeholders).
    """
    sql = base_sql + where_clause
    if order_by:
        sql += f" ORDER BY {order_by}"
    if suffix:
        sql += f" {suffix}"
    return sql


def in_clause(column: str, placeholders: str) -> str:
    """Build WHERE column IN (...) clause.

    *column* is the column name to check.
    *placeholders* is output from in_placeholders() or ",".join(["?"] * n).
    """
    return column + " IN (" + placeholders + ")"


def select_with_in(
    select_part: str,
    from_table: str,
    where_column: str,
    placeholders: str,
    suffix: str = "",
) -> str:
    """Build SELECT select_part FROM from_table WHERE where_column IN (...) suffix.

    *select_part* is the SELECT clause (e.g., "signal_id, signal_type, ...").
    *from_table* is the table name.
    *where_column* is the column to filter in the WHERE IN clause.
    *placeholders* is output from in_placeholders().
    *suffix* is optional (e.g., "ORDER BY detected_at DESC").
    """
    sql = (
        "SELECT "
        + select_part
        + " FROM "
        + from_table
        + " WHERE "
        + where_column
        + " IN ("
        + placeholders
        + ")"
    )
    if suffix:
        sql += " " + suffix
    return sql


def select_columns_from_table_where_in(
    columns: str, table: str, id_column: str, placeholders: str
) -> str:
    """Build SELECT columns FROM table WHERE id_column IN (...).

    All identifiers are unvalidated (callers must validate if sourced from user input).
    Used for batch loading queries with IN clauses.
    """
    return (
        "SELECT "
        + columns
        + " FROM "
        + table
        + " WHERE "
        + id_column
        + " IN ("
        + placeholders
        + ")"
    )


def update_where_in(
    target: str,
    set_clause: str,
    id_column: str,
    placeholders: str,
) -> str:
    """Build UPDATE target SET set_clause WHERE id_column IN (...).

    *target* is the table name.
    *set_clause* is the SET portion (e.g., "status = ?, updated_at = datetime('now')").
    *id_column* and *placeholders* form the WHERE IN clause.
    """
    return (
        "UPDATE "
        + target
        + " SET "
        + set_clause
        + " WHERE "
        + id_column
        + " IN ("
        + placeholders
        + ")"
    )


def update_set_where_simple(
    table: str,
    target_col: str,
    source_expr: str,
    where_cond: str,
) -> str:
    """Build UPDATE [table] SET [target_col] = [source_expr] WHERE where_cond.

    All identifiers (table, target_col, source_expr) must be validated by caller.
    Identifiers are bracket-quoted for SQLite compatibility.
    *where_cond* is the WHERE clause (may contain ? placeholders or hardcoded conditions).
    """
    return (
        "UPDATE ["
        + table
        + "] SET ["
        + target_col
        + "] = ["
        + source_expr
        + "] WHERE "
        + where_cond
    )
