#!/usr/bin/env python3
"""Check for duplicate API endpoints across all router files."""

import re
import sys
from collections import defaultdict
from pathlib import Path

API_DIR = Path("api")
EXCLUDE_PATTERNS = ["_archive", "__pycache__"]

# Pattern: @router.get("/path") or @app.post("/path") etc.
ENDPOINT_PATTERN = re.compile(
    r"@(?:app|router|spec_router|intelligence_router)\."
    r'(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']'
)


def should_exclude(path: Path) -> bool:
    """Check if path should be excluded."""
    path_str = str(path)
    return any(excl in path_str for excl in EXCLUDE_PATTERNS)


def extract_endpoints(filepath: Path) -> list[tuple[str, str, int]]:
    """Extract all endpoints from a file. Returns (method, path, line_num)."""
    endpoints = []
    try:
        content = filepath.read_text()
        for i, line in enumerate(content.splitlines(), 1):
            match = ENDPOINT_PATTERN.search(line)
            if match:
                method = match.group(1).upper()
                path = match.group(2)
                endpoints.append((method, path, i))
    except (OSError, UnicodeDecodeError):
        # Skip files that can't be read
        pass
    return endpoints


def main() -> int:
    """Main entry point."""
    if not API_DIR.exists():
        return 1  # BLOCKING

    # Collect all endpoints: (method, path) -> [(file, line), ...]
    endpoint_locations: dict[tuple[str, str], list[tuple[Path, int]]] = defaultdict(list)

    for py_file in API_DIR.rglob("*.py"):
        if should_exclude(py_file):
            continue

        for method, path, line_num in extract_endpoints(py_file):
            endpoint_locations[(method, path)].append((py_file, line_num))

    # Find duplicates
    duplicates = {k: v for k, v in endpoint_locations.items() if len(v) > 1}

    if duplicates:
        print("DUPLICATE ENDPOINTS FOUND:")
        for (method, path), locations in sorted(duplicates.items()):
            print(f"\n  {method} {path}")
            for filepath, line_num in locations:
                print(f"    - {filepath}:{line_num}")
        return 1

    return 0  # PASS when no violations


if __name__ == "__main__":
    sys.exit(main())
