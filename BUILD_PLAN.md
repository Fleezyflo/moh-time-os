# MOH Time OS — Unified Build Plan

**Date:** 2026-02-25
**Status:** Draft for review
**Scope:** Full product buildout — Phases 0-13. Foundation + redesign (0-5), capability buildout (6-13).
**Session governance:** `BUILD_STRATEGY.md` (sequencing, drift prevention, session contracts) + `SESSION_LOG.md` (living record)

---

## Resolved Decisions

| # | Decision | Resolution |
|---|----------|------------|
| D1 | Accent color | **Blue `#3b82f6`.** Standard accessible accent on dark backgrounds. Passes WCAG AA on slate-900 and slate-800. Doesn't compete with red/amber severity indicators in the signal system. |
| D2 | Tertiary text contrast | **`slate-400` at 5.1:1.** Passes WCAG AA. `slate-500` at 3.7:1 fails — not a real choice. Use slate-500 only for decorative/non-essential text. |

---

## Architecture: What the Product Becomes

### Current State

Two disconnected halves sharing a nav bar:

```
Control Room (spec_router)          Intelligence (spec_router /intelligence/*)
─────────────────────────           ────────────────────────────────────────
Inbox, Issues, Clients,             Command Center, Briefing,
Team, Fix Data, Proposals,          Signals, Patterns,
Watchers, Couplings                 Client/Person/Project Intel

Uses /api/v2/* endpoints            Uses /api/v2/intelligence/* endpoints
CSS tokens (--black, --grey-dim)    Hardcoded Tailwind slate classes
lib/api.ts + lib/hooks.ts           intelligence/api.ts + intelligence/hooks.ts
```

Two color systems. Two API clients. Two hook libraries. Every page reinvents its own layout. The user switches between two apps.

### Target State

One product. Seventeen sections. Unified design system. Full operational surface.

