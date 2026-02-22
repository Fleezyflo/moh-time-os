"""
SQL Dialect Translation.

Converts SQL between SQLite and PostgreSQL dialects.

Supported translations:
- AUTOINCREMENT → SERIAL/GENERATED ALWAYS
- INTEGER PRIMARY KEY → SERIAL PRIMARY KEY
- datetime('now') → NOW()
- GROUP_CONCAT → STRING_AGG
- IFNULL → COALESCE
- SUBSTR → SUBSTRING
- GLOB → SIMILAR TO
- Boolean handling (0/1 → true/false)
- || string concatenation (works in both)

Functions:
- translate_sqlite_to_pg(sql): Convert SQLite SQL to PostgreSQL
- translate_pg_to_sqlite(sql): Convert PostgreSQL SQL to SQLite
- detect_dialect(sql): Detect which dialect SQL uses
"""

import logging
import re
from typing import Literal

logger = logging.getLogger(__name__)


def translate_sqlite_to_pg(sql: str) -> str:
    """
    Convert SQLite-specific SQL to PostgreSQL.

    Handles:
    - AUTOINCREMENT → SERIAL
    - INTEGER PRIMARY KEY → SERIAL PRIMARY KEY
    - datetime('now') → NOW()
    - GROUP_CONCAT(...) → STRING_AGG(...)
    - IFNULL(a, b) → COALESCE(a, b)
    - SUBSTR(a, b, c) → SUBSTRING(a, b, c)
    - GLOB pattern → SIMILAR TO pattern
    - Boolean conversion (0 → false, 1 → true)

    Args:
        sql: SQLite SQL statement

    Returns:
        PostgreSQL SQL statement
    """
    result = sql

    # AUTOINCREMENT → SERIAL
    result = re.sub(
        r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b",
        "SERIAL PRIMARY KEY",
        result,
        flags=re.IGNORECASE,
    )

    # INTEGER PRIMARY KEY (not AUTOINCREMENT) → SERIAL PRIMARY KEY
    result = re.sub(
        r"\bINTEGER\s+PRIMARY\s+KEY\b",
        "SERIAL PRIMARY KEY",
        result,
        flags=re.IGNORECASE,
    )

    # datetime('now') → NOW()
    result = re.sub(
        r"datetime\s*\(\s*['\"]now['\"]\s*\)",
        "NOW()",
        result,
        flags=re.IGNORECASE,
    )

    # GROUP_CONCAT(col) → STRING_AGG(col, ',')
    result = re.sub(
        r"GROUP_CONCAT\s*\(\s*([^,)]+)\s*\)",
        r"STRING_AGG(\1, ',')",
        result,
        flags=re.IGNORECASE,
    )

    # GROUP_CONCAT(col, sep) → STRING_AGG(col, sep)
    result = re.sub(
        r"GROUP_CONCAT\s*\(\s*([^,]+)\s*,\s*(['\"][^'\"]*['\"]\s*)\)",
        r"STRING_AGG(\1, \2)",
        result,
        flags=re.IGNORECASE,
    )

    # IFNULL(a, b) → COALESCE(a, b)
    result = re.sub(
        r"IFNULL\s*\(\s*([^,]+)\s*,\s*([^)]+)\)",
        r"COALESCE(\1, \2)",
        result,
        flags=re.IGNORECASE,
    )

    # SUBSTR(a, b, c) → SUBSTRING(a, b, c)
    result = re.sub(
        r"\bSUBSTR\s*\(",
        "SUBSTRING(",
        result,
        flags=re.IGNORECASE,
    )

    # GLOB pattern → SIMILAR TO pattern
    # Convert GLOB to SIMILAR TO (PostgreSQL pattern syntax is different)
    # GLOB uses * (any chars) and ? (one char)
    # SIMILAR TO uses % (any chars) and _ (one char)
    result = re.sub(
        r"(\w+)\s+GLOB\s+(['\"][^'\"]*['\"])",
        lambda m: _convert_glob_to_similar(m.group(1), m.group(2)),
        result,
        flags=re.IGNORECASE,
    )

    # Boolean literals: 0 → false, 1 → true (in specific contexts)
    # Only convert in specific boolean contexts, not in numbers
    # This is conservative to avoid breaking numeric literals
    result = re.sub(
        r"\bCHECK\s*\(\s*(\w+)\s*IN\s*\(\s*0\s*,\s*1\s*\)\s*\)",
        r"CHECK (\1 IN (false, true))",
        result,
        flags=re.IGNORECASE,
    )

    return result


def _convert_glob_to_similar(column: str, pattern: str) -> str:
    """
    Convert GLOB pattern to SIMILAR TO pattern.

    GLOB: * = any chars, ? = one char
    SIMILAR TO: % = any chars, _ = one char

    Args:
        column: Column name
        pattern: Pattern string with quotes

    Returns:
        Converted pattern clause
    """
    # Remove quotes, convert pattern, re-add quotes
    inner = pattern[1:-1]  # Remove surrounding quotes
    quote_char = pattern[0]

    # Replace GLOB wildcards with SIMILAR TO wildcards
    converted = inner.replace("*", "%").replace("?", "_")

    return f"{column} SIMILAR TO {quote_char}{converted}{quote_char}"


