# UI BUILD CHECKPOINTS (Heartbeat-Controlled)

Rule: the NEXT DUE TASK is the lowest Step # whose Status is not PASS.

| Step | Prompt File | Status | Evidence Path(s) | Notes |
|------|-------------|--------|------------------|-------|
| 1 | prompts/ui_build/01_GLOBAL_RULES.md |  |  |  |
| 2 | prompts/ui_build/02_REPO_DISCOVERY_STACK_LOCK.md |  |  |  |
| 3 | prompts/ui_build/03_DESIGN_SYSTEM_LOCK.md |  |  |  |
| 4 | prompts/ui_build/04_IA_AND_ROUTING_LOCK.md |  |  |  |
| 5 | prompts/ui_build/05_PAGE_SPECS_LOCK.md |  |  |  |
| 6 | prompts/ui_build/06_COMPONENT_LIBRARY_LOCK.md |  |  |  |
| 7 | prompts/ui_build/07_VISUALS_PROTOTYPE_EXPORT.md |  |  |  |
| 8 | prompts/ui_build/08_DATA_ACCESS_LAYER.md |  |  |  |
| 9 | prompts/ui_build/09_BUILD_SNAPSHOT_CONTROL_ROOM.md |  |  |  |
| 10 | prompts/ui_build/10_BUILD_CLIENTS.md |  |  |  |
| 11 | prompts/ui_build/11_BUILD_TEAM.md |  |  |  |
| 12 | prompts/ui_build/12_BUILD_INTERSECTIONS.md |  |  |  |
| 13 | prompts/ui_build/13_BUILD_ISSUES_AND_WATCHERS.md |  |  |  |
| 14 | prompts/ui_build/14_BUILD_FIX_DATA.md |  |  |  |
| 15 | prompts/ui_build/15_TESTS_SCREENSHOTS_DONE_REPORT.md |  |  |  |

## Status values (strict)
- PASS
- FAIL
- BLOCKED (only if a defined stop-condition is met)

## Update protocol (mandatory)
At the end of each step:
1) Set Status to PASS/FAIL/BLOCKED
2) Fill Evidence Path(s) with concrete paths (screenshots, logs, command output files)
3) Add minimal Notes (what changed + why)

If FAIL/BLOCKED: do not touch later steps.
If PASS: proceed to the next due step (lowest non-PASS).
