# Step 13 — BUILD ISSUES INBOX + WATCHERS

## Objective
Build issue lifecycle UI with state machine enforcement and watcher visibility.

## Deliverables
- /issues list with states, filters
- issue detail drawer:
  - originating proposal snapshot
  - handoffs + commitments
  - watchers list and next trigger time

## Acceptance checks
- Invalid transitions blocked.
- Watcher next trigger visible and deduped.

## Stop condition
Transitions without required fields → STOP and enforce spec.
