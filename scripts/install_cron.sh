#!/bin/bash
# Install Time OS cron jobs (canonical entry only)
#
# This script installs ONLY the canonical scheduled_collect.py entry.
# It is IDEMPOTENT: running multiple times produces exactly one cron entry.
# All previous time-os entries are removed before adding the canonical one.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"

echo "Installing MOH TIME OS cron jobs..."
echo "Project dir: $PROJECT_DIR"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "Error: Python venv not found at $VENV_PYTHON"
    exit 1
fi

# Get current crontab (empty string if none)
CURRENT_CRONTAB=$(crontab -l 2>/dev/null || true)

# Show what will be removed
echo ""
echo "Removing existing time-os entries (if any):"
if echo "$CURRENT_CRONTAB" | grep -qE "(moh_time_os|time-os|MOH TIME OS)"; then
    echo "$CURRENT_CRONTAB" | grep -E "(moh_time_os|time-os|MOH TIME OS)" | while read -r line; do
        echo "  - $line"
    done
else
    echo "  (none found)"
fi
echo ""

# Remove ALL time-os related entries including:
# - Lines containing moh_time_os or time-os
# - Comment blocks with MOH TIME OS headers (═══ lines)
# - Empty lines that result from removal
# Use grep -v with multiple patterns, suppress errors for no matches
CLEANED_CRONTAB=$(echo "$CURRENT_CRONTAB" | \
    grep -v "moh_time_os" | \
    grep -v "time-os" | \
    grep -v "MOH TIME OS" | \
    grep -v "═══" | \
    grep -v "^# This is THE ONLY collection entry" | \
    grep -v "^# Features: stale lock detection" | \
    cat)  # cat prevents grep from failing on empty input

# Remove multiple consecutive blank lines, leaving at most one
CLEANED_CRONTAB=$(echo "$CLEANED_CRONTAB" | cat -s)

# Trim trailing whitespace/newlines
CLEANED_CRONTAB=$(echo "$CLEANED_CRONTAB" | sed -e :a -e '/^\s*$/d;N;ba' 2>/dev/null || echo "$CLEANED_CRONTAB")

# Build the new crontab with exactly one canonical block
# Note: Using printf to avoid issues with echo and special characters
NEW_CRONTAB=$(printf '%s\n\n# ═══════════════════════════════════════════════════════════════\n# MOH TIME OS - Canonical Periodic Collection\n# ═══════════════════════════════════════════════════════════════\n# This is THE ONLY collection entry. Do not add parallel schedulers.\n# Features: stale lock detection, watchdog timeout, guaranteed cleanup.\n*/15 * * * * cd %s && %s collectors/scheduled_collect.py >> /tmp/time-os-collect.log 2>&1\n' "$CLEANED_CRONTAB" "$PROJECT_DIR" "$VENV_PYTHON")

# Install the new crontab
echo "$NEW_CRONTAB" | crontab -

echo "Cron jobs installed successfully!"
echo ""
echo "Installed entry:"
crontab -l | grep "scheduled_collect" || echo "(check failed)"
echo ""
echo "Log file: /tmp/time-os-collect.log"
echo ""
echo "IMPORTANT: Only the canonical scheduled_collect.py entry is installed."
echo "All overlapping entries have been removed."