```
┌─────────────────────────────────────────────────────────────┐
│  NAV: Inbox │ Portfolio │ Clients │ Tasks │ Priorities │ ··· │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Every page uses:                                           │
│  - PageLayout (consistent header, spacing, max-width)       │
│  - SummaryGrid + MetricCard (top-level metrics)             │
│  - Shared Card/Badge/DataGrid components                    │
│  - CSS custom properties from tokens.css (single palette)   │
│  - Consistent loading/error/empty states                    │
│  - Two API clients remain (control room + intelligence)     │
│    but unified through consistent hook patterns             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## §1 — Information Architecture

### 1.1 Page Map

Seventeen sections, ~26 pages. Sections 1-7 are the foundation redesign (Phases 0-5). Sections 8-17 are the capability buildout (Phases 6-13). Each page lists what it shows, which endpoints feed it, and what hooks exist or need creation.

#### Section 1: Inbox (Home)

**Route:** `/`

**Purpose:** Triage queue. Every actionable item in the system flows here.

**What it shows:**
- Inbox items grouped by category (risk, opportunity, anomaly, maintenance)
- Category counts and unread counts
- Item cards with severity, headline, scope, age
- Quick actions: create issue, snooze, dismiss, mark read
- Filter by category, severity, client, date range

**Endpoints:**
- `GET /api/v2/inbox` — full inbox (new: use category/read filters)
- `GET /api/v2/inbox/counts` — category counts *(currently unsurfaced)*
- `GET /api/v2/inbox/recent` — recent items *(currently unsurfaced)*
- `POST /api/v2/inbox/{id}/action` — take action
- `POST /api/v2/inbox/{id}/read` — mark read

**Hooks needed:** `useInbox()`, `useInboxCounts()` — new, added to `lib/hooks.ts`. Corresponding `fetchInbox()`, `fetchInboxCounts()` added to `lib/api.ts`.

**New backend work:** None. Endpoints exist in spec_router (lines 771-930).

---

#### Section 2: Portfolio

**Route:** `/portfolio`

**Purpose:** Bird's-eye view of the entire business. Replaces Snapshot + Command Center + Briefing.

**What it shows:**
- Portfolio health score (composite) with dimension breakdown
- Revenue summary: total AR, overdue AR, collection rate
- Client distribution by tier and status
- Top 5 risks (from critical alerts)
- Structural patterns affecting the portfolio
- Score trajectory over time (sparkline)

**Endpoints (7 parallel fetches — 4 existing hooks + 3 new):**
- `GET /api/v2/intelligence/scores/portfolio` — portfolio scorecard → `usePortfolioScore()` (exists)
- `GET /api/v2/intelligence/entity/portfolio` — portfolio deep dive → `usePortfolioIntelligence()` (exists)
- `GET /api/v2/intelligence/critical` — critical items → `useCriticalItems()` (exists)
- `GET /api/v2/clients` — client index (for distribution counts) → `useClients()` (exists)
- `GET /api/v2/intelligence/portfolio/overview` — client metrics, project/task counts *(unsurfaced)* → new hook
- `GET /api/v2/intelligence/portfolio/risks` — structural risks with severity + evidence *(unsurfaced)* → new hook
- `GET /api/v2/intelligence/financial/aging` — AR aging bucketed 30/60/90+ *(unsurfaced)* → new hook

**Also available (wire if Portfolio needs depth):**
- `GET /api/v2/intelligence/portfolio/trajectory` — all-client trajectory over rolling windows *(unsurfaced)*
- `GET /api/v2/intelligence/projects/health` — all projects ranked by health score *(unsurfaced)*
- `GET /api/v2/intelligence/changes` — delta report since last snapshot *(unsurfaced)* — powers "What Changed" widget

**Response shape verification (confirmed from `lib/intelligence/engine.py` line 697):**
`get_portfolio_intelligence()` returns:
```
{
  generated_at: string,
  success: boolean,
  errors: StageError[],
  portfolio_score: { composite_score, dimensions: {...}, computed_at },
  signal_summary: { total_active, by_severity: {critical, warning, watch}, ... },
  structural_patterns: Pattern[],
  top_proposals: [{ headline, urgency, score }]
}
```
This composes cleanly. The Portfolio page renders `portfolio_score` in SummaryGrid, `signal_summary` in a status strip, `structural_patterns` as a list, and `top_proposals` as cards. The new `/portfolio/overview` adds client counts and operational metrics. `/portfolio/risks` adds typed risks (OVERDUE_PROJECT, OVERLOADED_PERSON, AGING_INVOICE) with severity and evidence — richer than filtering critical items. `/financial/aging` adds AR aging buckets for the revenue summary.

**New backend work:** None. All endpoints exist in intelligence_router and are reachable (auth always passes in single-user mode — verified `api/auth.py` line 29).

---

#### Section 3: Clients

**Route:** `/clients`, `/clients/:clientId`

**Purpose:** Client management. Index → detail drill-down.

##### 3a. Client Index (`/clients`)

**What it shows:**
- Client list with health score, status, tier, active engagements, overdue AR
- Sort by health score, name, overdue amount
- Filter by status (active, recently_active, cold), tier, has_issues, has_overdue_ar
- Cold clients shown inline via filter, not as separate page

**Endpoints:**
- `GET /api/v2/clients` — client index with filters → `useClients()` (exists)

##### 3b. Client Detail (`/clients/:clientId`)

**What it shows:**
- Client header: name, tier, status, health score, trajectory sparkline
- Tabbed sections:
  - **Overview**: engagement summary, key signals, recent activity (existing)
  - **Financials**: invoices, AR aging, payment history *(currently unsurfaced)*
  - **Signals**: client-specific signals with history
  - **Team**: team members involved with this client *(currently unsurfaced)*
  - **Engagements**: active/completed engagements with lifecycle state *(currently unsurfaced)*

**Endpoints:**
- `GET /api/v2/clients/{id}` — client detail (supports `?include=`) → exists, needs hook
- `GET /api/v2/clients/{id}/invoices` — invoice list *(unsurfaced)* → new hook
- `GET /api/v2/clients/{id}/ar-aging` — AR aging *(unsurfaced)* → new hook
- `GET /api/v2/clients/{id}/signals` — client signals *(unsurfaced)* → new hook
- `GET /api/v2/clients/{id}/team` — client team involvement *(unsurfaced)* → new hook
- `GET /api/v2/intelligence/scores/client/{id}` → `useClientScore()` (exists)
- `GET /api/v2/intelligence/clients/{id}/trajectory` → `useClientTrajectory()` (exists)
- `GET /api/v2/intelligence/clients/{id}/profile` → `useClientProfile()` (exists)
- `GET /api/v2/intelligence/entity/client/{id}` → `useClientIntelligence()` (exists)
- `GET /api/v2/intelligence/clients/{id}/tasks` — task breakdown by status/assignee *(unsurfaced)* → new hook
- `GET /api/v2/intelligence/clients/{id}/communication` — message counts by type *(unsurfaced)* → new hook
- `GET /api/v2/intelligence/scores/client/{id}/history` — score trend data *(unsurfaced)* → new hook (powers sparklines)
- `GET /api/v2/engagements/{id}` → new hook
- `POST /api/v2/engagements/{id}/transition` → new mutation

**Also available (wire for comparison features):**
- `GET /api/v2/intelligence/clients/{id}/compare` — period-over-period metrics comparison *(unsurfaced)*
- `GET /api/v2/intelligence/clients/compare` — all-client comparison *(unsurfaced)*

**New backend work:** None. Every endpoint exists. 8 new hooks needed in `lib/hooks.ts` (was 5 — added tasks, communication, score history).

---

#### Section 4: Team

**Route:** `/team`, `/team/:personId`

**Purpose:** Team workload visibility and individual performance.

##### 4a. Team Index (`/team`)

**What it shows:**
- Team grid with health scores, active task count, client assignments
- Load distribution visualization (who's overloaded, who has capacity)
- Sort by score, name, workload

**Endpoints:**
- `GET /api/v2/team` → `useTeam()` (exists)
- `GET /api/v2/intelligence/team/distribution` — load_score (0-100) per person *(unsurfaced)* → new hook
- `GET /api/v2/intelligence/team/capacity` — total people, active tasks, avg per person, overloaded/available counts *(unsurfaced)* → new hook

##### 4b. Team Detail (`/team/:personId`)

**What it shows:**
- Person header: name, role, health score, trajectory sparkline
- Active assignments and workload
- Client involvement breakdown
- Recent signals related to this person
- Score trend (improving/declining/stable)

**Endpoints:**
- `GET /api/v2/intelligence/scores/person/{id}` → `usePersonScore()` (exists)
- `GET /api/v2/intelligence/team/{id}/profile` → `usePersonProfile()` (exists)
- `GET /api/v2/intelligence/team/{id}/trajectory` → `usePersonTrajectory()` (exists)
- `GET /api/v2/intelligence/entity/person/{id}` → `usePersonIntelligence()` (exists)
- `GET /api/v2/intelligence/scores/person/{id}/history` — score trend data *(unsurfaced)* → new hook

**New backend work:** None. All endpoints exist. 3 new hooks needed (distribution, capacity, score history).

---

#### Section 5: Issues

**Route:** `/issues`

**Purpose:** Tracked problems requiring resolution.

**What it shows:**
- Issue list with severity, state, age, client, assignee
- State/severity filters
- Issue detail drawer with notes, evidence, state transitions

**Endpoints:**
- `GET /api/v2/issues` → `useIssues()` (exists)
- `PATCH /api/v2/issues/{id}/state` → `changeIssueState()` (exists)
- `PATCH /api/v2/issues/{id}/resolve` → `resolveIssue()` (exists)
- `POST /api/v2/issues/{id}/notes` → `addIssueNote()` (exists)
- `GET /api/v2/evidence/{entityType}/{entityId}` → `useEvidence()` (exists)

**New backend work:** None. Fully implemented.

---

#### Section 6: Intelligence

**Route:** `/intel/signals`, `/intel/patterns`

**Purpose:** Deep analytical views for system-detected intelligence.

##### 6a. Signals (`/intel/signals`)

**Endpoints:** `/signals`, `/signals/summary`, `/signals/active`, `/signals/history` — all hooks exist.

##### 6b. Patterns (`/intel/patterns`)

**Endpoints:** `/patterns`, `/patterns/catalog` — all hooks exist.

**New backend work:** None.

---

#### Section 7: Operations

**Route:** `/ops`

**Purpose:** System health, data quality, and housekeeping. Consolidates Fix Data + Watchers + Couplings.

**Three tabs:**
- Data Quality → `useFixData()` (exists)
- Watchers → `useWatchers()` (exists)
- Couplings → `useAllCouplings()` (exists)
- Health → `checkHealth()` (exists)

**New backend work:** None. All hooks exist.

---

#### Section 8: Tasks

**Route:** `/tasks`, `/tasks/:taskId`

**Purpose:** Full task management — the operational core missing from the current UI. Create, edit, delegate, escalate, recall, block, and track dependencies.

##### 8a. Task List (`/tasks`)

**What it shows:**
- Task list with status, priority, due date, assignee, project, client
- Filter by status (pending, in_progress, blocked, completed), assignee, project, priority range, due date range
- Group by project, assignee, or source
- Delegation split view: tasks delegated by me vs to me
- Dependency graph view (blocked/blocking relationships)
- Bulk actions: archive, complete, assign, change priority

**Endpoints:**
- `GET /api/tasks` — filtered task list → `useTasks()` (fix response shape bug: returns `{tasks:[...]}` not `{items:[...]}`)
- `GET /api/priorities/advanced` — advanced filtered/sorted priorities → `usePrioritiesAdvanced()`
- `GET /api/priorities/grouped` — grouped priorities → `usePrioritiesGrouped()`
- `GET /api/delegations` — delegated tasks split by direction → `useDelegations()`
- `GET /api/dependencies` — dependency graph → `useDependencies()`
- `POST /api/tasks` — create task → mutation
- `POST /api/priorities/bulk` — bulk actions → mutation
- `DELETE /api/tasks/{id}` — archive task → mutation

**Hooks needed:** `usePrioritiesAdvanced()`, `usePrioritiesGrouped()`, `useDelegations()`, `useDependencies()` — new, added to `lib/hooks.ts`.

##### 8b. Task Detail (`/tasks/:taskId`)

**What it shows:**
- Task header: title, status, priority, due date, assignee, project
- Editable fields: title, status, priority, due date, assignee, project
- Notes timeline
- Blockers list (add/remove)
- Action buttons: delegate, escalate, recall
- Governance approval dialog (when `requires_approval: true`)
- Bundle history (changes with rollback option)

**Endpoints:**
- `GET /api/tasks/{id}` — task detail → `useTaskDetail()`
- `PUT /api/tasks/{id}` — update task → mutation
- `POST /api/tasks/{id}/notes` — add note → mutation
- `POST /api/tasks/{id}/delegate` — delegate with workload awareness → mutation
- `POST /api/tasks/{id}/escalate` — escalate with priority boost → mutation
- `POST /api/tasks/{id}/recall` — recall delegation → mutation
- `POST /api/tasks/{id}/block` — add blocker → mutation
- `DELETE /api/tasks/{id}/block/{blockerId}` — remove blocker → mutation
- `GET /api/bundles/{id}` — bundle detail for change history → `useBundleDetail()`

**Hooks needed:** `useTaskDetail()`, `useBundleDetail()` — new, added to `lib/hooks.ts`.

**New backend work:** None. All endpoints exist in server.py. Fix the `useTasks()` response shape bug (`.tasks` → `.items` key).

---

#### Section 9: Priorities

**Route:** `/priorities`

**Purpose:** Rich priority management workspace — advanced filtering, grouping, bulk actions, saved filters. Replaces the thin task list with a scored, actionable view.

**What it shows:**
- Priority items scored and ranked with reason explanations
- Advanced filters: by due (today/week/overdue/range), assignee, project, status, score range, tags
- Sorting: by score, due, title, assignee (asc/desc)
- Group view: by project, assignee, or source with group totals
- Bulk action bar: archive, complete, assign, snooze, change priority, move to project
- Saved filter selector
- Quick actions per item: complete, snooze, delegate

**Endpoints:**
- `GET /api/priorities/filtered` — filtered priorities with reasons → `usePrioritiesFiltered()`
- `GET /api/priorities/advanced` — advanced filtered/sorted → `usePrioritiesAdvanced()` (shared with Task List)
- `GET /api/priorities/grouped` — grouped view → `usePrioritiesGrouped()` (shared with Task List)
- `POST /api/priorities/bulk` — bulk actions → mutation
- `POST /api/priorities/archive-stale` — archive stale items → mutation
- `GET /api/filters` — saved filters → `useSavedFilters()`
- `POST /api/priorities/{id}/complete` — complete item → mutation
- `POST /api/priorities/{id}/snooze` — snooze item → mutation
- `POST /api/priorities/{id}/delegate` — delegate item → mutation

**Hooks needed:** `usePrioritiesFiltered()`, `useSavedFilters()` — new, added to `lib/hooks.ts`. `usePrioritiesAdvanced()`, `usePrioritiesGrouped()` shared with Section 8.

**New backend work:** None. All endpoints exist in server.py.

---

#### Section 10: Schedule

**Route:** `/schedule`

**Purpose:** Time block scheduling and day/week calendar views.

**What it shows:**
- Day view: time blocks organized by lane, showing scheduled tasks, protected time, buffer blocks
- Week view: 7-day overview with block summaries per day
- Day summary: calendar sync info, available hours, deep work hours
- Schedule action: drag task onto time block or select from dialog
- Unschedule action: remove task from block

**Endpoints:**
- `GET /api/time/blocks` — time blocks for date with lane filter → `useTimeBlocks()`
- `GET /api/time/summary` — day summary (calendar + scheduling) → `useTimeSummary()`
- `POST /api/time/schedule` — schedule task into block → mutation
- `POST /api/time/unschedule` — remove task from block → mutation
- `GET /api/events` — calendar events for next N hours → `useEvents()`
- `GET /api/day/{date}` — full day view → `useDayView()`
- `GET /api/week` — week view → `useWeekView()`

**Hooks needed:** `useTimeBlocks()`, `useTimeSummary()`, `useEvents()`, `useDayView()`, `useWeekView()` — new, added to `lib/hooks.ts`.

**New backend work:** None. All endpoints exist in server.py.

---

#### Section 11: Capacity

**Route:** `/capacity`

**Purpose:** Capacity utilization and forecasting by lane.

**What it shows:**
- Capacity lanes with current utilization gauges
- Utilization detail per lane: scheduled vs available hours
- Forecast chart: capacity projection for next N days
- Capacity debt report (read-only — write endpoints are stubs)

**Endpoints:**
- `GET /api/capacity/lanes` — lane configuration → `useCapacityLanes()`
- `GET /api/capacity/utilization` — utilization by lane → `useCapacityUtilization()`
- `GET /api/capacity/forecast` — N-day forecast → `useCapacityForecast()`
- `GET /api/capacity/debt` — debt report → `useCapacityDebt()`

**Hooks needed:** `useCapacityLanes()`, `useCapacityUtilization()`, `useCapacityForecast()`, `useCapacityDebt()` — new, added to `lib/hooks.ts`.

**New backend work:** None. Read endpoints exist. Debt write endpoints (accrue, resolve) are 501 stubs — not wired.

---

#### Section 12: Commitments

**Route:** `/commitments`

**Purpose:** Track commitments extracted from communications. Link to tasks, monitor due dates, surface untracked commitments.

**What it shows:**
- Commitment list with status, owner, target, target date, confidence score
- Summary cards: total commitments, untracked count, due soon count
- Untracked commitments alert (commitments not linked to tasks)
- Due commitments view filtered by date
- Link-to-task dialog: connect commitment to existing task
- Mark-done action

**Endpoints:**
- `GET /api/commitments` — all commitments filtered by status → `useCommitments()`
- `GET /api/commitments/untracked` — unlinked commitments → `useUntrackedCommitments()`
- `GET /api/commitments/due` — due by date → `useCommitmentsDue()`
- `GET /api/commitments/summary` — summary stats → `useCommitmentsSummary()`
- `POST /api/commitments/{id}/link` — link to task → mutation
- `POST /api/commitments/{id}/done` — mark done → mutation

**Hooks needed:** `useCommitments()`, `useUntrackedCommitments()`, `useCommitmentsDue()`, `useCommitmentsSummary()` — new, added to `lib/hooks.ts`.

**New backend work:** None. All endpoints exist in server.py.

---

#### Section 13: Notifications

**Route:** `/notifications`

**Purpose:** Notification center with filtering, stats, and dismissal.

**What it shows:**
- Notification list with type icon, title, body, timestamp
- Filter by type and recency
- Stats bar: total count, unread count
- Dismiss single or dismiss all
- Notification badge in nav bar (unread count)

**Endpoints:**
- `GET /api/notifications` — notification list → `useNotifications()`
- `GET /api/notifications/stats` — counts → `useNotificationStats()`
- `POST /api/notifications/{id}/dismiss` — dismiss single → mutation
- `POST /api/notifications/dismiss-all` — dismiss all → mutation

**Hooks needed:** `useNotifications()`, `useNotificationStats()` — new, added to `lib/hooks.ts`.

**New backend work:** None. All endpoints exist in server.py.

---

#### Section 14: Digest & Email

**Route:** `/digest`

**Purpose:** Weekly digest summary and email triage queue.

**Two tabs:**

- **Weekly Digest**: period summary showing completed tasks, slipped tasks, archived count
- **Email Triage**: unprocessed emails with mark-actionable and dismiss actions

**Endpoints:**
- `GET /api/digest/weekly` — weekly summary → `useWeeklyDigest()`
- `GET /api/emails` — email queue → `useEmails()`
- `POST /api/emails/{id}/mark-actionable` — mark actionable → mutation
- `POST /api/emails/{id}/dismiss` — dismiss email → mutation

**Hooks needed:** `useWeeklyDigest()`, `useEmails()` — new, added to `lib/hooks.ts`.

**New backend work:** None. All endpoints exist in server.py.

---

#### Section 15: Governance & Admin

**Route:** `/admin/governance`, `/admin/approvals`, `/admin/data-quality`

**Purpose:** System administration — governance controls, approval processing, data quality management.

##### 15a. Governance (`/admin/governance`)

**What it shows:**
- Domain cards showing current mode (observe, advise, guard, enforce) and confidence threshold per domain
- Emergency brake toggle with reason field
- Governance action history timeline
- Calibration button (run/view last)
- Bundle audit trail (recent bundles with rollback option)

**Endpoints:**
- `GET /api/governance` — config, domains, brake status → `useGovernance()`
- `PUT /api/governance/{domain}` — set domain mode → mutation
- `PUT /api/governance/{domain}/threshold` — set threshold → mutation
- `GET /api/governance/history` — action history → `useGovernanceHistory()`
- `POST /api/governance/emergency-brake` — activate brake → mutation
- `DELETE /api/governance/emergency-brake` — release brake → mutation
- `GET /api/calibration` — last calibration → `useCalibration()`
- `POST /api/calibration/run` — run calibration → mutation
- `GET /api/bundles` — bundle list → `useBundles()`
- `GET /api/bundles/rollbackable` — rollback candidates → `useRollbackable()`
- `GET /api/bundles/summary` — bundle summary → `useBundleSummary()`
- `POST /api/bundles/{id}/rollback` — rollback bundle → mutation
- `POST /api/bundles/rollback-last` — rollback last → mutation

##### 15b. Approvals (`/admin/approvals`)

**What it shows:**
- Pending approval queue with decision type, description, proposed changes
- Approve/reject/modify-then-approve actions
- Side-effect preview (what happens when approved)

**Endpoints:**
- `GET /api/approvals` — pending approvals → `useApprovals()`
- `POST /api/approvals/{id}` — process approval → mutation
- `POST /api/approvals/{id}/modify` — modify and approve → mutation
- `POST /api/decisions/{id}` — process decision with side effects → mutation

##### 15c. Data Quality (`/admin/data-quality`)

**What it shows:**
- Health score with issue breakdown (stale, ancient, inactive tasks)
- Metrics: priority distribution, due distribution, inflation ratio, stale ratio
- Suggestions with severity and recommended actions
- Cleanup actions with preview-then-confirm flow (ancient, stale, legacy signals)
- Priority recalculation button
- Fix-data section: identity conflicts, ambiguous links (from control room fix-data endpoints already wired)

**Endpoints:**
- `GET /api/data-quality` — health score, issues, metrics, suggestions → `useDataQuality()`
- `POST /api/data-quality/cleanup/ancient` — archive ancient tasks → mutation (confirm flow)
- `POST /api/data-quality/cleanup/stale` — archive stale tasks → mutation (confirm flow)
- `POST /api/data-quality/cleanup/legacy-signals` — expire legacy signals → mutation (confirm flow)
- `POST /api/data-quality/recalculate-priorities` — recalculate all priorities → mutation
- `GET /api/data-quality/preview/{type}` — preview cleanup → `useCleanupPreview()`

**Hooks needed (all sections):** `useGovernance()`, `useGovernanceHistory()`, `useCalibration()`, `useBundles()`, `useRollbackable()`, `useBundleSummary()`, `useApprovals()`, `useDataQuality()`, `useCleanupPreview()` — new, added to `lib/hooks.ts`.

**New backend work:** None. All endpoints exist in server.py and governance_router.

---

#### Section 16: Project Enrollment

**Route:** `/projects/enrollment`

**Purpose:** Detect new projects, review candidates, process enrollment decisions.

**What it shows:**
- Detected projects alert (auto-detected from task patterns)
- Candidate list: unenrolled projects with client association
- Enrollment action bar per candidate: enroll, reject, snooze (with days), mark internal
- Enrolled projects: split by retainer vs project type
- New project proposal form

**Endpoints:**
- `GET /api/projects/candidates` — unenrolled projects → `useProjectCandidates()`
- `GET /api/projects/enrolled` — enrolled split by type → `useProjectsEnrolled()`
- `GET /api/projects/detect` — auto-detected projects → `useDetectedProjects()`
- `POST /api/projects/{id}/enrollment` — enrollment action → mutation
- `POST /api/projects/propose` — new proposal → mutation
- `GET /api/projects` — project list (enhances existing) → `useProjects()` (exists)
- `GET /api/projects/{id}` — project detail → `useProjectDetail()`

**Hooks needed:** `useProjectCandidates()`, `useProjectsEnrolled()`, `useDetectedProjects()`, `useProjectDetail()` — new, added to `lib/hooks.ts`.

**New backend work:** None. All endpoints exist in server.py.

---

#### Section 17: Collector Data Depth (tabs on existing pages)

**Purpose:** Surface the 20 write-only collector tables as new tabs/sections on existing detail pages. Requires new backend work — query_engine methods and API endpoints.

| Existing page | New tab/section | Tables surfaced | New endpoint |
|--------------|----------------|-----------------|-------------|
| Client Detail | Email Participants | gmail_participants, gmail_labels | `GET /api/v2/clients/{id}/email-participants` |
| Client Detail | Attachments | gmail_attachments | `GET /api/v2/clients/{id}/attachments` |
| Client Detail | Xero Detail | xero_line_items, xero_credit_notes | `GET /api/v2/clients/{id}/invoice-detail` |
| Team Detail | Calendar Detail | calendar_attendees, calendar_recurrence_rules | `GET /api/v2/team/{id}/calendar-detail` |
| Task Detail | Asana Context | asana_custom_fields, asana_subtasks, asana_sections, asana_stories, asana_task_dependencies, asana_attachments | `GET /api/v2/tasks/{id}/asana-detail` |
| Operations | Chat Analytics | chat_messages (core — 183K rows, surfaced via `/api/v2/communications`), chat_reactions, chat_attachments, chat_space_metadata, chat_space_members | `GET /api/v2/chat/analytics` |
| Portfolio | Financial Detail | xero_contacts, xero_bank_transactions, xero_tax_rates | `GET /api/v2/financial/detail` |
| Operations | Asana Portfolio & Goals | asana_portfolios, asana_goals | `GET /api/v2/projects/asana-context` |

**New backend work required:**
- ~8 new spec_router endpoints (listed above)
- ~8 new query_engine methods to read from collector tables
- Data quality check per table before wiring (some tables may have stale/empty data)

**Hooks needed:** `useClientEmailParticipants()`, `useClientAttachments()`, `useClientInvoiceDetail()`, `useTeamCalendarDetail()`, `useTaskAsanaDetail()`, `useChatAnalytics()`, `useFinancialDetail()`, `useAsanaContext()` — new, added to `lib/hooks.ts`.

**Database views:** The live DB has 9 views. 3 are production (issues_v29, signals_v29, inbox_items) — already surfaced via lifecycle managers and spec_router endpoints that read them. 6 are test fixtures (v_task_with_client, v_client_operational_profile, v_project_operational_state, v_person_load_profile, v_communication_client_link, v_invoice_client_project) — created in fixture_db.py for golden tests only, not production. No build work needed for views.

---

### 1.2 Pages Removed or Merged

| Current Page | Disposition |
|-------------|------------|
| Command Center (`/intel`) | Merged into Portfolio. |
| Briefing (`/intel/briefing`) | Merged into Portfolio. |
| Proposals (`/intel/proposals`) | Merged into Inbox. Proposals are inbox items. |
| Snapshot (`/snapshot`) | Replaced by Portfolio. |
| Cold Clients (`/clients/cold`) | Folded into Client Index as a filter. |
| Recently Active Drilldown (`/clients/:id/recently-active`) | Folded into Client Detail. |

**Net change:** 18 existing pages → 14 redesigned pages (Phases 0-5) + 12 new pages (Phases 6-13) = 26 total.

### 1.3 What's Deferred (not in Phases 0-13)

| Capability | Endpoint | Reason |
|-----------|----------|--------|
| SSE event stream | `/api/v2/events/stream` | Already implemented — no work needed. |
| Paginated list views | `/api/v2/paginated/*` | 4 endpoints. Wire when data volumes exceed non-paginated limits. |
| GDPR/SAR compliance | `/api/governance/sar/*` | 5 endpoints. Requires legal review before building UI. |
| Intelligence snapshot (full) | `/api/v2/intelligence/snapshot` | ~45s execution. Too slow for UI. Use targeted endpoints. |
| Capacity debt write | `POST /api/capacity/debt/accrue`, `POST /api/capacity/debt/{id}/resolve` | Return 501 — not implemented in backend. |
| Auth system | N/A | Single-user system. Auth is hardcoded as `token: 'local'`. Future track. |

**Moved from deferred to in-scope (Phases 6-13):**
- Data export → wired as button on list pages (Phase 11, Governance)
- Action proposals (batch) → wired in Phase 11 (Governance)
- Client comparison views → wired in Phase 3 (Client Detail enhancement, available endpoints)
- Signal tuning/export → wired in Phase 11 (Governance admin)
- Change detection widget → wired in Phase 3 (Portfolio, available endpoint)
- Project intelligence → wired in Phase 12 (Project Enrollment)

---

## §2 — Design System Resolution

### 2.1 Token Reconciliation

Source of truth: `design/system/tokens.css` (887 lines). Verified firsthand.

**Neutral palette — update token values to slate equivalents:**

| Token | Current | New Value | Slate Equivalent |
|-------|---------|-----------|-----------------|
| `--black` | `#000000` | `#0f172a` | slate-900 |
| `--grey-dim` | `#1a1a1a` | `#1e293b` | slate-800 |
| `--grey` | `#333333` | `#334155` | slate-700 |
| `--grey-light` | `#555555` | `#94a3b8` | slate-400 |
| `--white` | `#ffffff` | `#f1f5f9` | slate-100 |

**New tokens to add:**

| Token | Value | Purpose |
|-------|-------|---------|
| `--grey-mid` | `#475569` (slate-600) | Borders, secondary UI elements |
| `--grey-muted` | `#64748b` (slate-500) | Decorative text only (below AA) |
| `--grey-subtle` | `#cbd5e1` (slate-300) | Light borders, dividers |

**Accent color (resolved — blue):**
- `tokens.css` line 25: `--accent: #ff3d00` → `--accent: #3b82f6`
- `tokens.css` line 26: `--accent-dim: #ff3d0066` → `--accent-dim: #3b82f666`
- `tokens.css` line 98: `--border-active: 1px solid #ff3d00` → `--border-active: 1px solid var(--accent)`
- `tokens.css` line 512: `.btn--primary:hover` `#ff5522` → blue hover variant
- `index.css` lines 46-52: Remove the entire `:root { ... }` override block (no longer needed once tokens.css is updated)

**Semantic aliases (index.css @theme block, lines 4-43) — no changes needed.** The `@theme` block already maps tokens correctly. Once token values update, the theme updates automatically.

### 2.2 Layout Primitives

Three new components. Spec from UI_EXECUTION_SPEC.md §1B.

**PageLayout** (`components/layout/PageLayout.tsx`) — Wraps every page.
```
Props: title (string), subtitle? (string), actions? (ReactNode), children
Structure:
  <div class="min-h-screen bg-[var(--black)]">
    <div class="max-w-7xl mx-auto px-6 py-8">
      <header class="mb-8">
        <h1 class="text-2xl font-semibold text-[var(--white)]">{title}</h1>
        {subtitle && <p class="text-sm text-[var(--grey-light)] mt-1">{subtitle}</p>}
        {actions && <div class="mt-4">{actions}</div>}
      </header>
      <main>{children}</main>
    </div>
  </div>
```

**SummaryGrid** (`components/layout/SummaryGrid.tsx`) — Top-of-page metrics row.
```
Props: children (MetricCard instances)
Structure:
  <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
    {children}
  </div>
```

**MetricCard** (`components/layout/MetricCard.tsx`) — Individual metric display.
```
Props: label (string), value (string|number), trend? (up|down|flat), severity? (string)
Structure:
  <div class="bg-[var(--grey-dim)] rounded-lg p-4 border border-[var(--grey)]">
    <span class="text-sm text-[var(--grey-light)]">{label}</span>
    <span class="text-2xl font-semibold text-[var(--white)]">{value}</span>
    {trend indicator if present}
  </div>
```

### 2.3 Component Deduplication

Verified firsthand — 6 inline duplicates across 3 page files:

| Inline Component | File:Line | Shared Equivalent |
|-----------------|-----------|-------------------|
| `SeverityBadge` | `Signals.tsx:13` | `intelligence/components/Badges.tsx` |
| `SignalCard` | `Signals.tsx:27` | `intelligence/components/SignalCard.tsx` |
| `SeverityBadge` | `Patterns.tsx:12` | `intelligence/components/Badges.tsx` |
| `PatternCard` | `Patterns.tsx:46` | `intelligence/components/PatternCard.tsx` |
| `UrgencyBadge` | `Proposals.tsx:14` | `intelligence/components/Badges.tsx` |
| `ProposalCard` | `Proposals.tsx:30` | `intelligence/components/ProposalCard.tsx` |

**Action:** Delete inline definitions, add imports from shared components. Verify prop compatibility before replacing.

### 2.4 Issue Style Extraction

Extract the `stateStyles` map (duplicated in `IssueCard.tsx` and `IssueDrawer.tsx`) into `lib/issueStyles.ts`. Both components import from the shared location.

### 2.5 Hardcoded RGB in Chart Components

Verified firsthand — 16 occurrences across 3 files:

| File | Count | Examples |
|------|-------|---------|
| `Sparkline.tsx` | 7 | `rgb(148 163 184)` (slate-400), `rgb(74 222 128)` (green-400), `rgb(30 41 59)` (slate-800) |
| `DistributionChart.tsx` | 6 | `rgb(59 130 246)` (blue-500), `rgb(16 185 129)` (emerald-500), `rgb(100 116 139)` (slate-500) |
| `CommunicationChart.tsx` | 3 | `rgb(59 130 246)`, `rgb(16 185 129)`, `rgb(168 85 247)` |

These need replacement with CSS custom property values or a chart color palette constant. Deferred to Phase 5.

---

## §3 — Build Sequence

### Phase -1: Backend Cleanup ✅ COMPLETE

**Status:** Merged via PR #28 (2026-02-26). All CI gates passed.
**Scope exceeded plan:** In addition to the planned 4 items, Session 2 also enforced S110/S112/S113 everywhere, fixed all 53 mypy errors (zero baseline), replaced all MD5 with SHA256, replaced all hardcoded /tmp with tempfile.gettempdir(), replaced urllib with httpx, and formatted 264 files.

**Rationale:** Building UI on a backend with 165 `except Exception` blocks, duplicate routes, SQL injection, and dead routers means every session fights the same bugs. Clean first.

**Size:** 0 new files, ~10 edited files, ~15 deleted duplicate functions, ~500 lines changed. (Actual: 264 files touched across 3 commits.)
**Dependencies:** None. This is the new starting point.
**Protected files check:** Required — verify `protected-files.txt` in Fleezyflo/enforcement before any backend PR.

#### -1.1 SQL Injection Fix (Critical)

| Step | What | File | Line |
|------|------|------|------|
| -1.1.1 | Fix f-string SQL injection in `get_team()` — `type_filter` interpolated directly from query param | `api/server.py` | 1819 |

`f"p.type = '{type_filter}'"` → parameterized `"p.type = ?"` with `params.append(type_filter)`. The `# noqa: S608` comment claiming "hardcoded filters" is wrong — `type_filter` is user input.

#### -1.2 Duplicate Route Removal (High)

7 duplicate route definitions in server.py. FastAPI registers the first match; the second is dead code that confuses readers and tooling.

| Duplicate | First def | Second def | Action |
|-----------|-----------|------------|--------|
| `GET /api/delegations` | line 1321 | line 1898 | Remove second |
| `GET /api/insights` | line 1920 | line 2960 | Remove second |
| `GET /api/emails` | line 2926 | line 4050 | Remove second |
| `POST /api/priorities/{item_id}/complete` | line 1952 (`MutationResponse`) | line 2463 (`DetailResponse`) | Consolidate — keep `DetailResponse` version, remove first |
| `POST /api/priorities/{item_id}/snooze` | line 1996 | line 2482 | Remove second |
| `POST /api/priorities/{item_id}/delegate` | line 2031 | line 2503 | Remove second |

**Deletion rationale:** 6 dead duplicate route handlers (~120 lines). FastAPI uses first-registered match; second definitions are unreachable dead code.

#### -1.3 `except Exception` Triage (High)

165 `except Exception` blocks across 9 API files. Three categories:

| Category | Count | Files | Action |
|----------|-------|-------|--------|
| **Silent swallow** (return empty `{}` or `[]`) | ~47 | spec_router (19), server.py (28) | **Fix:** Log error, return typed error response or raise HTTPException 500 |
| **Log + re-raise as HTTPException** | ~75 | spec_router (24), server.py (15), action_router (7), governance_router (5), others | **Accept for now:** These at least surface errors. Narrow catch types in later passes. |
| **Log + return typed error** (`_intel_error()`) | ~43 | intelligence_router (39), spec_router (4) | **Accept:** These return structured `{error: ...}` responses. Already typed. |

**Phase -1 scope:** Fix the ~47 silent-swallow blocks only. The others log errors and surface them — imperfect but not hiding failures. Narrowing catch types across 165 blocks is a separate initiative.

**Approach per silent block:**
```python
# BEFORE (hides failures as empty data):
except Exception:
    return {"items": [], "total": 0}

# AFTER (surfaces the error):
except Exception:
    logger.error(f"<endpoint_name> failed: {e}", exc_info=True)
    raise HTTPException(status_code=500, detail=str(e)) from e
```

#### -1.4 Dead Router Cleanup (Medium)

| Item | File | Action |
|------|------|--------|
| `wave2_router.py` | `api/wave2_router.py` (368 lines, 16 endpoints) | Not registered in server.py. Either register at `/api/v2/ops` (as its docstring says) or delete. Decision: **Delete** — endpoints are stubs for future Wave 2 features (Notification Intelligence, Predictive Intelligence, etc.) that don't exist yet. Re-create from scratch when Wave 2 starts. |

**Deletion rationale:** 368 lines, 16 stub endpoints, 15 `except Exception` blocks. File is not imported or registered. Dead code.

#### -1.5 Verification

| Check | Command | Expected |
|-------|---------|----------|
| Zero f-string SQL from user input | `grep -n "f\".*type_filter" api/server.py` | 0 matches |
| Zero duplicate routes | Count unique route registrations | No path appears twice |
| Zero silent-swallow `except Exception` | `grep -A2 "except Exception" api/spec_router.py \| grep "return {"` | 0 matches |
| wave2_router.py deleted | `ls api/wave2_router.py` | File not found |
| All tests pass | `python -m pytest tests/ -x` | Green |
| Pre-commit passes | `pre-commit run --all-files` | All passed |

**PR structure (planned):** 3-4 PRs. **(Actual: 3 commits in 1 PR)**
1. SQL injection fix (1 line change, critical)
2. Duplicate route removal (~120 lines deleted)
3. Silent-swallow except blocks (~47 blocks in spec_router + server.py)
4. wave2_router deletion (368 lines)

**Completion evidence (PR #28, merged 2026-02-26):**
- Zero `except Exception` in api/ and lib/ (593 narrowed to specific types)
- Zero f-string SQL injection
- Zero duplicate routes (133 unique)
- Zero silent-swallow except blocks
- wave2_router.py deleted
- S110/S112/S113 enforced everywhere (22 violations fixed)
- Zero mypy errors (.mypy-baseline.txt emptied)
- Zero nosec/noqa bypass comments
- All 7 pre-push gates passing (ruff, ruff-format, fast tests, mypy, secrets, UI typecheck, guardrails)

---

### Phase 0: Design System Foundation ✅ COMPLETE
**Size:** 5 new files, 5 edited files. ~200 lines new, ~50 lines deleted.
**Dependencies:** Phase -1 (Backend Cleanup) ✅ COMPLETE.
**Completed:** Session 5, PR #30 merged. All 9 steps done. 26/26 CI checks passed.

#### Step 0.1: Update neutral token values in `design/system/tokens.css`

Change these 5 values to match Tailwind slate equivalents:

| Token | Current | Target |
|-------|---------|--------|
| `--black` | `#000000` | `#0f172a` (slate-900) |
| `--grey-dim` | `#1a1a1a` | `#1e293b` (slate-800) |
| `--grey` | `#333333` | `#334155` (slate-700) |
| `--grey-light` | `#555555` | `#94a3b8` (slate-400) |
| `--white` | `#ffffff` | `#f1f5f9` (slate-200) |

#### Step 0.2: Add 3 new tokens in `design/system/tokens.css`

Add after `--grey-light` in the Neutral Colors section:

```css
--grey-mid: #475569;    /* slate-600 */
--grey-muted: #64748b;  /* slate-500 */
--grey-subtle: #cbd5e1; /* slate-300 */
```

#### Step 0.3: Update accent color in `design/system/tokens.css`

Decision D1 resolved: accent = `#3b82f6` (blue).

