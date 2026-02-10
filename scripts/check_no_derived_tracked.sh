#!/usr/bin/env bash
# check_no_derived_tracked.sh - Verify no derived files are tracked in git
# Exit 1 if any derived files are found, exit 0 if clean.

set -euo pipefail

cd "$(dirname "$0")/.."

# Pattern for derived files that should never be tracked
DERIVED_PATTERN='__pycache__|\.pyc$|\.pyo$|\.pyd$|\.db$|\.db-shm$|\.db-wal$|\.bak$|\.backup$|\.log$|\.DS_Store|^data/|^out/|^output/|^logs/|^\.logs/|\.egg-info|^dist/|^build/|agent_state\.json$|agent_index_log\.md$|node_modules|time-os-ui/dist|time-os-ui/build'

# Check for derived files
DERIVED_FILES=$(git ls-files | grep -E "$DERIVED_PATTERN" || true)

if [ -n "$DERIVED_FILES" ]; then
    echo "❌ ERROR: Found derived files tracked in git:"
    echo "$DERIVED_FILES" | head -20
    TOTAL=$(echo "$DERIVED_FILES" | wc -l | tr -d ' ')
    if [ "$TOTAL" -gt 20 ]; then
        echo "... and $((TOTAL - 20)) more"
    fi
    echo ""
    echo "To fix, run:"
    echo "  git rm --cached <file>..."
    exit 1
fi

echo "✓ No derived files tracked in git"
exit 0
