#!/usr/bin/env bash
set -e

# Wire intelligence + mutation routes into spec_router
# Run this from the repo root on Mac

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Push intelligence routes"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Discard any sandbox contamination
echo ""
echo "[1/6] Cleaning sandbox artifacts..."
git checkout -- uv.lock 2>/dev/null || true
rm -f test_output.txt

# 2. Create branch
BRANCH="feat/wire-intelligence-routes"
echo "[2/6] Creating branch: $BRANCH"
git checkout -b "$BRANCH" 2>/dev/null || git checkout "$BRANCH"

# 3. Regenerate drift artifacts
echo "[3/6] Regenerating drift artifacts..."
uv run python scripts/export_openapi.py
uv run python scripts/export_schema.py

# Regenerate UI types if the script exists
if [ -f scripts/generate_ui_types.sh ]; then
    bash scripts/generate_ui_types.sh
fi

# 4. Stage files
echo "[4/6] Staging files..."
git add api/spec_router.py
git add docs/openapi.json
git add docs/schema.sql
git add time-os-ui/src/types/generated.ts 2>/dev/null || true

# 5. Commit
echo "[5/6] Committing..."
git commit -m "$(cat <<'EOF'
feat(api): wire 31 missing spec_router endpoints for UI

Wire all intelligence + mutation endpoints that the UI calls but
spec_router was missing. The UI was completely broken because it
calls /api/v2/* exclusively via Vite proxy, but spec_router only
had ~35 of the ~67 needed routes.

Added:
- 21 intelligence GET endpoints (critical, briefing, signals,
  patterns, proposals, scores, entity profiles, trajectories)
- 7 mutation POST endpoints (proposal snooze/dismiss, watcher
  snooze/dismiss, fix-data resolve, issue create, issue notes)
- 2 PATCH endpoints for issue resolve/state compatibility
- Helper functions _intel_response/_intel_error for ApiResponse
  envelope the UI expects
- 10 Pydantic request body models

Each route wired to actual backend implementation — no stubs.

large-change
EOF
)"

# 6. Push
echo "[6/6] Pushing..."
git push -u origin "$BRANCH"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ Done. Create PR from $BRANCH"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
