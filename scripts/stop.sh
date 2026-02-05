#!/bin/bash
# MOH TIME OS - Stop Script

cd "$(dirname "$0")/.."

if [ -f logs/api.pid ]; then
    PID=$(cat logs/api.pid)
    if kill -0 $PID 2>/dev/null; then
        echo "Stopping API server (PID: $PID)..."
        kill $PID
        rm logs/api.pid
        echo "Stopped."
    else
        echo "API server not running."
        rm logs/api.pid
    fi
else
    echo "No PID file found."
    # Try to find and kill any running server
    pkill -f "python api/server.py" 2>/dev/null && echo "Killed orphan process." || echo "Nothing running."
fi