| Line | Current | Target |
|------|---------|--------|
| `--accent` | `#ff3d00` | `#3b82f6` |
| `--accent-dim` | `#ff3d0066` | `#3b82f666` |
| `--border-active` (line ~98) | `1px solid #ff3d00` | `1px solid #3b82f6` |
| `.btn--primary:hover` (line ~512) | `#ff5522` | `#2563eb` |

#### Step 0.4: Remove `:root` override block

File: `time-os-ui/src/index.css` — find and remove any `:root` block that overrides tokens.css values (lines ~46-52). Verify line numbers before deleting.

#### Step 0.5: Create PageLayout component

File: `time-os-ui/src/components/layout/PageLayout.tsx` (new)

Reusable page wrapper: header area (title + optional actions slot), consistent max-width, padding, spacing. All pages will use this.

#### Step 0.6: Create SummaryGrid component

File: `time-os-ui/src/components/layout/SummaryGrid.tsx` (new)

2-3 column responsive grid for top-level metrics. Takes children (MetricCard instances).

#### Step 0.7: Create MetricCard component

File: `time-os-ui/src/components/layout/MetricCard.tsx` (new)

Metric display: label + value + optional trend indicator. Uses `.metric-card` CSS classes from tokens.css.

#### Step 0.8: Extract shared issue styles

Create: `time-os-ui/src/lib/issueStyles.ts` (new)

Extract shared card styling (colors, status mappings, severity indicators) used by both:
- `time-os-ui/src/components/IssueCard.tsx`
- `time-os-ui/src/components/IssueDrawer.tsx`

Update both files to import from `issueStyles.ts` instead of defining inline.

#### Step 0.9: Delete inline duplicates

Grep for duplicated card/badge/metric styling across these 3 files:
- `time-os-ui/src/intelligence/pages/Signals.tsx`
- `time-os-ui/src/intelligence/pages/Patterns.tsx`
- `time-os-ui/src/intelligence/pages/Proposals.tsx`

Replace with imports from the shared components created in 0.5-0.8.

**Verification:**
- `npx tsc --noEmit` passes (Mac only — do NOT run from sandbox)
- Open Inbox, Issues, Clients, Command Center, Signals in browser — no visual breakage
- DevTools: inspect `--black` → should show `#0f172a`, `--accent` → should show `#3b82f6`
- Signals/Patterns/Proposals pages still render cards correctly after deduplication
- `grep -r "ff3d00" time-os-ui/src/` returns 0 hits (old accent fully replaced)

---

### Phase 1: Slate Migration
**Size:** 396 replacements across 51 files.
**Dependencies:** Phase 0 (tokens must have new values first).

Verified counts (firsthand grep):

