#!/usr/bin/env python3
"""
Schema Audit for MOH TIME OS.
Task: SYSPREP 0.3 — Schema Audit
"""

import json
import logging
import re
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "data"
DB_PATH = DATA_DIR / "moh_time_os.db"

# Code directories to search
CODE_DIRS = ["lib", "api", "engine"]

# Core entities we need to map
CORE_ENTITIES = [
    "Clients",
    "Projects",
    "Tasks",
    "People/Contacts",
    "Gmail messages",
    "Chat messages",
    "Calendar events",
    "Drive files",
    "Invoices",
    "Issues",
    "Inbox items",
]


def load_baseline() -> dict:
    """Load the most recent baseline snapshot."""
    snapshots = list(DATA_DIR.glob("baseline_snapshot_*.json"))
    if not snapshots:
        raise FileNotFoundError("No baseline snapshot found")

    latest = max(snapshots, key=lambda p: p.stat().st_mtime)
    print(f"Loading baseline: {latest}")

    with open(latest) as f:
        return json.load(f)


def build_table_reference_index() -> dict:
    """Build index of which Python files reference each table name."""
    # Read all Python files once
    all_py_content = {}
    for code_dir in CODE_DIRS:
        dir_path = REPO_ROOT / code_dir
        if not dir_path.exists():
            continue
        for py_file in dir_path.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                rel_path = str(py_file.relative_to(REPO_ROOT))
                all_py_content[rel_path] = py_file.read_text(errors="ignore")
            except Exception:
                logger.debug("Failed to read %s", py_file, exc_info=True)

    return all_py_content


def find_table_references(table_name: str, py_content_index: dict) -> list:
    """Find Python files that reference a table name."""
    references = []

    # Patterns to look for
    patterns = [
        rf'"{table_name}"',
        rf"'{table_name}'",
        rf"FROM\s+{table_name}\b",
        rf"INTO\s+{table_name}\b",
        rf"UPDATE\s+{table_name}\b",
        rf"JOIN\s+{table_name}\b",
        rf"TABLE\s+{table_name}\b",
    ]

    combined_pattern = "|".join(patterns)

    for file_path, content in py_content_index.items():
        if re.search(combined_pattern, content, re.IGNORECASE):
            references.append(file_path)

    return references


def get_view_definition(db_path: Path, view_name: str) -> str:
    """Get the SQL definition of a view."""
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='view' AND name=?", (view_name,)
        )
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            # Extract the SELECT part
            sql = row[0]
            # Find what tables it selects from
            from_match = re.findall(r"FROM\s+(\w+)", sql, re.IGNORECASE)
            join_match = re.findall(r"JOIN\s+(\w+)", sql, re.IGNORECASE)
            tables = list(set(from_match + join_match))
            return ", ".join(tables) if tables else "(complex)"
        return "(unknown)"
    except Exception:
        return "(error)"


def identify_version_pattern(table_name: str) -> tuple:
    """Check if table has version suffix and extract base name."""
    match = re.match(r"^(.+?)_v(\d+)$", table_name)
    if match:
        return match.group(1), int(match.group(2))
    return None, None


def guess_core_entity(table_name: str) -> str:
    """Guess which core entity a table might represent."""
    name_lower = table_name.lower()

    mappings = {
        "clients": "Clients",
        "projects": "Projects",
        "tasks": "Tasks",
        "people": "People/Contacts",
        "contacts": "People/Contacts",
        "gmail": "Gmail messages",
        "chat": "Chat messages",
        "calendar": "Calendar events",
        "events": "Calendar events",
        "drive": "Drive files",
        "invoice": "Invoices",
        "issues": "Issues",
        "inbox": "Inbox items",
    }

    for key, entity in mappings.items():
        if key in name_lower:
            return entity

    return None


