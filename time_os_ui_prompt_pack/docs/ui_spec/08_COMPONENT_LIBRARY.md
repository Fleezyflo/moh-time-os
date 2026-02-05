# Component Library — Time OS Control Room

LOCKED_SPEC

## Overview
This document defines the exact UI components, their props, states, and behavior. All components reference only fields from PROPOSAL_ISSUE_ROOM_CONTRACT.md.

---

## 1. ProposalCard

The primary unit of attention. Renders a proposal with eligibility gate enforcement.

### Props
```typescript
interface ProposalCardProps {
  proposal: {
    proposal_id: string;
    headline: string;
    impact: {
      dimensions: {
        time?: { days_at_risk: number; deadline_at?: string };
        cash?: { amount: number; currency: string };
        reputation?: { severity: 'low' | 'medium' | 'high' };
      };
      deadline_at?: string;
    };
    top_hypotheses: Array<{
      label: string;
      confidence: number; // 0-1
      supporting_signal_ids: string[];
    }>; // max 3
    proof: Array<{
      excerpt_id: string;
      text: string;
      source_type: string;
      source_ref: string;
    }>; // 3-6 required
    missing_confirmations: string[]; // max 2
    score: number;
    trend: 'worsening' | 'improving' | 'flat';
    occurrence_count: number;
    linkage_confidence: number; // derived
    interpretation_confidence: number; // from top hypothesis
  };
  eligibility: {
    is_eligible: boolean;
    gate_violations: Array<{
      gate: 'proof_density' | 'scope_coverage' | 'reasoning' | 'source_validity';
      message: string;
    }>;
  };
  onTag?: () => void;
  onSnooze?: () => void;
  onDismiss?: () => void;
  onOpen?: () => void;
}
```

### States
| State | Condition | Rendering |
|-------|-----------|-----------|
| Loading | Data fetching | Skeleton with headline placeholder |
| Eligible | `is_eligible=true` | Full card, Tag button enabled |
| Ineligible | `is_eligible=false` | Muted card, Tag disabled, Fix Data CTA |
| Error | Fetch failed | Error message + retry |

### Behavior
- **Tap card body** → `onOpen()` (opens RoomDrawer)
- **Tap Tag & Monitor** → `onTag()` (disabled if ineligible)
- **Tap Snooze** → `onSnooze()` (opens duration picker)
- **Swipe left** → `onDismiss()` (with confirmation)

### Eligibility gate UI
```
┌──────────────────────────────────────┐
│ ⚠️ Ineligible                        │
│                                      │
│ headline (muted)                     │
│                                      │
│ Gate violations:                     │
│ • Weak linkage (0.58)                │
│ • Only 2 proof excerpts              │
│                                      │
│ [Fix Data →]                         │
│                                      │
│ [Tag & Monitor] ← DISABLED           │
└──────────────────────────────────────┘
```

---

## 2. IssueCard

Renders an issue with state, priority, and watcher info.

### Props
```typescript
interface IssueCardProps {
  issue: {
    issue_id: string;
    state: 'open' | 'monitoring' | 'awaiting' | 'blocked' | 'resolved' | 'closed';
    priority: 'critical' | 'high' | 'medium' | 'low';
    headline: string;
    primary_ref: string;
    resolution_criteria: string;
    last_activity_at: string; // ISO
    next_trigger?: string; // ISO, from watcher
  };
  onOpen?: () => void;
}
```

### States
| State | Condition | Rendering |
|-------|-----------|-----------|
| Loading | Data fetching | Skeleton row |
| Default | Data loaded | Full row with state icon |
| Error | Fetch failed | Error message |

### State icons
| State | Icon | Color |
|-------|------|-------|
| open | ● | red-500 |
| monitoring | ◐ | amber-500 |
| awaiting | ◑ | blue-500 |
| blocked | ■ | gray-900 |
| resolved | ✓ | green-500 |
| closed | ○ | gray-400 |

---

## 3. ConfidenceBadge

Renders dual confidence indicators.

### Props
```typescript
interface ConfidenceBadgeProps {
  type: 'linkage' | 'interpretation';
  value: number; // 0-1
  showLabel?: boolean; // default true
}
```

### Rendering rules
| Value range | Level | Color | Label |
|-------------|-------|-------|-------|
| ≥ 0.80 | High | green-500 | "High" |
| 0.60 - 0.79 | Medium | amber-500 | "Med" |
| < 0.60 | Low | red-500 | "Low" |
| null/undefined | Unknown | gray-400 | "—" |

### Always show both
```
┌─────────────────────────────────┐
│ Link: ●High  Interp: ●Med       │
└─────────────────────────────────┘
```

---

## 4. ProofList + ProofSnippet

Renders evidence excerpts with anchor navigation.

### ProofList Props
```typescript
interface ProofListProps {
  excerpts: Array<{
    excerpt_id: string;
    text: string;
    source_type: string;
    source_ref: string;
  }>;
  onExcerptClick?: (excerpt_id: string) => void;
  maxVisible?: number; // default 3, show "N more" link
}
```

