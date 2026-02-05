# 03 — Design System (LOCKED)

## Contract Binding (Non-Negotiable)

All UI data shapes and thresholds MUST be derived from backend contracts. No invention allowed.

### Truth Sources
- **Field names & shapes:** PROPOSAL_ISSUE_ROOM_CONTRACT.md
- **Eligibility gates & thresholds:** 06_PROPOSALS_BRIEFINGS.md
- **If mismatch occurs:** UI must prefer backend contract and label field as UNKNOWN

### A) Proposal Fields (from PROPOSAL_ISSUE_ROOM_CONTRACT.md)

| Contract Field | Type | UI Usage |
|----------------|------|----------|
| `proposal_id` | TEXT | Unique identifier |
| `proposal_type` | TEXT | 'risk'|'opportunity'|'request'|'decision_needed'|'anomaly'|'compliance' |
| `headline` | TEXT | Card title |
| `score` | REAL | Ranking score (sort key) |
| `impact_json` | JSON | `{dimensions:{time,cash,reputation}, deadline_at?}` |
| `hypotheses_json` | JSON | `[{label, score, confidence, signal_ids[], missing_confirmations[]}]` (max 3) |
| `signal_ids_json` | JSON | Array of signal_ids supporting the proposal |
| `proof_excerpt_ids_json` | JSON | Array of excerpt_ids (3-6 required for eligibility) |
| `missing_confirmations_json` | JSON | Array of strings (max 2 shown) |
| `scope_refs_json` | JSON | `[{type, id}]` — linked entities |
| `trend` | TEXT | 'worsening'|'improving'|'flat' |
| `occurrence_count` | INTEGER | Recurrence indicator |
| `status` | TEXT | 'open'|'snoozed'|'dismissed'|'accepted' |

### B) Issue Fields (from PROPOSAL_ISSUE_ROOM_CONTRACT.md)

| Contract Field | Type | UI Usage |
|----------------|------|----------|
| `issue_id` | TEXT | Unique identifier |
| `state` | TEXT | 'open'|'monitoring'|'awaiting'|'blocked'|'resolved'|'closed' |
| `priority` | TEXT | 'critical'|'high'|'medium'|'low' |
| `primary_ref` | TEXT | Headline reference |
| `resolution_criteria` | TEXT | Short-form completion definition |
| `last_activity_at` | TEXT | ISO timestamp |
| `next_trigger` | TEXT | From watchers, ISO timestamp |

### C) Confidence Display Mapping

Per PROPOSAL_ISSUE_ROOM_CONTRACT.md, the UI renders **two badges**:

| Badge | Contract Source | Description |
|-------|-----------------|-------------|
| **Link confidence** | Derived from `entity_links` coverage/edge strength for `scope_refs_json` | Entity linkage quality |
| **Interpretation confidence** | `hypotheses_json[].confidence` (top hypothesis) | Hypothesis quality |

**Display rule:** Always show BOTH badges. If a value is null or missing, show "Unknown".

### D) Evidence Strip Binding

The Evidence Strip renders from `proof_excerpt_ids_json`. Each excerpt resolves to:

| Contract Field | UI Element |
|----------------|------------|
| `excerpt_id` | Unique anchor for deep-link |
| Derived snippet text | From `artifact_excerpts` table lookup |
| `source_type` | Icon + label (email, asana_task, etc.) |
| `extracted_at` | Timestamp display |
| `source_ref` | Deep-link to original artifact |

If an `excerpt_id` cannot resolve: render error state "Broken evidence anchor" + Fix Data CTA.

---

## Eligibility Gates (UI Enforcement)

**Source:** 06_PROPOSALS_BRIEFINGS.md § "Proposal surfacing gates (hard rules)"

A proposal may render as taggable ONLY if ALL gates pass:

### Gate 1: Proof Density
- **Condition:** `proof_excerpt_ids_json` contains **≥ 3** distinct excerpt_ids
- **UI on FAIL:** Card dimmed, Tag button disabled
- **Copy:** "Needs more evidence (3 required)"
- **CTA:** → Fix Data Center (evidence queue)

### Gate 2: Scope Coverage (Link Confidence)
- **Condition:** Minimum link confidence across scope refs **≥ 0.70**
- **Source:** 06_PROPOSALS_BRIEFINGS.md: "minimum link confidence across used links ≥ 0.70"
- **UI on FAIL:** Warning badge, card partially disabled
- **Copy:** "Weak entity linkage"
- **CTA:** → Fix Data Center (link resolution)

### Gate 3: Reasoning (Hypothesis Confidence)
- **Condition:** At least **1 hypothesis** with `confidence ≥ 0.55` AND **≥ 2 supporting signals**
- **Source:** 06_PROPOSALS_BRIEFINGS.md: "at least 1 hypothesis with confidence ≥ 0.55 and ≥2 supporting signals"
- **UI on FAIL:** Hypothesis section shows uncertainty
- **Copy:** "Weak hypothesis — insufficient signal support"
- **CTA:** Review signals in drawer

