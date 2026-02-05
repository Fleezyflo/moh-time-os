# Step 5 — PAGE SPECS (LOCKED)

## Objective
Write deterministic, buildable page specs with explicit query/field mappings.

## Deliverables
Create docs/ui_spec/07_PAGE_SPECS/ with these files:
- 01_SNAPSHOT_CONTROL_ROOM.md
- 02_CLIENTS_PORTFOLIO.md
- 03_CLIENT_DETAIL_REPORT.md
- 04_TEAM_PORTFOLIO.md
- 05_TEAM_DETAIL_REPORT.md
- 06_INTERSECTIONS.md
- 07_ISSUES_INBOX.md
- 08_FIX_DATA_CENTER.md

Each page spec MUST include these sections:
1. Purpose
2. Primary decisions enabled (max 3)
3. Default view anatomy (zones + layout)
4. Primary surfaces (for each: queries, fields, confidence behavior, states, interactions)
5. Ranking/Sorting rules (deterministic)
6. Filters & scope
7. Drill-down paths
8. Drawer/Detail contract
9. Actions available (safe-by-default)
10. Performance budget
11. Telemetry
12. Acceptance tests

End each file with: LOCKED_SPEC

## Acceptance checks
- Every surface has exact query + field mapping (contract fields).
- Eligibility gate behavior exists on Snapshot and entity pages.
- Tables appear only in drill-down/audit views.

## Stop condition
Any missing mapping → STOP and fix before proceeding.
