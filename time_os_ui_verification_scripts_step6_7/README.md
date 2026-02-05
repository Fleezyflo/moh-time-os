Time OS UI Prompt Pack — Verification Scripts (Step 6 & 7)

Purpose
- Run deterministic verification commands locally
- Capture raw stdout/stderr into timestamped evidence files under:
  docs/ui_exec/evidence/

How to use
1) Copy the `scripts/` folder into your repo root:
   /Users/molhamhomsi/clawd/moh_time_os/time_os_ui_prompt_pack

2) Make scripts executable:
   chmod +x scripts/*.sh

3) Run:
   ./scripts/verify_steps_6_7.sh .

Outputs
- docs/ui_exec/evidence/step6_component_library_YYYYmmdd_HHMMSS.txt
- docs/ui_exec/evidence/step7_data_access_YYYYmmdd_HHMMSS.txt

Notes
- Grep commands never fail the run (they use `|| true`)
- Missing files/tools are logged explicitly
- Step 7 preview uses a short-lived background process; it is shut down at the end.

Requirements
- bash, find, sort
- ripgrep (`rg`)
- pnpm (only for Step 7 build/preview)
- curl