### ProofSnippet Props
```typescript
interface ProofSnippetProps {
  excerpt: {
    excerpt_id: string;
    text: string;
    source_type: string;
    source_ref: string;
  };
  highlighted?: boolean; // for anchor navigation
  onClick?: () => void;
}
```

### Rendering
```
┌──────────────────────────────────────┐
│ 📧 "Client mentioned delay concern…" │
│    ↳ email · 2 days ago              │
├──────────────────────────────────────┤
│ 📋 "Milestone pushed to next week…"  │
│    ↳ asana_task · yesterday          │
├──────────────────────────────────────┤
│ 📅 "Discussed timeline in standup…"  │
│    ↳ calendar · 3 days ago           │
└──────────────────────────────────────┘
│ +2 more excerpts                     │
```

---

## 5. HypothesesList

Renders ranked hypotheses with confidence and signal links.

### Props
```typescript
interface HypothesesListProps {
  hypotheses: Array<{
    label: string;
    confidence: number;
    supporting_signal_ids: string[];
    missing_confirmations?: string[];
  }>; // max 3
  onSignalClick?: (signal_id: string) => void;
}
```

### Rendering
```
┌──────────────────────────────────────┐
│ Why this matters:                    │
│                                      │
│ 1. Resource bottleneck (●High 0.82)  │
│    Supported by: 3 signals           │
│                                      │
│ 2. Scope creep (●Med 0.67)           │
│    Supported by: 2 signals           │
│    Missing: Client confirmation      │
│                                      │
│ 3. External dependency (●Low 0.45)   │
│    Supported by: 1 signal            │
└──────────────────────────────────────┘
```

---

## 6. RoomDrawer

Universal detail drawer for proposals, issues, and entities.

### Props
```typescript
interface RoomDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  entity: {
    type: 'proposal' | 'issue' | 'client' | 'team_member';
    id: string;
    headline: string;
    coverage_summary?: string; // link confidence
  };
  children: React.ReactNode; // tab content
}
```

### Structure
```
┌──────────────────────────────────────┐
│ × │ Entity Name                      │
│   │ Coverage: ●High (0.89)           │
├──────────────────────────────────────┤
│                                      │
│ [Content area - tabs or sections]    │
│                                      │
│ What changed                         │
│ ─────────────────────────────────    │
│ Summary text...                      │
│                                      │
│ Why likely                           │
│ ─────────────────────────────────    │
│ <HypothesesList />                   │
│                                      │
│ Proof                                │
│ ─────────────────────────────────    │
│ <ProofList />                        │
│                                      │
├──────────────────────────────────────┤
│ [Tag & Monitor] [Snooze] [Dismiss]   │
└──────────────────────────────────────┘
```

### States
| State | Rendering |
|-------|-----------|
| Closed | Not visible |
| Opening | Slide-in animation (300ms) |
| Open | Full content |
| Loading | Skeleton content |

### Behavior
- **Mobile:** Full-screen bottom sheet
- **Desktop:** Right-aligned panel (400px width)
- **Close:** Swipe right, tap outside, or × button
- **Stacking:** Max 2 drawers (parent + child)

---

## 7. EvidenceViewer

Anchored excerpt navigation within drawer.

### Props
```typescript
interface EvidenceViewerProps {
  excerpts: Array<{
    excerpt_id: string;
    text: string;
    context?: string; // surrounding text
    source_type: string;
    source_ref: string;
    extracted_at: string;
  }>;
  anchorId?: string; // scroll to this excerpt
  onSourceClick?: (source_ref: string) => void;
}
```

### Rendering
```
┌──────────────────────────────────────┐
│ Evidence (3 excerpts)                │
├──────────────────────────────────────┤
│ ┌────────────────────────────────┐   │
│ │ ★ ANCHORED                     │   │
│ │ "The client expressed concern  │   │
│ │ about the timeline shifting…"  │   │
│ │                                │   │
│ │ Context: Full email paragraph  │   │
│ │                                │   │
│ │ [Open in Gmail →]              │   │
│ └────────────────────────────────┘   │
│                                      │
│ ┌────────────────────────────────┐   │
│ │ "Milestone was pushed…"        │   │
│ │ [Open in Asana →]              │   │
│ └────────────────────────────────┘   │
│                                      │
│ ← Previous | Next →                  │
└──────────────────────────────────────┘
```

---

## 8. PostureStrip

Shows entity posture derived from proposals (not raw KPIs).

### Props
```typescript
interface PostureStripProps {
  posture: 'critical' | 'attention' | 'healthy' | 'inactive';
  proposal_count: number;
  issue_count: number;
  confidence?: number; // if any weak linkage
}
```

### Rendering
| Posture | Icon | Color | Text |
|---------|------|-------|------|
| critical | 🔴 | red-500 | "Needs attention" |
| attention | ⚠️ | amber-500 | "Review recommended" |
| healthy | ✓ | green-500 | "On track" |
| inactive | ◯ | gray-400 | "No recent activity" |

---

## 9. RightRail

Container for Issues, Watchers, and Fix Data on Snapshot.

