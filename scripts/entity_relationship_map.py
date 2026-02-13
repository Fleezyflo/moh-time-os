#!/usr/bin/env python3
"""
Entity Relationship Map for MOH TIME OS.
Task: SYSPREP 2.1 — Entity Relationship Map
"""

import sqlite3
import re
from datetime import datetime
from pathlib import Path
from collections import defaultdict

REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "data"
DB_PATH = DATA_DIR / "moh_time_os.db"

# Core entities from schema audit
CORE_ENTITIES = {
    "Client": "clients",
    "Project": "projects",
    "Task": "tasks",
    "Person": "people",
    "Gmail": None,  # Need to find the actual table
    "Chat": None,   # Need to find the actual table
    "Calendar": "calendar_events",
    "Drive": None,  # Need to find the actual table
    "Invoice": "invoices",
    "Issue": "issues",
    "Inbox": "inbox_items_v29",
}


def get_table_info(conn: sqlite3.Connection, table: str) -> dict:
    """Get table schema information."""
    cursor = conn.execute(f'PRAGMA table_info("{table}")')
    columns = []
    pk = None
    for row in cursor.fetchall():
        col = {
            "name": row[1],
            "type": row[2],
            "notnull": bool(row[3]),
            "pk": bool(row[5])
        }
        columns.append(col)
        if col["pk"]:
            pk = col["name"]

    # Get foreign keys
    cursor = conn.execute(f'PRAGMA foreign_key_list("{table}")')
    fks = []
    for row in cursor.fetchall():
        fks.append({
            "from_col": row[3],
            "to_table": row[2],
            "to_col": row[4]
        })

    # Get row count
    try:
        cursor = conn.execute(f'SELECT COUNT(*) FROM "{table}"')
        row_count = cursor.fetchone()[0]
    except:
        row_count = 0

    return {
        "table": table,
        "columns": columns,
        "primary_key": pk,
        "foreign_keys": fks,
        "row_count": row_count
    }


def find_entity_tables(conn: sqlite3.Connection) -> dict:
    """Find actual table names for each entity type."""
    # Get all tables
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    all_tables = [row[0] for row in cursor.fetchall()]

    entity_tables = {}

    # Direct mappings
    for entity, table in CORE_ENTITIES.items():
        if table and table in all_tables:
            entity_tables[entity] = table
        elif table is None:
            # Try to find matching table
            entity_lower = entity.lower()
            for t in all_tables:
                if entity_lower in t.lower():
                    entity_tables[entity] = t
                    break

    # Manual fixes based on known schema
    if "Gmail" not in entity_tables:
        for t in all_tables:
            if "gmail" in t.lower() or "email" in t.lower() or "message" in t.lower():
                entity_tables["Gmail"] = t
                break

    if "Chat" not in entity_tables:
        for t in all_tables:
            if "chat" in t.lower() or "gchat" in t.lower():
                entity_tables["Chat"] = t
                break

    if "Drive" not in entity_tables:
        for t in all_tables:
            if "drive" in t.lower() or "file" in t.lower():
                entity_tables["Drive"] = t
                break

    return entity_tables


def find_implicit_relationships(table_info: dict, target_tables: list) -> list:
    """Find columns that might implicitly reference other tables."""
    implicit = []

    for col in table_info["columns"]:
        name = col["name"].lower()

        # ID columns
        if name.endswith("_id") and name != "id":
            base = name[:-3]
            for target in target_tables:
                if base in target.lower():
                    implicit.append({
                        "column": col["name"],
                        "target_table": target,
                        "match_type": "id_column"
                    })

        # Email columns
        if "email" in name:
            implicit.append({
                "column": col["name"],
                "target_table": "people",
                "match_type": "email_field"
            })

        # Name columns might match people
        if name in ["owner", "assignee", "creator", "author"]:
            implicit.append({
                "column": col["name"],
                "target_table": "people",
                "match_type": "person_reference"
            })

    return implicit