| Batch | Target | Count | Files | Example |
|-------|--------|-------|-------|---------|
| 1a | `bg-slate-*` | 140 | 40 | `bg-slate-800` → `bg-[var(--grey-dim)]` |
| 1b | `text-slate-*` | 261 | 44 | `text-slate-400` → `text-[var(--grey-light)]` |
| 1c | `border-slate-*` | 75 | 26 | `border-slate-700` → `border-[var(--grey)]` |

**Replacement mapping:**

| Tailwind Class | CSS Variable | Token |
|---------------|-------------|-------|
| `slate-900` | `var(--black)` | `#0f172a` |
| `slate-800` | `var(--grey-dim)` | `#1e293b` |
| `slate-700` | `var(--grey)` | `#334155` |
| `slate-600` | `var(--grey-mid)` | `#475569` |
| `slate-500` | `var(--grey-muted)` | `#64748b` |
| `slate-400` | `var(--grey-light)` | `#94a3b8` |
| `slate-300` | `var(--grey-subtle)` | `#cbd5e1` |
| `slate-200` | `var(--white)` | `#f1f5f9` |

**Priority files (highest slate counts):**
1. `RoomDrawer.tsx` — 48 refs
2. `IssueDrawer.tsx` — 22 refs
3. `ProposalCard.tsx` (intelligence) — 21 refs
4. `Proposals.tsx` — 21 refs (after dedup, remaining layout refs)
5. `ConnectedEntities.tsx` — 17 refs
6. `Briefing.tsx` — 16 refs

**Verification per batch:**
- `tsc --noEmit`
- Open each modified page — colors should be visually identical (since new token values = slate values)
- After all batches: `grep -r "slate-" src/ --include="*.tsx" --include="*.ts"` returns 0

---

### Phase 2: Layout Adoption
**Size:** ~15 page files modified. ~30 lines added per file (PageLayout wrapper + SummaryGrid).
**Dependencies:** Phase 0 (PageLayout must exist).

| Step | Page | SummaryGrid Metrics | Data Source |
|------|------|-------------------|------------|
| 2.1 | Inbox (`/`) | Total items, Unread, Critical, Categories | Wire `fetchInboxCounts()` (new) |
| 2.2 | Issues (`/issues`) | Open, Investigating, Critical, Total | Derived from `useIssues()` response |
| 2.3 | Client Index (`/clients`) | Total, Active, At-risk, Overdue AR | Derived from `useClients()` response |
| 2.4 | Team Index (`/team`) | Team size, Avg score, Overloaded | Derived from `useTeam()` response |
| 2.5 | Fix Data → now under Ops | Fix items, Identity issues, Link issues | From `useFixData()` response |
| 2.6 | Signals (`/intel/signals`) | Total active, Critical, Warning, Watch | From `useSignalSummary()` (exists) |
| 2.7 | Patterns (`/intel/patterns`) | Total detected, Structural, Operational | Derived from `usePatterns()` response |
| 2.8 | Client Detail | Health score, AR total, Active projects, Open issues | From `useClientProfile()` (exists) |
| 2.9 | Team Detail | Health score, Active tasks, Overdue, Projects | From `usePersonProfile()` (exists) |

**Verification:**
- Every page renders with consistent header positioning and max-width
- SummaryGrid shows real numbers from API
- No layout shift on page transitions

---

### Phase 3: Page Redesign — Core
**Size:** 2 new pages, 3 enhanced pages, 9 new components, 16 new hooks.
**Dependencies:** Phase 0 + Phase 2.

#### 3.1 Portfolio Page (new)

**Component hierarchy:**
```
Portfolio.tsx
├── PageLayout title="Portfolio"
├── SummaryGrid
│   ├── MetricCard label="Health Score" value={portfolioScore.composite_score}
│   ├── MetricCard label="Critical Items" value={criticalItems.length} severity="danger"
│   ├── MetricCard label="Active Signals" value={signalSummary.total_active}
│   └── MetricCard label="Structural Patterns" value={structuralPatterns.length}
├── section "Top Risks"
│   └── CriticalItemList (new component — renders critical items as cards)
├── section "Portfolio Health"
│   ├── ScoreDimensionBreakdown (reuse Scorecard.tsx from intelligence/components)
│   └── TrajectorySparkline (new component — reusable, replaces hardcoded Sparkline)
├── section "Client Distribution"
│   └── ClientDistributionChart (new component — tier/status breakdown from useClients data)
└── section "Top Proposals"
    └── ProposalCard[] (reuse intelligence/components/ProposalCard.tsx)
```

**Hooks used:** `usePortfolioScore()`, `usePortfolioIntelligence()`, `useCriticalItems()`, `useClients()` — all exist.
**New hooks wired:** `usePortfolioOverview()`, `usePortfolioRisks()`, `useFinancialAging()` — endpoints exist, hooks are new.

**New components:** `CriticalItemList.tsx`, `TrajectorySparkline.tsx`, `ClientDistributionChart.tsx`, `RiskList.tsx` (renders portfolio risks with severity), `ARAgingSummary.tsx` (renders aging buckets)

#### 3.2 Inbox Enhancement

**Component hierarchy changes:**
```
Inbox.tsx (existing)
├── PageLayout title="Inbox"
├── SummaryGrid (from Phase 2)
├── InboxCategoryTabs (new) — tabs for risk/opportunity/anomaly/maintenance
│   └── Uses useInboxCounts() data
├── InboxItemList (existing, enhanced)
│   └── InboxItemCard (enhanced — add unread indicator, richer metadata)
└── ProposalDetailDrawer (enhanced — replaces legacy endpoint call)
```

**New hooks:** `useInbox()`, `useInboxCounts()` in `lib/hooks.ts`.
**New components:** `InboxCategoryTabs.tsx`

#### 3.3 Client Detail Enhancement

**Component hierarchy changes:**
```
ClientDetailSpec.tsx (existing)
├── PageLayout title={client.name}
├── SummaryGrid (from Phase 2)
├── TrajectorySparkline in header
├── TabContainer (new — or use existing pattern)
│   ├── Tab "Overview" (existing content, restructured)
│   ├── Tab "Financials" (new)
│   │   ├── ClientInvoiceTable (new) — from /clients/{id}/invoices
│   │   └── ClientARaging (new) — from /clients/{id}/ar-aging
│   ├── Tab "Signals" — from useActiveSignals(entityType='client', entityId)
│   ├── Tab "Team" (new) — from /clients/{id}/team
│   └── Tab "Engagements" (new) — from /engagements
```

**New hooks:** `useClientInvoices()`, `useClientARAging()`, `useClientTeam()`, `useEngagements()`, `useClientsHealth()`, `useAtRiskClients()`, `useClientSnapshot()` in `lib/hooks.ts`.
**New components:** `ClientInvoiceTable.tsx`, `ClientARAging.tsx`, `TabContainer.tsx`, `ClientHealthBadge.tsx`

**Client health sub-endpoints (server.py):** `GET /api/clients/health` (overview), `GET /api/clients/at-risk` (filtered by threshold), `GET /api/clients/{id}/health` (single client), `GET /api/clients/portfolio` (portfolio overview). These feed the health score badge on Client Detail and an "At-Risk" filter on the client list. `GET /api/v2/clients/{id}/snapshot` (spec_router) provides inbox-context client snapshots — wired to Client Detail when navigated from Inbox.

#### 3.4 Team Detail Enhancement

Existing page already uses intelligence hooks. Add `TrajectorySparkline` in header. Wire `GET /api/team/workload` (server.py) for workload distribution data — shows task counts, overdue items, and average priority per team member. New hook: `useTeamWorkload()` in `lib/hooks.ts`.

#### 3.5 Operations Page (new)

**Component hierarchy:**
```
Operations.tsx
├── PageLayout title="Operations"
├── SummaryGrid
│   ├── MetricCard "Fix Items" from useFixData()
│   ├── MetricCard "Active Watchers" from useWatchers()
│   ├── MetricCard "Couplings" from useAllCouplings()
│   └── MetricCard "System Health" from checkHealth()
├── TabContainer
│   ├── Tab "Data Quality"
│   │   └── FixDataCard[] (existing component, reused)
│   ├── Tab "Watchers"
│   │   └── WatcherList (extract from existing page or inline)
│   └── Tab "Couplings"
│       └── CouplingList (extract from existing page or inline)
```

**Hooks used:** `useFixData()`, `useWatchers()`, `useAllCouplings()`, `checkHealth()` — all exist.

**Verification for all of Phase 3:**
- Portfolio renders real data from 4 endpoints
- Inbox shows category tabs with correct counts
- Client Detail shows all 5 tabs with data
- Operations shows all 3 tabs with data
- All mutation actions work: snooze, dismiss, resolve, transition, add note
- Network tab shows correct API calls, no 404s

---

### Phase 4: Navigation & Route Cleanup ✅ COMPLETE (Session 9)
**Size:** router.tsx rewrite (~100 lines changed), nav component update, ~6 redirect rules.
**Dependencies:** Phase 3 (new pages must exist).

| Step | What |
|------|------|
| 4.1 | Add routes: `/portfolio` → Portfolio, `/ops` → Operations |
| 4.2 | Add redirects: `/snapshot` → `/portfolio`, `/intel` → `/portfolio`, `/intel/briefing` → `/portfolio`, `/intel/proposals` → `/` |
| 4.3 | Remove routes: `/clients/cold`, `/clients/:id/recently-active` |
| 4.4 | Update NAV_ITEMS array: `['/', '/portfolio', '/clients', '/issues', '/team', '/intel/signals', '/ops']` with labels Inbox, Portfolio, Clients, Issues, Team, Intel, Ops |
| 4.5 | Remove lazy imports for deleted pages: `Snapshot`, `Briefing`, `Proposals`, `ColdClients`, `RecentlyActiveDrilldown`, `CommandCenter` |
| 4.6 | Keep `/intel/signals`, `/intel/patterns`, `/intel/client/:id`, `/intel/person/:id` as-is |

**Verification:**
- Click every nav item — correct page loads
- Visit old URLs — redirects work
- Browser back/forward works across redirects
- No console errors about missing routes

---

### Phase 5: Accessibility & Polish ✅ COMPLETE (Session 10)
**Size:** ~15 files, ~200 lines changed.
**Dependencies:** Phase 4.

| Step | What | Files |
|------|------|-------|
| 5.1 | Keyboard navigation on clickable cards: `role="button"`, `tabIndex={0}`, `onKeyDown` (Enter/Space) | `IssueCard.tsx`, `ProposalCard.tsx` (both), `SignalCard.tsx`, `PatternCard.tsx` |
| 5.2 | Focus trap in drawers | `IssueDrawer.tsx`, `RoomDrawer.tsx` |
| 5.3 | ARIA labels on interactive elements | Audit all button/link elements without labels |
| 5.4 | Replace 16 hardcoded RGB values in chart components with CSS custom property values or a `CHART_COLORS` constant | `Sparkline.tsx` (7), `DistributionChart.tsx` (6), `CommunicationChart.tsx` (3) |
| 5.5 | Standardize loading/error/empty states to use shared components with token-based colors | All pages using inline loading states |

**Verification:**
- Tab through Inbox, Client Detail, Issues — all interactive elements reachable via keyboard
- `grep -rn "rgb(" src/intelligence/components/ src/components/` returns 0 (excluding CSS files)
- Screen reader on Inbox and Client Detail — all elements announced correctly

---

### Phase 6: Task Management (§1 Sections 8a, 8b)

**Size:** 2 new pages, ~5 new components, ~15 endpoints wired.
**Dependencies:** Phase 5 complete (shared components, design system, layout).
**Track:** T3

| Step | What | Files |
|------|------|-------|
| 6.1 | Fix `useTasks()` response shape bug — `/api/tasks` returns `{tasks:[...]}` but `ApiListResponse` expects `{items:[...]}`. Update `fetchTasks()` in `lib/api.ts` to remap key. | `lib/api.ts` |
| 6.2 | Add fetch functions: `fetchPrioritiesAdvanced()`, `fetchPrioritiesGrouped()`, `fetchDelegations()`, `fetchDependencies()`, `fetchTaskDetail()`, `fetchBundleDetail()` | `lib/api.ts` |
| 6.3 | Add hooks: `usePrioritiesAdvanced()`, `usePrioritiesGrouped()`, `useDelegations()`, `useDependencies()`, `useTaskDetail()`, `useBundleDetail()` | `lib/hooks.ts` |
| 6.4 | Create Task List page with filter/group/delegation views | `pages/TaskListPage.tsx` |
| 6.5 | Create Task Detail page with edit, notes, blockers, delegation/escalation/recall | `pages/TaskDetailPage.tsx` |
| 6.6 | Create components: TaskForm, TaskActions, BlockerList, DependencyGraph, DelegationSplit | `components/shared/` |
| 6.7 | Add governance approval dialog (triggered by `requires_approval: true` in delegation/escalation responses) | `components/shared/ApprovalDialog.tsx` |
| 6.8 | Add routes: `/tasks` → TaskListPage, `/tasks/:taskId` → TaskDetailPage | `router.tsx` |
| 6.9 | Update nav: add Tasks to NAV_ITEMS | `Nav.tsx` or equivalent |

**Verification:**
- Create task → appears in list
- Edit task fields → changes persist on refresh
- Delegate task → governance dialog appears when required, task reassigned on approve
- Add/remove blocker → blocker list updates
- Bulk actions → multiple items updated

---

### Phase 7: Priorities Workspace (§1 Section 9)

**Size:** 1 new page, ~4 new components, ~10 endpoints wired.
**Dependencies:** Phase 6 (reuses task components and hooks).
**Track:** T4

| Step | What | Files |
|------|------|-------|
| 7.1 | Add fetch functions: `fetchPrioritiesFiltered()`, `fetchSavedFilters()` | `lib/api.ts` |
| 7.2 | Add hooks: `usePrioritiesFiltered()`, `useSavedFilters()` | `lib/hooks.ts` |
| 7.3 | Create Priorities page with advanced filters, grouping, bulk actions | `pages/PrioritiesPage.tsx` |
| 7.4 | Create components: PriorityFilters, GroupedPriorityView, BulkActionBar, SavedFilterSelector | `components/shared/` |
| 7.5 | Add route: `/priorities` → PrioritiesPage | `router.tsx` |

**Verification:**
- Filter by due date range → results update
- Group by project → groups render with totals
- Bulk select + complete → items move to completed
- Saved filter select → filters apply

---

### Phase 8: Time & Capacity (§1 Sections 10, 11)

**Size:** 2 new pages, ~5 new components, ~10 endpoints wired.
**Dependencies:** Phase 6 (task references for scheduling).
**Track:** T5

| Step | What | Files |
|------|------|-------|
| 8.1 | Add fetch functions: `fetchTimeBlocks()`, `fetchTimeSummary()`, `fetchEvents()`, `fetchDayView()`, `fetchWeekView()`, `fetchCapacityLanes()`, `fetchCapacityUtilization()`, `fetchCapacityForecast()`, `fetchCapacityDebt()` | `lib/api.ts` |
| 8.2 | Add corresponding hooks | `lib/hooks.ts` |
| 8.3 | Create Schedule page with day/week views, time block grid by lane | `pages/SchedulePage.tsx` |
| 8.4 | Create Capacity page with utilization gauges and forecast chart | `pages/CapacityPage.tsx` |
| 8.5 | Create components: TimeBlockGrid, WeekView, CapacityGauge, ForecastChart, ScheduleTaskDialog | `components/shared/` |
| 8.6 | Add routes: `/schedule`, `/capacity` | `router.tsx` |

