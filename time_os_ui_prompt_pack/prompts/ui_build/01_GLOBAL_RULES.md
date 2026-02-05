# Step 1 — GLOBAL RULES (No Skipping)

## Objective
Lock non-negotiable execution constraints and logging requirements.

## Deliverables
Create/ensure these files exist (append-only discipline):
- docs/ui_exec/RUN_LOG.md
- docs/ui_exec/CHECKPOINTS.md

## Rules (must be followed)
1) No step skipping. No parallelization.
2) No invented fields or fake confidence.
3) Must enforce Proposal eligibility gates from 06_PROPOSALS_BRIEFINGS.md.
4) Must render both confidences: linkage_confidence + interpretation_confidence.
5) Must include evidence anchors (excerpt_id) for proof bullets.

## Acceptance checks
- RUN_LOG.md exists and includes a header.
- CHECKPOINTS.md exists with a table listing steps 1–15 and status empty.
- Agent writes a first log entry for Step 1.

## Stop condition
If any required backend contract file is missing, STOP and report missing paths.
