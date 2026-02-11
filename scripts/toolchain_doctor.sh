#!/usr/bin/env bash
# Toolchain doctor - verify all required tools and lockfiles.
#
# Checks:
# 1. Python version matches .python-version
# 2. Node version matches .nvmrc
# 3. uv.lock exists and is valid
# 4. pnpm-lock.yaml exists
# 5. Required tools installed
#
# Usage: ./scripts/toolchain_doctor.sh
#
# Exit codes:
#   0: All checks pass
#   1: One or more checks failed

set -euo pipefail

cd "$(dirname "$0")/.."

PASS=0
FAIL=0

pass() {
    echo "✅ $1"
    PASS=$((PASS + 1))
}

fail() {
    echo "❌ $1"
    FAIL=$((FAIL + 1))
}

warn() {
    echo "⚠️  $1"
}

echo "🩺 Toolchain Doctor"
echo "==================="
echo ""

# ==========================================
# Python Version
# ==========================================
echo "=== Python ==="

REQUIRED_PYTHON=""
if [ -f ".python-version" ]; then
    REQUIRED_PYTHON=$(cat .python-version | tr -d '\n')
fi

if [ -z "$REQUIRED_PYTHON" ]; then
    warn "No .python-version file found"
else
    CURRENT_PYTHON=$(python3 --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | head -1)
    CURRENT_MAJOR=$(echo "$CURRENT_PYTHON" | cut -d. -f1)
    REQUIRED_MAJOR=$(echo "$REQUIRED_PYTHON" | cut -d. -f1)
    CURRENT_MINOR=$(echo "$CURRENT_PYTHON" | cut -d. -f2)
    REQUIRED_MINOR=$(echo "$REQUIRED_PYTHON" | cut -d. -f2)

    # Allow equal or newer minor version
    if [ "$CURRENT_MAJOR" -eq "$REQUIRED_MAJOR" ] && [ "$CURRENT_MINOR" -ge "$REQUIRED_MINOR" ]; then
        pass "Python version: $CURRENT_PYTHON (min: $REQUIRED_PYTHON)"
    else
        fail "Python version mismatch: $CURRENT_PYTHON (min: $REQUIRED_PYTHON)"
    fi
fi

# uv installed
if command -v uv >/dev/null 2>&1; then
    UV_VERSION=$(uv --version 2>&1 | head -1)
    pass "uv installed: $UV_VERSION"
else
    fail "uv not installed"
fi

# uv.lock exists
if [ -f "uv.lock" ]; then
    pass "uv.lock exists"
else
    fail "uv.lock missing (run: uv lock)"
fi

echo ""

# ==========================================
# Node Version
# ==========================================
echo "=== Node.js ==="

REQUIRED_NODE=""
if [ -f ".nvmrc" ]; then
    REQUIRED_NODE=$(cat .nvmrc | tr -d '\n')
fi

if [ -z "$REQUIRED_NODE" ]; then
    warn "No .nvmrc file found"
else
    CURRENT_NODE=$(node --version 2>/dev/null | grep -oE '[0-9]+' | head -1)
    # Allow equal or newer major version
    if [ "$CURRENT_NODE" -ge "$REQUIRED_NODE" ]; then
        pass "Node version: v$CURRENT_NODE (min: $REQUIRED_NODE)"
    else
        fail "Node version mismatch: v$CURRENT_NODE (min: $REQUIRED_NODE)"
    fi
fi

# pnpm installed
if command -v pnpm >/dev/null 2>&1; then
    PNPM_VERSION=$(pnpm --version 2>&1 | head -1)
    pass "pnpm installed: $PNPM_VERSION"
else
    fail "pnpm not installed"
fi

# pnpm-lock.yaml exists
if [ -f "time-os-ui/pnpm-lock.yaml" ]; then
    pass "pnpm-lock.yaml exists"
else
    fail "pnpm-lock.yaml missing (run: cd time-os-ui && pnpm install)"
fi

echo ""

# ==========================================
# Required Tools
# ==========================================
echo "=== Required Tools ==="

TOOLS=("git" "curl" "make")
for tool in "${TOOLS[@]}"; do
    if command -v "$tool" >/dev/null 2>&1; then
        pass "$tool installed"
    else
        fail "$tool not installed"
    fi
done

echo ""

# ==========================================
# Portable Timeout Wrapper
# ==========================================
echo "=== Portability ==="

# Check timeout wrapper exists and works
if [ -f "scripts/timeout.py" ]; then
    # Quick self-test (should complete in <2s)
    if python3 scripts/timeout.py 2 -- python3 -c "print('ok')" >/dev/null 2>&1; then
        pass "scripts/timeout.py works (portable timeout)"
    else
        fail "scripts/timeout.py failed self-test"
    fi
else
    fail "scripts/timeout.py missing (portable timeout wrapper)"
fi

echo ""

# ==========================================
# Summary
# ==========================================
echo "==================="
echo "Summary: $PASS passed, $FAIL failed"

if [ "$FAIL" -gt 0 ]; then
    echo ""
    echo "Fix the above issues before proceeding."
    exit 1
fi

echo ""
echo "✅ Toolchain healthy!"
exit 0
