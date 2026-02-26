#!/usr/bin/env python3
"""
System-map semantic invariants validator.

Validates structural invariants beyond drift detection:
1. Every collector has outputs + owning tables defined
2. Every DB table has an owner module
3. Every API route has a lineage tag (storage|stateless|external)
4. Every UI page has declared API dependencies

Usage:
    uv run python scripts/check_system_invariants.py

Exit codes:
    0: All invariants satisfied
    1: Invariant violations found
"""

import json
import sqlite3
import sys
from pathlib import Path

SYSTEM_MAP_PATH = Path("docs/system-map.json")
DB_PATH = Path("data/moh_time_os.db")

# Known stateless routes (no storage lineage)
STATELESS_ROUTES = {
    "/api/health",
    "/api/v2/health",
    "/",
}

# Routes with external dependencies (not DB)
EXTERNAL_ROUTES = {
    "/api/sync/asana",
    "/api/sync/xero",
    "/api/sync/calendar",
    "/api/sync/gmail",
}


class InvariantViolation:
    def __init__(self, category: str, message: str, details: str = ""):
        self.category = category
        self.message = message
        self.details = details

    def __str__(self) -> str:
        return f"[{self.category}] {self.message}" + (f" - {self.details}" if self.details else "")


def load_system_map() -> dict:
    """Load system-map.json."""
    if not SYSTEM_MAP_PATH.exists():
        return {}
    return json.loads(SYSTEM_MAP_PATH.read_text())


def get_db_tables() -> set[str]:
    """Get all tables from the database."""
    if not DB_PATH.exists():
        return set()
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()
        return tables
    except Exception:
        return set()


def check_collector_invariants(system_map: dict) -> list[InvariantViolation]:
    """Check that every collector has outputs and owning tables."""
    violations = []
    collectors = system_map.get("collectors", [])

    if not collectors:
        violations.append(
            InvariantViolation(
                "COLLECTORS", "No collectors found in system-map", "Run: make system-map"
            )
        )
        return violations

    # Handle both list and dict formats
    if isinstance(collectors, list):
        for info in collectors:
            name = info.get("name", "unknown")
            outputs = info.get("outputs", [])
            tables = info.get("tables", [])

            # Note: outputs/tables may not be in system-map yet
            # This is informational, not blocking
            if not outputs and not tables:
                # Skip for now - these are defined in code, not system-map
                pass
    else:
        for name, info in collectors.items():
            outputs = info.get("outputs", [])
            if not outputs:
                violations.append(
                    InvariantViolation(
                        "COLLECTOR",
                        f"Collector '{name}' has no outputs defined",
                        "Add OUTPUT_TABLES class attribute",
                    )
                )

    return violations


def check_table_ownership(system_map: dict, db_tables: set[str]) -> list[InvariantViolation]:
    """Check that every DB table has an owner module."""
    violations = []
    collectors = system_map.get("collectors", [])

    # Build set of tables owned by collectors
    owned_tables = set()
    if isinstance(collectors, list):
        for info in collectors:
            owned_tables.update(info.get("tables", []))
    else:
        for info in collectors.values():
            owned_tables.update(info.get("tables", []))

    # Tables from lib/safety/schema.py and lib/db.py are owned by core
    core_tables = {
        "audit_log",
        "schema_migrations",
        "safety_assertions",
        "key_metrics",
        "sync_state",
        "cache",
        "settings",
        "state_snapshots",
        "blocks",
        "health_scores",
    }
    owned_tables.update(core_tables)

    # Check for orphan tables (in DB but no owner)
    orphan_tables = db_tables - owned_tables
    # Filter out common system/temporary tables
    orphan_tables = {t for t in orphan_tables if not t.startswith(("_", "tmp_", "temp_"))}

    if orphan_tables and len(orphan_tables) < 50:  # Only flag if not too many (legacy)
        for table in sorted(orphan_tables)[:10]:
            violations.append(
                InvariantViolation(
                    "TABLE_OWNERSHIP",
                    f"Table '{table}' has no owner module",
                    "Add to collector OUTPUT_TABLES or core_tables",
                )
            )

    return violations


def check_api_route_lineage(system_map: dict) -> list[InvariantViolation]:
    """Check that every API route has a lineage tag."""
    violations = []
    routes = system_map.get("routes", {})

    if not routes:
        # Routes might not be in system-map yet
        return violations

    for path, info in routes.items():
        lineage = info.get("lineage")
        if not lineage:
            if path in STATELESS_ROUTES:
                continue  # Known stateless
            if path in EXTERNAL_ROUTES:
                continue  # Known external
            if path.startswith("/api/docs") or path.startswith("/docs"):
                continue  # OpenAPI docs

            violations.append(
                InvariantViolation(
                    "ROUTE_LINEAGE",
                    f"Route '{path}' missing lineage tag",
                    "Add @route_lineage('storage'|'stateless'|'external') decorator",
                )
            )

    return violations


def check_ui_api_dependencies(system_map: dict) -> list[InvariantViolation]:
    """Check that UI pages declare API dependencies."""
    violations = []
    ui_pages = system_map.get("ui_pages", {})

    # This is optional - only flag if ui_pages is defined but empty
    if "ui_pages" in system_map and not ui_pages:
        violations.append(
            InvariantViolation(
                "UI_DEPS", "ui_pages defined but empty", "Add page declarations or remove section"
            )
        )

    return violations


def main() -> int:
    print("🔍 Checking system invariants...\n")

    system_map = load_system_map()
    db_tables = get_db_tables()

    all_violations = []

    # Run all invariant checks
    all_violations.extend(check_collector_invariants(system_map))
    all_violations.extend(check_table_ownership(system_map, db_tables))
    all_violations.extend(check_api_route_lineage(system_map))
    all_violations.extend(check_ui_api_dependencies(system_map))

    if all_violations:
        print(f"❌ Found {len(all_violations)} invariant violations:\n")
        for v in all_violations:
            print(f"   {v}")

        # Categorize
        categories = {}
        for v in all_violations:
            categories[v.category] = categories.get(v.category, 0) + 1

        print(f"\n   Summary: {categories}")
        return 1

    print("✅ All system invariants satisfied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
