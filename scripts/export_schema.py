#!/usr/bin/env python3
"""
Export SQLite database schema to docs/schema.sql.

Usage:
    uv run python scripts/export_schema.py [--check]

    --check: Verify existing docs/schema.sql matches current schema (exit 1 if drift)
"""

import argparse
import re
import sqlite3
import sys
from pathlib import Path


def normalize_schema(schema: str) -> str:
    """Normalize schema for comparison (remove timestamps, whitespace variations)."""
    # Remove comments
    lines = [line for line in schema.split("\n") if not line.strip().startswith("--")]
    # Normalize whitespace
    schema = "\n".join(lines)
    schema = re.sub(r"\s+", " ", schema)
    schema = re.sub(r"\s*;\s*", ";\n", schema)
    return schema.strip()


def get_db_schema(db_path: Path) -> str:
    """Extract schema from SQLite database."""
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all table schemas
    cursor.execute(
        """
        SELECT sql FROM sqlite_master
        WHERE type IN ('table', 'index', 'trigger', 'view')
        AND sql IS NOT NULL
        ORDER BY type, name
    """
    )

    schemas = [row[0] for row in cursor.fetchall()]
    conn.close()

    return "\n\n".join(schemas) + "\n"


def get_expected_schema() -> str:
    """Get expected schema from lib/schema TABLES declaration."""
    from lib.schema import TABLES
    from lib.schema_engine import _build_create_sql

    statements = []
    for table_name, table_def in TABLES.items():
        statements.append(_build_create_sql(table_name, table_def))
    return "\n\n".join(statements) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Export database schema")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if docs/schema.sql is up to date (exit 1 if drift)",
    )
    parser.add_argument(
        "--output",
        default="docs/schema.sql",
        help="Output path (default: docs/schema.sql)",
    )
    parser.add_argument(
        "--source",
        choices=["db", "code"],
        default="code",
        help="Schema source: 'db' (from running DB) or 'code' (from migrations)",
    )
    args = parser.parse_args()

    output_path = Path(args.output)

    if args.source == "code":
        schema = get_expected_schema()
    else:
        # Use default DB path from lib.paths
        from lib import paths

        db_path = paths.get_db_path()
        schema = get_db_schema(Path(db_path))

    if args.check:
        if not output_path.exists():
            print(f"❌ {output_path} does not exist. Run without --check to generate.")
            return 1

        existing = output_path.read_text()
        if normalize_schema(existing) != normalize_schema(schema):
            print(f"❌ Schema drift detected! {output_path} is stale.")
            print("   Run: uv run python scripts/export_schema.py")
            return 1

        print(f"✅ {output_path} is up to date.")
        return 0

    # Generate mode
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(schema)
    print(f"✅ Exported schema to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
