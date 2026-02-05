# Step 6 — COMPONENT LIBRARY (LOCKED)

## Objective
Define exact UI components (props, states, behavior) that implement the locked specs.

## Deliverables
Write docs/ui_spec/08_COMPONENT_LIBRARY.md defining:
- ProposalCard
- IssueCard
- ConfidenceBadge (two confidences)
- ProofList + ProofSnippet (excerpt anchors)
- HypothesesList
- RoomDrawer (universal)
- EvidenceViewer (excerpt navigation)
- PostureStrip (driven by top proposals, not raw KPIs)
- RightRail (Issues/Watchers/Fix Data)
- CouplingRibbon (inline intersections)
- FixDataCard + FixDataDetail
- FiltersScopeBar
- EvidenceTimeline (drill-down)

## Acceptance checks
- Every component references only fields in PROPOSAL_ISSUE_ROOM_CONTRACT.md.
- Each component has loading/empty/error/ineligible states.
- ProposalCard explicitly enforces eligibility gates.

## Stop condition
Invented field or missing state → STOP and fix.
