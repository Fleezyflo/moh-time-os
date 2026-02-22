# Brief 28: Intelligence Observability & Explainability
> **Status:** DESIGNED | **Priority:** P2 | **Prefix:** IO

## Problem

When a client's score drops from 72 to 58, Molham asks "why?" Today the answer requires digging through signal_state, score_history, and pattern_snapshots manually. There's no audit trail connecting a score change to its causes. Intelligence is a black box.

AO-3.1 adds Prometheus metrics for the daemon loop (cycle timing, collector counts). That's infrastructure observability. This brief is about **intelligence observability** — understanding WHY the intelligence layer produces what it produces.

## Dependencies

- **Requires:** Brief 17 (persistence), Brief 18 (depth modules)
- **Enhances:** Brief 26 (API surfaces explanations), Brief 24 (prepared intelligence needs to explain "why")

## Scope

1. **Computation audit trail** — every score, signal, pattern computation logged with inputs and outputs
2. **Explainability** — human-readable "because" statements for every intelligence output
3. **Drift detection** — are scores clustering? Are signals getting noisier?
4. **Debug mode** — run intelligence for single entity with full trace

## Tasks

| Task | Title | Est. Lines |
|------|-------|------------|
| IO-1.1 | Computation Audit Trail | ~300 |
| IO-2.1 | Explainability Engine | ~400 |
| IO-3.1 | Intelligence Drift Detection | ~250 |
| IO-4.1 | Debug Mode & Single-Entity Trace | ~200 |
| IO-5.1 | Observability Validation | ~300 |

## Estimated Effort

~1,450 lines. 5 tasks. Medium-large.

## Success Criteria

- Every score change has a traceable "because" chain
- Molham can ask "why did Client X's score drop?" and get a concrete answer
- Intelligence drift is detected before it becomes a problem
- Debug mode lets the implementing agent trace issues in a single entity
