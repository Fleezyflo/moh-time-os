#!/usr/bin/env python3
"""
Generate system map: collectors → DB tables → API routes → UI routes.

This is the single source of truth for the data flow in the system.

Usage:
    uv run python scripts/generate_system_map.py [--check]
"""

import argparse
import json
import re
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


def _parse_router_mounts(server_content: str) -> dict[str, str]:
    """Map each router module to its include_router(prefix=...) mount prefix.

    server.py declares routers as ``from api.<module> import <symbol>`` (optionally
    ``as <alias>``) and mounts them with ``app.include_router(<symbol>, prefix="...")``.
    The include_router call keys on the imported symbol, not the module name, so the
    alias must be resolved to recover the owning module. Routers mounted without a
    prefix argument map to "" (their own APIRouter prefix carries the full path).
    """
    symbol_to_module: dict[str, str] = {}
    for match in re.finditer(
        r"from\s+api\.(\w+)\s+import\s+(\w+)(?:\s+as\s+(\w+))?",
        server_content,
    ):
        module, imported, alias = match.group(1), match.group(2), match.group(3)
        symbol_to_module[alias or imported] = module

    module_to_mount: dict[str, str] = {}
    for match in re.finditer(
        r'app\.include_router\(\s*(\w+)\s*(?:,\s*prefix\s*=\s*["\']([^"\']*)["\'])?',
        server_content,
    ):
        symbol, prefix = match.group(1), (match.group(2) or "")
        module = symbol_to_module.get(symbol)
        if module is not None:
            module_to_mount[module] = prefix
    return module_to_mount


def _parse_router_declaration(content: str) -> tuple[str | None, str]:
    """Return (local router variable, own APIRouter prefix) for a router file.

    Matches the ``<var> = APIRouter(...)`` assignment and scans its argument span
    (which may span multiple lines) for ``prefix="..."``. Returns (None, "") when the
    file declares no APIRouter (e.g. api/server.py, which uses the ``app`` object).
    """
    match = re.search(r"(\w+)\s*=\s*APIRouter\s*\(", content)
    if not match:
        return None, ""
    var = match.group(1)
    start, depth, i = match.end(), 1, match.end()
    while i < len(content) and depth > 0:
        char = content[i]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        i += 1
    prefix_match = re.search(r'prefix\s*=\s*["\']([^"\']*)["\']', content[start : i - 1])
    return var, (prefix_match.group(1) if prefix_match else "")


