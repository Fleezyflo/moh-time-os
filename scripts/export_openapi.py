#!/usr/bin/env python3
"""
Export OpenAPI schema from FastAPI app.

Usage:
    uv run python scripts/export_openapi.py [--check]

    --check: Verify existing docs/openapi.json matches current schema (exit 1 if drift)
"""

import argparse
import json
import sys
from pathlib import Path


def get_openapi_schema() -> dict:
    """Import the FastAPI app and extract OpenAPI schema."""
    # Import here to avoid circular imports and ensure fresh state
    from api.server import app

    return app.openapi()


def main() -> int:
    parser = argparse.ArgumentParser(description="Export OpenAPI schema")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if docs/openapi.json is up to date (exit 1 if drift)",
    )
    parser.add_argument(
        "--output",
        default="docs/openapi.json",
        help="Output path (default: docs/openapi.json)",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    schema = get_openapi_schema()
    schema_json = json.dumps(schema, indent=2, sort_keys=True) + "\n"

    if args.check:
        if not output_path.exists():
            print(f"❌ {output_path} does not exist. Run without --check to generate.")
            return 1

        existing = output_path.read_text()
        if existing != schema_json:
            print(f"❌ OpenAPI drift detected! {output_path} is stale.")
            print("   Run: uv run python scripts/export_openapi.py")
            return 1

        print(f"✅ {output_path} is up to date.")
        return 0

    # Generate mode
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(schema_json)
    print(f"✅ Exported OpenAPI schema to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
