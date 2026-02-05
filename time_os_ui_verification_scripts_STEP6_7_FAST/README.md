Time OS UI Prompt Pack — FAST Verification Scripts (Step 6 & 7)

What “FAST” means
- No pnpm build
- No pnpm preview
- No network curls
- Only deterministic repo checks: file existence + ripgrep scans + source tree presence.

Run (from repo root)
  chmod +x scripts/*.sh
  ./scripts/verify_steps_6_7_fast.sh .

Outputs (timestamped)
- docs/ui_exec/evidence/step6_component_library_<TS>.txt
- docs/ui_exec/evidence/step7_data_access_FAST_<TS>.txt

Prereqs
- bash, find (macOS default)
- ripgrep (`rg`) recommended. If missing, scripts log it and continue.

Install helpers (optional)
- ripgrep via Homebrew: `brew install ripgrep`
- pnpm is NOT required for FAST mode.
