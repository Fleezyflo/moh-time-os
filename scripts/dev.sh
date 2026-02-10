#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

LOGS_DIR="$PROJECT_ROOT/.logs"
mkdir -p "$LOGS_DIR"
API_LOG="$LOGS_DIR/api.log"
UI_LOG="$LOGS_DIR/ui.log"

API_PID=""
UI_PID=""

cleanup() {
  [ -n "${API_PID:-}" ] && kill "$API_PID" 2>/dev/null || true
  [ -n "${UI_PID:-}" ] && kill "$UI_PID" 2>/dev/null || true
}
trap cleanup EXIT SIGINT SIGTERM

dump_logs() {
  echo ""
  echo "=== Last 30 lines of API log ==="
  tail -n 30 "$API_LOG" 2>/dev/null || echo "(empty)"
  echo ""
  echo "=== Last 30 lines of UI log ==="
  tail -n 30 "$UI_LOG" 2>/dev/null || echo "(empty)"
}

echo "Starting Moh Time OS Development Environment"
echo ""

: > "$API_LOG"
: > "$UI_LOG"

echo "Starting backend..."
(
  source "$PROJECT_ROOT/.venv/bin/activate"
  cd "$PROJECT_ROOT"
  PYTHONPATH=. exec python -m api.server
) >>"$API_LOG" 2>&1 &
API_PID=$!

echo "Starting frontend..."
(
  cd "$PROJECT_ROOT/time-os-ui"
  exec npm run dev
) >>"$UI_LOG" 2>&1 &
UI_PID=$!

echo "Waiting for services..."

BACKEND_URL=""
FRONTEND_URL=""

for i in $(seq 1 20); do
  if [ -z "$BACKEND_URL" ]; then
    if ! kill -0 "$API_PID" 2>/dev/null; then
      echo "URL not detected; see logs: $API_LOG"
      dump_logs
      exit 1
    fi
    if BACKEND_URL="$("$SCRIPT_DIR/detect_uvicorn_url.sh" "$API_LOG")"; then :; else BACKEND_URL=""; fi
  fi

  if [ -z "$FRONTEND_URL" ]; then
    if ! kill -0 "$UI_PID" 2>/dev/null; then
      echo "URL not detected; see logs: $UI_LOG"
      dump_logs
      exit 1
    fi
    if FRONTEND_URL="$("$SCRIPT_DIR/detect_vite_url.sh" "$UI_LOG")"; then :; else FRONTEND_URL=""; fi
  fi

  if [ -n "$BACKEND_URL" ] && [ -n "$FRONTEND_URL" ]; then
    break
  fi
  sleep 1
done

if [ -z "$BACKEND_URL" ]; then
  echo "URL not detected; see logs: $API_LOG"
  dump_logs
  exit 1
fi

if [ -z "$FRONTEND_URL" ]; then
  echo "URL not detected; see logs: $UI_LOG"
  dump_logs
  exit 1
fi

echo ""
echo "Backend: $BACKEND_URL"
echo "Docs: $BACKEND_URL/docs"
echo "Frontend: $FRONTEND_URL"
echo ""

echo "Probing services..."

CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BACKEND_URL/health" || true)
[ "$CODE" = "200" ] || { dump_logs; exit 1; }
echo "  OK: $BACKEND_URL/health (HTTP 200)"

CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BACKEND_URL/api/v2/inbox" || true)
[ "$CODE" = "200" ] || { dump_logs; exit 1; }
echo "  OK: $BACKEND_URL/api/v2/inbox (HTTP 200)"

BODY=$(curl -s "$FRONTEND_URL" || true)
echo "$BODY" | grep -qi "<!doctype html" || { dump_logs; exit 1; }
echo "  OK: $FRONTEND_URL (HTML)"

echo ""
echo "========================================"
echo "  Development Environment Ready"
echo "========================================"
echo ""
echo "  Backend:  $BACKEND_URL"
echo "  Docs:     $BACKEND_URL/docs"
echo "  Frontend: $FRONTEND_URL"
echo ""
echo "  Logs: $LOGS_DIR/"
echo "  Press Ctrl+C to stop"
echo "========================================"
echo ""

tail -f "$API_LOG" "$UI_LOG" &
TAIL_PID=$!

wait "$API_PID" "$UI_PID" || true
STATUS=$?
kill "$TAIL_PID" 2>/dev/null || true
exit $STATUS
