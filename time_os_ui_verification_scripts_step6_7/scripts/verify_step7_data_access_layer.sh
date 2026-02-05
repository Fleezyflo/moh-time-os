\
#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-.}"
OUT_DIR="${ROOT}/docs/ui_exec/evidence"
TS="$(date '+%Y%m%d_%H%M%S')"
OUT="${OUT_DIR}/step7_data_access_${TS}.txt"

mkdir -p "$OUT_DIR"

need() {
  command -v "$1" >/dev/null 2>&1 || { echo "MISSING_TOOL: $1" >> "$OUT"; return 1; }
  return 0
}

run() {
  echo "" >> "$OUT"
  echo "============================================================" >> "$OUT"
  echo "\$ $*" >> "$OUT"
  echo "------------------------------------------------------------" >> "$OUT"
  (cd "$ROOT" && bash -lc "$*") >> "$OUT" 2>&1 || { echo "COMMAND_EXIT_CODE=$?" >> "$OUT"; return 1; }
  return 0
}

echo "STEP 7 EVIDENCE — Data Access Layer" > "$OUT"
echo "Timestamp: $(date)" >> "$OUT"
echo "Root: $ROOT" >> "$OUT"

need rg || true
need find || true
need sort || true
need pnpm || true
need curl || true

run "ls -la docs/ui_spec/09_DATA_ACCESS_LAYER.md" || true
run "rg -n '(TBD|todo|placeholder|unmapped|figure out|later)' docs/ui_spec/09_DATA_ACCESS_LAYER.md || true" || true
run "rg -n '(query function|recipe|CONTROL_ROOM_QUERIES|cache|caching|invalidation|offline|hydration|loading state|stale|revalidate)' docs/ui_spec/09_DATA_ACCESS_LAYER.md || true" || true
run "rg -n '(/clients|/team|/intersections|/issues|/fix-data|Snapshot)' docs/ui_spec/09_DATA_ACCESS_LAYER.md || true" || true
run "find time-os-ui/src -maxdepth 5 -type f \( -name 'queries.ts' -o -name 'api.ts' -o -name 'data*.ts' -o -name '*query*.ts' \) | sort" || true
run "rg -n '(getSnapshot|getClients|getClientDetail|getTeam|getTeamDetail|getIssues|getFixData|getCouplings|fetchSnapshot|fetchClients|fetchClient|fetchTeam|fetchIssues|fetchFixData|fetchCouplings)' time-os-ui/src -S || true" || true

PREVIEW_PID=""
if command -v pnpm >/dev/null 2>&1; then
  run "pnpm -C time-os-ui build" || true

  echo "" >> "$OUT"
  echo "============================================================" >> "$OUT"
  echo "\$ pnpm -C time-os-ui preview --host 127.0.0.1 --port 4173 (background)" >> "$OUT"
  echo "------------------------------------------------------------" >> "$OUT"
  (cd "$ROOT" && pnpm -C time-os-ui preview --host 127.0.0.1 --port 4173 >> "$OUT" 2>&1 & echo $! > /tmp/timeos_preview_pid) || true
  if [ -f /tmp/timeos_preview_pid ]; then
    PREVIEW_PID="$(cat /tmp/timeos_preview_pid || true)"
    echo "PREVIEW_PID=${PREVIEW_PID}" >> "$OUT"
  fi

  sleep 2
  run "curl -I http://127.0.0.1:4173/ || true" || true
  run "curl -I http://127.0.0.1:4173/clients || true" || true
  run "curl -I http://127.0.0.1:4173/team || true" || true
  run "curl -I http://127.0.0.1:4173/issues || true" || true
  run "curl -I http://127.0.0.1:4173/fix-data || true" || true
fi

if [ -n "${PREVIEW_PID}" ]; then
  echo "" >> "$OUT"
  echo "============================================================" >> "$OUT"
  echo "\$ kill ${PREVIEW_PID}" >> "$OUT"
  echo "------------------------------------------------------------" >> "$OUT"
  kill "${PREVIEW_PID}" >> "$OUT" 2>&1 || true
fi

echo "" >> "$OUT"
echo "WROTE: $OUT" >> "$OUT"
printf "%s\n" "$OUT"
