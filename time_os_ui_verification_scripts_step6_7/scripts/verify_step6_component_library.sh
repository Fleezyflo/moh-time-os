\
#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-.}"
OUT_DIR="${ROOT}/docs/ui_exec/evidence"
TS="$(date '+%Y%m%d_%H%M%S')"
OUT="${OUT_DIR}/step6_component_library_${TS}.txt"

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

echo "STEP 6 EVIDENCE — Component Library" > "$OUT"
echo "Timestamp: $(date)" >> "$OUT"
echo "Root: $ROOT" >> "$OUT"

need rg || true
need find || true
need sort || true

run "ls -la docs/ui_spec/08_COMPONENT_LIBRARY.md" || true
run "rg -n '(TBD|todo|placeholder|unmapped|figure out|later)' docs/ui_spec/08_COMPONENT_LIBRARY.md || true" || true
run "rg -n '(ProposalCard|IssueCard|TrustStrip|EvidenceStrip|EvidenceViewer|RoomDrawer|IssueDrawer|CouplingDrawer|FiltersBar|CommandPalette)' docs/ui_spec/08_COMPONENT_LIBRARY.md || true" || true
run "rg -n '(Props|States|Interactions|Empty state|Error state|Accessibility|Keyboard|Mobile|Touch)' docs/ui_spec/08_COMPONENT_LIBRARY.md || true" || true
run "rg -n '(Eligibility|ineligible|06_PROPOSALS_BRIEFINGS|link_confidence|hypothesis|proof_density|confidence)' docs/ui_spec/08_COMPONENT_LIBRARY.md || true" || true
run "find time-os-ui/src -maxdepth 4 -type f \( -name '*.tsx' -o -name '*.ts' \) | sort" || true
run "rg -n '(ProposalCard|IssueCard|TrustStrip|EvidenceStrip|EvidenceViewer|RoomDrawer|IssueDrawer|CouplingDrawer|FiltersBar|CommandPalette)' time-os-ui/src -S || true" || true

echo "" >> "$OUT"
echo "WROTE: $OUT" >> "$OUT"
printf "%s\n" "$OUT"
