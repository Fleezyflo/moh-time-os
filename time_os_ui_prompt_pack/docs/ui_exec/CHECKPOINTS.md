# UI BUILD CHECKPOINTS (Heartbeat-Controlled)

Rule: the NEXT DUE TASK is the lowest Step # whose Status is not PASS.

| Step | Prompt File | Status | Evidence Path(s) | Notes |
|------|-------------|--------|------------------|-------|
| 1 | prompts/ui_build/01_GLOBAL_RULES.md | PASS | docs/ui_exec/RUN_LOG.md | Control files created, backend contracts verified |
| 2 | prompts/ui_build/02_REPO_DISCOVERY_STACK_LOCK.md | PASS | time-os-ui/package.json, docs/ui_exec/RUN_LOG.md, docs/ui_exec/evidence/step2_routes/*.png | Vite+React+TanStack Router+PWA scaffold (verified with raw evidence) |
| 3 | prompts/ui_build/03_DESIGN_SYSTEM_LOCK.md | PASS | docs/ui_spec/01_PRODUCT_PRINCIPLES.md, docs/ui_spec/03_DESIGN_SYSTEM.md, RUN_LOG.md (STEP 3 VERIFICATION — RAW EVIDENCE) | VERIFIED: Contract binding, eligibility gates, all decimals contract-sourced |
| 4 | prompts/ui_build/04_IA_AND_ROUTING_LOCK.md | PASS | docs/ui_spec/02_INFORMATION_ARCHITECTURE.md, docs/ui_spec/06_NAVIGATION_AND_ROUTING.md, RUN_LOG.md (Entry 8) | PATCHED: Route→Query table with exact CONTROL_ROOM_QUERIES.md line refs (L9,L14-19,L25-27,L29-31) |
| 5 | prompts/ui_build/05_PAGE_SPECS_LOCK.md | PASS | docs/ui_spec/07_PAGE_SPECS/*.md, RUN_LOG.md (Entry 8) | PATCHED: All invented thresholds removed, "Fields used" blocks added (18 occurrences) |
| 6 | prompts/ui_build/06_COMPONENT_LIBRARY_LOCK.md | PASS | docs/ui_spec/08_COMPONENT_LIBRARY.md, time-os-ui/src/components/*.tsx, RUN_LOG.md (STEP 6 RAW PROOF) | 13 spec components, RoomDrawer+IssueDrawer+EvidenceViewer implemented |
| 7 | prompts/ui_build/07_VISUALS_PROTOTYPE_EXPORT.md | PASS | docs/ui_spec/visuals/*.png (5 files), time-os-ui/src/fixtures/index.ts | snapshot.png, client_detail.png, team_detail.png, intersections.png, fix_data.png |
| 8 | prompts/ui_build/08_DATA_ACCESS_LAYER.md | PASS | docs/ui_spec/09_DATA_ACCESS_LAYER.md, time-os-ui/src/lib/queries.ts, RUN_LOG.md (STEP 7 RAW PROOF) | 12 query functions, caching spec, offline behavior, all routes covered |
| 9 | prompts/ui_build/09_BUILD_SNAPSHOT_CONTROL_ROOM.md | PASS | time-os-ui/src/router.tsx, time-os-ui/src/components/RoomDrawer.tsx, RUN_LOG.md Entry 9 | RoomDrawer wired, eligibility gates enforced, tagging stubbed with payload shape logged |
| 10 | prompts/ui_build/10_BUILD_CLIENTS.md | PASS | time-os-ui/src/router.tsx, RUN_LOG.md Entry 10 | Portfolio search/sort + Detail with RoomDrawer/IssueDrawer/EvidenceViewer wired |
| 11 | prompts/ui_build/11_BUILD_TEAM.md | PASS | time-os-ui/src/router.tsx, RUN_LOG.md Entry 11 | Portfolio search/sort + Detail with responsible telemetry (bands, confidence, caveats) |
| 12 | prompts/ui_build/12_BUILD_INTERSECTIONS.md | PASS | time-os-ui/src/router.tsx, RUN_LOG.md Entry 12 | Anchor selection, coupling map, why-drivers, no coupling without evidence |
| 13 | prompts/ui_build/13_BUILD_ISSUES_AND_WATCHERS.md | PASS | time-os-ui/src/router.tsx, RUN_LOG.md Entry 13 | State/priority filters, search, watcher indicators, IssueDrawer with valid transitions |
| 14 | prompts/ui_build/14_BUILD_FIX_DATA.md | PASS | time-os-ui/src/router.tsx, RUN_LOG.md Entry 14 | Type/sort filters, FixDataDrawer, audit logging (logFixDataAction) |
| 15 | prompts/ui_build/15_TESTS_SCREENSHOTS_DONE_REPORT.md | PASS | time-os-ui/src/__tests__/*.test.ts, docs/ui_exec/99_DONE_REPORT.md | Tests + vitest config + done report complete |

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
