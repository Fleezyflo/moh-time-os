#!/usr/bin/env bash
# Check if an ADR is required for the current changes.
#
# ADR required when changes touch:
# - DB schema (lib/safety/schema.py, lib/migrations/, docs/schema.sql)
# - API routes/models (api/server.py, api/spec_router.py)
# - V5 architecture (lib/v5/)
# - System-map generator (scripts/generate_system_map.py)
#
# Usage: ./scripts/check_adr_required.sh [base_ref]
#
# Exit codes:
#   0: No ADR required OR ADR was added
#   1: ADR required but not found

set -euo pipefail

BASE_REF="${1:-origin/main}"

# Patterns that require an ADR
ADR_TRIGGERS=(
    "lib/safety/schema.py"
    "lib/migrations/"
    "docs/schema.sql"
    "api/server.py"
    "api/spec_router.py"
    "lib/v5/"
    "scripts/generate_system_map.py"
)

# Get list of changed files
CHANGED_FILES=$(git diff --name-only "$BASE_REF" 2>/dev/null || git diff --name-only HEAD~1)

echo "📋 Checking if ADR is required..."
echo "   Base: $BASE_REF"
echo ""

# Check if any trigger files were changed
TRIGGERS_HIT=()
for pattern in "${ADR_TRIGGERS[@]}"; do
    if echo "$CHANGED_FILES" | grep -q "^$pattern"; then
        TRIGGERS_HIT+=("$pattern")
    fi
done

if [ ${#TRIGGERS_HIT[@]} -eq 0 ]; then
    echo "✅ No ADR required (no trigger files changed)"
    exit 0
fi

echo "   Trigger files changed:"
for t in "${TRIGGERS_HIT[@]}"; do
    echo "     - $t"
done
echo ""

# Check if an ADR was added or modified
ADR_CHANGED=$(echo "$CHANGED_FILES" | grep "^docs/adr/[0-9]" || true)

if [ -n "$ADR_CHANGED" ]; then
    echo "✅ ADR found in changes:"
    echo "$ADR_CHANGED" | sed 's/^/     /'
    exit 0
fi

# Check commit message for ADR reference
COMMIT_MSG=$(git log -1 --pretty=%B 2>/dev/null || echo "")

if echo "$COMMIT_MSG" | grep -qi "ADR-[0-9]\|docs/adr/"; then
    echo "✅ ADR reference found in commit message"
    exit 0
fi

# ADR required but not found
echo "❌ ADR REQUIRED but not found"
echo ""
echo "   Changes to the following require an ADR:"
for t in "${TRIGGERS_HIT[@]}"; do
    echo "     - $t"
done
echo ""
echo "   To fix, add an ADR file:"
echo "     cp docs/adr/0000-template.md docs/adr/NNNN-your-decision.md"
echo "     # Edit and commit"
echo ""
echo "   Or reference an existing ADR in your commit message:"
echo "     git commit --amend -m 'feat: ... (ADR-0001)'"
echo ""

exit 1
