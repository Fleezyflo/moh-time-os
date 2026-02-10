#!/bin/bash
# scripts/patchwork_scan.sh
#
# STRICT Patchwork Anti-Pattern Scan
# Per IMPLEMENTATION_PLAN_V4_FROZEN.md Amendment 1 + GLOBAL_PROMPT tenets
#
# This script scans for post-processing patterns that violate the
# "no patchwork" constraint. Logic must live in extract/normalize/aggregate,
# not in post-build mutations.
#
# ALWAYS STRICT: Exits non-zero on ANY match (--ci is accepted but redundant).
#
# SCAN PATHS (critical):
#   - lib/agency_snapshot/
#   - lib/contracts/
#   - lib/normalize/
#
# BANNED PATTERNS (any match = failure):
#   - .setdefault(           # lazy initialization in output path
#   - .update({              # dict surgery (specific to dict literal)
#   - deepmerge              # merging into final output
#   - enrich_snapshot        # post-hoc enrichment function calls
#   - snapshot[...] =        # direct mutation (only AFTER boundary in generator.py)
#
# SPECIAL HANDLING:
#   - generator.py: snapshot mutations allowed BEFORE "PATCHWORK_BOUNDARY" marker
#   - Other files: snapshot mutations banned entirely
#
# USAGE:
#   ./scripts/patchwork_scan.sh          # strict mode (default)
#   ./scripts/patchwork_scan.sh --ci     # same as above (CI compatibility)

set -euo pipefail

# --ci flag accepted for compatibility but mode is always strict
MODE="strict"
if [ "${1:-}" = "--ci" ]; then
    MODE="strict"
fi

echo "╔════════════════════════════════════════════════════════════╗"
echo "║          PATCHWORK ANTI-PATTERN SCAN (STRICT)              ║"
echo "╠════════════════════════════════════════════════════════════╣"
echo "║ Scanning: lib/agency_snapshot/, lib/contracts/, lib/normalize/"
echo "║ Mode: $MODE (always strict - exits non-zero on ANY match)"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Critical paths to scan
SCAN_PATHS=(
    "lib/agency_snapshot/"
    "lib/contracts/"
    "lib/normalize/"
)

# Verify paths exist
for path in "${SCAN_PATHS[@]}"; do
    if [ ! -d "$path" ]; then
        echo "⚠️  Warning: $path does not exist, skipping"
    fi
done

# Track violations
TOTAL_MATCHES=0
VIOLATION_LOG=""

# ───────────────────────────────────────────────────────────────────
# SCAN 1: Universal patterns (banned everywhere)
# ───────────────────────────────────────────────────────────────────

declare -A UNIVERSAL_PATTERNS=(
    # Dict mutation patterns (output surgery)
    ["setdefault"]="\.setdefault\s*\("
    ["update_dict"]="\.update\s*\(\s*\{"

    # Deep merge utilities
    ["deepmerge"]="deepmerge|deep_merge"

    # Post-hoc enrichment
    ["enrich_snapshot"]="enrich_snapshot"
)

echo "Phase 1: Scanning for universal banned patterns..."

for pattern_name in "${!UNIVERSAL_PATTERNS[@]}"; do
    pattern="${UNIVERSAL_PATTERNS[$pattern_name]}"

    for scan_path in "${SCAN_PATHS[@]}"; do
        if [ ! -d "$scan_path" ]; then
            continue
        fi

        while IFS= read -r match; do
            if [ -z "$match" ]; then
                continue
            fi

            file=$(echo "$match" | cut -d: -f1)
            lineno=$(echo "$match" | cut -d: -f2)
            content=$(echo "$match" | cut -d: -f3-)

            # Exclude comments
            if echo "$content" | grep -qE '^\s*#'; then
                continue
            fi

            # Exclude test files
            if [[ "$file" == *"test_"* ]] || [[ "$file" == *"_test.py"* ]]; then
                continue
            fi

            # Exclude string literals (pattern definitions)
            if echo "$content" | grep -qiE 'PATTERNS\s*=|BANNED|".*setdefault.*"'; then
                continue
            fi

            TOTAL_MATCHES=$((TOTAL_MATCHES + 1))
            VIOLATION_LOG+="[$pattern_name] $file:$lineno: $content
"
        done < <(grep -rn --include="*.py" -E "$pattern" "$scan_path" 2>/dev/null | grep -v __pycache__ || true)
    done
done

# ───────────────────────────────────────────────────────────────────
# SCAN 2: Snapshot mutation patterns (context-dependent)
# ───────────────────────────────────────────────────────────────────

echo "Phase 2: Scanning for post-assembly snapshot mutations..."

# Pattern for snapshot mutations
MUTATION_PATTERN='snapshot\[.+\]\s*='

for scan_path in "${SCAN_PATHS[@]}"; do
    if [ ! -d "$scan_path" ]; then
        continue
    fi

    while IFS= read -r match; do
        if [ -z "$match" ]; then
            continue
        fi

        file=$(echo "$match" | cut -d: -f1)
        lineno=$(echo "$match" | cut -d: -f2)
        content=$(echo "$match" | cut -d: -f3-)

        # Exclude comments
        if echo "$content" | grep -qE '^\s*#'; then
            continue
        fi

        # Exclude test files
        if [[ "$file" == *"test_"* ]] || [[ "$file" == *"_test.py"* ]]; then
            continue
        fi

        # Exclude initial creation: snapshot = {
        if echo "$content" | grep -qE '^\s*snapshot\s*=\s*\{'; then
            continue
        fi

        # SPECIAL CASE: generator.py
        # Only flag mutations AFTER the PATCHWORK_BOUNDARY marker
        if [[ "$file" == *"generator.py" ]]; then
            # Find the line number of PATCHWORK_BOUNDARY
            boundary_line=$(grep -n "PATCHWORK_BOUNDARY" "$file" 2>/dev/null | head -1 | cut -d: -f1 || echo "99999")

            if [ -n "$boundary_line" ] && [ "$lineno" -lt "$boundary_line" ]; then
                # Before boundary = legitimate build phase, skip
                continue
            fi
        fi

        TOTAL_MATCHES=$((TOTAL_MATCHES + 1))
        VIOLATION_LOG+="[snapshot_mutation] $file:$lineno: $content
"
    done < <(grep -rn --include="*.py" -E "$MUTATION_PATTERN" "$scan_path" 2>/dev/null | grep -v __pycache__ || true)
done

# ───────────────────────────────────────────────────────────────────
# RESULTS
# ───────────────────────────────────────────────────────────────────

echo ""
echo "════════════════════════════════════════════════════════════"

if [ "$TOTAL_MATCHES" -gt 0 ]; then
    echo "❌ PATCHWORK VIOLATIONS FOUND"
    echo ""
    echo "MATCH COUNT: $TOTAL_MATCHES"
    echo ""
    echo "VIOLATIONS:"
    echo "────────────────────────────────────────────────────────────"
    echo "$VIOLATION_LOG"
    echo "────────────────────────────────────────────────────────────"
    echo ""
    echo "These patterns suggest post-processing. Move logic upstream to:"
    echo "  • lib/normalize/extractors/ (for extraction logic)"
    echo "  • lib/normalize/resolvers.py (for resolution logic)"
    echo "  • Build sections in generator.py BEFORE PATCHWORK_BOUNDARY"
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "SCAN FAILED"
    exit 1
else
    echo "✅ No patchwork patterns detected"
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "SCAN PASSED"
    exit 0
fi
