#!/bin/zsh
# Moh Time OS — Verification Script
# Usage: zsh scripts/verify_timeos.sh
set -uo pipefail

cd "$(dirname "$0")/.."

echo "========================================"
echo "MOH TIME OS — Verification Pack"
echo "========================================"

echo ""
echo "=== 1. GIT STATUS (staged changes) ==="
git diff --cached --name-only | head -20 || echo "(none)"
echo "(First 20 staged files)"

echo ""
echo "=== 2. NO DERIVED FILES TRACKED ==="
DERIVED=$(git ls-files | grep -E "__pycache__|\.pyc$|\.db$|\.db-|\.bak$|\.log$|\.DS_Store|^data/|^out/|^output/" | wc -l | tr -d ' ')
if [ "$DERIVED" -eq 0 ]; then
    echo "✓ No derived files tracked (count: $DERIVED)"
else
    echo "✗ Found $DERIVED derived files still tracked:"
    git ls-files | grep -E "__pycache__|\.pyc$|\.db$|\.db-|\.bak$|\.log$|\.DS_Store|^data/|^out/|^output/" | head -10
    exit 1
fi

echo ""
echo "=== 3. PRE-COMMIT HOOKS ==="
uv run pre-commit run -a || true

echo ""
echo "=== 4. PYTEST (inbox evidence + collector registry) ==="
uv run pytest -q tests/contract/test_collector_registry.py tests/test_inbox_evidence_persistence.py

echo ""
echo "=== 5. DB PAYLOAD COMPLETENESS ==="
sqlite3 data/moh_time_os.db "
SELECT
    COUNT(*) AS total,
    SUM(CASE WHEN
        json_extract(evidence, '\$.payload.sender') IS NOT NULL
        AND json_extract(evidence, '\$.payload.subject') IS NOT NULL
        AND json_extract(evidence, '\$.url') IS NOT NULL
    THEN 1 ELSE 0 END) AS complete
FROM inbox_items_v29
WHERE type='flagged_signal';
"

echo ""
echo "=== 6. DB FRESHNESS ==="
sqlite3 data/moh_time_os.db "
SELECT MAX(updated_at) AS max_updated, MAX(created_at) AS max_created
FROM inbox_items_v29;
"

echo ""
echo "=== 7. SAMPLE INBOX ITEM ==="
sqlite3 -json data/moh_time_os.db "
SELECT id,
    json_extract(evidence, '\$.payload.sender') AS sender,
    json_extract(evidence, '\$.payload.subject') AS subject,
    json_extract(evidence, '\$.url') AS url
FROM inbox_items_v29
WHERE type='flagged_signal'
LIMIT 1;
"

echo ""
echo "========================================"
echo "✓ VERIFICATION COMPLETE"
echo "========================================"