def analyze_relationships(conn: sqlite3.Connection, entity_tables: dict) -> dict:
    """Analyze relationships between all entity tables."""

    # Get info for each entity table
    table_info = {}
    for entity, table in entity_tables.items():
        if table:
            table_info[entity] = get_table_info(conn, table)

    # Build relationship matrix
    relationships = {}
    entities = list(entity_tables.keys())

    for from_entity in entities:
        if from_entity not in table_info:
            continue

        relationships[from_entity] = {}
        from_info = table_info[from_entity]

        for to_entity in entities:
            if from_entity == to_entity:
                relationships[from_entity][to_entity] = {"type": "-", "path": ""}
                continue

            if to_entity not in entity_tables or not entity_tables[to_entity]:
                relationships[from_entity][to_entity] = {"type": "UNKNOWN", "path": "No table found"}
                continue

            to_table = entity_tables[to_entity]

            # Check for direct FK
            direct_fk = None
            for fk in from_info["foreign_keys"]:
                if fk["to_table"] == to_table:
                    direct_fk = fk
                    break

            if direct_fk:
                relationships[from_entity][to_entity] = {
                    "type": "DIRECT",
                    "path": f'{entity_tables[from_entity]}.{direct_fk["from_col"]} = {to_table}.{direct_fk["to_col"]}'
                }
                continue

            # Check for implicit relationship
            implicit = find_implicit_relationships(from_info, [to_table])
            if implicit:
                relationships[from_entity][to_entity] = {
                    "type": "IMPLICIT",
                    "path": f'{entity_tables[from_entity]}.{implicit[0]["column"]} → {to_table} ({implicit[0]["match_type"]})'
                }
                continue

            # Check reverse direction
            if to_entity in table_info:
                to_info = table_info[to_entity]
                for fk in to_info["foreign_keys"]:
                    if fk["to_table"] == entity_tables[from_entity]:
                        relationships[from_entity][to_entity] = {
                            "type": "REVERSE",
                            "path": f'{to_table}.{fk["from_col"]} = {entity_tables[from_entity]}.{fk["to_col"]} (reverse)'
                        }
                        break
                else:
                    # Check for common links through entity_links table
                    try:
                        cursor = conn.execute("SELECT name FROM sqlite_master WHERE name='entity_links'")
                        if cursor.fetchone():
                            relationships[from_entity][to_entity] = {
                                "type": "INDIRECT",
                                "path": f"Via entity_links table"
                            }
                        else:
                            relationships[from_entity][to_entity] = {"type": "MISSING", "path": ""}
                    except:
                        relationships[from_entity][to_entity] = {"type": "MISSING", "path": ""}
            else:
                relationships[from_entity][to_entity] = {"type": "MISSING", "path": ""}

    return relationships, table_info


