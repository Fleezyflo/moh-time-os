#!/usr/bin/env bash
# verify_github_rulesets.sh — Verify GitHub Rulesets are correctly configured
#
# Checks that all required rulesets exist, are active, and have correct settings.
# Fails if any ruleset is missing, misconfigured, or has bypass actors.
#
# Prerequisites:
#   - gh CLI installed and authenticated
#   - Repository read access
#
# Usage:
#   ./scripts/verify_github_rulesets.sh
#   REPO=owner/repo ./scripts/verify_github_rulesets.sh

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Get repo
REPO="${REPO:-$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "")}"

if [[ -z "$REPO" ]]; then
    echo -e "${RED}ERROR: Could not detect repository. Set REPO=owner/repo${NC}"
    exit 1
fi

echo "═══════════════════════════════════════════════════════════════════"
echo "  GitHub Rulesets Verification for: $REPO"
echo "═══════════════════════════════════════════════════════════════════"
echo ""

# Fetch all rulesets
echo "Fetching rulesets..."
RULESETS=$(gh api "repos/$REPO/rulesets" 2>/dev/null || echo "[]")

if [[ "$RULESETS" == "[]" ]] || [[ -z "$RULESETS" ]]; then
    echo -e "${RED}ERROR: No rulesets found or API access denied${NC}"
    exit 1
fi

RULESET_COUNT=$(echo "$RULESETS" | jq 'length')
echo -e "Found ${CYAN}$RULESET_COUNT${NC} rulesets"
echo ""

# Track issues
ISSUES=0

# Expected rulesets
declare -A EXPECTED_RULESETS=(
    ["Main Gate"]="branch"
    ["Sandbox Guard"]="branch"
    ["Tag Protection"]="tag"
    ["Workflow Protection"]="branch"
    ["Sensitive File Gate"]="push"
    ["Config Protection"]="branch"
)

# Expected status checks for Main Gate
MAIN_GATE_CHECKS=(
    "pre-commit"
    "python-guards"
    "security-scan"
    "route-integrity"
    "ratchet"
    "test"
    "build-ui"
)

# Expected status checks for Sandbox Guard
SANDBOX_CHECKS=(
    "Sandbox Security"
)

# Function to check a ruleset
check_ruleset() {
    local name="$1"
    local expected_target="$2"
    
    echo -e "${CYAN}Checking: $name${NC}"
    
    # Find ruleset by name
    local ruleset
    ruleset=$(echo "$RULESETS" | jq -r ".[] | select(.name == \"$name\")")
    
    if [[ -z "$ruleset" ]] || [[ "$ruleset" == "null" ]]; then
        echo -e "  ${RED}✗ MISSING: Ruleset not found${NC}"
        ISSUES=$((ISSUES + 1))
        return 1
    fi
    
    local id target enforcement bypass_count
    id=$(echo "$ruleset" | jq -r '.id')
    target=$(echo "$ruleset" | jq -r '.target')
    enforcement=$(echo "$ruleset" | jq -r '.enforcement')
    bypass_count=$(echo "$ruleset" | jq '.bypass_actors | length')
    
    echo "  ID: $id"
    
    # Check target
    if [[ "$target" != "$expected_target" ]]; then
        echo -e "  ${RED}✗ Target: $target (expected: $expected_target)${NC}"
        ISSUES=$((ISSUES + 1))
    else
        echo -e "  ${GREEN}✓ Target: $target${NC}"
    fi
    
    # Check enforcement
    if [[ "$enforcement" != "active" ]]; then
        echo -e "  ${RED}✗ Enforcement: $enforcement (expected: active)${NC}"
        ISSUES=$((ISSUES + 1))
    else
        echo -e "  ${GREEN}✓ Enforcement: active${NC}"
    fi
    
    # Check bypass actors
    if [[ "$bypass_count" -gt 0 ]]; then
        echo -e "  ${RED}✗ Bypass actors: $bypass_count (expected: 0)${NC}"
        echo "$ruleset" | jq -r '.bypass_actors[] | "    - \(.actor_type): \(.actor_id)"'
        ISSUES=$((ISSUES + 1))
    else
        echo -e "  ${GREEN}✓ Bypass actors: 0 (no bypasses)${NC}"
    fi
    
    return 0
}