**Verification:**
- Day view shows time blocks by lane
- Schedule task into block → block updates
- Capacity gauge reflects utilization data
- Forecast chart renders N-day projection

---

### Phase 9: Commitments (§1 Section 12)

**Size:** 1 new page, ~3 new components, ~6 endpoints wired.
**Dependencies:** Phase 5 (shared components). Can run parallel with Phases 6-8.
**Track:** T6

| Step | What | Files |
|------|------|-------|
| 9.1 | Add fetch functions: `fetchCommitments()`, `fetchUntrackedCommitments()`, `fetchCommitmentsDue()`, `fetchCommitmentsSummary()` | `lib/api.ts` |
| 9.2 | Add corresponding hooks | `lib/hooks.ts` |
| 9.3 | Create Commitments page with list, summary cards, untracked alert, due view | `pages/CommitmentsPage.tsx` |
| 9.4 | Create components: CommitmentList, CommitmentSummaryCards, LinkToTaskDialog | `components/shared/` |
| 9.5 | Add route: `/commitments` | `router.tsx` |

**Verification:**
- Commitment list renders with status, owner, date
- Untracked commitments highlighted
- Link-to-task dialog → commitment linked, task_id populated
- Mark done → status updates

---

### Phase 10: Notifications, Digest & Email (§1 Sections 13, 14)

**Size:** 2 new pages, ~4 new components, ~8 endpoints wired.
**Dependencies:** Phase 5. Can run parallel with Phase 9.
**Track:** T8

| Step | What | Files |
|------|------|-------|
| 10.1 | Add fetch functions: `fetchNotifications()`, `fetchNotificationStats()`, `fetchWeeklyDigest()`, `fetchEmails()` | `lib/api.ts` |
| 10.2 | Add corresponding hooks | `lib/hooks.ts` |
| 10.3 | Create Notifications page with list, stats bar, dismiss actions | `pages/NotificationsPage.tsx` |
| 10.4 | Create Digest page with weekly summary tab + email triage tab | `pages/DigestPage.tsx` |
| 10.5 | Create components: NotificationList, NotificationBadge (for nav), WeeklyDigestView, EmailTriageList | `components/shared/` |
| 10.6 | Add NotificationBadge to nav bar (shows unread count) | `Nav.tsx` |
| 10.7 | Add routes: `/notifications`, `/digest` | `router.tsx` |

**Verification:**
- Notification list renders with correct icons per type
- Badge shows unread count in nav
- Dismiss single → item removed, stats update
- Weekly digest shows period, completed, slipped counts
- Email triage: mark actionable/dismiss → item state updates

---

### Phase 11: Governance & Admin (§1 Section 15)

**Size:** 3 new pages, ~9 new components, ~18 endpoints wired.
**Dependencies:** Phase 5. Can run parallel with Phases 9-10.
**Track:** T7

| Step | What | Files |
|------|------|-------|
| 11.1 | Add fetch functions: `fetchGovernance()`, `fetchGovernanceHistory()`, `fetchCalibration()`, `fetchBundles()`, `fetchRollbackable()`, `fetchBundleSummary()`, `fetchApprovals()`, `fetchDataQuality()`, `fetchCleanupPreview()` | `lib/api.ts` |
| 11.2 | Add corresponding hooks | `lib/hooks.ts` |
| 11.3 | Create Governance page with domain cards, emergency brake, history, calibration, bundles | `pages/GovernancePage.tsx` |
| 11.4 | Create Approvals page with queue and decision dialog | `pages/ApprovalsPage.tsx` |
| 11.5 | Create Data Quality page with health score, issues, cleanup, recalculation | `pages/DataQualityPage.tsx` |
| 11.6 | Create components: GovernanceDomainCards, EmergencyBrakeToggle, ApprovalQueue, ApprovalDecisionDialog, DataQualityHealthScore, CleanupPreviewConfirm, BundleTimeline | `components/shared/` |
| 11.7 | Wire search: add `fetchSearch()`, SearchOverlay component, keyboard shortcut (Ctrl/Cmd+K) | `lib/api.ts`, `components/shared/SearchOverlay.tsx` |
| 11.8 | Wire data export: add export buttons on list pages using `/governance/export/*` | Relevant list pages |
| 11.9 | Add routes: `/admin/governance`, `/admin/approvals`, `/admin/data-quality` | `router.tsx` |

**Verification:**
- Domain mode change → mode card updates
- Emergency brake on/off → all endpoints respect it
- Approval approve → side effects execute (task updates, notifications created)
- Cleanup preview → shows count and sample → confirm → items archived
- Search overlay: type query → results from tasks, projects, clients

---

### Phase 12: Project Enrollment (§1 Section 16)

**Size:** 1 new page, ~4 new components, ~7 endpoints wired.
**Dependencies:** Phase 5 + Phase 3 (client/project pages exist).
**Track:** T9

| Step | What | Files |
|------|------|-------|
| 12.1 | Add fetch functions: `fetchProjectCandidates()`, `fetchProjectsEnrolled()`, `fetchDetectedProjects()`, `fetchProjectDetail()`, `fetchLinkingStats()`, `bulkLinkTasks()`, `syncXero()` | `lib/api.ts` |
| 12.2 | Add corresponding hooks (including `useLinkingStats()`) | `lib/hooks.ts` |
| 12.3 | Create Enrollment page with detected alert, candidate list, enrolled split | `pages/ProjectEnrollmentPage.tsx` |
| 12.4 | Create components: CandidateList, EnrollmentActionBar, DetectedProjectsAlert, ProjectProposalForm | `components/shared/` |
| 12.5 | Add route: `/projects/enrollment` | `router.tsx` |

**Verification:**
- Detected projects alert shows auto-detected projects
- Enroll candidate → moves to enrolled list
- Reject/snooze → removes from candidates (snooze reappears after N days)
- Create proposal → new project created

---

### Phase 13: Collector Data Depth (§1 Section 17)

**Size:** 0 new pages (tabs on existing), ~6 new components, ~8 new backend endpoints, ~8 new query_engine methods.
**Dependencies:** Phase 3 (detail pages must exist). This is the only phase requiring significant new backend work.
**Track:** T10

| Step | What | Files |
|------|------|-------|
| 13.1 | Data quality audit: check each of the 20 collector tables for row counts, staleness, completeness. Document which tables have usable data vs empty/stale. | Investigation only |
| 13.2 | Add query_engine methods for each collector table grouping (8 methods) | `lib/query_engine.py` |
| 13.3 | Add spec_router endpoints (8 new endpoints) | `api/spec_router.py` — **protected files check required** |
| 13.4 | Add fetch functions and hooks for new endpoints | `lib/api.ts`, `lib/hooks.ts` |
| 13.5 | Add Email Participants tab to Client Detail | `pages/ClientDetail.tsx` |
| 13.6 | Add Attachments tab to Client Detail | `pages/ClientDetail.tsx` |
| 13.7 | Add Xero Detail tab to Client Detail | `pages/ClientDetail.tsx` |
| 13.8 | Add Calendar Detail tab to Team Detail | `pages/TeamDetail.tsx` |
| 13.9 | Add Asana Context tab to Task Detail | `pages/TaskDetailPage.tsx` |
| 13.10 | Add Chat Analytics section to Operations | `pages/Operations.tsx` |
| 13.11 | Add Financial Detail section to Portfolio | `pages/PortfolioPage.tsx` |
| 13.12 | Add Asana Portfolio & Goals section to Operations | `pages/Operations.tsx` |
| 13.13 | Create components: ParticipantNetwork, AttachmentTimeline, InvoiceLineItemTable, CalendarAttendeeList, AsanaDetailPanel, ChatSpaceOverview | `components/shared/` |

**Verification:**
- Each new tab renders data from collector tables
- Empty tables show meaningful empty states (not errors)
- New backend endpoints return correct response shapes
- Pre-commit passes on all new Python code

---

## §4 — Backend Changes

### 4.1 Legacy Endpoint Migration

**`GET /api/tasks` (server.py line 616):**
- UI callsite: `lib/api.ts` line 211 (`fetchTasks`)
- Replacement: `GET /api/v2/priorities` exists in spec_router (line 995)
- **Response shape mismatch (verified firsthand):**
  - `/api/tasks` returns `{tasks: [{SELECT * from tasks}], total}` — key `tasks`, all columns
  - `/api/v2/priorities` returns `{items: [{id, title, status, priority, due_date, assignee, project_id, project_name, client_id, client_name}], total}` — key `items`, 10 selected columns
- **Existing bug (verified firsthand):** `fetchTasks()` returns `ApiListResponse<Task>` which expects `{items: [...]}`, but `/api/tasks` returns `{tasks: [...]}`. TeamDetail.tsx line 74 does `(apiTasks?.items || [])` — `.items` is always `undefined`, so the tasks section silently shows 0 tasks. Migrating to `/api/v2/priorities` (which returns `{items: [...]}`) fixes this bug.
- **Fields needed by TeamDetail.tsx (verified firsthand):** `status` (line 75, 218), `priority` (line 219, 241), `due_date` (line 220, 231), `title` (line 230). All 4 fields are present in v2's response. No missing fields. Migration is safe.
- **Action:** Update `fetchTasks()` to call `/api/v2/priorities`. No key rename needed — v2 already returns `{items: [...]}` matching `ApiListResponse`. This will un-break TeamDetail's task display.
- **Bug (spec_router line 1018-1020, verified firsthand):** `except Exception` returns `{"items": [], "total": 0}` — swallows errors as empty data. Flag for fix alongside migration.

**`GET /api/control-room/proposals/{id}` (server.py line 5016):**
- UI callsite: `lib/api.ts` line 202 (`fetchProposalDetailLegacy`)
- **Problem found during verification: There is no `GET /api/v2/proposals/{id}` endpoint.** spec_router has `GET /api/v2/proposals` (list) but no single-proposal detail endpoint.
- **Enrichment logic (verified firsthand, 132 lines):** Parses `signal_summary_json` and `score_breakdown_json` from DB row. Fetches top 5 signals via `SignalService`. For each signal, builds type-aware human-readable description (8 signal type handlers: `ar_aging_risk`, `client_health_declining`, `communication_gap`, `data_quality_issue`, `deadline_overdue`, `deadline_approaching`, `hierarchy_violation`, `commitment_made`). Constructs `issues_url` from client_id.
- **Response shape (verified):**
  ```
  {proposal_id, proposal_type, scope_level, scope_name, client_id, client_name,
   client_tier, headline, score, score_breakdown, signal_summary, worst_signal,
   status, trend, first_seen_at, last_seen_at, signals[]{signal_id, signal_type,
   entity_type, entity_id, task_title, assignee, days_overdue, days_until,
   severity, status, detected_at, description}, total_signals,
   affected_task_ids[], issues_url}
  ```
- **Bugs found:** (1) Signal type fallback — unhandled types get `description=None`, no logging. (2) Title truncation to 40-80 chars with no `"..."` indicator. (3) Hardcoded top-5 signal limit. (4) Inconsistent signal value key names suggest upstream normalization needed.
- **Action required: New backend work.** Add `GET /api/v2/proposals/{proposal_id}` to spec_router. Port enrichment logic (~76 lines of active enrichment + 56 lines of boilerplate = 132 lines total). Fix the 4 bugs during port.
- **Dependencies:** `ProposalService`, `SignalService` (both from `lib/v4/`)
- **Enforcement note:** spec_router.py may be protected. Check before editing.

### 4.2 wave2_router Decision

**Kill it.** 368 lines, 15 endpoints, never mounted, stub implementations only.

**Action:** Delete `api/wave2_router.py`. Single-purpose PR with deletion rationale.

**Enforcement note:** Check if wave2_router.py is protected.

### 4.3 spec_router Intelligence Endpoints — Route Shadowing Problem

**Finding from firsthand verification:** spec_router registers 21 endpoints under `/intelligence/*` (lines 1374-1829). Mounted at `/api/v2` (line 105), these resolve to paths like `/api/v2/intelligence/critical`. intelligence_router registers its own endpoints mounted at `/api/v2/intelligence` (line 106) — resolving to the **same paths**.

Since spec_router is mounted first, FastAPI matches its routes first. **21 intelligence_router endpoints are shadowed and unreachable:**

```
Shadowed (21 routes — intelligence_router versions are dead code):
/critical, /briefing, /signals, /signals/summary, /signals/active,
/signals/history, /patterns, /patterns/catalog, /proposals,
/scores/client/{id}, /scores/project/{id}, /scores/person/{id},
/scores/portfolio, /entity/client/{id}, /entity/person/{id},
/entity/portfolio, /projects/{id}/state, /clients/{id}/profile,
/team/{id}/profile, /clients/{id}/trajectory, /team/{id}/trajectory

Reachable (18 routes — unique to intelligence_router):
/portfolio/overview, /portfolio/risks, /portfolio/trajectory,
/clients/{id}/tasks, /clients/{id}/communication, /clients/{id}/compare,
/clients/compare, /team/distribution, /team/capacity, /projects/health,
/financial/aging, /snapshot, /signals/export, /signals/thresholds,
/scores/{entity_type}/{entity_id}/history, /scores/history/summary,
/scores/record (POST), /changes
```

**Implications:**
- intelligence_router's auth requirement (`INTEL_API_TOKEN`) is bypassed for all 21 shadowed routes
- The UI exclusively hits spec_router's versions
- Two independent implementations exist per shadowed route — potential response shape divergence
- The 18 unique intelligence_router endpoints DO require auth and are reachable

**Decision for this build: No action.** The UI works. Flag for dedicated cleanup after redesign.

### 4.4 Legacy server.py

~160 endpoints. The UI uses 2 (both being migrated per §4.1).

**Not as simple as "don't touch."** server.py contains ~70 endpoints with unique functionality that has no v2 equivalent: capacity management, time blocks, commitments, notifications, approvals/decisions, bundle audit trail, governance controls, data quality cleanup, rich priority management (grouped, filtered, bulk), task CRUD/delegation/escalation, project enrollment, calendar analysis, search, calibration, email management, and weekly digest. See **Appendix B** for the complete catalog.

**Decision for this build:** Don't touch server.py. The 14 redesigned pages can be built entirely from v2 + intelligence_router endpoints. But acknowledge that shipping the redesign means choosing to NOT surface these capabilities. After launch, audit server.py traffic logs to determine which capabilities need v2 equivalents.

### 4.5 Invoice Column Consistency

No dual-column problem — `invoices` schema uses `due_date`, `paid_date`, `amount` consistently.

**Bug found:** spec_router line 1127 selects `payment_date` which doesn't exist (column is `paid_date`). Single-line fix.

### 4.6 Code Smells Found During Endpoint Verification

| Location | Severity | Issue |
|----------|----------|-------|
| spec_router line 1018-1020 (`GET /priorities`) | **High** | `except Exception` returns `{"items": [], "total": 0}` — swallows DB errors as empty data |
| spec_router line 828-830 (`GET /engagements`) | **High** | `except Exception: pass` returns empty engagements list — silent failure |
| spec_router line 694-696 (`GET /clients/{id}/team`) | **High** | `except Exception: pass` returns empty involvement — silent failure |
| spec_router line 627-631 (`GET /clients/{id}/signals`) | **Medium** | Logs malformed JSON but silently continues with `{}` evidence |
| server.py line 5068-5107 (proposal detail) | **Medium** | Unhandled signal types get `description=None`, no logging |
| server.py line 5063 (proposal detail) | **Low** | `signals[:5]` hardcoded limit |

