# Step 9 — BUILD SNAPSHOT (CONTROL ROOM) FULLY

## Objective
Build the real Snapshot page wired to data access.

## Deliverables
- Snapshot route implemented per LOCKED spec.
- Proposal stack renders eligible vs ineligible correctly.
- RightRail renders Issues/Watchers/Fix Data.
- RoomDrawer opens with EvidenceViewer.

Tagging:
- If Tag endpoint exists, call it.
- If not, stub it but log the payload shape required by 07_TAG_TO_ISSUE_TRANSACTION.md.

## Acceptance checks
- Clicking a proposal opens RoomDrawer with evidence.
- Ineligible proposals cannot be tagged and show Fix Data CTA.
- Tagging produces an Issue entry (real or stubbed) in RightRail.

## Stop condition
If tag flow is not idempotent, STOP and fix.
