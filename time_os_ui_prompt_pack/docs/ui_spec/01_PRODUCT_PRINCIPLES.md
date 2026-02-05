# 01 — Product Principles (LOCKED)

## Truth Sources

All thresholds and field names in this document are contract-sourced:
- **Eligibility gates & thresholds:** 06_PROPOSALS_BRIEFINGS.md
- **UI field shapes:** PROPOSAL_ISSUE_ROOM_CONTRACT.md
- **If mismatch occurs:** UI must prefer backend contract and label UNKNOWN

---

## Executive Session Model (90-Second Rule)

The executive's attention is scarce. Time OS exists to **compress decision latency**, not expand information volume.

**Session budget:** 90 seconds for a complete check-in.
- 30s: Scan top proposals (max 7)
- 30s: Check active issues + watchers
- 30s: Address Fix Data (if any)

Everything that reaches the executive must be **pre-filtered, ranked, and actionable**.

---

## The Proposal Is the Unit of Executive Attention

### What a Proposal IS:
- A bundled, ranked **briefing** about something that may need attention
- Contains: what changed, impact, hypotheses, proof, missing confirmations
- Surfaces ONLY when eligibility gates pass

### What a Proposal IS NOT:
- A raw signal
- An unverified alert
- A task list item

### Eligibility Gates (Contract-Sourced from 06_PROPOSALS_BRIEFINGS.md)

A proposal surfaces to the executive ONLY IF:

| Gate | Requirement | Contract Citation |
|------|-------------|-------------------|
| **Proof density** | ≥3 distinct excerpt_ids in `proof_excerpt_ids_json` | "proof_excerpt_ids_json contains ≥ 3 distinct excerpt ids" |
| **Scope coverage** | Min link confidence ≥ 0.70 across scope refs | "minimum link confidence across used links ≥ 0.70" |
| **Reasoning** | ≥1 hypothesis with confidence ≥ 0.55 AND ≥2 supporting signals | "at least 1 hypothesis with confidence ≥ 0.55 and ≥2 supporting signals" |
| **Source validity** | Every excerpt_id resolves to real `artifact_excerpts` record | "every proof bullet must resolve to a real artifact_excerpts.excerpt_id" |

**If ANY gate fails:** Proposal does NOT surface. Instead → Fix Data queue.

---

## Proof-First Rendering

### Every surface must answer:
1. **What changed?** (delta)
2. **Why does it matter?** (impact: time/cash/reputation)
3. **What's the likely cause?** (hypotheses with confidence)
4. **What's the evidence?** (proof excerpts with anchors)
5. **What would raise certainty?** (missing confirmations)

### Visual hierarchy (top to bottom):
```
┌─────────────────────────────────────────┐
│ HEADLINE (what changed)                 │
│ Impact strip (time | cash | reputation) │
├─────────────────────────────────────────┤
│ Hypotheses (ranked by confidence)       │
│   └─ Supporting signals (collapsed)     │
├─────────────────────────────────────────┤
│ Proof (3-6 excerpts with anchors)       │
│   └─ [Open evidence →]                  │
├─────────────────────────────────────────┤
│ Missing confirmations (if any)          │
├─────────────────────────────────────────┤
│ Confidence badges (link | interp)       │
│ Actions: [Tag] [Snooze] [Dismiss]       │
└─────────────────────────────────────────┘
```

---

## Dual Confidence Model

Every surface with derived conclusions displays **TWO** confidence indicators:

### 1. Linkage Confidence
- "Are we looking at the right entities?"
- Driven by entity_links coverage for `scope_refs_json`
- Gate threshold: ≥ 0.70 (per 06_PROPOSALS_BRIEFINGS.md)

### 2. Interpretation Confidence
- "Is the conclusion warranted by the evidence?"
- Driven by `hypotheses_json[].confidence` (top hypothesis)
- Gate threshold: ≥ 0.55 (per 06_PROPOSALS_BRIEFINGS.md)

**UI must show BOTH.** Never hide confidence. Display numeric value + pass/fail indicator.

---

## Ineligible States + Fix Data CTA

When a proposal fails eligibility gates (per 06_PROPOSALS_BRIEFINGS.md):

| Gate Failure | UI Behavior | CTA Copy |
|--------------|-------------|----------|
| Proof density < 3 | Card dimmed, Tag disabled | "Needs more evidence (3 required)" |
| Link confidence < 0.70 | Warning badge | "Weak entity linkage" |
| Hypothesis confidence < 0.55 | Low confidence indicator | "Weak hypothesis — insufficient signal support" |
| Orphan excerpt | Error state | "Broken evidence anchor" |

**CTAs are direct links to resolution workflows.** No dead ends.

---

## Safe-by-Default Actions

| Action | Effect | Reversible |
|--------|--------|------------|
| Tag | Creates monitored Issue | Yes (untagging returns to Proposal) |
| Snooze | Hides until snooze_until | Yes (wake early) |
| Dismiss | Removes from view, feeds feedback | Yes (undo within session) |
| Copy Draft | Generates text for external send | No send—copy only |

**No auto-send.** Executive controls the final mile.

---

## Mobile-First Mandate

Every screen must be:
- Usable on a phone in portrait mode
- Touch-friendly (44px minimum tap targets)
- Scannable in 10 seconds
- Functional offline (cached data + queued actions)

---

LOCKED: 2026-02-05 (PATCHED for contract binding)