### Gate 4: Source Validity
- **Condition:** Every `excerpt_id` in `proof_excerpt_ids_json` resolves to a real `artifact_excerpts` record
- **Source:** 06_PROPOSALS_BRIEFINGS.md: "every proof bullet must resolve to a real artifact_excerpts.excerpt_id"
- **UI on FAIL:** Error state, evidence strip broken
- **Copy:** "Broken evidence anchor"
- **CTA:** → Fix Data Center (orphan excerpt)

**If ANY gate fails:** Do not allow Tag action. Show appropriate CTA to Fix Data.

---

## Design Philosophy

**Editorial, not dashboardy.** Time OS surfaces insights like a newspaper editor—curated, ranked, evidence-backed. Not a wall of charts.

**Sparse, not dense.** Whitespace is a feature. Every pixel must earn its place.

**Proof-first.** Evidence is always one tap away. No assertions without anchors.

---

## Color System

### Base Palette (Dark Theme)
```css
--color-bg-primary: #0f172a;      /* slate-900 */
--color-bg-secondary: #1e293b;    /* slate-800 */
--color-bg-tertiary: #334155;     /* slate-700 */
--color-bg-elevated: #475569;     /* slate-600 */

--color-text-primary: #f1f5f9;    /* slate-100 */
--color-text-secondary: #94a3b8;  /* slate-400 */
--color-text-muted: #64748b;      /* slate-500 */

--color-border-default: #334155;  /* slate-700 */
--color-border-subtle: #1e293b;   /* slate-800 */
```

### Semantic Colors (Minimal — used sparingly)
```css
/* Confidence indicators ONLY */
--color-confidence-pass: #22c55e;    /* green-500 — meets gate threshold */
--color-confidence-fail: #ef4444;    /* red-500 — below gate threshold */
--color-confidence-unknown: #64748b; /* slate-500 — null/missing */

/* Impact domain accents */
--color-impact-time: #f97316;        /* orange-500 */
--color-impact-cash: #22c55e;        /* green-500 */
--color-impact-reputation: #8b5cf6;  /* violet-500 */

/* State indicators */
--color-state-open: #3b82f6;         /* blue-500 */
--color-state-blocked: #ef4444;      /* red-500 */
--color-state-resolved: #22c55e;     /* green-500 */
```

### Color Usage Rules
1. **Background colors** dominate (95%+ of pixels)
2. **Semantic colors** appear ONLY on:
   - Confidence badges
   - Impact indicators
   - State chips
3. **Never** use color alone to convey meaning—always pair with text/icon

---

## Typography Scale

### Font Stack
```css
--font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
--font-mono: 'SF Mono', 'Fira Code', monospace;
```

### Type Scale (Mobile-First)
| Token | Size | Line Height | Weight | Usage |
|-------|------|-------------|--------|-------|
| `text-xs` | 12px | 16px | 400 | Labels, captions |
| `text-sm` | 14px | 20px | 400 | Body small, metadata |
| `text-base` | 16px | 24px | 400 | Body default |
| `text-lg` | 18px | 28px | 500 | Card titles |
| `text-xl` | 20px | 28px | 600 | Section headers |
| `text-2xl` | 24px | 32px | 600 | Page titles |
| `text-3xl` | 30px | 36px | 700 | Hero numbers |

### Responsive Adjustments
```css
@media (min-width: 640px) {
  --text-2xl: 28px;
  --text-3xl: 36px;
}
```

---

## Spacing Scale

### Base Unit: 4px
| Token | Value | Usage |
|-------|-------|-------|
| `space-0` | 0 | Reset |
| `space-1` | 4px | Tight inline gaps |
| `space-2` | 8px | Icon-to-text, badge padding |
| `space-3` | 12px | Card internal padding (mobile) |
| `space-4` | 16px | Card internal padding (desktop) |
| `space-5` | 20px | Section gaps |
| `space-6` | 24px | Card margins |
| `space-8` | 32px | Section margins |
| `space-10` | 40px | Page margins |
| `space-12` | 48px | Major section breaks |

---

## Layout Grid

### Mobile (< 640px)
- Single column
- Horizontal padding: 16px
- Cards: full width
- Stack everything vertically

### Tablet (640px – 1024px)
- 2-column max
- Horizontal padding: 24px
- Cards: can sit side-by-side

### Desktop (> 1024px)
- 12-column grid
- Max content width: 1280px
- Horizontal padding: 32px
- Primary content: 8 cols
- Right rail: 4 cols

```css
.container {
  width: 100%;
  max-width: 1280px;
  margin: 0 auto;
  padding: 0 var(--space-4);
}

@media (min-width: 640px) {
  .container { padding: 0 var(--space-6); }
}

@media (min-width: 1024px) {
  .container { padding: 0 var(--space-8); }
}
```