**Action:** Fix the 3 high-severity `except Exception: pass` patterns alongside the endpoint migration work. These violate the codebase rule against swallowing errors.

### 4.7 New Backend Work

**Phases 0-5 (1 new endpoint):**
- `GET /api/v2/proposals/{proposal_id}` — proposal detail with enrichment. Port from server.py lines 5016-5147. 132 lines total. Fix 4 bugs during port.

**Phases 6-12 (0 new endpoints):**
All server.py endpoints already exist. Frontend wires directly to `/api/*` routes via `lib/api.ts`. No new backend code needed.

**Phase 13 (~8 new endpoints + ~8 query_engine methods):**
Collector secondary tables (20 tables) are write-only — no read paths exist. New backend work:

| New endpoint | Query method | Tables read | Response shape |
|-------------|-------------|-------------|---------------|
| `GET /api/v2/clients/{id}/email-participants` | `get_client_email_participants(client_id)` | gmail_participants, gmail_labels | `{participants: [{email, role, message_count}], labels: [{name, count}]}` |
| `GET /api/v2/clients/{id}/attachments` | `get_client_attachments(client_id)` | gmail_attachments | `{attachments: [{filename, mime_type, size, thread_id, date}]}` |
| `GET /api/v2/clients/{id}/invoice-detail` | `get_client_invoice_detail(client_id)` | xero_line_items, xero_credit_notes | `{line_items: [...], credit_notes: [...]}` |
| `GET /api/v2/team/{id}/calendar-detail` | `get_person_calendar_detail(person_id)` | calendar_attendees, calendar_recurrence_rules | `{attendees: [...], recurrence: [...]}` |
| `GET /api/v2/tasks/{id}/asana-detail` | `get_task_asana_detail(task_id)` | asana_custom_fields, asana_subtasks, asana_stories, asana_task_dependencies, asana_attachments | `{custom_fields: [...], subtasks: [...], stories: [...], dependencies: [...], attachments: [...]}` |
| `GET /api/v2/chat/analytics` | `get_chat_analytics()` | chat_reactions, chat_attachments, chat_space_metadata, chat_space_members | `{spaces: [...], reaction_summary: {...}, attachment_summary: {...}}` |
| `GET /api/v2/financial/detail` | `get_financial_detail()` | xero_contacts, xero_bank_transactions, xero_tax_rates | `{contacts: [...], transactions: [...], tax_rates: [...]}` |
| `GET /api/v2/projects/asana-context` | `get_asana_portfolio_context()` | asana_portfolios, asana_goals | `{portfolios: [...], goals: [...]}` |

**Note:** Response shapes above are preliminary. Each must be verified against actual table schemas during Phase 13 build sessions (Rule 7). Some tables may be empty or stale — Step 13.1 audits data quality before wiring.

### 4.8 Backend Change Summary

| Change | Phase | Size | Protected? | PR |
|--------|-------|------|-----------|-----|
| Add `GET /api/v2/proposals/{id}` to spec_router | 3 | 132 lines | Check | Standalone, before Phase 3 |
| Fix 3 `except Exception: pass` in spec_router | 3 | ~15 lines | Check | Bundle with proposal endpoint |
| Fix `useTasks()` response shape (`.tasks` → `.items`) | 6 | ~5 lines | No (frontend) | Phase 6 PR |
| Update UI legacy callsites (proposal detail) | 3 | ~10 lines | No (frontend) | Phase 3 PR |
| Delete wave2_router.py | Any | -368 lines | Check | Standalone |
| Fix `payment_date` → `paid_date` in spec_router | Any | 1 line | Check | Standalone |
| Add 8 new spec_router endpoints (collector depth) | 13 | ~400 lines | Check | 2-3 PRs |
| Add 8 new query_engine methods (collector depth) | 13 | ~300 lines | No | Bundle with endpoints |
| Resolve route shadowing (21 endpoints) | Future | Medium | Check | After buildout |

---

## §5 — Verification Strategy

### Per-Phase Gates

| Phase | Gate | How to Verify |
|-------|------|--------------|
| 0 (Foundation) | TypeScript compiles. Tokens resolve. No visual breakage. | `tsc --noEmit`. Manual open of Inbox, Issues, Clients, Command Center, Signals. DevTools check token values. |
| 1 (Slate Migration) | Zero `slate-` references in src/. Visual parity. | `grep -r "slate-" src/ --include="*.tsx" --include="*.ts"` → 0 results. Screenshot comparison. |
| 2 (Layout) | Every page has PageLayout. SummaryGrid shows real data. | Visual audit all redesigned pages. Grep for `PageLayout` import in every page file. |
| 3 (Redesign) | New pages render real data. All actions work. No legacy API calls. | Manual test every action. Network tab audit — no `/api/tasks` or `/api/control-room/*` calls. |
| 4 (Navigation) | All routes resolve. Redirects work. Nav correct. | Click every nav item. Visit every old URL. Browser back/forward. |
| 5 (Polish) | Keyboard navigation works. No hardcoded RGB. | Tab-only navigation test. `grep -rn "rgb(" src/intelligence/components/ src/components/` → 0. |
| 6 (Tasks) | Task CRUD works end-to-end. Delegation triggers governance when required. | Create → edit → delegate → escalate → recall → complete cycle. Verify governance dialog. |
| 7 (Priorities) | Advanced filtering, grouping, bulk actions all functional. | Apply filters → results update. Group → groups render. Bulk select + action → items change. |
| 8 (Time & Capacity) | Schedule page shows time blocks. Capacity gauges render. | View day → blocks by lane. Schedule task → block assigned. Capacity page shows utilization. |
| 9 (Commitments) | Commitment list renders. Link-to-task works. | View list → items render. Link → task_id populated. Mark done → status updates. |
| 10 (Notifications) | Notification center functional. Badge shows count. | List renders. Dismiss → removed. Badge updates. Digest tab shows weekly summary. |
| 11 (Governance) | Admin pages functional. Approval flow works end-to-end. | Change domain mode → saved. Approve decision → side effects execute. Search returns results. |
| 12 (Enrollment) | Project enrollment workflow complete. | Detect → candidates appear. Enroll → moves to enrolled. Reject → removed. |
| 13 (Collector Depth) | All 8 new endpoints return data. Tabs render on detail pages. | curl each endpoint → valid JSON. Open detail pages → new tabs show data. |

### Pre-Push Checks (Every PR)

- `tsc --noEmit` — TypeScript compilation
- Ruff, ruff-format, bandit — if any Python files changed
- Pre-commit hooks — must run, never skip
- Visual spot-check — open the pages you changed

### Regression Indicators

- Any page shows blank screen → broken import or missing component
- Console errors about missing CSS variables → token rename missed a reference
- API calls returning 404 → route changed but UI not updated
- Cards/badges showing wrong colors → color mapping regression
- Text unreadable → contrast regression from token value change

---

## §6 — Sequencing & Dependencies

```
Phase -1 (cleanup)
  │
  ▼
Phase 0 ─── Design System Foundation
  │
  ├──▶ Phase 1 ─── Slate Migration (parallel with Phase 2)
  │
  └──▶ Phase 2 ─── Layout Adoption (parallel with Phase 1)
         │
         ▼
       Phase 3 ─── Page Redesign (needs Phase 0 + 2, benefits from Phase 1)
         │         REQUIRES: proposal detail endpoint (§4.1) before Inbox enhancement
         ▼
       Phase 4 ─── Navigation Cleanup (needs Phase 3)
         │
         ▼
       Phase 5 ─── Accessibility & Polish (needs Phase 4)
         │
         │  ════════════════════════════════════════════
         │  Foundation complete. Capability buildout below.
         │  ════════════════════════════════════════════
         │
         ├──▶ Phase 6 ─── Task Management (needs Phase 5 shared components)
         │      │
         │      ├──▶ Phase 7 ─── Priorities Workspace (needs Phase 6 task components)
         │      │
         │      └──▶ Phase 8 ─── Time & Capacity (needs Phase 6 task references)
         │
         ├──▶ Phase 9 ─── Commitments (independent, parallel with 6-8)
         │
         ├──▶ Phase 10 ── Notifications, Digest & Email (independent, parallel with 6-8)
         │
         ├──▶ Phase 11 ── Governance & Admin (independent, parallel with 6-8)
         │
         ├──▶ Phase 12 ── Project Enrollment (needs Phase 3 client/project pages)
         │
         └──▶ Phase 13 ── Collector Data Depth (needs detail pages from Phase 3+6)
                          REQUIRES: 8 new backend endpoints + query_engine methods

Backend (parallel track):
  ├── Add GET /api/v2/proposals/{id} ────── before Phase 3
  ├── Delete wave2_router.py ─────────────── anytime
  ├── Fix payment_date bug ────────────────── anytime
  ├── Fix useTasks() response shape ────────── Phase 6
  └── Add 8 collector-depth endpoints ─────── before Phase 13
```

**Critical path (foundation):** Phase -1 → Phase 0 → Phase 2 → Phase 3 → Phase 4 → Phase 5

**Critical path (buildout):** Phase 5 → Phase 6 → Phase 7/8 (parallel)

**Parallel after Phase 5:** Phases 9, 10, 11 can all run independently alongside Phase 6.

**Blockers:**
- Proposal detail endpoint (§4.1) must ship before Phase 3 Inbox enhancement
- Phase 6 before Phases 7, 8 (task component dependency)
- 8 new backend endpoints before Phase 13 (protected files check required)

---

## §7 — State Management

### Current Architecture (verified firsthand)

Two parallel data-fetching layers with identical patterns:

**Control Room** (`lib/api.ts` → `lib/hooks.ts`):
- `useFetch<T>(fetcher, deps)` — generic hook with 30s TTL cache, retry, error recovery
- 10 hooks: `useProposals`, `useIssues`, `useWatchers`, `useFixData`, `useCouplings`, `useAllCouplings`, `useClients`, `useTeam`, `useTasks`, `useEvidence`
- Mutations via `postJson`/`patchJson` with manual `invalidateCache()` calls

**Intelligence** (`intelligence/api.ts` → `intelligence/hooks.ts`):
- `useData<T>(fetchFn, deps, options)` — generic hook with `enabled` flag, no cache
- 20 hooks: scores, signals, patterns, proposals, entity intelligence, profiles, trajectories
- No mutations (read-only endpoints)

### Assessment

This architecture is adequate for the redesign. Reasons:
- Both hook factories return `{ data, loading, error, refetch }` — identical consumer interface
- The two API clients map cleanly to the two router families (spec_router vs spec_router-intelligence)
- Adding 5-7 new hooks in Phase 3 follows established patterns exactly
- No state sharing between pages (each page fetches its own data) — no global state needed
- The 30s cache in the control room layer is sufficient for a single-user system

### What NOT to do

Don't introduce React Query, SWR, Zustand, or any state management library during this build. The custom hooks work, the patterns are consistent, and the migration risk outweighs the benefit for a single-user app.

### New hooks — all phases

#### Phase 3 (16 hooks — v2 and intelligence endpoints)

Add to `lib/api.ts` + `lib/hooks.ts` — spec_router endpoints:
- `useInbox()`, `useInboxCounts()`, `useClientInvoices(id)`, `useClientARAging(id)`, `useClientTeam(id)`, `useEngagements(clientId?)`, `useProposalDetail(id)`, `useIssueDetail(id)`

Add to `intelligence/api.ts` + `intelligence/hooks.ts` — intelligence_router unique endpoints:
- `usePortfolioOverview()`, `usePortfolioRisks()`, `useFinancialAging()`, `useTeamDistribution()`, `useTeamCapacity()`, `useClientTasks(id)`, `useClientCommunication(id)`, `useScoreHistory(entityType, entityId)`

#### Phase 6 (6 hooks — server.py task endpoints)

Add to `lib/api.ts` + `lib/hooks.ts`:
- `usePrioritiesAdvanced()`, `usePrioritiesGrouped()`, `useDelegations()`, `useDependencies()`, `useTaskDetail()`, `useBundleDetail()`

#### Phase 7 (2 hooks — server.py priority endpoints)

Add to `lib/api.ts` + `lib/hooks.ts`:
- `usePrioritiesFiltered()`, `useSavedFilters()`

#### Phase 8 (9 hooks — server.py time/capacity endpoints)

Add to `lib/api.ts` + `lib/hooks.ts`:
- `useTimeBlocks()`, `useTimeSummary()`, `useEvents()`, `useDayView()`, `useWeekView()`, `useCapacityLanes()`, `useCapacityUtilization()`, `useCapacityForecast()`, `useCapacityDebt()`

#### Phase 9 (4 hooks — server.py commitment endpoints)

Add to `lib/api.ts` + `lib/hooks.ts`:
- `useCommitments()`, `useUntrackedCommitments()`, `useCommitmentsDue()`, `useCommitmentsSummary()`

#### Phase 10 (4 hooks — server.py notification/digest endpoints)

Add to `lib/api.ts` + `lib/hooks.ts`:
- `useNotifications()`, `useNotificationStats()`, `useWeeklyDigest()`, `useEmails()`

#### Phase 11 (9 hooks — server.py + governance_router endpoints)

Add to `lib/api.ts` + `lib/hooks.ts`:
- `useGovernance()`, `useGovernanceHistory()`, `useCalibration()`, `useBundles()`, `useRollbackable()`, `useBundleSummary()`, `useApprovals()`, `useDataQuality()`, `useCleanupPreview()`

#### Phase 12 (4 hooks — server.py project endpoints)

Add to `lib/api.ts` + `lib/hooks.ts`:
- `useProjectCandidates()`, `useProjectsEnrolled()`, `useDetectedProjects()`, `useProjectDetail()`

#### Phase 13 (8 hooks — new spec_router collector endpoints)

Add to `lib/api.ts` + `lib/hooks.ts`:
- `useClientEmailParticipants()`, `useClientAttachments()`, `useClientInvoiceDetail()`, `useTeamCalendarDetail()`, `useTaskAsanaDetail()`, `useChatAnalytics()`, `useFinancialDetail()`, `useAsanaContext()`

**Total: 62 new hooks across all phases.** Phase 3 hooks wire v2/intelligence endpoints. Phases 6-12 hooks wire existing server.py endpoints. Phase 13 hooks wire new collector-depth endpoints.

---

## Appendix A: Endpoint Usage Map

### Complete Backend Inventory (audited 2026-02-25, all routers read firsthand)

