#!/usr/bin/env bash
# MOH TIME OS — Graceful shutdown
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PID_FILE="$PROJECT_ROOT/logs/api.pid"

stop_pid() {
    local pid=$1
    local label=$2

    if ! kill -0 "$pid" 2>/dev/null; then
        echo "$label (PID: $pid) not running."
        return 0
    fi

    echo "Stopping $label (PID: $pid)..."

    # Graceful: SIGTERM + 5s wait
    kill "$pid" 2>/dev/null || true
    for i in $(seq 1 5); do
        if ! kill -0 "$pid" 2>/dev/null; then
            echo "  Stopped."
            return 0
        fi
        sleep 1
    done

    # Forceful: SIGKILL
    echo "  Still running after 5s, sending SIGKILL..."
    kill -9 "$pid" 2>/dev/null || true
    sleep 1

    if kill -0 "$pid" 2>/dev/null; then
        echo "  ERROR: Failed to kill PID $pid"
        return 1
    fi
    echo "  Killed."
}

# ── Stop via PID file ────────────────────────────
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    stop_pid "$PID" "API server"
    rm -f "$PID_FILE"
    exit 0
fi

# ── Fallback: find by process pattern ────────────
echo "No PID file found, searching for running server..."
PIDS=$(pgrep -f "python -m api.server" 2>/dev/null || true)

if [ -z "$PIDS" ]; then
    echo "No running server found."
    exit 0
fi

for pid in $PIDS; do
    stop_pid "$pid" "API server"
done
