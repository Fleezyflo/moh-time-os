#!/usr/bin/env bash
# Security audit: pip-audit, pnpm audit, gitleaks, SBOM generation.
#
# Usage:
#   ./scripts/security_audit.sh [--ci]
#
# --ci: Fail on any vulnerability (for CI enforcement)

set -euo pipefail

cd "$(dirname "$0")/.."

CI_MODE=false
if [[ "${1:-}" == "--ci" ]]; then
    CI_MODE=true
fi

FAILURES=0

echo "========================================"
echo "SECURITY AUDIT"
echo "========================================"
echo ""

# ==========================================
# 1. Python Dependency Audit (pip-audit)
# ==========================================
echo "=== 1. Python Dependencies (pip-audit) ==="
if command -v pip-audit >/dev/null 2>&1 || uv run pip-audit --version >/dev/null 2>&1; then
    if uv run pip-audit --require-hashes=false 2>&1; then
        echo "✅ No Python vulnerabilities found"
    else
        echo "⚠️  Python vulnerabilities detected"
        if $CI_MODE; then
            FAILURES=$((FAILURES + 1))
        fi
    fi
else
    echo "⚠️  pip-audit not installed. Install: uv pip install pip-audit"
fi
echo ""

# ==========================================
# 2. UI Dependency Audit (pnpm audit)
# ==========================================
echo "=== 2. UI Dependencies (pnpm audit) ==="
if [[ -d "time-os-ui" ]]; then
    cd time-os-ui
    if command -v pnpm >/dev/null 2>&1; then
        if pnpm audit --audit-level=high 2>&1; then
            echo "✅ No high-severity UI vulnerabilities found"
        else
            echo "⚠️  UI vulnerabilities detected"
            if $CI_MODE; then
                FAILURES=$((FAILURES + 1))
            fi
        fi
    else
        echo "⚠️  pnpm not installed"
    fi
    cd ..
else
    echo "⚠️  time-os-ui not found"
fi
echo ""

# ==========================================
# 3. Secrets Detection (gitleaks)
# ==========================================
echo "=== 3. Secrets Detection (gitleaks) ==="
if command -v gitleaks >/dev/null 2>&1; then
    if gitleaks detect --source . --no-git 2>&1; then
        echo "✅ No secrets detected"
    else
        echo "❌ Secrets detected!"
        FAILURES=$((FAILURES + 1))
    fi
else
    echo "⚠️  gitleaks not installed. Install: brew install gitleaks"
fi
echo ""

# ==========================================
# 4. SBOM Generation
# ==========================================
echo "=== 4. SBOM Generation ==="
SBOM_DIR="docs/sbom"
mkdir -p "$SBOM_DIR"

# Python SBOM
if command -v pip-audit >/dev/null 2>&1 || uv run pip-audit --version >/dev/null 2>&1; then
    echo "Generating Python SBOM..."
    uv run pip freeze > "$SBOM_DIR/python-requirements.txt" 2>/dev/null || true
    echo "✅ Python SBOM: $SBOM_DIR/python-requirements.txt"
fi

# UI SBOM
if [[ -d "time-os-ui" ]] && command -v pnpm >/dev/null 2>&1; then
    echo "Generating UI SBOM..."
    cd time-os-ui
    pnpm list --depth=0 > "../$SBOM_DIR/ui-dependencies.txt" 2>/dev/null || true
    cd ..
    echo "✅ UI SBOM: $SBOM_DIR/ui-dependencies.txt"
fi
echo ""

# ==========================================
# Summary
# ==========================================
echo "========================================"
if [[ $FAILURES -eq 0 ]]; then
    echo "✅ SECURITY AUDIT PASSED"
    exit 0
else
    echo "❌ SECURITY AUDIT FAILED ($FAILURES issues)"
    exit 1
fi