---

## Elevation (Shadows)

```css
--shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
--shadow-md: 0 4px 6px rgba(0, 0, 0, 0.4);
--shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.5);
--shadow-drawer: 0 0 40px rgba(0, 0, 0, 0.6);
```

| Level | Usage |
|-------|-------|
| None | Default surfaces |
| `shadow-sm` | Hover states, chips |
| `shadow-md` | Cards, dropdowns |
| `shadow-lg` | Modals, popovers |
| `shadow-drawer` | Side drawers |

---

## Confidence UI Display

### Badge Rendering (Contract-Bound)

Confidence values are numeric (0-1). UI renders based on eligibility gate thresholds from 06_PROPOSALS_BRIEFINGS.md:

| Confidence Type | Gate Threshold | Pass Color | Fail Color |
|-----------------|----------------|------------|------------|
| Link confidence | ≥ 0.70 | green | red |
| Interpretation confidence | ≥ 0.55 | green | red |

**Note:** Thresholds 0.70 and 0.55 are sourced directly from 06_PROPOSALS_BRIEFINGS.md. No other numeric thresholds exist in the contract.

### Badge Display Pattern
```
┌────────────────────────────────────┐
│ [🔗 Link: 0.82 ✓] [💡 Hyp: 0.61 ✓] │
└────────────────────────────────────┘
```
- Always show BOTH badges
- Show numeric value + pass/fail indicator
- Link confidence: pass if ≥ 0.70 (per contract)
- Interpretation confidence: pass if ≥ 0.55 (per contract)
- If null/missing: show "Unknown" in gray

---

## Evidence Strip Pattern

Proof excerpts render in a consistent strip (bound to `proof_excerpt_ids_json`):

```
┌──────────────────────────────────────────┐
│ ● "Client mentioned budget concerns..."  │
│   📎 Email from John, Jan 15            │
│   [Open evidence →]                      │
├──────────────────────────────────────────┤
│ ● "Invoice #4521 overdue by 14 days"    │
│   📎 Xero invoice, Jan 1                │
│   [Open evidence →]                      │
├──────────────────────────────────────────┤
│ ● "Task blocked for 5 days"             │
│   📎 Asana task update, Jan 10          │
│   [Open evidence →]                      │
└──────────────────────────────────────────┘
```

### Evidence Strip Tokens
```css
--evidence-bullet: #3b82f6;     /* blue-500 */
--evidence-anchor-bg: rgba(59, 130, 246, 0.1);
--evidence-anchor-hover: rgba(59, 130, 246, 0.2);
--evidence-text: var(--color-text-secondary);
--evidence-source: var(--color-text-muted);
```

---

## Touch Targets (Mobile-First)

### Minimum Sizes
| Element | Min Width | Min Height |
|---------|-----------|------------|
| Button | 44px | 44px |
| Icon button | 44px | 44px |
| List item | 100% | 48px |
| Nav link | 44px | 44px |
| Badge (tappable) | 32px | 32px |

### Spacing Between Targets
- Minimum gap: 8px between tappable elements
- Recommended gap: 12px for primary actions

---

## Responsive Breakpoints

```css
/* Mobile-first base styles */

/* Small (sm): 640px+ */
@media (min-width: 640px) { ... }

/* Medium (md): 768px+ */
@media (min-width: 768px) { ... }

/* Large (lg): 1024px+ */
@media (min-width: 1024px) { ... }

/* XL: 1280px+ */
@media (min-width: 1280px) { ... }
```

---

## Component State Patterns

### Interactive States
```css
/* Default */
.card { background: var(--color-bg-secondary); }

/* Hover */
.card:hover { background: var(--color-bg-tertiary); }

/* Active/Pressed */
.card:active { background: var(--color-bg-elevated); }

/* Focus */
.card:focus-visible {
  outline: 2px solid var(--color-state-open);
  outline-offset: 2px;
}

/* Disabled / Ineligible */
.card.ineligible {
  opacity: 0.5;
  pointer-events: none;
}
```

---

## Acceptance Checklist

- [x] Contract Binding section with exact field names from PROPOSAL_ISSUE_ROOM_CONTRACT.md
- [x] Eligibility Gates sourced from 06_PROPOSALS_BRIEFINGS.md (0.70 link, 0.55 hypothesis, 3 excerpts)
- [x] Typography scale defined (7 levels)
- [x] Spacing scale defined (12 tokens)
- [x] Layout grid defined (mobile/tablet/desktop)
- [x] Confidence display bound to contract thresholds (no invented numbers)
- [x] Evidence strip bound to contract fields
- [x] Touch targets specified (44px minimum)
- [x] Responsive breakpoints defined

---

LOCKED: 2026-02-05 (PATCHED for contract binding)
