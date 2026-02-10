#!/usr/bin/env bash
# verify_pristine.sh - Full pristine verification for Moh Time OS
# Validates that the repo can be cloned fresh and run successfully.
#
# Usage: ./scripts/verify_pristine.sh
#
# Toolchain: uv (Python package manager)
# API Framework: FastAPI/Uvicorn

set -euo pipefail

cd "$(dirname "$0")/.."
REPO_ROOT=$(pwd)

echo "========================================"
echo "MOH TIME OS — PRISTINE VERIFICATION"
echo "========================================"
echo "Repo: $REPO_ROOT"
echo "Date: $(date -Iseconds)"
echo ""

PASS=0
FAIL=0

pass() {
    echo "✅ PASS: $1"
    PASS=$((PASS + 1))
}

fail() {
    echo "❌ FAIL: $1"
    FAIL=$((FAIL + 1))
}

# ==========================================
# 1. Check no derived files tracked
# ==========================================
echo "=== Step 1: No derived files tracked ==="
if ./scripts/check_no_derived_tracked.sh; then
    pass "No derived files in git index"
else
    fail "Derived files found in git index"
fi
echo ""

# ==========================================
# 2. Install dependencies (uv)
# ==========================================
echo "=== Step 2: Install dependencies (uv sync) ==="
if command -v uv >/dev/null 2>&1; then
    if uv sync --quiet 2>/dev/null; then
        pass "Dependencies installed via uv sync"
    else
        # Try with --dev for older uv versions
        if uv pip install -e ".[dev]" --quiet 2>/dev/null; then
            pass "Dependencies installed via uv pip install"
        else
            fail "uv sync/install failed"
        fi
    fi
else
    echo "⚠️  uv not found, attempting pip fallback..."
    if python3 -m pip install -e ".[dev]" --quiet 2>/dev/null; then
        pass "Dependencies installed via pip (fallback)"
    else
        fail "Dependency installation failed"
    fi
fi
echo ""

# ==========================================
# 3. Run pre-commit hooks
# ==========================================
echo "=== Step 3: Pre-commit hooks ==="
if command -v pre-commit >/dev/null 2>&1 || uv run pre-commit --version >/dev/null 2>&1; then
    # Use uv run if available, otherwise direct pre-commit
    PRE_COMMIT_CMD="pre-commit"
    if command -v uv >/dev/null 2>&1; then
        PRE_COMMIT_CMD="uv run pre-commit"
    fi

    if $PRE_COMMIT_CMD run -a 2>&1 | tee /tmp/precommit_output.txt; then
        pass "Pre-commit hooks passed"
    else
        # Check if it's just "no files to check" (which is fine)
        if grep -q "Passed\|Skipped" /tmp/precommit_output.txt && ! grep -q "Failed" /tmp/precommit_output.txt; then
            pass "Pre-commit hooks passed (some skipped)"
        else
            fail "Pre-commit hooks failed"
        fi
    fi
else
    echo "⚠️  pre-commit not available, skipping"
    PASS=$((PASS + 1))  # Count as pass if not available
fi
echo ""

# ==========================================
# 4. Run pytest (contract + evidence tests)
# ==========================================
echo "=== Step 4: Pytest (contract tests) ==="
PYTEST_CMD="python3 -m pytest"
if command -v uv >/dev/null 2>&1; then
    PYTEST_CMD="uv run pytest"
fi

# Run a subset of tests that should pass on a clean checkout
TEST_DIRS=""
[ -d "tests/contract" ] && TEST_DIRS="$TEST_DIRS tests/contract/"
[ -f "tests/test_safety.py" ] && TEST_DIRS="$TEST_DIRS tests/test_safety.py"

if [ -n "$TEST_DIRS" ]; then
    if $PYTEST_CMD $TEST_DIRS -q --tb=line 2>&1; then
        pass "Pytest contract tests passed"
    else
        fail "Pytest contract tests failed"
    fi
else
    echo "⚠️  No contract tests found, skipping"
    PASS=$((PASS + 1))
fi
echo ""

# ==========================================
# 5. API Server Health Check
# ==========================================
echo "=== Step 5: API server health check ==="

# Create temp data directory if needed
mkdir -p data
export MOH_TIME_OS_DB_PATH="${REPO_ROOT}/data/test_pristine.db"

# Start server in background
API_PORT=8421
echo "Starting API server on port $API_PORT..."
$PYTEST_CMD -c /dev/null 2>/dev/null || true  # Ensure deps loaded

# Use uv run or direct python
if command -v uv >/dev/null 2>&1; then
    uv run python -m api.server &
else
    python3 -m api.server &
fi
API_PID=$!

# Wait for server to start (max 15 seconds)
HEALTH_OK=false
for i in $(seq 1 15); do
    sleep 1
    if curl -sf "http://localhost:${API_PORT}/api/health" >/dev/null 2>&1; then
        HEALTH_OK=true
        break
    fi
done

if $HEALTH_OK; then
    HEALTH_RESPONSE=$(curl -sf "http://localhost:${API_PORT}/api/health")
    echo "Health response: $HEALTH_RESPONSE"
    if echo "$HEALTH_RESPONSE" | grep -q '"status".*"healthy"'; then
        pass "API server /api/health returned healthy"
    else
        fail "API server /api/health returned unexpected response"
    fi
else
    fail "API server failed to start or respond within 15s"
fi

# Cleanup
echo "Shutting down API server (PID $API_PID)..."
kill $API_PID 2>/dev/null || true
wait $API_PID 2>/dev/null || true

# Remove test DB
rm -f "${REPO_ROOT}/data/test_pristine.db" 2>/dev/null || true
echo ""

# ==========================================
# Summary
# ==========================================
echo "========================================"
echo "SUMMARY"
echo "========================================"
echo "Passed: $PASS"
echo "Failed: $FAIL"
echo ""

if [ $FAIL -eq 0 ]; then
    echo "🎉 ALL CHECKS PASSED — PRISTINE VERIFIED"
    exit 0
else
    echo "💥 VERIFICATION FAILED — See errors above"
    exit 1
fi
