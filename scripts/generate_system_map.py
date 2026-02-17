#!/usr/bin/env python3
"""
Generate system map: collectors → DB tables → API routes → UI routes.

This is the single source of truth for the data flow in the system.

Usage:
    uv run python scripts/generate_system_map.py [--check]
"""

import argparse
import ast
import json
import re
import sqlite3
import sys
from pathlib import Path


def get_collectors() -> list[dict]:
    """Extract collector definitions from lib/collector_registry.py and lib/collectors/."""
    collectors = []

    # From collector_registry.py
    registry_path = Path("lib/collector_registry.py")
    if registry_path.exists():
        content = registry_path.read_text()
        # Look for ENABLED_COLLECTORS or similar
        match = re.search(r"ENABLED_COLLECTORS\s*=\s*\[(.*?)\]", content, re.DOTALL)
        if match:
            for name in re.findall(r'"(\w+)"', match.group(1)):
                collectors.append({"name": name, "source": "collector_registry.py"})

    # From lib/collectors/orchestrator.py
    orch_path = Path("lib/collectors/orchestrator.py")
    if orch_path.exists():
        content = orch_path.read_text()
        # Look for collector imports and registrations
        for match in re.finditer(r"from lib\.collectors\.(\w+) import", content):
            name = match.group(1)
            if name not in ["base", "orchestrator", "__init__"]:
                if not any(c["name"] == name for c in collectors):
                    collectors.append({"name": name, "source": "orchestrator.py"})

    # Scan lib/collectors/ for collector classes
    collectors_dir = Path("lib/collectors")
    if collectors_dir.exists():
        for py_file in collectors_dir.glob("*.py"):
            if py_file.name.startswith("debug_") or py_file.name.startswith("test_"):
                continue
            if py_file.name in ["__init__.py", "base.py", "orchestrator.py"]:
                continue
            name = py_file.stem
            if not any(c["name"] == name for c in collectors):
                collectors.append({"name": name, "source": f"collectors/{py_file.name}"})

    return collectors


def get_db_tables() -> list[dict]:
    """Extract table definitions from lib/db.py and migrations."""
    tables = []

    # From lib/db.py
    db_path = Path("lib/db.py")
    if db_path.exists():
        content = db_path.read_text()
        for match in re.finditer(r"CREATE TABLE IF NOT EXISTS (\w+)", content):
            tables.append({"name": match.group(1), "source": "lib/db.py"})

    # From migrations
    migrations_dir = Path("lib/migrations")
    if migrations_dir.exists():
        for py_file in migrations_dir.glob("*.py"):
            content = py_file.read_text()
            for match in re.finditer(r"CREATE TABLE IF NOT EXISTS (\w+)", content):
                name = match.group(1)
                if not any(t["name"] == name for t in tables):
                    tables.append({"name": name, "source": f"migrations/{py_file.name}"})

    # From v5 migrations
    v5_migrations = Path("lib/v5/migrations")
    if v5_migrations.exists():
        for sql_file in v5_migrations.glob("*.sql"):
            content = sql_file.read_text()
            for match in re.finditer(r"CREATE TABLE IF NOT EXISTS (\w+)", content):
                name = match.group(1)
                if not any(t["name"] == name for t in tables):
                    tables.append({"name": name, "source": f"v5/migrations/{sql_file.name}"})

    return tables


def get_api_routes() -> list[dict]:
    """Extract API routes from api/server.py and api/spec_router.py."""
    routes = []

    for api_file in ["api/server.py", "api/spec_router.py"]:
        path = Path(api_file)
        if not path.exists():
            continue

        content = path.read_text()

        # Match @app.get/post/put/delete/patch decorators
        for match in re.finditer(
            r'@(?:app|router|spec_router)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
            content,
        ):
            method = match.group(1).upper()
            route_path = match.group(2)
            routes.append(
                {
                    "method": method,
                    "path": route_path,
                    "source": api_file,
                }
            )

    return routes


def get_ui_routes() -> list[dict]:
    """Extract UI routes from time-os-ui/src/router.tsx."""
    routes = []

    router_path = Path("time-os-ui/src/router.tsx")
    if not router_path.exists():
        return routes

    content = router_path.read_text()

    # Match path definitions in router
    for match in re.finditer(r'path:\s*["\']([^"\']+)["\']', content):
        route_path = match.group(1)
        routes.append({"path": route_path, "source": "router.tsx"})

    return routes


def get_ui_api_calls() -> list[dict]:
    """Extract API calls from UI source files."""
    api_calls = []

    src_dir = Path("time-os-ui/src")
    if not src_dir.exists():
        return api_calls

    for ts_file in src_dir.rglob("*.ts"):
        content = ts_file.read_text()
        # Match fetch calls to /api/
        for match in re.finditer(r'fetch\s*\(\s*[`"\']([^`"\']*\/api\/[^`"\']+)[`"\']', content):
            api_calls.append(
                {
                    "endpoint": match.group(1),
                    "source": str(ts_file.relative_to(src_dir)),
                }
            )

    for tsx_file in src_dir.rglob("*.tsx"):
        content = tsx_file.read_text()
        for match in re.finditer(r'fetch\s*\(\s*[`"\']([^`"\']*\/api\/[^`"\']+)[`"\']', content):
            api_calls.append(
                {
                    "endpoint": match.group(1),
                    "source": str(tsx_file.relative_to(src_dir)),
                }
            )

    return api_calls


def generate_system_map() -> dict:
    """Generate the complete system map."""
    return {
        "version": "1.0.0",
        "generated_by": "scripts/generate_system_map.py",
        "collectors": get_collectors(),
        "db_tables": get_db_tables(),
        "api_routes": get_api_routes(),
        "ui_routes": get_ui_routes(),
        "ui_api_calls": get_ui_api_calls(),
        "summary": {
            "collectors_count": len(get_collectors()),
            "db_tables_count": len(get_db_tables()),
            "api_routes_count": len(get_api_routes()),
            "ui_routes_count": len(get_ui_routes()),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate system map")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if docs/system-map.json is up to date",
    )
    parser.add_argument(
        "--output",
        default="docs/system-map.json",
        help="Output path (default: docs/system-map.json)",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    system_map = generate_system_map()
    # Sort lists for cross-platform determinism
    for key, val in system_map.items():
        if isinstance(val, list):
            try:
                system_map[key] = sorted(
                    val,
                    key=lambda x: json.dumps(x, sort_keys=True) if isinstance(x, dict) else str(x),
                )
            except TypeError:
                pass
    system_map_json = json.dumps(system_map, indent=2, sort_keys=True) + "\n"

    if args.check:
        if not output_path.exists():
            print(f"❌ {output_path} does not exist. Run without --check to generate.")
            return 1

        existing = output_path.read_text()
        if existing != system_map_json:
            print(f"❌ System map drift detected! {output_path} is stale.")
            print("   Run: uv run python scripts/generate_system_map.py")
            return 1

        print(f"✅ {output_path} is up to date.")
        return 0

    # Generate mode
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(system_map_json)
    print(f"✅ Generated system map: {output_path}")
    print(f"   Collectors: {system_map['summary']['collectors_count']}")
    print(f"   DB tables: {system_map['summary']['db_tables_count']}")
    print(f"   API routes: {system_map['summary']['api_routes_count']}")
    print(f"   UI routes: {system_map['summary']['ui_routes_count']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
