\
#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-.}"
OUT_DIR="${ROOT}/docs/ui_exec/evidence"
TS="$(date '+%Y%m%d_%H%M%S')"
OUT="${OUT_DIR}/step6_component_library_${TS}.txt"
mkdir -p "$OUT_DIR"

run() {
  echo "" >> "$OUT"
  echo "============================================================" >> "$OUT"
  echo "\$ $*" >> "$OUT"
  echo "------------------------------------------------------------" >> "$OUT"
  (cd "$ROOT" && bash -lc "$*") >> "$OUT" 2>&1 || echo "COMMAND_EXIT_CODE=$?" >> "$OUT"
}

echo "STEP 6 FAST EVIDENCE — Component Library" > "$OUT"
echo "Timestamp: $(date)" >> "$OUT"
echo "Root: $ROOT" >> "$OUT"
echo "Tools: bash=$(bash --version | head -n 1)" >> "$OUT"
command -v rg >/dev/null 2>&1 && echo "Tools: rg=$(rg --version | head -n 1)" >> "$OUT" || echo "MISSING_TOOL: rg" >> "$OUT"

run "ls -la docs/ui_spec/08_COMPONENT_LIBRARY.md || true"
run "rg -n '(TBD|todo|placeholder|unmapped|figure out|later)' docs/ui_spec/08_COMPONENT_LIBRARY.md || true"
run "rg -n '(ProposalCard|IssueCard|TrustStrip|EvidenceStrip|EvidenceViewer|RoomDrawer|IssueDrawer|CouplingDrawer|FiltersBar|CommandPalette)' docs/ui_spec/08_COMPONENT_LIBRARY.md || true"
run "rg -n '(Eligibility|ineligible|06_PROPOSALS_BRIEFINGS|link_confidence|hypothesis|proof_density|confidence)' docs/ui_spec/08_COMPONENT_LIBRARY.md || true"
run "find time-os-ui/src/components -type f -maxdepth 3 -print | sort || true"
run "rg -n '(export function|export const|interface|type)\\s+(ProposalCard|IssueCard|TrustStrip|EvidenceStrip|EvidenceViewer|RoomDrawer|IssueDrawer|CouplingDrawer)' time-os-ui/src/components -S || true"

echo "" >> "$OUT"
echo "WROTE: $OUT" >> "$OUT"
printf "%s\n" "$OUT"