| Router | Mount Point | Endpoints | Currently used | After Phases 0-5 | After full buildout (Phases 0-13) |
|--------|------------|-----------|---------------|-----------------|----------------------------------|
| server.py | `/api/*` | ~140 | 2 (legacy) | 7 (client health, portfolio) | ~103 (task, priority, time, capacity, commitment, notification, approval, governance, data quality, project, calendar, search, email, digest, bundle, client health, linking-stats) |
| spec_router | `/api/v2` | 61 | 22 | 33 (+snapshot) | 41 (+8 collector depth) |
| intelligence_router | `/api/v2/intelligence` | 39 (18 unique, 21 shadowed) | 0 directly | 8 unique + 21 shadow | 8 unique + 21 shadow |
| paginated_router | `/api/v2/paginated` | 4 | 0 | 0 (deferred) | 0 (deferred) |
| sse_router | `/api/v2` | 3 | 1 | 1 | 1 |
| export_router | `/api/governance` | 4 | 0 | 0 | 4 (Phase 11) |
| governance_router | `/api/governance` | 5 | 0 | 0 | 5 (Phase 11) |
| action_router | `/api/actions` | 7 | 0 | 0 | 7 (Phase 11) |
| chat_webhook_router | `/chat` | 2 | 0 | 0 | 0 (not frontend) |
| wave2_router | (not mounted) | 15 | 0 | 0 (delete) | 0 (deleted) |
| **Total** | | **~300 (~285 reachable)** | **45 + 1 SSE** | **~63 + 1 SSE** | **~177 + 1 SSE (~62%)** |

### Currently Used by UI (45 endpoints + 1 SSE)

**Control Room (spec_router, `/api/v2/`):**
`/proposals`, `/issues`, `/clients`, `/team`, `/fix-data`, `/couplings`, `/watchers`, `/evidence/{type}/{id}`, `/health`, `/inbox`, `/inbox/counts`, `POST /inbox/{id}/action`, `POST /issues`, `POST /issues/{id}/transition`, `POST /proposals/{id}/snooze`, `POST /proposals/{id}/dismiss`, `POST /watchers/{id}/dismiss`, `POST /watchers/{id}/snooze`, `POST /fix-data/{type}/{id}/resolve`, `PATCH /issues/{id}/resolve`, `PATCH /issues/{id}/state`, `POST /issues/{id}/notes`

**Intelligence (`/api/v2/intelligence/` — served by spec_router shadow, not intelligence_router):**
`/briefing`, `/critical`, `/signals`, `/signals/summary`, `/signals/active`, `/signals/history`, `/patterns`, `/patterns/catalog`, `/proposals`, `/scores/client/{id}`, `/scores/person/{id}`, `/scores/project/{id}`, `/scores/portfolio`, `/entity/client/{id}`, `/entity/person/{id}`, `/entity/portfolio`, `/clients/{id}/profile`, `/clients/{id}/trajectory`, `/team/{id}/profile`, `/team/{id}/trajectory`, `/projects/{id}/state`

**SSE:** `/api/v2/events/stream` (wired via `EventStreamSetup.tsx` → `useEventStream`)

**Legacy (to be migrated):**
`GET /api/tasks`, `GET /api/control-room/proposals/{id}`

### Added by Redesign (~25 newly wired)

**spec_router endpoints (existing but previously uncalled):**
`/inbox/recent`, `/issues/{id}`, `/clients/{id}/invoices`, `/clients/{id}/ar-aging`, `/clients/{id}/signals`, `/clients/{id}/team`, `/clients/{id}/snapshot`, `/engagements`, `/engagements/{id}`, `POST /engagements/{id}/transition`

**intelligence_router unique endpoints (previously invisible to frontend):**
`/portfolio/overview`, `/portfolio/risks`, `/financial/aging`, `/team/distribution`, `/team/capacity`, `/clients/{id}/tasks`, `/clients/{id}/communication`, `/scores/{type}/{id}/history`

**server.py client health endpoints (newly wired in Phase 3):**
`GET /api/clients/health`, `GET /api/clients/at-risk`, `GET /api/clients/{id}/health`, `GET /api/clients/{id}/projects`, `GET /api/clients/portfolio`

**New endpoint created:**
`GET /api/v2/proposals/{proposal_id}` — proposal detail with enrichment (1 new, 132 lines)

### After Phases 0-5 (Redesign): ~69 of ~285 reachable (~24%)

### After Full Buildout (Phases 0-13): ~183 of ~285 reachable (~64%)

### Added by Phases 6-13 (~113 newly wired)

**server.py endpoints wired directly via `lib/api.ts`:**
- Phase 6 (Tasks): ~15 endpoints — task CRUD, delegate, escalate, recall, block, dependency, priorities advanced/grouped, delegations
- Phase 7 (Priorities): ~10 endpoints — priorities filtered/advanced/grouped, bulk, archive-stale, filters, per-item complete/snooze/delegate
- Phase 8 (Time & Capacity): ~10 endpoints — time blocks/summary, schedule/unschedule, events, day/week view, capacity lanes/utilization/forecast/debt
- Phase 9 (Commitments): ~6 endpoints — commitments list/untracked/due/summary, link, done
- Phase 10 (Notifications): ~8 endpoints — notifications list/stats/dismiss, digest weekly, emails list/mark-actionable/dismiss
- Phase 11 (Governance): ~18 endpoints — governance config/domains/history/brake, approvals, decisions, data quality, bundles, calibration, search
- Phase 12 (Enrollment): ~10 endpoints — project candidates/enrolled/detect/enrollment, propose, linking-stats, bulk-link-tasks, sync/xero

**governance_router endpoints wired (Phase 11):** 5 endpoints
**export_router endpoints wired (Phase 11):** 4 endpoints
**action_router endpoints wired (Phase 11):** 7 endpoints

**New spec_router endpoints (Phase 13):** 8 collector-depth endpoints

### Remaining Unwired After Full Buildout (~102 endpoints)

