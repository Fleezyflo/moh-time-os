#!/bin/bash
# Install Time OS cron jobs (runs WITHOUT Clawdbot heartbeat)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"

echo "Installing MOH TIME OS cron jobs..."
echo "Project dir: $PROJECT_DIR"

# Check venv exists
if [ ! -f "$VENV_PYTHON" ]; then
    echo "Error: Python venv not found at $VENV_PYTHON"
    exit 1
fi

# Remove any existing Time OS cron jobs
crontab -l 2>/dev/null | grep -v "moh_time_os" > /tmp/crontab_backup || true

# Add new cron jobs
cat >> /tmp/crontab_backup << EOF

# ═══════════════════════════════════════════════════════════════
# MOH TIME OS - Autonomous System (runs independently of Clawdbot)
# ═══════════════════════════════════════════════════════════════

# Autonomous Loop - every 15 minutes
*/15 * * * * cd $PROJECT_DIR && $VENV_PYTHON -m lib.autonomous_loop run >> /tmp/time-os.log 2>&1

# Full sync from external systems - every 5 minutes
*/5 * * * * cd $PROJECT_DIR && $VENV_PYTHON -m lib.collectors.orchestrator sync >> /tmp/time-os-sync.log 2>&1

# Daily brief - 9:00 AM Dubai (UTC+4 = 05:00 UTC)
0 5 * * * cd $PROJECT_DIR && $VENV_PYTHON -m lib.notifier.briefs daily >> /tmp/time-os-briefs.log 2>&1

# Midday pulse - 13:00 Dubai (UTC+4 = 09:00 UTC)
0 9 * * * cd $PROJECT_DIR && $VENV_PYTHON -m lib.notifier.briefs midday >> /tmp/time-os-briefs.log 2>&1

# End of day - 19:30 Dubai (UTC+4 = 15:30 UTC)
30 15 * * * cd $PROJECT_DIR && $VENV_PYTHON -m lib.notifier.briefs eod >> /tmp/time-os-briefs.log 2>&1

# ═══════════════════════════════════════════════════════════════
EOF

# Install the new crontab
crontab /tmp/crontab_backup

echo ""
echo "Cron jobs installed successfully!"
echo ""
echo "Installed jobs:"
crontab -l | grep "moh_time_os" || echo "(none found - check installation)"

echo ""
echo "Log files:"
echo "  - /tmp/time-os.log (autonomous loop)"
echo "  - /tmp/time-os-sync.log (sync)"
echo "  - /tmp/time-os-briefs.log (briefs)"
