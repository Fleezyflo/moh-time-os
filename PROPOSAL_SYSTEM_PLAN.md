# Time OS Proposal System Redesign - Implementation Plan

**Created:** 2026-02-06
**Status:** BACKEND COMPLETE (Phases 1-6, 11-12) | FRONTEND PENDING (Phases 8-10)
**Log File:** `PROPOSAL_SYSTEM_LOG.md`

---

## Overview

Redesign the proposal system to aggregate signals at the Project/Retainer level instead of individual tasks, with proper hierarchy (Client → Brand → Project/Retainer → Task → Signal) and improved scoring.

---

## Phase 1: Schema Migration

### 1.1 Add columns to proposals_v4 table
- [ ] scope_level TEXT DEFAULT 'project'
- [ ] scope_name TEXT
- [ ] client_id TEXT
- [ ] client_name TEXT
- [ ] client_tier TEXT
- [ ] brand_id TEXT
- [ ] brand_name TEXT
- [ ] engagement_type TEXT ('project' or 'retainer')
- [ ] signal_summary TEXT (JSON)
- [ ] score_breakdown TEXT (JSON)
- [ ] affected_task_ids TEXT (JSON array)

### 1.2 Add columns to signals table
- [ ] resolved_at TEXT
- [ ] resolution TEXT

### 1.3 Create indexes
- [ ] idx_proposals_hierarchy ON proposals_v4(client_id, brand_id, scope_level)
- [ ] idx_signals_resolved ON signals(status, resolved_at)

### 1.4 Verify schema
- [ ] Run PRAGMA table_info on both tables
- [ ] Confirm all columns exist

---

## Phase 2: Scoring Function

### 2.1 Create new scoring module
- [ ] Create `lib/v4/proposal_scoring.py`
- [ ] Implement `compute_urgency_score(signal)` - returns 0-60
- [ ] Implement `compute_breadth_score(signals)` - returns 0-40
- [ ] Implement `compute_diversity_score(signals)` - returns 0-30
- [ ] Implement `compute_impact_multiplier(hierarchy)` - returns 0.8-2.0
- [ ] Implement `compute_proposal_score(signals, hierarchy)` - main function

### 2.2 Urgency scoring by signal type
- [ ] deadline_overdue: min(60, 15 + days_overdue * 1.5)
- [ ] ar_aging_risk: min(60, 10 + days * 0.5 + amount / 2000)
- [ ] deadline_approaching: max(0, 30 - days_until * 5)
- [ ] client_health_declining: 35
- [ ] communication_gap: min(40, 10 + days_silent * 2)
- [ ] default: 10

### 2.3 Impact multiplier factors
- [ ] Client tier: A=1.5, B=1.2, C=1.0, None=0.8
- [ ] Engagement type: retainer=1.1, project=1.0
- [ ] Project value: >50k=1.3, >20k=1.1, else=1.0

### 2.4 Test scoring
- [ ] Test with sample data
- [ ] Verify score differentiation

---

## Phase 3: Signal Aggregation

### 3.1 Create aggregation module
- [ ] Create `lib/v4/proposal_aggregator.py`
- [ ] Implement `get_signal_hierarchy(signal)` - returns task→project→brand→client chain
- [ ] Implement `group_signals_by_scope()` - groups signals into proposal buckets
- [ ] Implement `determine_proposal_level(client_id)` - decides client/brand/project level
- [ ] Implement `build_signal_summary(signals)` - creates summary JSON

### 3.2 Aggregation rules
- [ ] If client has >2 brands with issues → client-level proposal
- [ ] If brand has >3 projects with issues → brand-level proposal
- [ ] Otherwise → project/retainer-level proposals
- [ ] Never create single-task proposals

### 3.3 Handle edge cases
- [ ] Tasks with no project → client-level proposal
- [ ] Client-level signals (AR, health) → client-level proposal
- [ ] Retainer vs Project distinction

---

## Phase 4: Proposal Generation

### 4.1 Rewrite ProposalService.generate_proposals_from_signals()
- [ ] Fetch all active signals with hierarchy data
- [ ] Group by scope using aggregator
- [ ] Compute scores using new scoring
- [ ] Build proposal records with all new fields
- [ ] Insert/update proposals

### 4.2 Proposal record structure
- [ ] proposal_id (hash of scope_level + scope_id)
- [ ] scope_level, scope_id, scope_name
- [ ] Full hierarchy (client, brand, engagement_type)
- [ ] score + score_breakdown
- [ ] signal_summary (counts by type)
- [ ] signal_ids (JSON array)
- [ ] affected_task_ids (JSON array)
- [ ] top 5 signal details embedded

### 4.3 Deduplication
- [ ] Check existing by (scope_level, primary_ref_id)
- [ ] Update if exists, insert if new
- [ ] Never create duplicates

---

## Phase 5: Signal Lifecycle

### 5.1 Implement signal resolution
- [ ] Create `resolve_signal(signal_id, resolution_type)`
- [ ] Set status='resolved', resolved_at=now, resolution=type

### 5.2 Implement task completion handler
- [ ] Create `handle_task_completed(task_id)`
- [ ] Find all signals for task
- [ ] Resolve each signal with 'task_completed'
- [ ] Recalculate parent proposal score
- [ ] Archive proposal if all signals resolved

