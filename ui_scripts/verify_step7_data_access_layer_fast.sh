\
#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-.}"
OUT_DIR="${ROOT}/docs/ui_exec/evidence"
TS="$(date '+%Y%m%d_%H%M%S')"
OUT="${OUT_DIR}/step7_data_access_FAST_${TS}.txt"
mkdir -p "$OUT_DIR"

run() {
  echo "" >> "$OUT"
  echo "============================================================" >> "$OUT"
  echo "\$ $*" >> "$OUT"
  echo "------------------------------------------------------------" >> "$OUT"
  (cd "$ROOT" && bash -lc "$*") >> "$OUT" 2>&1 || echo "COMMAND_EXIT_CODE=$?" >> "$OUT"
}

echo "STEP 7 FAST EVIDENCE — Data Access Layer" > "$OUT"
echo "Timestamp: $(date)" >> "$OUT"
echo "Root: $ROOT" >> "$OUT"
command -v rg >/dev/null 2>&1 && echo "Tools: rg=$(rg --version | head -n 1)" >> "$OUT" || echo "MISSING_TOOL: rg" >> "$OUT"

run "ls -la docs/ui_spec/09_DATA_ACCESS_LAYER.md || true"
run "rg -n '(TBD|todo|placeholder|unmapped|figure out|later)' docs/ui_spec/09_DATA_ACCESS_LAYER.md || true"
run "rg -n '(CONTROL_ROOM_QUERIES|query recipe|cache|caching|invalidation|offline|hydration|loading|stale|revalidate)' docs/ui_spec/09_DATA_ACCESS_LAYER.md || true"
run "rg -n '(/clients|/team|/intersections|/issues|/fix-data|Snapshot|Control Room)' docs/ui_spec/09_DATA_ACCESS_LAYER.md || true"

run "find time-os-ui/src -maxdepth 5 -type f \\( -name 'queries.ts' -o -name 'api.ts' -o -name 'data*.ts' -o -name '*query*.ts' \\) | sort || true"
run "rg -n '(getSnapshot|getClients|getClientDetail|getTeam|getTeamDetail|getIssues|getFixData|getCouplings|fetchSnapshot|fetchClients|fetchClient|fetchTeam|fetchIssues|fetchFixData|fetchCouplings)' time-os-ui/src -S || true"
run "rg -n '(local-first|cache|indexeddb|idb|localStorage|persist|offline|stale-while-revalidate)' time-os-ui/src -S || true"

echo "" >> "$OUT"
echo "WROTE: $OUT" >> "$OUT"
printf "%s\n" "$OUT"
