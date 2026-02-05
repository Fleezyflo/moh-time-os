# Step 8 — DATA ACCESS LAYER (LOCAL-FIRST)

## Objective
Implement query functions exactly per CONTROL_ROOM_QUERIES.md with local-first caching.

## Deliverables
1) docs/ui_spec/09_DATA_ACCESS_LAYER.md describing caching + invalidation + offline behavior.
2) Code: one function per query recipe, typed to PROPOSAL_ISSUE_ROOM_CONTRACT.md.
3) DataProvider supporting:
   - fixture mode
   - real mode (DB/API)

## Acceptance checks
- Every query compiles and returns contract shape.
- Sorting is deterministic and matches page specs.

## Stop condition
Missing backend endpoint → implement adapter stub + document the missing endpoint; do not invent fields.