### Props
```typescript
interface RightRailProps {
  issues: IssueCardProps['issue'][];
  watchers: Array<{
    watcher_id: string;
    issue_id: string;
    next_check_at: string;
    trigger_condition: string;
  }>;
  fixDataCount: number;
  onIssueClick?: (issue_id: string) => void;
  onWatcherClick?: (watcher_id: string) => void;
  onFixDataClick?: () => void;
}
```

### Structure
```
┌──────────────────────────┐
│ Issues (5)               │
│ ─────────────────────    │
│ <IssueCard /> × 5        │
│                          │
│ Watchers (3)             │
│ ─────────────────────    │
│ <WatcherRow /> × 3       │
│                          │
│ Fix Data (12)            │
│ ─────────────────────    │
│ [View all →]             │
└──────────────────────────┘
```

---

## 10. CouplingRibbon

Inline coupling indicator for intersections.

### Props
```typescript
interface CouplingRibbonProps {
  couplings: Array<{
    coupling_id: string;
    coupled_type: string;
    coupled_id: string;
    coupled_label: string;
    strength: number; // 0-1
    confidence: number;
  }>;
  onCouplingClick?: (coupling_id: string) => void;
}
```

### Rendering
```
┌────────────────────────────────────────┐
│ Linked to: Client A (●Strong)          │
│            Team: Bob (●Medium)         │
│            Issue #45 (●Weak)           │
└────────────────────────────────────────┘
```

---

## 11. FixDataCard + FixDataDetail

Data quality resolution components.

### FixDataCard Props
```typescript
interface FixDataCardProps {
  fixData: {
    fix_data_id: string;
    fix_type: 'identity_conflict' | 'ambiguous_link' | 'missing_mapping';
    description: string;
    candidates_json: string; // JSON array
    impact_summary: string;
    affected_proposal_ids: string[];
  };
  onResolve?: (action: string, selection?: string) => void;
  onOpen?: () => void;
}
```

### States
| State | Rendering |
|-------|-----------|
| Pending | Full card with actions |
| Resolving | Loading spinner |
| Resolved | Success message, fade out |
| Error | Error message + retry |

### Fix type icons
| Type | Icon |
|------|------|
| identity_conflict | 🔀 |
| ambiguous_link | 🔗 |
| missing_mapping | ➕ |

---

## 12. FiltersScopeBar

Scope and filter controls for portfolio pages.

### Props
```typescript
interface FiltersScopeBarProps {
  scope?: {
    type: 'client' | 'brand' | 'engagement';
    id: string;
    label: string;
  };
  timeHorizon: 'today' | '7d' | '30d';
  filters?: Record<string, string[]>;
  onScopeChange?: (scope: FiltersScopeBarProps['scope']) => void;
  onHorizonChange?: (horizon: string) => void;
  onFilterChange?: (key: string, values: string[]) => void;
}
```

### Rendering
```
┌──────────────────────────────────────────────┐
│ Scope: [All ▼] | Time: [7 days ▼] | 🔍 Search │
└──────────────────────────────────────────────┘
```

---

## 13. EvidenceTimeline

Drill-down evidence view for entity detail pages.

### Props
```typescript
interface EvidenceTimelineProps {
  excerpts: Array<{
    excerpt_id: string;
    text: string;
    source_type: string;
    source_ref: string;
    extracted_at: string;
  }>;
  groupBy?: 'date' | 'source_type';
  onExcerptClick?: (excerpt_id: string) => void;
}
```

### Rendering (grouped by date)
```
┌──────────────────────────────────────┐
│ Today                                │
│ ├─ 📧 "Email excerpt…" · 2h ago      │
│ └─ 📋 "Task update…" · 4h ago        │
│                                      │
│ Yesterday                            │
│ ├─ 📅 "Meeting note…" · 10am         │
│ └─ 📧 "Reply from…" · 3pm            │
│                                      │
│ Feb 3                                │
│ └─ 📋 "Milestone marked…"            │
└──────────────────────────────────────┘
```

---

## Component States (Universal)

All components must implement these states:

| State | Skeleton | Empty | Error | Ineligible |
|-------|----------|-------|-------|------------|
| ProposalCard | ✅ | N/A | ✅ | ✅ |
| IssueCard | ✅ | N/A | ✅ | N/A |
| ProofList | ✅ | "No proof" | ✅ | N/A |
| HypothesesList | ✅ | "No hypotheses" | ✅ | N/A |
| RoomDrawer | ✅ | "Not found" | ✅ | N/A |
| FixDataCard | ✅ | N/A | ✅ | N/A |

---

## Touch Targets

All interactive elements: minimum 44×44px touch target (per design system).

## Responsive Behavior

| Component | Mobile | Tablet | Desktop |
|-----------|--------|--------|---------|
| ProposalCard | Full width | 2-up grid | 3-up grid |
| RoomDrawer | Full screen sheet | Right panel 50% | Right panel 400px |
| RightRail | Bottom sheet tabs | Side panel | Side panel |
| FiltersScopeBar | Collapsed + sheet | Inline | Inline |

LOCKED_SPEC
