#!/usr/bin/env bash
# Check for large changes that require rationale.
#
# Usage: ./scripts/check_change_size.sh [base_ref]
#
# Fails if:
# - >50 files changed without "large-change" in commit message
# - >20 deletions without "deletion rationale" in commit message

set -euo pipefail

BASE_REF="${1:-HEAD~1}"

# Count changes
FILES_CHANGED=$(git diff --name-only "$BASE_REF" | wc -l | tr -d ' ')
DELETIONS=$(git diff --stat "$BASE_REF" | tail -1 | grep -oE '[0-9]+ deletion' | grep -oE '[0-9]+' || echo "0")

echo "Files changed: $FILES_CHANGED"
echo "Deletions: $DELETIONS"

# Get latest commit message
COMMIT_MSG=$(git log -1 --pretty=%B)

FAILURES=0

# Check for large changes
if [ "$FILES_CHANGED" -gt 50 ]; then
    if ! echo "$COMMIT_MSG" | grep -qi "large-change\|bulk\|recovery\|refactor"; then
        echo "❌ Large change ($FILES_CHANGED files) without rationale"
        echo "   Add 'large-change' to commit message or PR description"
        FAILURES=$((FAILURES + 1))
    else
        echo "✅ Large change acknowledged in commit message"
    fi
fi

# Check for many deletions
if [ "$DELETIONS" -gt 20 ]; then
    if ! echo "$COMMIT_MSG" | grep -qi "delet\|remov\|deprecat\|cleanup"; then
        echo "❌ Many deletions ($DELETIONS) without rationale"
        echo "   Add deletion rationale to commit message"
        FAILURES=$((FAILURES + 1))
    else
        echo "✅ Deletion rationale found in commit message"
    fi
fi

if [ "$FAILURES" -gt 0 ]; then
    echo ""
    echo "❌ Change size check failed"
    exit 1
fi

echo "✅ Change size check passed"
