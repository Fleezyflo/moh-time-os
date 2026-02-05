#!/bin/bash
# Time OS V4 Full Cycle - Collection + Processing
# Run this periodically via cron

set -e

cd /Users/molhamhomsi/clawd/moh_time_os
source .venv/bin/activate

echo "$(date '+%Y-%m-%d %H:%M:%S') Starting Time OS V4 cycle..."

# Step 1: Collect from all sources
echo "Step 1: Collecting data..."
python collectors/scheduled_collect.py 2>&1 || echo "Collection had errors, continuing..."

# Step 2: Run V4 pipeline cycle
echo "Step 2: Running V4 pipeline..."
python cli_v4.py cycle 2>&1

echo "$(date '+%Y-%m-%d %H:%M:%S') Time OS V4 cycle complete"
