#!/usr/bin/env python3
"""
Ratchet Snapshot — Capture current metric baselines.

Captures metrics that should never increase (ratchet pattern).
Run this to establish a new baseline after intentional changes.

Usage:
    python scripts/ratchet_snapshot.py          # Write to .ratchet-baseline.json
    python scripts/ratchet_snapshot.py --print  # Print metrics without writing
"""

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
BASELINE_FILE = PROJECT_ROOT / ".ratchet-baseline.json"

# Directories to scan
SCAN_DIRS = ["lib", "api", "engine", "cli", "collectors", "scripts"]
EXCLUDE_DIRS = {"__pycache__", ".venv", "_archive", "node_modules", ".git"}


def find_python_files() -> list[Path]:
    """Find all Python files in scan directories."""
    files = []
    for dir_name in SCAN_DIRS:
        dir_path = PROJECT_ROOT / dir_name
        if dir_path.exists():
            for f in dir_path.rglob("*.py"):
                if not any(ex in f.parts for ex in EXCLUDE_DIRS):
                    files.append(f)
    return files


def count_sql_fstrings() -> int:
    """Count f-string SQL queries (injection risk).
    
    Matches patterns like:
    - store.query(f"...
    - conn.execute(f"...
    - cur.execute(f"...
    - cursor.execute(f"...
    - db.execute(f"...
    - .execute(f"...
    - .executemany(f"...
    """
    patterns = [
        re.compile(r'store\.query\(f["\']'),
        re.compile(r'conn\.execute\(f["\']'),
        re.compile(r'cur\.execute\(f["\']'),
        re.compile(r'cursor\.execute\(f["\']'),
        re.compile(r'db\.execute\(f["\']'),
        re.compile(r'\.execute\(f["\']'),
        re.compile(r'\.executemany\(f["\']'),
        re.compile(r'\.executescript\(f["\']'),
    ]
    count = 0
    for f in find_python_files():
        try:
            content = f.read_text()
            for pattern in patterns:
                count += len(pattern.findall(content))
        except Exception:
            pass
    return count


def count_unprotected_write_endpoints() -> int:
    """Count POST/PUT/DELETE/PATCH endpoints without auth decorator."""
    # Look for route decorators followed by async def without auth
    server_py = PROJECT_ROOT / "api" / "server.py"
    if not server_py.exists():
        return 0

    content = server_py.read_text()
    lines = content.split("\n")

    write_methods = {"post", "put", "delete", "patch"}
    count = 0

    for i, line in enumerate(lines):
        # Check for @app.post, @app.put, etc. or @router.post, etc.
        match = re.match(r'\s*@\w+\.(post|put|delete|patch)\s*\(', line, re.IGNORECASE)
        if match:
            # Look backwards for auth decorator (within 5 lines)
            has_auth = False
            for j in range(max(0, i - 5), i):
                if "auth" in lines[j].lower() or "depends" in lines[j].lower():
                    has_auth = True
                    break
            if not has_auth:
                count += 1

    return count


def count_server_py_lines() -> int:
    """Count lines in api/server.py."""
    server_py = PROJECT_ROOT / "api" / "server.py"
    if not server_py.exists():
        return 0
    return len(server_py.read_text().split("\n"))


def count_duplicate_routes() -> int:
    """Count duplicate method+path registrations."""
    server_py = PROJECT_ROOT / "api" / "server.py"
    if not server_py.exists():
        return 0

    content = server_py.read_text()
    # Match @app.get("/path") or @router.post("/path")
    pattern = re.compile(r'@\w+\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']')
    routes = pattern.findall(content)

    # Count duplicates
    seen = set()
    duplicates = 0
    for method, path in routes:
        key = (method.lower(), path)
        if key in seen:
            duplicates += 1
        seen.add(key)

    return duplicates


def count_traceback_leaks() -> int:
    """Count traceback.format_exc() in response dicts."""
    pattern = re.compile(r'traceback\.format_exc\(\)')
    count = 0
    for f in find_python_files():
        if "api" in str(f):
            try:
                content = f.read_text()
                count += len(pattern.findall(content))
            except Exception:
                pass
    return count


def count_hardcoded_emails() -> int:
    """Count hardcoded email strings in .py files."""
    # Simple email pattern - matches obvious hardcoded emails
    pattern = re.compile(r'["\'][a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}["\']')
    count = 0
    for f in find_python_files():
        # Skip test files
        if "test" in f.name.lower():
            continue
        try:
            content = f.read_text()
            matches = pattern.findall(content)
            count += len(matches)
        except Exception:
            pass
    return count


def count_bare_excepts() -> int:
    """Count 'except Exception:' blocks (too broad)."""
    # Match "except Exception:" or "except Exception as"
    pattern = re.compile(r'except\s+Exception\s*[:\s]')
    count = 0
    for f in find_python_files():
        try:
            content = f.read_text()
            count += len(pattern.findall(content))
        except Exception:
            pass
    return count


def collect_metrics() -> dict:
    """Collect all ratchet metrics."""
    return {
        "sql_fstring_count": count_sql_fstrings(),
        "unprotected_write_endpoints": count_unprotected_write_endpoints(),
        "server_py_lines": count_server_py_lines(),
        "duplicate_routes": count_duplicate_routes(),
        "traceback_leak_count": count_traceback_leaks(),
        "hardcoded_email_count": count_hardcoded_emails(),
        "bare_except_count": count_bare_excepts(),
    }


def main():
    metrics = collect_metrics()

    if "--print" in sys.argv:
        print("Current metrics:")
        for k, v in sorted(metrics.items()):
            print(f"  {k}: {v}")
        return

    # Write baseline
    BASELINE_FILE.write_text(json.dumps(metrics, indent=2) + "\n")
    print(f"✅ Baseline written to {BASELINE_FILE}")
    print("\nMetrics:")
    for k, v in sorted(metrics.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