def classify_tables(tables: list, py_content_index: dict) -> dict:
    """Classify all tables into categories."""
    classifications = {
        "ACTIVE": [],
        "POPULATED-ORPHAN": [],
        "EMPTY-REFERENCED": [],
        "EMPTY-ORPHAN": [],
        "VIEW": [],
        "LEGACY-VERSION": [],
    }

    # Track version patterns
    version_groups = defaultdict(list)

    for table in tables:
        name = table["name"]
        obj_type = table["type"]
        row_count = table.get("row_count", 0)
        table.get("columns", [])

        # Check for version pattern
        base_name, version = identify_version_pattern(name)
        if base_name:
            version_groups[base_name].append((name, version, row_count))

        if obj_type == "view":
            selects_from = get_view_definition(DB_PATH, name)
            classifications["VIEW"].append({**table, "selects_from": selects_from})
            continue

        # Find code references
        references = find_table_references(name, py_content_index)

        # Classify
        if row_count > 0 and references:
            classifications["ACTIVE"].append(
                {**table, "referenced_by": references, "core_entity": guess_core_entity(name)}
            )
        elif row_count > 0 and not references:
            classifications["POPULATED-ORPHAN"].append(
                {**table, "possible_purpose": guess_core_entity(name) or "(unknown)"}
            )
        elif row_count == 0 and references:
            classifications["EMPTY-REFERENCED"].append({**table, "referenced_by": references})
        else:  # row_count == 0 and not references
            classifications["EMPTY-ORPHAN"].append(table)

    # Process version groups to identify legacy tables
    for _base_name, versions in version_groups.items():
        if len(versions) > 1:
            # Sort by version number descending
            sorted_versions = sorted(versions, key=lambda x: x[1], reverse=True)
            current = sorted_versions[0]
            for name, ver, rows in sorted_versions[1:]:
                # Mark older versions as legacy
                classifications["LEGACY-VERSION"].append(
                    {"name": name, "version": ver, "row_count": rows, "current_version": current[0]}
                )

    return classifications, version_groups


def map_core_entities(active_tables: list) -> dict:
    """Map core entities to their canonical tables."""
    entity_map = dict.fromkeys(CORE_ENTITIES)

    # Prioritize tables with _v29 suffix or most rows
    for table in sorted(active_tables, key=lambda t: (-t.get("row_count", 0), t["name"])):
        entity = table.get("core_entity")
        if entity and entity_map.get(entity) is None:
            # Get primary key
            pk_col = None
            for col in table.get("columns", []):
                if col.get("pk"):
                    pk_col = col["name"]
                    break

            entity_map[entity] = {
                "table": table["name"],
                "primary_key": pk_col or "(unknown)",
                "row_count": table.get("row_count", 0),
                "relationships": "(pending analysis)",
            }

    return entity_map


def generate_report(
    classifications: dict,
    version_groups: dict,
    entity_map: dict,
    total_tables: int,
    total_views: int,
) -> str:
    """Generate markdown report."""
    date_str = datetime.now().strftime("%Y-%m-%d")

    # Calculate totals
    active_rows = sum(t.get("row_count", 0) for t in classifications["ACTIVE"])
    orphan_rows = sum(t.get("row_count", 0) for t in classifications["POPULATED-ORPHAN"])

    lines = [
        f"# Schema Audit — {date_str}",
        "",
        "## Summary",
        f"- Total tables: {total_tables}",
        f"- Total views: {total_views}",
        f"- ACTIVE: {len(classifications['ACTIVE'])} ({active_rows:,} rows)",
        f"- POPULATED-ORPHAN: {len(classifications['POPULATED-ORPHAN'])} ({orphan_rows:,} rows)",
        f"- EMPTY-REFERENCED: {len(classifications['EMPTY-REFERENCED'])}",
        f"- EMPTY-ORPHAN: {len(classifications['EMPTY-ORPHAN'])} (safe to drop)",
        f"- LEGACY-VERSION: {len(classifications['LEGACY-VERSION'])}",
        "",
        "---",
        "",
        "## Core Entity Tables",
        "| Entity | Table Name | Primary Key | Row Count | Key Relationships |",
        "|--------|-----------|-------------|-----------|-------------------|",
    ]

    for entity in CORE_ENTITIES:
        info = entity_map.get(entity)
        if info:
            lines.append(
                f"| {entity} | `{info['table']}` | {info['primary_key']} | {info['row_count']:,} | {info['relationships']} |"
            )
        else:
            lines.append(f"| {entity} | _(not found)_ | — | — | — |")

    lines.extend(
        [
            "",
            "---",
            "",
            "## ACTIVE Tables",
            "| Table | Rows | Referenced By |",
            "|-------|------|--------------|",
        ]
    )

    for t in sorted(classifications["ACTIVE"], key=lambda x: -x.get("row_count", 0)):
        refs = ", ".join(t.get("referenced_by", [])[:3])
        if len(t.get("referenced_by", [])) > 3:
            refs += f" (+{len(t['referenced_by']) - 3} more)"
        lines.append(f"| `{t['name']}` | {t.get('row_count', 0):,} | {refs} |")

    lines.extend(
        [
            "",
            "---",
            "",
            "## POPULATED-ORPHAN Tables (have data, nothing reads them)",
            "| Table | Rows | Sample Columns | Possible Purpose |",
            "|-------|------|----------------|-----------------|",
        ]
    )

    for t in sorted(classifications["POPULATED-ORPHAN"], key=lambda x: -x.get("row_count", 0)):
        cols = [c["name"] for c in t.get("columns", [])[:4]]
        cols_str = ", ".join(cols)
        if len(t.get("columns", [])) > 4:
            cols_str += "..."
        lines.append(
            f"| `{t['name']}` | {t.get('row_count', 0):,} | {cols_str} | {t.get('possible_purpose', '?')} |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## EMPTY-REFERENCED Tables",
            "| Table | Referenced By |",
            "|-------|--------------|",
        ]
    )

    for t in sorted(classifications["EMPTY-REFERENCED"], key=lambda x: x["name"]):
        refs = ", ".join(t.get("referenced_by", [])[:3])
        lines.append(f"| `{t['name']}` | {refs} |")

    lines.extend(
        [
            "",
            "---",
            "",
            "## EMPTY-ORPHAN Tables (safe to drop)",
            "| Table |",
            "|-------|",
        ]
    )

    for t in sorted(classifications["EMPTY-ORPHAN"], key=lambda x: x["name"]):
        lines.append(f"| `{t['name']}` |")

    lines.extend(
        [
            "",
            "---",
            "",
            "## LEGACY-VERSION Tables",
            "| Table | Version | Rows | Likely Current Version |",
            "|-------|---------|------|----------------------|",
        ]
    )

    for t in sorted(classifications["LEGACY-VERSION"], key=lambda x: x["name"]):
        lines.append(
            f"| `{t['name']}` | v{t.get('version', '?')} | {t.get('row_count', 0):,} | `{t.get('current_version', '?')}` |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## Views",
            "| View | Selects From | Purpose |",
            "|------|-------------|---------|",
        ]
    )

    for t in sorted(classifications["VIEW"], key=lambda x: x["name"]):
        selects = t.get("selects_from", "?")
        purpose = guess_core_entity(t["name"]) or "(utility)"
        lines.append(f"| `{t['name']}` | {selects} | {purpose} |")

    lines.extend(
        [
            "",
            "---",
            "",
            "## Version Lineage",
            "",
        ]
    )

    for base_name, versions in sorted(version_groups.items()):
        if len(versions) > 1:
            sorted_versions = sorted(versions, key=lambda x: x[1])
            version_str = " → ".join(
                [f"{name} ({rows:,} rows)" for name, ver, rows in sorted_versions]
            )
            lines.append(f"- **{base_name}**: {version_str}")

    if not any(len(v) > 1 for v in version_groups.values()):
        lines.append("_(no multi-version tables detected)_")

    return "\n".join(lines)


