#!/usr/bin/env bash
# CI Gate: Ensure tests don't directly reference the live database path.
# This prevents non-deterministic tests that depend on user data.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "🔍 Checking for live DB references in tests..."

# Patterns that indicate live DB usage (not fixture-based)
# Exclude conftest.py since it contains the guard and documentation
VIOLATIONS=$(grep -r --include="*.py" \
    -E 'data/moh_time_os\.db|DB_PATH\s*=.*data.*moh_time_os' \
    tests/ \
    --exclude="conftest.py" \
    --exclude="fixture_db.py" \
    2>/dev/null || true)

if [ -n "$VIOLATIONS" ]; then
    echo "❌ DETERMINISM VIOLATION: Found live DB references in tests:"
    echo "$VIOLATIONS"
    echo ""
    echo "Fix: Tests must use fixture_db.py, not data/moh_time_os.db"
    echo "See: tests/fixtures/fixture_db.py"
    exit 1
fi

# Additional check: ensure golden tests import from fixtures
GOLDEN_IMPORTS=$(grep -l "from tests.fixtures" tests/golden/*.py 2>/dev/null | wc -l | tr -d ' ')
GOLDEN_FILES=$(ls tests/golden/test_*.py 2>/dev/null | wc -l | tr -d ' ')

# conftest.py should have the import
if ! grep -q "from tests.fixtures" tests/golden/conftest.py 2>/dev/null; then
    echo "❌ tests/golden/conftest.py must import from tests.fixtures"
    exit 1
fi

echo "✅ No live DB references found in tests"
echo "✅ Golden tests use fixture infrastructure"
