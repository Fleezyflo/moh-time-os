# Step 14 — BUILD FIX DATA CENTER

## Objective
Build Fix Data UI to resolve identity/link conflicts and improve confidence.

## Deliverables
- /fix-data:
  - identity conflicts (merge/split)
  - ambiguous links (confirm/deny)
  - missing mappings (create alias)
- Audit logging of every fix

## Acceptance checks
- Resolving Fix Data updates linkage and changes proposal eligibility where applicable.
- Audit trail exists for all fixes.

## Stop condition
If actions are not persisted, STOP and implement persistence.