# Function to check status checks for a ruleset
check_status_checks() {
    local name="$1"
    shift
    local expected_checks=("$@")
    
    local ruleset
    ruleset=$(echo "$RULESETS" | jq -r ".[] | select(.name == \"$name\")")
    
    if [[ -z "$ruleset" ]] || [[ "$ruleset" == "null" ]]; then
        return 1
    fi
    
    # Get required status checks
    local actual_checks
    actual_checks=$(echo "$ruleset" | jq -r '
        .rules[]? | 
        select(.type == "required_status_checks") | 
        .parameters.required_status_checks[]?.context // empty
    ' 2>/dev/null | sort)
    
    local missing=0
    for check in "${expected_checks[@]}"; do
        if echo "$actual_checks" | grep -qx "$check"; then
            echo -e "  ${GREEN}✓ Status check: $check${NC}"
        else
            echo -e "  ${RED}✗ Status check MISSING: $check${NC}"
            missing=$((missing + 1))
        fi
    done
    
    if [[ $missing -gt 0 ]]; then
        ISSUES=$((ISSUES + missing))
    fi
}

# Check each expected ruleset
echo "─────────────────────────────────────────────────────────────────────"

for name in "${!EXPECTED_RULESETS[@]}"; do
    target="${EXPECTED_RULESETS[$name]}"
    check_ruleset "$name" "$target"
    
    # Check status checks for specific rulesets
    if [[ "$name" == "Main Gate" ]]; then
        check_status_checks "$name" "${MAIN_GATE_CHECKS[@]}"
    elif [[ "$name" == "Sandbox Guard" ]]; then
        check_status_checks "$name" "${SANDBOX_CHECKS[@]}"
    fi
    
    echo ""
done

echo "─────────────────────────────────────────────────────────────────────"

# Additional checks
echo -e "${CYAN}Additional Verification:${NC}"

# Check for any rulesets in evaluate mode (should all be active)
EVALUATE_COUNT=$(echo "$RULESETS" | jq '[.[] | select(.enforcement == "evaluate")] | length')
if [[ "$EVALUATE_COUNT" -gt 0 ]]; then
    echo -e "  ${YELLOW}⚠ $EVALUATE_COUNT ruleset(s) in evaluate mode (not enforcing)${NC}"
    ISSUES=$((ISSUES + 1))
else
    echo -e "  ${GREEN}✓ No rulesets in evaluate mode${NC}"
fi

# Check for any rulesets with bypass actors
BYPASS_RULESETS=$(echo "$RULESETS" | jq '[.[] | select(.bypass_actors | length > 0) | .name] | join(", ")')
if [[ -n "$BYPASS_RULESETS" ]] && [[ "$BYPASS_RULESETS" != '""' ]]; then
    echo -e "  ${YELLOW}⚠ Rulesets with bypass actors: $BYPASS_RULESETS${NC}"
else
    echo -e "  ${GREEN}✓ No rulesets have bypass actors${NC}"
fi

# Check for disabled rulesets
DISABLED_COUNT=$(echo "$RULESETS" | jq '[.[] | select(.enforcement == "disabled")] | length')
if [[ "$DISABLED_COUNT" -gt 0 ]]; then
    echo -e "  ${YELLOW}⚠ $DISABLED_COUNT ruleset(s) are disabled${NC}"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════════"

# Summary
if [[ $ISSUES -eq 0 ]]; then
    echo -e "${GREEN}  ✓ All rulesets verified successfully${NC}"
    echo ""
    echo "  6 rulesets active with no bypass actors"
    echo "  All required status checks configured"
    exit 0
else
    echo -e "${RED}  ✗ $ISSUES issue(s) found${NC}"
    echo ""
    echo "  Run ./scripts/setup_github_rulesets.sh to fix"
    exit 1
fi
