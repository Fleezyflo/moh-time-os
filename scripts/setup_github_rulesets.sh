#!/usr/bin/env bash
# setup_github_rulesets.sh — Configure GitHub Rulesets for repository protection
#
# Uses GitHub CLI (gh) to create/update rulesets via REST API.
# Rulesets are the modern replacement for branch protection rules.
# Key advantage: empty bypass lists cannot be overridden by admins.
#
# Prerequisites:
#   - gh CLI installed and authenticated
#   - Repository write access
#
# Usage:
#   ./scripts/setup_github_rulesets.sh
#   REPO=owner/repo ./scripts/setup_github_rulesets.sh

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get repo from environment or detect from git
REPO="${REPO:-$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "")}"

if [[ -z "$REPO" ]]; then
    echo -e "${RED}ERROR: Could not detect repository. Set REPO=owner/repo${NC}"
    exit 1
fi

echo "═══════════════════════════════════════════════════════════════════"
echo "  GitHub Rulesets Setup for: $REPO"
echo "═══════════════════════════════════════════════════════════════════"
echo ""

# Track failures
FAILURES=0

# Function to check if ruleset exists by name
ruleset_exists() {
    local name="$1"
    gh api "repos/$REPO/rulesets" --jq ".[] | select(.name == \"$name\") | .id" 2>/dev/null || echo ""
}

# Function to create or update ruleset
apply_ruleset() {
    local name="$1"
    local payload="$2"
    
    local existing_id
    existing_id=$(ruleset_exists "$name")
    
    if [[ -n "$existing_id" ]]; then
        echo -e "  ${YELLOW}Updating existing ruleset (ID: $existing_id)${NC}"
        if gh api "repos/$REPO/rulesets/$existing_id" -X PUT --input - <<< "$payload" > /dev/null 2>&1; then
            echo -e "  ${GREEN}✓ Updated successfully${NC}"
            return 0
        else
            echo -e "  ${RED}✗ Update failed${NC}"
            return 1
        fi
    else
        echo -e "  Creating new ruleset..."
        local result
        if result=$(gh api "repos/$REPO/rulesets" -X POST --input - <<< "$payload" 2>&1); then
            local new_id
            new_id=$(echo "$result" | jq -r '.id // empty')
            if [[ -n "$new_id" ]]; then
                echo -e "  ${GREEN}✓ Created successfully (ID: $new_id)${NC}"
                return 0
            fi
        fi
        echo -e "  ${RED}✗ Creation failed${NC}"
        echo "$result" | head -5
        return 1
    fi
}

# ============================================================================
# RULESET 1: Main Gate — Branch: main
# ============================================================================
echo "RULESET 1: Main Gate (branch: main)"

MAIN_GATE_PAYLOAD=$(cat <<'EOF'
{
  "name": "Main Gate",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": {
    "ref_name": {
      "include": ["refs/heads/main"],
      "exclude": []
    }
  },
  "rules": [
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 1,
        "dismiss_stale_reviews_on_push": true,
        "require_code_owner_review": true,
        "require_last_push_approval": true,
        "required_review_thread_resolution": true
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": true,
        "required_status_checks": [
          {"context": "Python Quality"},
          {"context": "Python Tests"},
          {"context": "Drift Detection"},
          {"context": "UI Quality"},
          {"context": "System Invariants"},
          {"context": "Security Audit"},
          {"context": "API Smoke Test"},
          {"context": "ALL GUARDS MUST PASS"}
        ]
      }
    },
    {
      "type": "required_signatures"
    },
    {
      "type": "required_linear_history"
    },
    {
      "type": "non_fast_forward"
    },
    {
      "type": "deletion"
    }
  ]
}
EOF
)

if ! apply_ruleset "Main Gate" "$MAIN_GATE_PAYLOAD"; then
    FAILURES=$((FAILURES + 1))
fi
echo ""

# ============================================================================
# RULESET 2: Sandbox Guard — Branches: sandbox/**
# ============================================================================
echo "RULESET 2: Sandbox Guard (branches: sandbox/**)"

SANDBOX_GUARD_PAYLOAD=$(cat <<'EOF'
{
  "name": "Sandbox Guard",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": {
    "ref_name": {
      "include": ["refs/heads/sandbox/**"],
      "exclude": []
    }
  },
  "rules": [
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": false,
        "required_status_checks": [
          {"context": "Sandbox Security"}
        ]
      }
    },
    {
      "type": "non_fast_forward"
    },
    {
      "type": "deletion"
    }
  ]
}
EOF
)