def get_api_routes() -> list[dict]:
    """Extract fully-qualified API routes from all router files including sub-routers.

    The recorded path is ``mount_prefix + own_prefix + decorator_path`` so it matches a
    real request URL. ``@app.<method>`` routes in server.py are already absolute and are
    recorded verbatim.
    """
    routes = []

    server_path = Path("api/server.py")
    server_content = server_path.read_text() if server_path.exists() else ""
    module_to_mount = _parse_router_mounts(server_content)

    # Discover router modules from server.py imports (plus server itself and spec_router)
    modules = {"server", "spec_router"}
    for match in re.finditer(r"from\s+api\.(\w+)\s+import\s+\w+", server_content):
        modules.add(match.group(1))

    for module in modules:
        path = Path(f"api/{module}.py")
        if not path.exists():
            continue

        content = path.read_text()
        router_var, own_prefix = _parse_router_declaration(content)
        mount_prefix = module_to_mount.get(module, "")

        # Decorators reference the file-local router variable (often `router`) or `app`
        decorator_names = {"app"}
        if router_var:
            decorator_names.add(router_var)
        name_alternation = "|".join(re.escape(n) for n in sorted(decorator_names))

        for match in re.finditer(
            rf'@(?:{name_alternation})\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
            content,
        ):
            method = match.group(1).upper()
            decorator_path = match.group(2)
            if match.group(0).startswith("@app."):
                full_path = decorator_path
            else:
                full_path = f"{mount_prefix}{own_prefix}{decorator_path}"
            routes.append(
                {
                    "method": method,
                    "path": full_path,
                    "source": f"api/{module}.py",
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


# Wrapper helpers and fetch() that issue HTTP requests in the UI
_UI_CALL_RE = re.compile(r"(?:fetchJson|postJson|patchJson|putJson|delJson|fetch)\s*\(\s*`([^`]*)`")
# Query-string template tails use these variable names by convention
_QUERY_VARS = frozenset({"qs", "query"})


def _resolve_api_base(content: str) -> str | None:
    """Resolve a file's ``const API_BASE`` to its literal string value.

    Handles ``const API_BASE = '/lit'`` and ``const API_BASE = ENV || '/lit'`` (the env
    fallback after ``||`` is the literal used at build time when the env var is unset).
    Returns None when the file defines no API_BASE.
    """
    match = re.search(r"const\s+API_BASE\s*=\s*([^\n;]+)", content)
    if not match:
        return None
    expr = match.group(1)
    fallback = re.search(r"""\|\|\s*['"]([^'"]+)['"]""", expr)
    if fallback:
        return fallback.group(1)
    literal = re.search(r"""['"]([^'"]+)['"]""", expr)
    return literal.group(1) if literal else None


def _strip_query_tail(path: str) -> str:
    """Drop query-string tails while preserving path-param interpolations.

    Cuts at the first literal ``?`` and at the first ``${...}`` that is not a bare path
    param. Path params look like ``${clientId}``; query builders look like
    ``${qs ? '?' + qs : ''}`` or the trailing ``${query}``.
    """
    question = path.find("?")
    if question != -1:
        path = path[:question]
    out: list[str] = []
    i = 0
    while i < len(path):
        if path.startswith("${", i):
            close = path.find("}", i)
            if close == -1:
                # Truncated (an inner backtick ended the literal early) -- drop the rest
                break
            body = path[i + 2 : close]
            if re.fullmatch(r"\w+", body) and body not in _QUERY_VARS:
                out.append(path[i : close + 1])
                i = close + 1
                continue
            break
        out.append(path[i])
        i += 1
    return "".join(out)


def _normalize_ui_endpoint(raw: str, api_base: str | None) -> str | None:
    """Resolve ``${API_BASE}`` / ``${apiBase}`` and strip query tails.

    Returns a comparable ``/api/...`` path, or None when the call is not an API call
    (no resolvable base and no literal ``/api`` segment).
    """
    raw = raw.strip()
    for token in ("${API_BASE}", "${apiBase}"):
        if raw.startswith(token):
            if api_base is None:
                return None
            raw = api_base + raw[len(token) :]
            break
    path = _strip_query_tail(raw)
    if not path.startswith("/api"):
        return None
    return path


def get_ui_api_calls() -> list[dict]:
    """Extract API calls from UI source files.

    Handles direct ``fetch()`` calls and the ``fetchJson``/``postJson``/``patchJson``/
    ``putJson``/``delJson`` wrappers, including multi-line calls. ``${API_BASE}`` is
    resolved per file (e.g. lib/api.ts -> "/api/v2", intelligence/api.ts ->
    "/api/v2/intelligence") and query-string tails are stripped so endpoints are
    directly comparable to api_routes.
    """
    api_calls = []

    src_dir = Path("time-os-ui/src")
    if not src_dir.exists():
        return api_calls

    for source_file in sorted(src_dir.rglob("*.ts")) + sorted(src_dir.rglob("*.tsx")):
        content = source_file.read_text()
        api_base = _resolve_api_base(content)
        for match in _UI_CALL_RE.finditer(content):
            endpoint = _normalize_ui_endpoint(match.group(1), api_base)
            if endpoint is None:
                continue
            api_calls.append(
                {
                    "endpoint": endpoint,
                    "source": str(source_file.relative_to(src_dir)),
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
