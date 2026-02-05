# Time OS UI Build — Execution Index (Heartbeat-Amended)

## Source of truth (backend contracts)
UI data + contracts MUST come from:
- /Users/molhamhomsi/Downloads/time_os_backend_spec_pack/docs/backend_spec/CONTROL_ROOM_QUERIES.md
- /Users/molhamhomsi/Downloads/time_os_backend_spec_pack/docs/backend_spec/PROPOSAL_ISSUE_ROOM_CONTRACT.md
- /Users/molhamhomsi/Downloads/time_os_backend_spec_pack/docs/backend_spec/06_PROPOSALS_BRIEFINGS.md

## Heartbeat control files (mandatory)
- docs/ui_exec/CHECKPOINTS.md MUST match templates/CHECKPOINTS_TEMPLATE.md exactly
- docs/ui_exec/RUN_LOG.md initial content must come from templates/RUN_LOG_TEMPLATE.md

NEXT DUE TASK = lowest Step # whose Status != PASS in docs/ui_exec/CHECKPOINTS.md

## Execution order (MUST be followed)
1) 01_GLOBAL_RULES.md
2) 02_REPO_DISCOVERY_STACK_LOCK.md
3) 03_DESIGN_SYSTEM_LOCK.md
4) 04_IA_AND_ROUTING_LOCK.md
5) 05_PAGE_SPECS_LOCK.md
6) 06_COMPONENT_LIBRARY_LOCK.md
7) 07_VISUALS_PROTOTYPE_EXPORT.md
8) 08_DATA_ACCESS_LAYER.md
9) 09_BUILD_SNAPSHOT_CONTROL_ROOM.md
10) 10_BUILD_CLIENTS.md
11) 11_BUILD_TEAM.md
12) 12_BUILD_INTERSECTIONS.md
13) 13_BUILD_ISSUES_AND_WATCHERS.md
14) 14_BUILD_FIX_DATA.md
15) 15_TESTS_SCREENSHOTS_DONE_REPORT.md

## Hard gates (non-negotiable)
- No eligible Proposal renders unless eligibility gates from 06_PROPOSALS_BRIEFINGS.md are satisfied (≥3 proof excerpts + confidence floors).
- UI always shows BOTH: linkage_confidence and interpretation_confidence.
- No invented fields. Only contract fields.
- Stop on failed acceptance checks. No skipping.

## End condition
Done only when:
- Steps 1–15 are PASS in CHECKPOINTS.md
- Tests pass
- Visual evidence exported
- Done report written