def main():
    print("Starting Schema Audit...")

    # Load baseline
    baseline = load_baseline()
    tables = baseline["database"]["tables"]
    total_tables = baseline["database"]["total_tables"]
    total_views = baseline["database"]["total_views"]
    print(f"Loaded {len(tables)} tables/views from baseline")

    # Build reference index
    print("Building code reference index...")
    py_content_index = build_table_reference_index()
    print(f"Indexed {len(py_content_index)} Python files")

    # Classify
    print("Classifying tables...")
    classifications, version_groups = classify_tables(tables, py_content_index)

    # Map core entities
    print("Mapping core entities...")
    entity_map = map_core_entities(classifications["ACTIVE"])

    # Generate report
    print("Generating report...")
    report = generate_report(classifications, version_groups, entity_map, total_tables, total_views)

    # Save
    date_str = datetime.now().strftime("%Y%m%d")
    output_file = DATA_DIR / f"schema_audit_{date_str}.md"
    output_file.write_text(report)

    print(f"\n✓ Report saved to: {output_file}")

    # Summary
    print("\n=== SCHEMA AUDIT SUMMARY ===")
    print(f"Total tables:       {total_tables}")
    print(f"Total views:        {total_views}")
    print(f"ACTIVE:             {len(classifications['ACTIVE'])}")
    print(f"POPULATED-ORPHAN:   {len(classifications['POPULATED-ORPHAN'])}")
    print(f"EMPTY-REFERENCED:   {len(classifications['EMPTY-REFERENCED'])}")
    print(f"EMPTY-ORPHAN:       {len(classifications['EMPTY-ORPHAN'])} (safe to drop)")
    print(f"LEGACY-VERSION:     {len(classifications['LEGACY-VERSION'])}")
    print(f"VIEWS:              {len(classifications['VIEW'])}")

    # Verify all accounted for
    accounted = sum(len(v) for v in classifications.values())
    expected = len(tables)
    if accounted != expected:
        print(f"\n⚠️  WARNING: {expected - accounted} tables unaccounted for!")
    else:
        print(f"\n✓ All {expected} tables/views categorized")


if __name__ == "__main__":
    main()
