#!/bin/bash
# Time OS V4 Full Cycle - Collection + Processing
# Run this periodically via cron

set -e

# Resolve script directory (works even when called via symlink/cron)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
source .venv/bin/activate

echo "$(date '+%Y-%m-%d %H:%M:%S') Starting Time OS V4 cycle..."

# Step 1: Collect from all sources
echo "Step 1: Collecting data..."
python collectors/scheduled_collect.py 2>&1 || echo "Collection had errors, continuing..."

# Step 2: Run V4 pipeline cycle
echo "Step 2: Running V4 pipeline..."
python cli_v4.py cycle 2>&1

# Step 3: Run V5 signal detection and issue formation
echo "Step 3: Running V5 pipeline..."
python -m lib.v5.orchestrator --full 2>&1 || echo "V5 pipeline had errors, continuing..."

echo "$(date '+%Y-%m-%d %H:%M:%S') Time OS cycle complete"
