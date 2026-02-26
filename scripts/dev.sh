#!/usr/bin/env bash
# MOH TIME OS — Development Environment
#
# Starts API + UI, health-checks both, opens browser.
# Single canonical launcher: `make dev` runs this.
#
# Usage:
#   ./scripts/dev.sh          # default ports (API 8420, UI 5173)
#   PORT=9000 ./scripts/dev.sh  # custom API port
#
# Stop: Ctrl+C (cleanup trap handles everything)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

API_PORT="${PORT:-8420}"
UI_PORT="${UI_PORT:-5173}"
LOGS_DIR="$PROJECT_ROOT/logs"
API_LOG="$LOGS_DIR/api.log"
UI_LOG="$LOGS_DIR/ui.log"
PID_FILE="$LOGS_DIR/api.pid"

mkdir -p "$LOGS_DIR"

# ── State ─────────────────────────────────────────
API_PID=""
UI_PID=""
TAIL_PID=""

# ── Cleanup on exit ──────────────────────────────
cleanup() {
    echo ""
    echo "Shutting down..."
    [ -n "$TAIL_PID" ] && kill "$TAIL_PID" 2>/dev/null || true
    [ -n "$UI_PID" ]   && kill "$UI_PID"   2>/dev/null || true
    [ -n "$API_PID" ]  && kill "$API_PID"  2>/dev/null || true
    [ -n "$UI_PID" ]   && wait "$UI_PID"   2>/dev/null || true
    [ -n "$API_PID" ]  && wait "$API_PID"  2>/dev/null || true
    rm -f "$PID_FILE"
    echo "Done."
}
trap cleanup EXIT INT TERM

dump_logs() {
    echo ""
    echo "=== Last 30 lines of API log ==="
    tail -n 30 "$API_LOG" 2>/dev/null || echo "(empty)"
    echo ""
    echo "=== Last 30 lines of UI log ==="
    tail -n 30 "$UI_LOG" 2>/dev/null || echo "(empty)"
}

# ── Pre-flight checks ────────────────────────────

# Ensure uv is available
if ! command -v uv &>/dev/null; then
    echo "Error: uv not found. Install via: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Find a working venv python, rebuild if missing or broken
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

# Ensure pnpm is available
if ! command -v pnpm &>/dev/null; then
    echo "Error: pnpm not found. Install via: npm install -g pnpm"
    exit 1
fi

# Ensure UI dependencies are installed
if [ ! -d "time-os-ui/node_modules" ]; then
    echo "  Installing UI dependencies..."
    (cd "$PROJECT_ROOT/time-os-ui" && pnpm install)
fi

# Kill stale server from previous run
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "Stopping stale server (PID: $OLD_PID)..."
        kill "$OLD_PID" 2>/dev/null || true
        sleep 1
    fi
    rm -f "$PID_FILE"
fi

echo "════════════════════════════════════════"
echo "  MOH TIME OS — Development"
echo "════════════════════════════════════════"

# ── Initialize database ──────────────────────────
echo ""
echo "Initializing database..."
PYTHONPATH="$PROJECT_ROOT" "$PYTHON" -c "from lib.state_store import get_store; get_store()" 2>/dev/null \
    && echo "  OK" || echo "  Skipped (already exists)"

# ── Truncate logs ────────────────────────────────
: > "$API_LOG"
: > "$UI_LOG"

# ── Start API server ─────────────────────────────
echo ""
echo "[1/2] Starting API server on :$API_PORT ..."
PYTHONPATH="$PROJECT_ROOT" "$PYTHON" -m api.server >>"$API_LOG" 2>&1 &
API_PID=$!
echo "$API_PID" > "$PID_FILE"

# Health-check API (30s timeout)
for i in $(seq 1 30); do
    if ! kill -0 "$API_PID" 2>/dev/null; then
        echo "  API server died during startup."
        dump_logs
        exit 1
    fi
    if curl -sf "http://127.0.0.1:$API_PORT/api/health" >/dev/null 2>&1; then
        echo "  API ready (PID: $API_PID)"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "  API failed to respond after 30s."
        dump_logs
        exit 1
    fi
    sleep 1
done

# ── Start UI dev server ──────────────────────────
echo "[2/2] Starting UI on :$UI_PORT ..."
(cd "$PROJECT_ROOT/time-os-ui" && exec pnpm dev --host 127.0.0.1 --port "$UI_PORT") \
    >>"$UI_LOG" 2>&1 &
UI_PID=$!

# Health-check UI (20s timeout — Vite is fast)
for i in $(seq 1 20); do
    if ! kill -0 "$UI_PID" 2>/dev/null; then
        echo "  UI server died during startup."
        dump_logs
        exit 1
    fi
    if curl -sf "http://127.0.0.1:$UI_PORT" >/dev/null 2>&1; then
        echo "  UI ready (PID: $UI_PID)"
        break
    fi
    if [ "$i" -eq 20 ]; then
        echo "  UI failed to respond after 20s."
        dump_logs
        exit 1
    fi
    sleep 1
done

# ── Probe endpoints ──────────────────────────────
echo ""
echo "Probing services..."
CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$API_PORT/api/health" || true)
[ "$CODE" = "200" ] || { echo "  FAIL: /api/health → HTTP $CODE"; dump_logs; exit 1; }
echo "  OK: /api/health (HTTP 200)"

CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$API_PORT/api/v2/inbox" || true)
[ "$CODE" = "200" ] || { echo "  FAIL: /api/v2/inbox → HTTP $CODE"; dump_logs; exit 1; }
echo "  OK: /api/v2/inbox (HTTP 200)"

BODY=$(curl -s "http://127.0.0.1:$UI_PORT" || true)
echo "$BODY" | grep -qi "<!doctype html" || { echo "  FAIL: UI not returning HTML"; dump_logs; exit 1; }
echo "  OK: UI serving HTML"

# ── Open browser ─────────────────────────────────
open "http://localhost:$UI_PORT" 2>/dev/null || true

# ── Ready ─────────────────────────────────────────
echo ""
echo "════════════════════════════════════════"
echo "  MOH TIME OS Running"
echo "════════════════════════════════════════"
echo ""
echo "  UI:       http://localhost:$UI_PORT"
echo "  API:      http://localhost:$API_PORT"
echo "  API Docs: http://localhost:$API_PORT/docs"
echo ""
echo "  Logs:     $LOGS_DIR/"
echo "  Stop:     Ctrl+C"
echo "            or: ./scripts/stop.sh"
echo "════════════════════════════════════════"
echo ""

# ── Stream logs until exit ────────────────────────
tail -f "$API_LOG" "$UI_LOG" &
TAIL_PID=$!

wait "$API_PID" "$UI_PID" || true
STATUS=$?
kill "$TAIL_PID" 2>/dev/null || true
exit $STATUS