if ! apply_ruleset "Sandbox Guard" "$SANDBOX_GUARD_PAYLOAD"; then
    FAILURES=$((FAILURES + 1))
fi
echo ""

# ============================================================================
# RULESET 3: Tag Protection — Tags: v*
# ============================================================================
echo "RULESET 3: Tag Protection (tags: v*)"

TAG_PROTECTION_PAYLOAD=$(cat <<'EOF'
{
  "name": "Tag Protection",
  "target": "tag",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": {
    "ref_name": {
      "include": ["refs/tags/v*"],
      "exclude": []
    }
  },
  "rules": [
    {
      "type": "creation"
    },
    {
      "type": "deletion"
    },
    {
      "type": "non_fast_forward"
    }
  ]
}
EOF
)

if ! apply_ruleset "Tag Protection" "$TAG_PROTECTION_PAYLOAD"; then
    FAILURES=$((FAILURES + 1))
fi
echo ""

# ============================================================================
# RULESET 4: Workflow Protection — Paths: .github/**
# ============================================================================
echo "RULESET 4: Workflow Protection (paths: .github/**)"

# Note: Path-based rulesets require push ruleset type
WORKFLOW_PROTECTION_PAYLOAD=$(cat <<'EOF'
{
  "name": "Workflow Protection",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": {
    "ref_name": {
      "include": ["~ALL"],
      "exclude": []
    }
  },
  "rules": [
    {
      "type": "file_path_restriction",
      "parameters": {
        "restricted_file_paths": [".github/**"]
      }
    },
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 1,
        "dismiss_stale_reviews_on_push": true,
        "require_code_owner_review": true,
        "require_last_push_approval": false,
        "required_review_thread_resolution": true
      }
    }
  ]
}
EOF
)

if ! apply_ruleset "Workflow Protection" "$WORKFLOW_PROTECTION_PAYLOAD"; then
    FAILURES=$((FAILURES + 1))
fi
echo ""

# ============================================================================
# RULESET 5: Sensitive File Gate — Push restriction for dangerous files
# ============================================================================
echo "RULESET 5: Sensitive File Gate (push restriction)"

SENSITIVE_FILE_GATE_PAYLOAD=$(cat <<'EOF'
{
  "name": "Sensitive File Gate",
  "target": "push",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": {
    "ref_name": {
      "include": ["~ALL"],
      "exclude": []
    }
  },
  "rules": [
    {
      "type": "file_path_restriction",
      "parameters": {
        "restricted_file_paths": [
          "**/*.db",
          "**/*.sqlite",
          "**/*.sqlite3",
          "**/*.pem",
          "**/*.key",
          "**/*.p12",
          "**/sa-*.json",
          "**/.env",
          "**/.env.*",
          "**/*-full.json"
        ]
      }
    }
  ]
}
EOF
)

if ! apply_ruleset "Sensitive File Gate" "$SENSITIVE_FILE_GATE_PAYLOAD"; then
    FAILURES=$((FAILURES + 1))
fi
echo ""

# ============================================================================
# RULESET 6: Config Protection — Paths: config/**
# ============================================================================
echo "RULESET 6: Config Protection (paths: config/**)"

CONFIG_PROTECTION_PAYLOAD=$(cat <<'EOF'
{
  "name": "Config Protection",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": {
    "ref_name": {
      "include": ["~ALL"],
      "exclude": []
    }
  },
  "rules": [
    {
      "type": "file_path_restriction",
      "parameters": {
        "restricted_file_paths": ["config/**"]
      }
    },
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 1,
        "dismiss_stale_reviews_on_push": true,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": false
      }
    }
  ]
}
EOF
)

if ! apply_ruleset "Config Protection" "$CONFIG_PROTECTION_PAYLOAD"; then
    FAILURES=$((FAILURES + 1))
fi
echo ""

# ============================================================================
# Summary
# ============================================================================
echo "═══════════════════════════════════════════════════════════════════"
if [[ $FAILURES -eq 0 ]]; then
    echo -e "${GREEN}  ✓ All 6 rulesets configured successfully${NC}"
    echo ""
    echo "  Run ./scripts/verify_github_rulesets.sh to verify configuration"
    exit 0
else
    echo -e "${RED}  ✗ $FAILURES ruleset(s) failed to configure${NC}"
    echo ""
    echo "  Check GitHub permissions and try again"
    exit 1
fi
