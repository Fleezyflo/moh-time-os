#!/usr/bin/env python3
"""
Generate baseline snapshot of MOH TIME OS system state.
Task: SYSPREP 0.1 — Baseline Snapshot
"""

import json
import os
import re
import sqlite3
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).parent.parent
DB_PATH = REPO_ROOT / "data" / "moh_time_os.db"
LIB_DIRS = ["lib", "api", "engine", "collectors"]
UI_DIR = REPO_ROOT / "time-os-ui" / "src"
OUTPUT_DIR = REPO_ROOT / "data"


def get_table_inventory(db_path: Path) -> dict:
    """Step 2: Get complete table inventory from database."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    tables = []
    total_rows = 0
    view_count = 0

    # Get all tables and views
    cursor = conn.execute("""
        SELECT name, type FROM sqlite_master
        WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%'
        ORDER BY type, name
    """)

    for row in cursor.fetchall():
        table_name = row["name"]
        obj_type = row["type"]

        # Get row count
        try:
            count_cursor = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"')  # nosql: safe
            row_count = count_cursor.fetchone()[0]
        except Exception:
            row_count = 0

        # Get columns
        columns = []
        try:
            col_cursor = conn.execute(f'PRAGMA table_info("{table_name}")')  # nosql: safe
            for col in col_cursor.fetchall():
                columns.append(
                    {"name": col[1], "type": col[2], "notnull": bool(col[3]), "pk": bool(col[5])}
                )
        except Exception:
            pass

        # Get indexes
        indexes = []
        try:
            idx_cursor = conn.execute(f'PRAGMA index_list("{table_name}")')  # nosql: safe
            for idx in idx_cursor.fetchall():
                indexes.append(idx[1])
        except Exception:
            pass

        tables.append(
            {
                "name": table_name,
                "type": obj_type,
                "row_count": row_count,
                "columns": columns,
                "indexes": indexes,
            }
        )

        total_rows += row_count
        if obj_type == "view":
            view_count += 1

    conn.close()

    return {
        "path": str(db_path),
        "tables": tables,
        "total_tables": len([t for t in tables if t["type"] == "table"]),
        "total_views": view_count,
        "total_rows": total_rows,
    }


def build_import_index(repo_root: Path) -> dict:
    """Build index of all imports in Python files - single pass."""
    # Maps module_name -> list of files that import it
    import_index = defaultdict(list)

    # Find all Python files
    for py_file in repo_root.rglob("*.py"):
        if "__pycache__" in str(py_file) or ".venv" in str(py_file):
            continue

        rel_path = str(py_file.relative_to(repo_root))

        try:
            content = py_file.read_text(errors="ignore")

            # Find all imports
            # "from X import Y" or "from X.Y import Z"
            for match in re.finditer(r"^from\s+([\w.]+)\s+import", content, re.MULTILINE):
                module = match.group(1)
                import_index[module].append(rel_path)

            # "import X" or "import X.Y"
            for match in re.finditer(r"^import\s+([\w.]+)", content, re.MULTILINE):
                module = match.group(1)
                import_index[module].append(rel_path)
        except Exception:
            pass

    return dict(import_index)


def get_module_inventory(repo_root: Path, lib_dirs: list, import_index: dict) -> dict:
    """Step 3: Get complete Python module inventory."""
    modules = []

    for lib_dir in lib_dirs:
        dir_path = repo_root / lib_dir
        if not dir_path.exists():
            continue

        for py_file in dir_path.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue

            rel_path = py_file.relative_to(repo_root)
            str_rel_path = str(rel_path)

            # Get file stats
            try:
                stat = py_file.stat()
                content = py_file.read_text(errors="ignore")
                line_count = len(content.splitlines())
            except Exception:
                continue

            # Compute module names for import search
            module_parts = list(rel_path.with_suffix("").parts)
            module_names = []

            # Full module path: lib.safety.context
            module_names.append(".".join(module_parts))

            # Without __init__
            if module_parts[-1] == "__init__":
                module_names.append(".".join(module_parts[:-1]))

            # Look up imports
            imported_by = set()
            for mod_name in module_names:
                if mod_name in import_index:
                    for importer in import_index[mod_name]:
                        if importer != str_rel_path:
                            imported_by.add(importer)
                # Also check partial matches (e.g., "from lib import X" matches "lib")
                for indexed_mod, importers in import_index.items():
                    if indexed_mod.startswith(mod_name + ".") or indexed_mod == mod_name:
                        for importer in importers:
                            if importer != str_rel_path:
                                imported_by.add(importer)

            modules.append(
                {
                    "path": str_rel_path,
                    "module_name": module_names[0],
                    "size_bytes": stat.st_size,
                    "line_count": line_count,
                    "imported_by": sorted(imported_by),
                    "import_count": len(imported_by),
                }
            )

    orphaned = [m for m in modules if m["import_count"] == 0]

    return {
        "files": modules,
        "total_modules": len(modules),
        "orphaned_count": len(orphaned),
        "orphaned_modules": [m["path"] for m in orphaned],
    }


def get_endpoint_inventory(repo_root: Path) -> dict:
    """Step 4: Extract API endpoints from router files."""

    def extract_routes(file_path: Path) -> list:
        """Extract route decorators from a Python file."""
        routes = []
        if not file_path.exists():
            return routes

        content = file_path.read_text(errors="ignore")
        lines = content.split("\n")

        # Pattern for route decorators
        pattern = r'@(\w+)\.(get|post|put|patch|delete)\s*\(\s*["\']([^"\']+)["\']'

        for i, line in enumerate(lines):
            match = re.search(pattern, line)
            if match:
                router_name, method, path = match.groups()

                # Find the function name in subsequent lines
                func_name = "unknown"
                for j in range(i + 1, min(i + 5, len(lines))):
                    func_match = re.search(r"(?:async\s+)?def\s+(\w+)", lines[j])
                    if func_match:
                        func_name = func_match.group(1)
                        break

                routes.append(
                    {
                        "path": path,
                        "method": method.upper(),
                        "function": func_name,
                        "router": router_name,
                    }
                )

        return routes

    spec_router_routes = extract_routes(repo_root / "api" / "spec_router.py")
    server_routes = extract_routes(repo_root / "api" / "server.py")

    return {
        "spec_router": spec_router_routes,
        "server_legacy": server_routes,
        "total_active": len(spec_router_routes),
        "total_legacy": len(server_routes),
    }


def get_ui_inventory(ui_dir: Path) -> dict:
    """Step 5: Inventory UI components and API calls."""
    components = []
    api_calls = []

    if not ui_dir.exists():
        return {"files": [], "total_components": 0, "api_calls": []}

    extensions = [".tsx", ".jsx", ".ts", ".js"]

    for ext in extensions:
        for file_path in ui_dir.rglob(f"*{ext}"):
            if "node_modules" in str(file_path):
                continue

            try:
                rel_path = file_path.relative_to(ui_dir.parent.parent)
                content = file_path.read_text(errors="ignore")
            except Exception:
                continue

            # Find exported components
            component_names = []
            for match in re.finditer(
                r"export\s+(?:default\s+)?(?:function|const|class)\s+(\w+)", content
            ):
                component_names.append(match.group(1))
            for match in re.finditer(r"export\s+\{\s*([^}]+)\s*\}", content):
                names = [n.strip().split(" as ")[0] for n in match.group(1).split(",")]
                component_names.extend([n for n in names if n])

            # Find API calls
            file_api_calls = []
            for match in re.finditer(
                r'(?:fetch|get|post|put|delete|patch)\s*\(\s*[`"\']([^`"\']*(?:api|/v2)[^`"\']*)[`"\']',
                content,
                re.IGNORECASE,
            ):
                endpoint = match.group(1)
                if endpoint not in file_api_calls:
                    file_api_calls.append(endpoint)
                    api_calls.append({"file": str(rel_path), "endpoint": endpoint})

            components.append(
                {
                    "path": str(rel_path),
                    "components": component_names,
                    "api_calls": file_api_calls,
                    "line_count": len(content.splitlines()),
                }
            )

    return {"files": components, "total_components": len(components), "api_calls": api_calls}


def run_tests(repo_root: Path) -> dict:
    """Step 6: Run test suite and capture results."""
    try:
        result = subprocess.run(
            ["uv", "run", "python", "-m", "pytest", "tests/", "-q", "--tb=no"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=300,
        )

        output = result.stdout + result.stderr

        # Parse output
        match = re.search(r"(\d+)\s+passed", output)
        passed = int(match.group(1)) if match else 0

        match = re.search(r"(\d+)\s+failed", output)
        failed = int(match.group(1)) if match else 0

        match = re.search(r"(\d+)\s+error", output)
        errors = int(match.group(1)) if match else 0

        return {
            "total": passed + failed + errors,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "all_passing": failed == 0 and errors == 0,
        }
    except Exception as e:
        return {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "errors": 1,
            "error_message": str(e),
            "all_passing": False,
        }


def main():
    """Generate complete baseline snapshot."""
    print("Generating baseline snapshot...")

    # Step 1: Verify DB
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        sys.exit(1)
    print(f"✓ Database found: {DB_PATH}")

    # Step 2: Table inventory
    print("Collecting table inventory...")
    database = get_table_inventory(DB_PATH)
    print(
        f"✓ Found {database['total_tables']} tables, {database['total_views']} views, {database['total_rows']:,} total rows"
    )

    # Build import index once (single pass)
    print("Building import index...")
    import_index = build_import_index(REPO_ROOT)
    print(f"✓ Indexed {len(import_index)} unique import paths")

    # Step 3: Module inventory
    print("Collecting module inventory...")
    modules = get_module_inventory(REPO_ROOT, LIB_DIRS, import_index)
    print(
        f"✓ Found {modules['total_modules']} modules, {modules['orphaned_count']} potentially orphaned"
    )

    # Step 4: Endpoint inventory
    print("Collecting endpoint inventory...")
    endpoints = get_endpoint_inventory(REPO_ROOT)
    print(
        f"✓ Found {endpoints['total_active']} active endpoints, {endpoints['total_legacy']} legacy endpoints"
    )

    # Step 5: UI inventory
    print("Collecting UI inventory...")
    ui_components = get_ui_inventory(UI_DIR)
    print(
        f"✓ Found {ui_components['total_components']} UI files, {len(ui_components['api_calls'])} API calls"
    )

    # Step 6: Test baseline
    print("Running test suite...")
    tests = run_tests(REPO_ROOT)
    print(f"✓ Tests: {tests['passed']} passed, {tests['failed']} failed, {tests['errors']} errors")

    # Step 7: Assemble snapshot
    snapshot = {
        "generated": datetime.now().astimezone().isoformat(),
        "database": database,
        "modules": modules,
        "endpoints": endpoints,
        "ui_components": ui_components,
        "tests": tests,
    }

    # Save
    date_str = datetime.now().strftime("%Y%m%d")
    output_file = OUTPUT_DIR / f"baseline_snapshot_{date_str}.json"

    with open(output_file, "w") as f:
        json.dump(snapshot, f, indent=2)

    print(f"\n✓ Snapshot saved to: {output_file}")

    # Summary
    print("\n=== BASELINE SNAPSHOT SUMMARY ===")
    print(f"Tables:     {database['total_tables']} ({database['total_rows']:,} rows)")
    print(f"Views:      {database['total_views']}")
    print(f"Modules:    {modules['total_modules']} ({modules['orphaned_count']} orphaned)")
    print(f"Endpoints:  {endpoints['total_active']} active, {endpoints['total_legacy']} legacy")
    print(f"UI Files:   {ui_components['total_components']}")
    print(f"Tests:      {tests['passed']} passing")

    return snapshot


if __name__ == "__main__":
    main()
