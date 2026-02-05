#!/bin/bash
# MOH TIME OS - Start Script

set -e

cd "$(dirname "$0")/.."
BASE_DIR=$(pwd)

echo "═══════════════════════════════════════"
echo "  MOH TIME OS - Starting"
echo "═══════════════════════════════════════"

# Create logs directory
mkdir -p logs

# Activate virtual environment
source .venv/bin/activate

# Check dependencies
echo "Checking dependencies..."
pip install -q pyyaml fastapi uvicorn pydantic

# Initialize database if needed
echo "Initializing database..."
python -c "from lib.state_store import get_store; get_store()" 2>/dev/null

# Run initial sync
echo "Running initial sync..."
python -m cli.main sync 2>&1 | grep -E "✓|✗"

# Start API server in background
echo "Starting API server..."
python api/server.py &
API_PID=$!
echo "  API PID: $API_PID"

# Save PID
echo $API_PID > logs/api.pid

echo ""
echo "═══════════════════════════════════════"
echo "  MOH TIME OS Running"
echo "═══════════════════════════════════════"
echo ""
echo "  API: http://localhost:8420"
echo "  Dashboard: file://$BASE_DIR/ui/index.html"
echo ""
echo "  CLI: python -m cli.main <command>"
echo ""
echo "  Stop: kill \$(cat logs/api.pid)"
echo ""