def translate_pg_to_sqlite(sql: str) -> str:
    """
    Convert PostgreSQL-specific SQL to SQLite.

    Handles:
    - SERIAL → INTEGER PRIMARY KEY AUTOINCREMENT
    - NOW() → datetime('now')
    - STRING_AGG(..., ',') → GROUP_CONCAT(...)
    - COALESCE(a, b) → IFNULL(a, b) (COALESCE also works in SQLite 3.32+)
    - SUBSTRING(a, b, c) → SUBSTR(a, b, c)
    - SIMILAR TO pattern → GLOB pattern
    - Boolean literals (true/false) → 1/0

    Args:
        sql: PostgreSQL SQL statement

    Returns:
        SQLite SQL statement
    """
    result = sql

    # SERIAL → INTEGER PRIMARY KEY AUTOINCREMENT
    result = re.sub(
        r"\bSERIAL\s+PRIMARY\s+KEY\b",
        "INTEGER PRIMARY KEY AUTOINCREMENT",
        result,
        flags=re.IGNORECASE,
    )

    # NOW() → datetime('now')
    result = re.sub(
        r"\bNOW\s*\(\s*\)",
        "datetime('now')",
        result,
        flags=re.IGNORECASE,
    )

    # STRING_AGG(col, sep) → GROUP_CONCAT(col, sep)
    result = re.sub(
        r"STRING_AGG\s*\(\s*([^,]+)\s*,\s*(['\"][^'\"]*['\"]\s*)\)",
        r"GROUP_CONCAT(\1, \2)",
        result,
        flags=re.IGNORECASE,
    )

    # SUBSTRING(a, b, c) → SUBSTR(a, b, c)
    result = re.sub(
        r"\bSUBSTRING\s*\(",
        "SUBSTR(",
        result,
        flags=re.IGNORECASE,
    )

    # SIMILAR TO pattern → GLOB pattern
    result = re.sub(
        r"(\w+)\s+SIMILAR\s+TO\s+(['\"][^'\"]*['\"])",
        lambda m: _convert_similar_to_glob(m.group(1), m.group(2)),
        result,
        flags=re.IGNORECASE,
    )

    # Boolean literals: true → 1, false → 0
    result = re.sub(r"\btrue\b", "1", result, flags=re.IGNORECASE)
    result = re.sub(r"\bfalse\b", "0", result, flags=re.IGNORECASE)

    return result


def _convert_similar_to_glob(column: str, pattern: str) -> str:
    """
    Convert SIMILAR TO pattern to GLOB pattern.

    SIMILAR TO: % = any chars, _ = one char
    GLOB: * = any chars, ? = one char

    Args:
        column: Column name
        pattern: Pattern string with quotes

    Returns:
        Converted pattern clause
    """
    # Remove quotes, convert pattern, re-add quotes
    inner = pattern[1:-1]  # Remove surrounding quotes
    quote_char = pattern[0]

    # Replace SIMILAR TO wildcards with GLOB wildcards
    converted = inner.replace("%", "*").replace("_", "?")

    return f"{column} GLOB {quote_char}{converted}{quote_char}"


def detect_dialect(sql: str) -> Literal["sqlite", "postgresql", "standard"]:
    """
    Detect which SQL dialect is used.

    Returns:
        'sqlite' if SQLite-specific syntax detected
        'postgresql' if PostgreSQL-specific syntax detected
        'standard' if no dialect-specific features detected

    Args:
        sql: SQL statement to analyze

    Returns:
        Dialect identifier
    """
    sql.upper()

    # SQLite-specific patterns
    sqlite_patterns = [
        r"\bAUTOINCREMENT\b",
        r"datetime\s*\(\s*['\"]now['\"]\s*\)",
        r"\bGROUP_CONCAT\b",
        r"\bIFNULL\b",
        r"\bGLOB\b",
    ]

    # PostgreSQL-specific patterns
    postgresql_patterns = [
        r"\bSERIAL\b",
        r"\bNOW\s*\(\)",
        r"\bSTRING_AGG\b",
        r"\bSIMILAR\s+TO\b",
        r"\bcreate\s+extension\b",
        r"\bCREATE\s+EXTENSION\b",
    ]

    # Check for SQLite patterns
    for pattern in sqlite_patterns:
        if re.search(pattern, sql, re.IGNORECASE):
            return "sqlite"

    # Check for PostgreSQL patterns
    for pattern in postgresql_patterns:
        if re.search(pattern, sql, re.IGNORECASE):
            return "postgresql"

    # Standard SQL
    return "standard"