### 5.3 Hook into task update endpoint
- [ ] When task status → 'completed', call handler

---

## Phase 6: Proposals API

### 6.1 Update GET /api/control-room/proposals
- [ ] Return new structure with hierarchy
- [ ] Include signal_summary
- [ ] Include worst_signal text
- [ ] Include remaining_count
- [ ] Sort by score DESC

### 6.2 Create GET /api/control-room/proposals/{id}
- [ ] Return full proposal detail
- [ ] Include score_breakdown
- [ ] Include top 5 signals with full detail
- [ ] Include issues_url for "see more"

### 6.3 Update proposal actions
- [ ] Snooze should work with new structure
- [ ] Resolve should handle all child signals
- [ ] Tag & Monitor should create issue group

---

## Phase 7: Issues API

### 7.1 Update GET /api/issues
- [ ] Add hierarchy parameter support
- [ ] Return nested structure: client → brand → project → task
- [ ] Include client-level issues at top
- [ ] Support filtering by any level

### 7.2 Issue hierarchy response
- [ ] Client node with client-level signals
- [ ] Brand nodes (collapsible)
- [ ] Project/Retainer nodes with type indicator
- [ ] Task nodes with issue details

---

## Phase 8: Frontend - Proposal Card

### 8.1 Update ProposalCard component
- [ ] Show scope_name as title
- [ ] Show client_name + brand_name as subtitle
- [ ] Show score prominently
- [ ] Show signal_summary as icon badges (⚠️ 8 overdue, ⏰ 2 approaching)
- [ ] Show worst_signal text
- [ ] Show "and X more..." link

### 8.2 Card styling
- [ ] Different colors for project vs retainer
- [ ] Tier badge (A/B/C)
- [ ] Score color coding (red >100, orange >50, yellow >25)

---

## Phase 9: Frontend - Proposal Detail Drawer

### 9.1 Update RoomDrawer component
- [ ] Header with full hierarchy breadcrumb
- [ ] Score breakdown visualization
- [ ] Top 5 signals list with task details
- [ ] "View all X issues" button → navigates to Issues page

### 9.2 Signal list item
- [ ] Signal type icon
- [ ] Task title
- [ ] Assignee
- [ ] Age (days overdue/until)
- [ ] Severity indicator

---

## Phase 10: Frontend - Issues Page Hierarchy

### 10.1 Create hierarchical tree component
- [ ] Collapsible client level
- [ ] Collapsible brand level
- [ ] Collapsible project/retainer level
- [ ] Task list with issue details

### 10.2 Client node
- [ ] Client name + tier badge
- [ ] Total issue count
- [ ] Client-level signals (AR, health)

### 10.3 Brand node
- [ ] Brand name
- [ ] Issue count for brand
- [ ] Expandable to projects

### 10.4 Project/Retainer node
- [ ] Name + type indicator (📁 Project / 🔄 Retainer)
- [ ] Issue count
- [ ] Task list when expanded

### 10.5 Task node
- [ ] Title, assignee, status
- [ ] Days overdue/until
- [ ] Signal type badges
- [ ] Click to see task detail

---

## Phase 11: Data Migration

### 11.1 Clean existing data
- [ ] DELETE FROM proposals_v4
- [ ] DELETE FROM issues
- [ ] UPDATE signals SET status='active' WHERE status='resolved' (reset for regeneration)

### 11.2 Regenerate proposals
- [ ] Run new generate_proposals_from_signals()
- [ ] Verify proposal count and score distribution

### 11.3 Verify results
- [ ] Check no duplicate proposals
- [ ] Check hierarchy is populated
- [ ] Check scores are differentiated
- [ ] Check signal summaries are accurate

---

## Phase 12: Testing & Verification

### 12.1 Backend verification
- [ ] Single-task signals don't create standalone proposals
- [ ] Client-level signals appear in client proposals
- [ ] Retainers and Projects distinguished
- [ ] Scores calculate correctly
- [ ] A-tier scores higher than C-tier

### 12.2 Frontend verification
- [ ] Cards show correct hierarchy
- [ ] Detail drawer shows top 5 signals
- [ ] "View more" navigates correctly
- [ ] Issues page shows full hierarchy
- [ ] Collapsing/expanding works

### 12.3 End-to-end verification
- [ ] Complete a task → signals resolve
- [ ] Proposal score recalculates
- [ ] Resolved signals don't appear in counts

---

## Files to Create/Modify

### New Files
- `lib/v4/proposal_scoring.py`
- `lib/v4/proposal_aggregator.py`

### Modified Files
- `lib/v4/proposal_service.py`
- `lib/v4/signal_service.py`
- `lib/state_store.py` (migrations)
- `api/server.py` (endpoints)
- `time-os-ui/src/components/ProposalCard.tsx`
- `time-os-ui/src/components/RoomDrawer.tsx`
- `time-os-ui/src/pages/Issues.tsx`

---

## Success Criteria

1. No duplicate proposals in system
2. Proposals aggregate at project/retainer level minimum
3. Scores range from ~20 to ~150 with clear differentiation
4. UI shows hierarchy context on every card
5. Clicking "more" shows full issue tree
6. Completed tasks archive their signals
7. Client tier affects scoring visibly