- **Duplicates** (~40): server.py endpoints that duplicate v2 functionality — includes `/api/overview` (replaced by Portfolio page wiring `/portfolio/overview` + `/briefing`), `/api/summary` (replaced by Portfolio page), `/api/team` (replaced by spec_router `/api/v2/team`), `/api/inbox` (replaced by spec_router `/api/v2/inbox`), client CRUD, project list, control-room/* (27 endpoints), etc.
- **Paginated variants** (4): Wire when data volumes grow
- **GDPR/SAR** (5): Requires legal review
- **Intelligence snapshot** (1): 45s execution, too slow for UI
- **Capacity debt writes** (2): Return 501 (not implemented)
- **SSE extras** (2): `/events/history`, `/events/publish`
- **System/internal** (~50): health checks (`/api/health`, `/api/status`), sync triggers (`/api/sync`, `/api/analyze`, `/api/cycle`), debug (`/api/debug/db`), metrics (`/api/metrics`), admin (`/api/admin/seed-identities`), SPA fallback (`/{path}`), chat webhooks, feedback (`/api/feedback`), control-room health
- **Intelligence extras already covered by other routes** (~4): snapshot, record, history summary

---

## Appendix B: server.py — Unique Capabilities Without v2 Equivalents

The plan previously dismissed server.py as "142 legacy endpoints, don't touch." This was wrong. server.py contains ~160 endpoints, and many provide **unique functionality that exists nowhere in the v2 API**. These are not duplicates — they represent real system capabilities the frontend cannot access through any v2 endpoint.

### B.1 Capabilities with NO v2 equivalent (server.py exclusive)

#### Capacity Management (6 endpoints)
- `GET /api/capacity/lanes` — lane configuration
- `GET /api/capacity/utilization` — utilization metrics
- `GET /api/capacity/forecast` — upcoming capacity forecast
- `GET /api/capacity/debt` — overcommitment tracking
- `POST /api/capacity/debt/accrue` — record accrued debt (stub)
- `POST /api/capacity/debt/{id}/resolve` — resolve debt (stub)

**Impact:** The Team page could show utilization and forecast data. intelligence_router has `/team/capacity` (aggregate overview) but NOT lanes, forecast, or debt tracking. These are complementary, not duplicative.

#### Time Management (4 endpoints)
- `GET /api/time/blocks` — time blocks by date/lane
- `GET /api/time/summary` — day summary
- `POST /api/time/schedule` — schedule task into time block
- `POST /api/time/unschedule` — remove from time block

**Impact:** No scheduling concept exists in the v2 API or the redesigned UI. This is a complete capability gap if the product needs time-block scheduling.

#### Commitments (6 endpoints)
- `GET /api/commitments` — all commitments
- `GET /api/commitments/untracked` — not linked to tasks
- `GET /api/commitments/due` — due by date
- `GET /api/commitments/summary` — summary stats
- `POST /api/commitments/{id}/link` — link to task
- `POST /api/commitments/{id}/done` — mark done

**Impact:** Commitment tracking is entirely absent from the redesign. If commitments matter (e.g., client promises with deadlines), this needs a page or integration into Client Detail.

#### Notifications (4 endpoints)
- `GET /api/notifications` — notification list
- `GET /api/notifications/stats` — notification stats
- `POST /api/notifications/{id}/dismiss` — dismiss one
- `POST /api/notifications/dismiss-all` — dismiss all

**Impact:** SSE delivers events to toasts, but there's no persistent notification center. These endpoints provide one. Could enhance Inbox or become a notification panel.

#### Approvals & Decisions (5 endpoints)
- `GET /api/approvals` — pending approvals
- `GET /api/decisions` — pending decisions
- `POST /api/decisions/{id}` — approve/reject with side-effect execution
- `POST /api/approvals/{id}` — process approval
- `POST /api/approvals/{id}/modify` — modify and approve

**Impact:** A human-in-the-loop approval pipeline. The action_router (`/actions/*`) provides a similar propose→approve→execute flow. Neither is surfaced. If the product needs human approval gates, this is the infrastructure.

#### Bundle Audit Trail (6 endpoints)
- `GET /api/bundles` — change bundles
- `GET /api/bundles/{id}` — specific bundle
- `GET /api/bundles/rollbackable` — rollback candidates
- `GET /api/bundles/summary` — activity summary
- `POST /api/bundles/{id}/rollback` — rollback specific
- `POST /api/bundles/rollback-last` — rollback most recent

**Impact:** Change tracking with rollback capability. Could be in Operations page as "Recent Changes" with undo. No v2 equivalent exists.

#### Governance Controls (6 endpoints)
- `GET /api/governance` — governance config and status
- `PUT /api/governance/{domain}` — set mode for domain
- `PUT /api/governance/{domain}/threshold` — set confidence threshold
- `GET /api/governance/history` — action history
- `POST /api/governance/emergency-brake` — activate emergency brake
- `DELETE /api/governance/emergency-brake` — release emergency brake

**Impact:** System-level governance controls (different from governance_router's GDPR/SAR). Includes emergency brake. Could be in Operations or a Settings page.

#### Data Quality Cleanup (6 endpoints, vs fix-data's read+resolve)
- `GET /api/data-quality` — quality metrics and cleanup suggestions
- `POST /api/data-quality/cleanup/ancient` — archive tasks >30 days overdue
- `POST /api/data-quality/cleanup/stale` — archive 14-30 days overdue
- `POST /api/data-quality/cleanup/legacy-signals` — clean up legacy signals
- `POST /api/data-quality/recalculate-priorities` — recalculate all priorities
- `GET /api/data-quality/preview/{type}` — preview cleanup impact

**Impact:** v2's `/fix-data` handles identity conflicts and ambiguous links. These server.py endpoints handle a different problem: stale data cleanup and priority recalculation. The Operations page should surface cleanup capabilities.

#### Rich Priority Management (8 endpoints, vs v2's thin `/priorities`)
- `GET /api/priorities` — base priority list
- `GET /api/priorities/filtered` — with filter reasons
- `GET /api/priorities/advanced` — advanced filtering
- `GET /api/priorities/grouped` — grouped by project/assignee/source
- `POST /api/priorities/{id}/complete` — mark complete
- `POST /api/priorities/{id}/snooze` — snooze
- `POST /api/priorities/{id}/delegate` — delegate
- `POST /api/priorities/bulk` — bulk actions
- `POST /api/priorities/archive-stale` — archive stale

**Impact:** spec_router's `GET /api/v2/priorities` is a thin alias. server.py's priorities system has grouping, advanced filtering, bulk actions, delegation, completion, and archival. If the redesign's task view needs any of this, it needs server.py or new v2 endpoints.

#### Task Management (13 endpoints)
- Full CRUD: `GET/POST/PUT/DELETE /api/tasks/{id}`, `POST /api/tasks/{id}/notes`
- Delegation: `POST /api/tasks/{id}/delegate`, `POST /api/tasks/{id}/escalate`, `POST /api/tasks/{id}/recall`, `GET /api/delegations`
- Dependencies: `POST /api/tasks/{id}/block`, `DELETE /api/tasks/{id}/block/{blocker_id}`, `GET /api/dependencies`

**Impact:** v2 has no task CRUD, delegation, escalation, or dependency management. If the product needs task creation/editing from the UI, these have no v2 equivalent.

#### Project Enrollment (7 endpoints)
- `GET /api/projects/candidates` — enrollment candidates
- `GET /api/projects/enrolled` — enrolled with task counts
- `GET /api/projects/detect` — detect from tasks
- `POST /api/projects/{id}/enrollment` — process enrollment
- `POST /api/projects/propose` — propose new project
- `POST /api/sync/xero` — Xero sync
- `POST /api/tasks/link` — bulk link tasks

**Impact:** v2 has `GET /api/v2/projects` (list with status filter) but no enrollment lifecycle. If the product needs project onboarding, these are server.py-only.

#### Calendar & Day/Week Analysis (3 endpoints)
- `GET /api/calendar` — events for date range
- `GET /api/day/{date}` — day analysis
- `GET /api/week` — week analysis

**Impact:** v2 has `GET /api/v2/events` (event list). server.py has richer calendar views with daily/weekly analysis. Different from time blocks.

#### Other (unique, 1-2 endpoints each)
- Calibration: `GET/POST /api/calibration` — run and view scoring calibration
- Feedback: `POST /api/feedback` — submit feedback on recommendations
- Digest: `GET /api/digest/weekly` — weekly digest report
- Email mgmt: `GET /api/emails`, `POST /api/emails/{id}/mark-actionable`, `POST /api/emails/{id}/dismiss`
- Insights/anomalies: `GET /api/insights`, `GET /api/anomalies`
- Search: `GET /api/search` — cross-entity search
- Sync: `GET /api/sync/status`, `POST /api/sync`, `POST /api/analyze`, `POST /api/cycle`

### B.2 server.py endpoints that ARE duplicated in v2 (safe to ignore)

~27 endpoints under `/api/control-room/*` duplicate spec_router v2 endpoints: proposals, issues, watchers, fix-data, couplings, clients, team, evidence, health. These are the original v4 control room API that v2 replaced.

~5 client endpoints (`/api/clients`, `/api/clients/{id}`, `PUT /api/clients/{id}`) overlap with spec_router's `/api/v2/clients/*`. Note: `/api/clients/health`, `/api/clients/at-risk`, `/api/clients/linking-stats`, `/api/clients/portfolio`, `/api/clients/{id}/health`, `/api/clients/{id}/projects` are NOT duplicates — these are unique server.py capabilities wired in Phase 3.

### B.3 Decision: Full product buildout

**All server.py-exclusive capabilities will be surfaced.** Phases 0-5 (this document) build the foundation and redesign existing pages. Phases 6-13 (`BUILD_STRATEGY.md`) wire the remaining ~140 endpoints to new frontend pages.

**API client strategy:** server.py endpoints are called directly from the frontend via `lib/api.ts` (same pattern as existing control room hooks). No third API client. The server.py endpoints use `/api/*` paths; v2 uses `/api/v2/*`. Both are served by the same FastAPI app. The frontend already hits both — this just adds more hooks for server.py routes.

**Sequencing:** Foundation first (Phases 0-5), then operational core (Phases 6-8: tasks, priorities, time), then supporting capabilities (Phases 9-13). See `BUILD_STRATEGY.md` §2 for the full dependency graph and parallel work opportunities.

---

## Appendix C: Verification Log

### Verified Firsthand

| Claim | Source | Verdict |
|-------|--------|---------|
| spec_router intelligence endpoints are independent implementations | `spec_router.py` lines 1374-1420 | **Confirmed.** Import from `lib.intelligence.*` directly. |
| 21 route conflicts between spec_router and intelligence_router | Both router files, grep for decorators | **Confirmed.** spec_router shadows 21 intelligence_router endpoints. Subagent missed this. |
| `payment_date` bug | `spec_router.py` line 1127 | **Confirmed.** Column is `paid_date`. |
| wave2_router not mounted | `server.py` lines 95-113 | **Confirmed.** |
| Two legacy UI callsites | `lib/api.ts` lines 200-214 | **Confirmed.** |
| No `GET /api/v2/proposals/{id}` endpoint | `spec_router.py` grep for `proposals` routes | **Confirmed.** Only list and mutations exist. Plan §4.1 corrected — new endpoint needed. |
| Color system conflict | `tokens.css` line 25, `index.css` line 51 | **Confirmed.** `--accent: #ff3d00` vs `--accent: #3b82f6`. |
| Additional hardcoded accent refs | `tokens.css` lines 98, 512 | **Found.** `--border-active` and `.btn--primary:hover` hardcode `#ff3d00`/`#ff5522`. |
| Slate reference counts | Grep across `src/**/*.{tsx,ts}` | **Corrected.** 396 refs across 51 files (not 400/53). bg:140, text:261, border:75 (not 55/266/115). |
| Inline component duplication | Grep in `intelligence/pages/` | **Confirmed.** 6 inline defs across 3 files with exact line numbers. |
| Hardcoded RGB in charts | Grep in `intelligence/components/` | **Confirmed.** 16 occurrences across 3 files. |
| Portfolio response shape | `lib/intelligence/engine.py` lines 697-792 | **Confirmed.** Clean dict with portfolio_score, signal_summary, structural_patterns, top_proposals. |
| Router structure | `router.tsx` full file (480 lines) | **Confirmed.** 18 routes, 7 nav items. |
| Hook architecture | `lib/hooks.ts` (120 lines), `intelligence/hooks.ts` (291 lines) | **Confirmed.** Two parallel layers, identical consumer interface. |
| State management adequacy | Both hook files, both API clients | **Confirmed.** Custom hooks sufficient for single-user system. |

| Full backend endpoint audit (all 9 routers + server.py) | All router files read firsthand by subagents | **Completed.** ~300 total endpoints (~285 reachable). server.py: ~160, spec_router: 61, intelligence_router: 39, paginated: 4, SSE: 3, export: 4, governance: 5, action: 7, chat_webhook: 2, wave2: 15 (dead). |
| Frontend API call mapping | `lib/api.ts`, `intelligence/api.ts`, all pages with direct fetch | **Completed.** 45 endpoints used + 1 SSE. 23 via lib/api.ts (incl. direct fetches in pages), 22 via intelligence/api.ts. Legacy: `/api/tasks`, `/api/control-room/proposals/{id}`. |
| Auth bypass confirmation | `api/auth.py` line 26-31 | **Confirmed.** `require_auth` always passes (line 29: "Always passes"). Token is hardcoded `"local"`. Intelligence_router unique endpoints are reachable without tokens. |
| SSE already wired | `EventStreamSetup.tsx`, `useEventStream.ts`, `main.tsx` | **Confirmed.** `EventStreamSetup` wraps the app in `main.tsx`. SSE connected to `/api/v2/events/stream`. Not deferred — already working. |
| Intelligence_router unique endpoints reachable | `intelligence_router.py` unique paths + `auth.py` | **Confirmed.** 18 unique endpoints not shadowed by spec_router. All reachable because auth always passes. |

| `/api/v2/priorities` response shape vs `/api/tasks` | spec_router line 995-1022, server.py line 615-649 | **Mismatch found.** v2 returns `{items: [...10 columns]}`, legacy returns `{tasks: [...all columns]}`. Key name and column set differ. Plan §4.1 updated with migration notes. |
| `/api/v2/priorities` error handling | spec_router line 1018-1020 | **Bug.** `except Exception` returns `{"items": [], "total": 0}` — violates no-swallow-errors rule. |
| Proposal detail enrichment (the code to port) | server.py lines 5016-5147 | **Confirmed.** 132 lines total, 76 lines active enrichment. 8 signal type handlers. Dependencies: `ProposalService`, `SignalService`. 4 bugs found. |
| Inbox response shape | spec_router line 255 → `InboxResponse` → `endpoints.py` 1094-1241 | **Verified.** Rich shape with counts (by_severity, by_type), items with read_at, available_actions, trust metadata. Clean implementation. |
| Inbox counts shape | spec_router line 332 → `InboxCountsResponse` | **Verified.** `{scope, needs_attention, snoozed, snoozed_returning_soon, recently_actioned, unprocessed, by_severity{}, by_type{}}` |
| Issue detail shape | spec_router line 484 → `DetailResponse` | **Verified.** Returns full issue with `available_actions` enrichment. Clean. |
| Engagement list/detail shapes | spec_router lines 756, 835, 877 | **Verified.** List: `{engagements[], total, limit, offset}`. Detail adds `transition_history[]`. Transition returns `{success, previous_state, new_state, transition_id}`. |
| Engagement list error handling | spec_router line 828-830 | **Bug.** `except Exception: pass` returns empty list silently. |
| Client invoices shape | spec_router line 217 → `InvoiceListResponse` → `endpoints.py` 791-859 | **Verified.** `{invoices[]{id, number, issue_date, due_date, amount, status, days_overdue, aging_bucket, status_inconsistent}, total, page, limit}` |
| Client AR aging shape | spec_router line 237 → `endpoints.py` 861-920 | **Verified.** `{total_outstanding, buckets[]{bucket, amount, pct}}` |
| Client signals shape | spec_router line 554 → `SignalListResponse` | **Verified.** `{summary{good, neutral, bad, by_source{}}, signals[], total, page}` |
| Client team shape | spec_router line 651 → `TeamInvolvementResponse` | **Verified.** `{involvement[]{user_id, name, role, email, open_tasks, overdue_tasks}, total}` |
| Client team error handling | spec_router line 694-696 | **Bug.** `except Exception: pass` returns empty involvement silently. |
| Intelligence_router: portfolio/overview | intelligence_router.py line 72 | **Verified.** Calls `engine.client_portfolio_overview()`. Cached 120s. Returns client metrics + project counts. |
| Intelligence_router: portfolio/risks | intelligence_router.py line 96 | **Verified.** Returns `{risks[]{type: OVERDUE_PROJECT|OVERLOADED_PERSON|AGING_INVOICE, severity: HIGH|MEDIUM|LOW, evidence}]}`. Configurable thresholds. |
| Intelligence_router: financial/aging | intelligence_router.py line 445 | **Verified.** Returns `{total_outstanding, by_bucket{current, 30, 60, 90+}, clients_with_overdue[]}`. |
| Intelligence_router: team/distribution | intelligence_router.py line 313 | **Verified.** Returns people with `assigned_tasks, active_tasks, project_count, load_score (0-100)`. |
| Intelligence_router: team/capacity | intelligence_router.py line 330 | **Verified.** Returns `{total_people, total_active_tasks, avg_tasks_per_person, people_overloaded, people_available, distribution[]}`. |
| Intelligence_router: client/tasks | intelligence_router.py line 180 | **Verified.** Returns `{total_tasks, active_tasks, completed_tasks, overdue_tasks, completion_rate, tasks_by_status, tasks_by_assignee}`. |
| Intelligence_router: client/communication | intelligence_router.py line 197 | **Verified.** Returns `{total_communications, by_type{}, recent_messages[]}`. |
| Intelligence_router: scores/{type}/{id}/history | intelligence_router.py line 879 | **Verified.** Returns `{history[]{date, score, classification}, trend: improving|declining|stable|insufficient_data, change_pct, current_score, period_high, period_low}`. Validates entity_type against whitelist. |
| Intelligence_router: /changes | intelligence_router.py line 1027 | **Verified.** Runs full snapshot + change detection. Returns `{changes{}, summary, has_changes}`. Heavy — triggers `generate_intelligence_snapshot()`. |

| QueryEngine method return shapes (8 methods) | `lib/query_engine.py`, `lib/intelligence/scorecard.py` | **7/8 match docstrings.** One naming divergence: `client_communication_summary()` returns key `total_communications` but docstring says `total_links`. Bonus fields found in 4 methods (extra data, not missing data). |
| `except Exception: pass` in spec_router (3 locations) | spec_router.py lines 694, 828, 1018 | **Confirmed firsthand.** Line 694: `{"involvement": [], "total": 0}`. Line 828: `{"engagements": [], "total": 0, ...}`. Line 1018: `{"items": [], "total": 0}`. All comments say "Table may not exist" — lazy error handling. |
| `useTasks()` consumer field requirements | `TeamDetail.tsx` lines 59, 74-75, 217-241 | **Verified.** Uses `status`, `priority`, `due_date`, `title` — all present in v2 `/priorities` response. Migration is safe. |
| `useTasks()` existing bug — `.items` always `undefined` | `TeamDetail.tsx` line 74, `api.ts` line 211, `types/api.ts` line 249 | **Bug confirmed.** `/api/tasks` returns `{tasks: [...]}`, frontend expects `{items: [...]}`. `.items` is always `undefined`, fallback `\|\| []` masks it. TeamDetail task section silently shows 0 tasks. Migration to `/api/v2/priorities` fixes this. |
| Protected files status | Enforcement repo (`Fleezyflo/enforcement`) | **Cannot verify.** Enforcement repo not accessible from sandbox. Must check before starting backend work. |

### Previously Unverified — Now Verified

| Item | Source | Finding |
|------|--------|---------|
| Schema table counts | `lib/schema.py`, `data/moh_time_os.db` | **schema.py declares 73 tables** (OrderedDict, schema version 12). Live database has **121 tables + 9 views**. Delta: 19 migration-created tables (v4, v29, v30, v33 series) + 30 tables created by collectors/runtime (system tables, intelligence tables, expanded entity tables). **Total: 1,272 columns, 405,607 rows across 76 populated tables.** Largest: `chat_messages` (183K rows), `couplings` (56K), `artifact_excerpts` (42K), `calendar_events` (38K). |
| Collector architecture | `lib/collectors/base.py`, `lib/collector_registry.py`, `lib/collectors/orchestrator.py`, `collectors/scheduled_collect.py` | **8 collectors registered** in `COLLECTOR_REGISTRY`: gmail, calendar, tasks, chat, asana, xero, drive, contacts. All inherit `BaseCollector` (except XeroCollector — standalone). BaseCollector enforces: `source_name`, `target_table` (abstract), `collect()` → `transform()` → `store.insert_many()` pipeline. Built-in resilience: circuit breaker (3 states), retry with exponential backoff, rate limiter, file locking (prevents concurrent runs). Orchestrator runs all 8 in parallel via `ThreadPoolExecutor(max_workers=5)`. Post-collection triggers: entity linking → inbox enrichment. **No `except Exception: pass` found.** No `shell=True` found. All DB writes go through StateStore — no raw SQL in collectors. |
| Collector output tables | `lib/collectors/gmail.py`, `calendar.py`, `asana.py`, `chat.py`, `xero.py`, `tasks.py` | **Gmail → 4 tables:** communications, gmail_participants, gmail_attachments, gmail_labels. **Calendar → 3 tables:** events, calendar_attendees, calendar_recurrence_rules. **Asana → 8 tables:** tasks, asana_custom_fields, asana_subtasks, asana_stories, asana_task_dependencies, asana_attachments, asana_portfolios, asana_goals. **Chat → 5 tables:** chat_messages, chat_reactions, chat_attachments, chat_space_metadata, chat_space_members. **Xero → 6 tables:** invoices, xero_line_items, xero_contacts, xero_credit_notes, xero_bank_transactions, xero_tax_rates. **Tasks → 1 table:** tasks. Drive and contacts write JSON only (no DB tables). |
| InboxLifecycleManager | `lib/ui_spec_v21/inbox_lifecycle.py` lines 164–787 | **4 states:** PROPOSED → SNOOZED / LINKED_TO_ISSUE / DISMISSED. **4 item types** with different action sets: ISSUE [tag, assign, snooze, dismiss], FLAGGED_SIGNAL [same], ORPHAN [link, create, dismiss], AMBIGUOUS [select, dismiss]. 14 public methods. Writes to `inbox_items_v29` (28 cols) and `issue_transitions`. Uses `SuppressionManager` for dismiss (atomic: update inbox + insert rule). Snooze expiry via `process_snooze_expiry()` (hourly scheduled). **No `except Exception: pass`.** No silent failures — all errors return `ActionResult` with error field or `(None, error_message)` tuple. |
| EngagementLifecycleManager | `lib/ui_spec_v21/engagement_lifecycle.py` lines 108–436 | **7 states:** PLANNED → ACTIVE → BLOCKED/PAUSED/DELIVERING → DELIVERED → COMPLETED. Full transition graph validated. Heuristic triggers: task_started, kickoff_meeting, blocked_keyword, eighty_percent_complete, all_tasks_complete, invoice_paid, thirty_day_timeout. 11 public methods. Writes to `engagements` (12 cols, CHECK constraint on valid states) and `engagement_transitions` (audit trail). Auto-complete: `check_thirty_day_timeout()` transitions DELIVERED → COMPLETED after 30 days. **No `except Exception: pass`.** No silent failures. |
| IssueLifecycleManager | `lib/ui_spec_v21/issue_lifecycle.py` lines 125–766 | **10 states** (most complex). Critical design: RESOLVED is **conceptual only** — never persisted in DB. `_action_resolve()` atomically transitions to `regression_watch` and logs both transitions. DB constraint `chk_no_resolved_state` enforces this. 90-day regression watch period; `trigger_regression()` called when signal recurs. 16 public methods. Writes to `issues_v29` (30 cols) and `issue_transitions`. **No `except Exception: pass`.** |
| SignalLifecycleTracker | `lib/intelligence/signal_lifecycle.py` lines 101–526 | **6 persistence classifications:** NEW, RECENT (1-3 biz days), ONGOING (4-10), CHRONIC (11+), ESCALATING (severity increased), RESOLVING (improving). Auto-escalation: watch → warning after 14 business days. Writes to `signal_state` table. Feeds into InboxLifecycleManager via `create_inbox_item`. |

---

## Appendix D: Protected File Awareness

| File | Phase | Why it might be protected |
|------|-------|--------------------------|
| `api/spec_router.py` | §4.1 (new endpoint), §4.5 (payment_date fix) | Core API file |
| `api/wave2_router.py` | §4.2 (deletion) | API file |
| `api/server.py` | Not touched in this plan | Known critical file |

**Action:** Before starting any backend change, check `protected-files.txt` in the enforcement repo. If any target file is listed, stop and request blessing from Molham.

Frontend files (`time-os-ui/src/*`) are unlikely to be protected but verify.
