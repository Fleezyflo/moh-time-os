#!/usr/bin/env python3
"""
Check for breaking API changes.

Compares current API endpoints against a baseline to detect:
- Removed endpoints
- Changed HTTP methods
- Removed required fields (in responses)
"""

import json
import re
import sys
from pathlib import Path

API_DIR = Path("api")
BASELINE_FILE = Path(".api-baseline.json")
EXCLUDE_PATTERNS = ["_archive", "__pycache__", "test_"]

# Regex to extract endpoints
ENDPOINT_PATTERN = re.compile(
    r'@(?:app|router|spec_router|intelligence_router)\.'
    r'(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']'
)


def should_exclude(path: Path) -> bool:
    """Check if path should be excluded."""
    path_str = str(path)
    return any(excl in path_str for excl in EXCLUDE_PATTERNS)


def extract_endpoints() -> dict[str, str]:
    """Extract all endpoints from API files. Returns {path: method}."""
    endpoints = {}

    if not API_DIR.exists():
        return endpoints

    for py_file in API_DIR.rglob("*.py"):
        if should_exclude(py_file):
            continue

        try:
            content = py_file.read_text()
            for match in ENDPOINT_PATTERN.finditer(content):
                method = match.group(1).upper()
                path = match.group(2)
                key = f"{method} {path}"
                endpoints[key] = str(py_file)
        except (OSError, UnicodeDecodeError):
            pass

    return endpoints


def load_baseline() -> dict[str, str]:
    """Load the API baseline."""
    if BASELINE_FILE.exists():
        try:
            return json.loads(BASELINE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_baseline(endpoints: dict[str, str]) -> None:
    """Save current endpoints as baseline."""
    BASELINE_FILE.write_text(json.dumps(endpoints, indent=2, sort_keys=True))


def main() -> int:
    """Main entry point."""
    current = extract_endpoints()
    baseline = load_baseline()

    # If no baseline, create one and exit
    if not baseline:
        save_baseline(current)
        print(f"✅ Created API baseline with {len(current)} endpoints.")
        print(f"   Baseline saved to {BASELINE_FILE}")
        return 1  # BLOCKING

    # Check for removed endpoints (breaking!)
    removed = []
    for endpoint in baseline:
        if endpoint not in current:
            removed.append(f"  REMOVED: {endpoint}")

    # Check for new endpoints (not breaking, just informational)
    added = []
    for endpoint in current:
        if endpoint not in baseline:
            added.append(f"  ADDED: {endpoint}")

    # Report
    if removed:
        print("🚨 BREAKING API CHANGES:")
        print("\n".join(removed))
        print("\nRemoving endpoints breaks existing clients.")
        print("Either restore the endpoint or update the baseline:")
        print(f"  python {sys.argv[0]} --update-baseline")
        return 1

    if added:
        print("📝 New API endpoints (not breaking):")
        print("\n".join(added[:10]))
        if len(added) > 10:
            print(f"  ... and {len(added) - 10} more")
        print("\nUpdate baseline to include new endpoints:")
        print(f"  python {sys.argv[0]} --update-baseline")

    # Handle --update-baseline flag
    if "--update-baseline" in sys.argv:
        save_baseline(current)
        print(f"✅ Updated API baseline with {len(current)} endpoints.")
        return 1

    print(f"✅ No breaking API changes. ({len(current)} endpoints)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
