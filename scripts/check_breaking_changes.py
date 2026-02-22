#!/usr/bin/env python3
"""
Check for breaking changes in OpenAPI schema.

Compares current schema against the pinned docs/openapi.json.
Detects:
- Removed endpoints
- Removed required fields
- Changed response types
- Removed enum values

Usage:
    uv run python scripts/check_breaking_changes.py

Requires: oasdiff (install via: go install github.com/tufin/oasdiff@latest)
Or falls back to basic Python comparison.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path


def get_current_schema() -> dict:
    """Get current OpenAPI schema from FastAPI app."""
    from api.server import app

    return app.openapi()


def load_pinned_schema() -> dict:
    """Load pinned schema from docs/openapi.json."""
    pinned_path = Path("docs/openapi.json")
    if not pinned_path.exists():
        print("❌ docs/openapi.json not found. Run: uv run python scripts/export_openapi.py")
        sys.exit(1)
    return json.loads(pinned_path.read_text())


def check_with_oasdiff(pinned_path: str, current_path: str) -> tuple[bool, str]:
    """Use oasdiff for breaking change detection."""
    oasdiff = shutil.which("oasdiff")
    if not oasdiff:
        return False, "oasdiff not installed"

    result = subprocess.run(
        [oasdiff, "breaking", pinned_path, current_path],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode == 0:
        return True, "No breaking changes detected"
    else:
        return False, result.stdout or result.stderr


def check_breaking_python(pinned: dict, current: dict) -> list[str]:
    """Basic Python-based breaking change detection."""
    breaking = []

    pinned_paths = set(pinned.get("paths", {}).keys())
    current_paths = set(current.get("paths", {}).keys())

    # Check for removed endpoints
    removed = pinned_paths - current_paths
    for path in removed:
        breaking.append(f"REMOVED endpoint: {path}")

    # Check for removed methods on existing endpoints
    for path in pinned_paths & current_paths:
        pinned_methods = set(pinned["paths"][path].keys())
        current_methods = set(current["paths"][path].keys())
        for method in pinned_methods - current_methods:
            if method not in ["parameters", "summary", "description"]:
                breaking.append(f"REMOVED method: {method.upper()} {path}")

    # Check for removed schemas
    pinned_schemas = set(pinned.get("components", {}).get("schemas", {}).keys())
    current_schemas = set(current.get("components", {}).get("schemas", {}).keys())
    for schema in pinned_schemas - current_schemas:
        breaking.append(f"REMOVED schema: {schema}")

    return breaking


def main() -> int:
    print("🔍 Checking for breaking API changes...")

    pinned = load_pinned_schema()
    current = get_current_schema()

    # Try oasdiff first
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(current, f)
        current_path = f.name

    oasdiff = shutil.which("oasdiff")
    if oasdiff:
        success, message = check_with_oasdiff("docs/openapi.json", current_path)
        Path(current_path).unlink()
        if success:
            print(f"✅ {message}")
            return 0
        else:
            print(f"❌ Breaking changes detected:\n{message}")
            return 1

    # Fallback to Python
    Path(current_path).unlink()
    breaking = check_breaking_python(pinned, current)

    if not breaking:
        print("✅ No breaking changes detected (Python check)")
        return 0

    print("❌ Breaking changes detected:")
    for change in breaking:
        print(f"   - {change}")
    print("\nTo accept these changes, regenerate the pinned schema:")
    print("   uv run python scripts/export_openapi.py")
    return 1


if __name__ == "__main__":
    sys.exit(main())
