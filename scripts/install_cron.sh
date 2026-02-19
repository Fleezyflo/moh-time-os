#!/bin/bash
# Install Time OS cron jobs (canonical entry only)
#
# This script installs ONLY the canonical scheduled_collect.py entry.
# It preserves unrelated crontab lines.

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

CURRENT_CRONTAB=$(crontab -l 2>/dev/null || true)

# Show what will be removed
echo ""
echo "Removing overlapping entries (if any):"
echo "$CURRENT_CRONTAB" | grep -E "(moh_time_os|time-os)" | while read line; do
    echo "  - $line"
done || echo "  (none found)"
echo ""

# Remove ALL moh_time_os/time-os entries to prevent lock contention
CLEANED_CRONTAB=$(echo "$CURRENT_CRONTAB" | grep -v "moh_time_os" | grep -v "time-os" || true)

NEW_CRONTAB="$CLEANED_CRONTAB

# ═══════════════════════════════════════════════════════════════
# MOH TIME OS - Canonical Periodic Collection
# ═══════════════════════════════════════════════════════════════
# This is THE ONLY collection entry. Do not add parallel schedulers.
# Features: stale lock detection, watchdog timeout, guaranteed cleanup.

*/15 * * * * cd $PROJECT_DIR && $VENV_PYTHON collectors/scheduled_collect.py >> /tmp/time-os-collect.log 2>&1

# ═══════════════════════════════════════════════════════════════
"

echo "$NEW_CRONTAB" | crontab -

echo ""
echo "Cron jobs installed successfully!"
echo ""
echo "Installed jobs:"
crontab -l | grep "moh_time_os" || echo "(none found - check installation)"

echo ""
echo "Log file: /tmp/time-os-collect.log"
echo ""
echo "IMPORTANT: Only the canonical scheduled_collect.py entry is installed."
echo "Overlapping entries (autonomous_loop, orchestrator sync) have been removed."
