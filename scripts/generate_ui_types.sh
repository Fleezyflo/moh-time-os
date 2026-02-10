#!/usr/bin/env bash
# Generate TypeScript types from OpenAPI schema.
#
# Usage:
#   ./scripts/generate_ui_types.sh [--check]
#
# Requires: pnpm, openapi-typescript (installed via pnpm)
#
# --check: Verify generated.ts is up to date (exit 1 if drift)

set -euo pipefail

cd "$(dirname "$0")/.."

OPENAPI_FILE="docs/openapi.json"
OUTPUT_FILE="time-os-ui/src/types/generated.ts"
CHECK_MODE=false

if [[ "${1:-}" == "--check" ]]; then
    CHECK_MODE=true
fi

# Ensure OpenAPI file exists
if [[ ! -f "$OPENAPI_FILE" ]]; then
    echo "❌ $OPENAPI_FILE not found. Run: uv run python scripts/export_openapi.py"
    exit 1
fi

# Install openapi-typescript if needed
cd time-os-ui
if ! pnpm list openapi-typescript >/dev/null 2>&1; then
    echo "Installing openapi-typescript..."
    pnpm add -D openapi-typescript
fi

# Generate types to temp file
TEMP_FILE=$(mktemp)
pnpm exec openapi-typescript "../$OPENAPI_FILE" -o "$TEMP_FILE" 2>/dev/null

# Add header
HEADER="// AUTO-GENERATED from docs/openapi.json — DO NOT EDIT
// Regenerate: ./scripts/generate_ui_types.sh
// Source: FastAPI OpenAPI schema

"

echo "$HEADER$(cat "$TEMP_FILE")" > "$TEMP_FILE.final"
mv "$TEMP_FILE.final" "$TEMP_FILE"

cd ..

if $CHECK_MODE; then
    if [[ ! -f "$OUTPUT_FILE" ]]; then
        echo "❌ $OUTPUT_FILE does not exist. Run without --check to generate."
        rm "$TEMP_FILE"
        exit 1
    fi

    if ! diff -q "$OUTPUT_FILE" "$TEMP_FILE" >/dev/null 2>&1; then
        echo "❌ UI types drift detected! $OUTPUT_FILE is stale."
        echo "   Run: ./scripts/generate_ui_types.sh"
        rm "$TEMP_FILE"
        exit 1
    fi

    echo "✅ $OUTPUT_FILE is up to date."
    rm "$TEMP_FILE"
    exit 0
fi

# Generate mode
mv "$TEMP_FILE" "$OUTPUT_FILE"
echo "✅ Generated TypeScript types: $OUTPUT_FILE"
