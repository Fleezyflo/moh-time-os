#!/usr/bin/env bash
# MOH TIME OS — Production-style API starter
# Starts the API server, verifies health, saves PID for stop.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

API_PORT="${PORT:-8420}"
LOGS_DIR="$PROJECT_ROOT/logs"
PID_FILE="$LOGS_DIR/api.pid"

mkdir -p "$LOGS_DIR"

# ── Cleanup on exit ──────────────────────────────
cleanup() {
    if [ -n "${API_PID:-}" ] && kill -0 "$API_PID" 2>/dev/null; then
        echo "Shutting down API server (PID: $API_PID)..."
        kill "$API_PID" 2>/dev/null || true
        wait "$API_PID" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
}
trap cleanup EXIT INT TERM

# ── Pre-flight checks ────────────────────────────

if ! command -v uv &>/dev/null; then
    echo "Error: uv not found. Install via: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

find_python() {
    for name in python python3; do
        local candidate="$PROJECT_ROOT/.venv/bin/$name"
        if [ -x "$candidate" ] && "$candidate" --version &>/dev/null; then
            echo "$candidate"
            return 0
        fi
    done
    return 1
}

PYTHON="$(find_python)" || PYTHON=""
if [ -z "$PYTHON" ]; then
    echo "  Venv missing or broken — rebuilding..."
    rm -rf "$PROJECT_ROOT/.venv"
    uv sync --project "$PROJECT_ROOT"
    PYTHON="$(find_python)" || PYTHON=""
    if [ -z "$PYTHON" ]; then
        echo "Error: uv sync completed but no working python in .venv/bin/."
        exit 1
    fi
    echo "  Venv rebuilt OK"
fi

# Kill stale process from previous run
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "Stopping stale server (PID: $OLD_PID)..."
        kill "$OLD_PID" 2>/dev/null || true
        sleep 1
    fi
    rm -f "$PID_FILE"
fi

echo "═══════════════════════════════════════"
echo "  MOH TIME OS — Starting"
echo "═══════════════════════════════════════"

# ── Initialize database ──────────────────────────
echo ""
echo "Initializing database..."
PYTHONPATH="$PROJECT_ROOT" "$PYTHON" -c "from lib.state_store import get_store; get_store()" 2>/dev/null && echo "  OK" || echo "  Skipped (already exists)"

# ── Start API server ─────────────────────────────
echo ""
echo "Starting API server on :$API_PORT ..."
PYTHONPATH="$PROJECT_ROOT" "$PYTHON" -m api.server >>"$LOGS_DIR/api.log" 2>&1 &
API_PID=$!
echo "$API_PID" > "$PID_FILE"

# ── Health check ─────────────────────────────────
echo "Waiting for health check..."
for i in $(seq 1 30); do
    if ! kill -0 "$API_PID" 2>/dev/null; then
        echo ""
        echo "API server exited unexpectedly. Last 20 lines:"
        tail -n 20 "$LOGS_DIR/api.log" 2>/dev/null || true
        exit 1
    fi
    if curl -sf "http://127.0.0.1:$API_PORT/api/health" >/dev/null 2>&1; then
        echo "  API ready (PID: $API_PID)"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo ""
        echo "API failed to start after 30s. Last 20 lines:"
        tail -n 20 "$LOGS_DIR/api.log" 2>/dev/null || true
        exit 1
    fi
    sleep 1
done

echo ""
echo "═══════════════════════════════════════"
echo "  MOH TIME OS Running"
echo "═══════════════════════════════════════"
echo ""
echo "  API:  http://localhost:$API_PORT"
echo "  Docs: http://localhost:$API_PORT/docs"
echo "  Logs: $LOGS_DIR/api.log"
echo ""
echo "  Stop: ./scripts/stop.sh"
echo "        or: kill \$(cat $PID_FILE)"
echo ""
echo "  Press Ctrl+C to stop"
echo "═══════════════════════════════════════"

# ── Stay alive ───────────────────────────────────
wait "$API_PID"