def generate_report(entity_tables: dict, relationships: dict, table_info: dict) -> str:
    """Generate the relationship map report."""
    date_str = datetime.now().strftime("%Y-%m-%d")

    lines = [
        f"# Entity Relationship Map — {date_str}",
        "",
        "## Core Entities",
        "| Entity | Table | Primary Key | Row Count |",
        "|--------|-------|-------------|-----------|",
    ]

    for entity, table in sorted(entity_tables.items()):
        if table and entity in table_info:
            info = table_info[entity]
            lines.append(f"| {entity} | `{table}` | {info['primary_key']} | {info['row_count']:,} |")
        else:
            lines.append(f"| {entity} | _(not found)_ | — | — |")

    lines.extend([
        "",
        "## Relationship Matrix",
        "",
        "Legend: DIRECT (FK), IMPLICIT (joinable field), REVERSE (FK from target), INDIRECT (via junction), MISSING (no path), UNKNOWN (table not found)",
        "",
    ])

    # Build matrix header
    entities = list(entity_tables.keys())
    header = "| From \\ To |"
    for e in entities:
        header += f" {e[:4]} |"
    lines.append(header)

    sep = "|-----------|"
    for _ in entities:
        sep += "------|"
    lines.append(sep)

    # Matrix rows
    for from_entity in entities:
        row = f"| {from_entity} |"
        for to_entity in entities:
            if from_entity not in relationships:
                cell = "?"
            elif to_entity not in relationships[from_entity]:
                cell = "?"
            else:
                rel = relationships[from_entity][to_entity]
                cell = rel["type"][:4] if rel["type"] else "?"
        row += f" {cell:4} |"
        lines.append(row)

    # Connection paths
    lines.extend([
        "",
        "## Connection Paths (Documented)",
        "",
    ])

    for from_entity in sorted(relationships.keys()):
        for to_entity in sorted(relationships[from_entity].keys()):
            rel = relationships[from_entity][to_entity]
            if rel["type"] not in ["-", "MISSING", "UNKNOWN", ""]:
                lines.append(f"- **{from_entity} → {to_entity}**: {rel['type']} — `{rel['path']}`")

    # Missing connections
    lines.extend([
        "",
        "## Missing Connections",
        "| From | To | Priority | Data Needed | Resolution Path |",
        "|------|-----|----------|-------------|-----------------|",
    ])

    priority_map = {
        ("Client", "Gmail"): "HIGH",
        ("Client", "Calendar"): "HIGH",
        ("Project", "Person"): "HIGH",
        ("Task", "Person"): "HIGH",
        ("Invoice", "Project"): "MEDIUM",
        ("Issue", "Client"): "HIGH",
    }

    for from_entity in sorted(relationships.keys()):
        for to_entity in sorted(relationships[from_entity].keys()):
            rel = relationships[from_entity][to_entity]
            if rel["type"] == "MISSING":
                priority = priority_map.get((from_entity, to_entity), "LOW")
                lines.append(f"| {from_entity} | {to_entity} | {priority} | FK or junction table | Create relationship in schema |")

    # Key findings
    lines.extend([
        "",
        "## Key Findings",
        "",
        "### What We Can Traverse",
    ])

    direct_count = 0
    implicit_count = 0
    indirect_count = 0
    missing_count = 0

    for from_entity in relationships:
        for to_entity in relationships[from_entity]:
            rel_type = relationships[from_entity][to_entity]["type"]
            if rel_type == "DIRECT":
                direct_count += 1
            elif rel_type == "IMPLICIT":
                implicit_count += 1
            elif rel_type == "INDIRECT" or rel_type == "REVERSE":
                indirect_count += 1
            elif rel_type == "MISSING":
                missing_count += 1

    lines.extend([
        f"- Direct FK relationships: {direct_count}",
        f"- Implicit relationships: {implicit_count}",
        f"- Indirect/reverse relationships: {indirect_count}",
        f"- Missing relationships: {missing_count}",
        "",
        "### Critical Gaps",
        "- Many entity pairs lack direct relationships",
        "- The `entity_links` table may provide indirect connections",
        "- Email-based matching can connect people to communications",
        "",
        "### Recommendations",
        "1. Review `entity_links` table for existing junction relationships",
        "2. Consider adding views that normalize implicit relationships",
        "3. Prioritize HIGH-priority missing connections for Phase 2.3",
    ])

    return "\n".join(lines)


def main():
    print("Generating Entity Relationship Map...")

    conn = sqlite3.connect(str(DB_PATH))

    # Find entity tables
    print("Finding entity tables...")
    entity_tables = find_entity_tables(conn)

    for entity, table in entity_tables.items():
        if table:
            print(f"  {entity}: {table}")
        else:
            print(f"  {entity}: NOT FOUND")

    # Analyze relationships
    print("\nAnalyzing relationships...")
    relationships, table_info = analyze_relationships(conn, entity_tables)

    # Generate report
    print("Generating report...")
    report = generate_report(entity_tables, relationships, table_info)

    # Save
    date_str = datetime.now().strftime("%Y%m%d")
    output_file = DATA_DIR / f"entity_relationship_map_{date_str}.md"
    output_file.write_text(report)

    conn.close()

    print(f"\n✓ Report saved to: {output_file}")

    # Summary
    direct = sum(1 for f in relationships for t in relationships[f] if relationships[f][t]["type"] == "DIRECT")
    implicit = sum(1 for f in relationships for t in relationships[f] if relationships[f][t]["type"] == "IMPLICIT")
    indirect = sum(1 for f in relationships for t in relationships[f] if relationships[f][t]["type"] in ["INDIRECT", "REVERSE"])
    missing = sum(1 for f in relationships for t in relationships[f] if relationships[f][t]["type"] == "MISSING")

    print(f"\n=== RELATIONSHIP SUMMARY ===")
    print(f"Entities mapped:  {len(entity_tables)}")
    print(f"Direct (FK):      {direct}")
    print(f"Implicit:         {implicit}")
    print(f"Indirect/Reverse: {indirect}")
    print(f"Missing:          {missing}")


if __name__ == "__main__":
    main()
