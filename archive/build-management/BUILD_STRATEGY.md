# MOH Time OS — Build Strategy

**Date:** 2026-02-25
**Governs:** Full product buildout across multiple Cowork sessions
**Companion:** `BUILD_PLAN.md` (detailed specs per phase)

---

## Why This Document Exists

Each Cowork session starts fresh with no memory. BUILD_PLAN.md has the *what*. This document has the *how* — the session architecture, sequencing rules, and drift prevention system that keeps 50+ PRs across dozens of sessions aimed at the same target.

---

## 1. Product Scope

### What "full buildout" means

Wire every production-ready backend capability to a frontend view. The backend has ~285 reachable endpoints. The current UI uses 45. The target is ~200+.

### Scope boundary

| In scope | Out of scope |
|----------|-------------|
| Backend cleanup: SQL injection, duplicate routes, silent-swallow exceptions, dead router ✅ DONE (PR #28) | 2 stub endpoints (capacity debt accrue/resolve — return 501) |
| All server.py production-ready endpoints (~140 after cleanup) | wave2_router (16 dead endpoints — delete in Phase -1) |
| All spec_router endpoints (61) | ~75 `except Exception` blocks that log+re-raise (narrow later, not Phase -1) |
| All intelligence_router unique endpoints (18) | GDPR/SAR compliance endpoints (5 — legal review needed) |
| All governance_router endpoints (5) | Intelligence full snapshot (45s — too slow for UI) |
| All action_router endpoints (7) | Paginated list variants (wire when data volumes grow) |
| All export_router endpoints (4) | |
| SSE (already wired — no work) | |
| 20 collector secondary tables (new query methods + endpoints) | |
| 9 database views (6 already queried, 3 to evaluate) | |

### The ten tracks

The buildout breaks into ten tracks. Each track is a coherent capability area that can be built, tested, and shipped independently once its prerequisites are met.

| # | Track | Phases | New pages | New/wired endpoints | Prerequisites |
|---|-------|--------|-----------|-------------------|---------------|
| T0 | Backend Cleanup | -1 | 0 | 0 (fix existing) | Protected files check |
| T1 | Design System & Foundation | 0, 1, 2 | 0 | 0 | T0 |
| T2 | Existing Page Redesign | 3, 4, 5 | 7 redesigned | ~19 newly wired | T1 |
| T3 | Task Management | 6 | 2 (list + detail) | ~15 | T1, T2 (shared components) |
| T4 | Priorities Workspace | 7 | 1 | ~10 | T1, T3 (task components reused) |
| T5 | Time & Capacity | 8 | 2 (schedule + capacity) | ~10 | T1, T3 (task references) |
| T6 | Commitments | 9 | 1 | ~6 | T1 |
| T7 | Governance & Admin | 11 | 3 (governance, approvals, data quality) | ~18 | T1 |
| T8 | Notifications, Digest & Email | 10 | 2 (notifications + digest/email) | ~8 | T1 |
| T9 | Project Enrollment | 12 | 1 (enrollment workflow) | ~7 | T1, T2 (client/project context) |
| T10 | Collector Data Depth | 13 | 0 (tabs on existing pages) | ~20 new endpoints | T2 (existing detail pages), new query_engine methods |

---

## 2. Phase Sequence

Tracks map to phases. Phases are ordered by dependency and value.

```
                    D1, D2 decisions
                          │
                          ▼
              ┌── Phase 0: Design System Foundation (T1)
              │
              ├── Phase 1: Slate Migration (T1 cont.) ──────────────┐
              │                                                      │ parallel
              ├── Phase 2: Layout Adoption (T1 cont.) ──────────────┘
              │         │
              │         ▼
              ├── Phase 3: Existing Page Redesign (T2)
              │         │
              │         ▼
              ├── Phase 4: Nav & Route Cleanup (T2 cont.)
              │         │
              │         ▼
              ├── Phase 5: Accessibility & Polish (T2 cont.)
              │
              │   ═══════════════════════════════════════
              │   Foundation complete. Tracks 3-10 below.
              │   ═══════════════════════════════════════
              │
              ├── Phase 6: Task Management (T3)
              │         │
              │         ├── Phase 7: Priorities Workspace (T4)
              │         │
              │         └── Phase 8: Time & Capacity (T5)
              │
              ├── Phase 9: Commitments (T6)  ─────────────────────┐
              │                                                     │ parallel
              ├── Phase 10: Notifications, Digest & Email (T8) ───┘
              │
              ├── Phase 11: Governance & Admin (T7)
              │
              ├── Phase 12: Project Enrollment (T9)
              │
              └── Phase 13: Collector Data Depth (T10)
```

### Phase definitions

**Phase 0-5 (Foundation + Redesign):** Already fully specified in BUILD_PLAN.md. ~15-20 PRs.

**Phase 6: Task Management**
Build the missing task management UI. Full CRUD, delegation, escalation, recall, blockers, dependency graph. This is the operational core — every other workflow references tasks.

| Page | Route | Endpoints wired |
|------|-------|----------------|
| Task List | `/tasks` | `GET /api/tasks` (filtered), `GET /api/priorities/advanced`, `GET /api/priorities/grouped`, `GET /api/delegations`, `GET /api/dependencies`, `POST /api/tasks` (create), `DELETE /api/tasks/{id}` |
| Task Detail | `/tasks/:taskId` | `GET /api/tasks/{id}`, `PUT /api/tasks/{id}`, `POST /api/tasks/{id}/notes`, `POST /api/tasks/{id}/delegate`, `POST /api/tasks/{id}/escalate`, `POST /api/tasks/{id}/recall`, `POST /api/tasks/{id}/block`, `DELETE /api/tasks/{id}/block/{blockerId}` |

Backend: Fix `useTasks()` response shape bug (`.tasks` vs `.items`). Add governance check UI for delegation/escalation (shows approval dialog when `requires_approval: true`).

Components: TaskForm, TaskActions (delegate/escalate/recall), BlockerList, DependencyGraph, DelegationSplit (by_me/to_me tabs).

~5-6 PRs.

**Phase 7: Priorities Workspace**
Rich priority management — advanced filtering, grouping, bulk actions, saved filters.

| Page | Route | Endpoints wired |
|------|-------|----------------|
| Priorities | `/priorities` | `GET /api/priorities/filtered`, `GET /api/priorities/advanced`, `GET /api/priorities/grouped`, `POST /api/priorities/bulk`, `POST /api/priorities/archive-stale`, `GET /api/filters`, `POST /api/priorities/{id}/complete`, `POST /api/priorities/{id}/snooze`, `POST /api/priorities/{id}/delegate` |

Components: PriorityFilters (advanced), GroupedPriorityView, BulkActionBar, SavedFilterSelector.

~3-4 PRs.

**Phase 8: Time & Capacity**
Time block scheduling and capacity management.

| Page | Route | Endpoints wired |
|------|-------|----------------|
| Schedule | `/schedule` | `GET /api/time/blocks`, `GET /api/time/summary`, `POST /api/time/schedule`, `POST /api/time/unschedule`, `GET /api/events`, `GET /api/day/{date}`, `GET /api/week` |
| Capacity | `/capacity` | `GET /api/capacity/lanes`, `GET /api/capacity/utilization`, `GET /api/capacity/forecast` |

Components: TimeBlockGrid (day view with lanes), WeekView, CapacityGauge, ForecastChart, ScheduleTaskDialog.

~4-5 PRs.

**Phase 9: Commitments**
Track commitments extracted from communications.

| Page | Route | Endpoints wired |
|------|-------|----------------|
| Commitments | `/commitments` | `GET /api/commitments`, `GET /api/commitments/untracked`, `GET /api/commitments/due`, `GET /api/commitments/summary`, `POST /api/commitments/{id}/link`, `POST /api/commitments/{id}/done` |

Components: CommitmentList, CommitmentSummaryCards, UntrackedCommitmentAlert, LinkToTaskDialog.

~2-3 PRs.

**Phase 10: Notifications, Digest & Email**
Notification center, weekly digest, email triage.

| Page | Route | Endpoints wired |
|------|-------|----------------|
| Notifications | `/notifications` | `GET /api/notifications`, `GET /api/notifications/stats`, `POST /api/notifications/{id}/dismiss`, `POST /api/notifications/dismiss-all` |
| Digest & Email | `/digest` | `GET /api/digest/weekly`, `GET /api/emails`, `POST /api/emails/{id}/mark-actionable`, `POST /api/emails/{id}/dismiss` |

Components: NotificationList, NotificationBadge (nav), WeeklyDigestView, EmailTriageList.

~3-4 PRs.

**Phase 11: Governance & Admin**
Governance controls, approval processing, data quality dashboard, bundle audit, calibration, search.

| Page | Route | Endpoints wired |
|------|-------|----------------|
| Governance | `/admin/governance` | `GET /api/governance`, `PUT /api/governance/{domain}`, `PUT /api/governance/{domain}/threshold`, `GET /api/governance/history`, `POST /api/governance/emergency-brake`, `DELETE /api/governance/emergency-brake` |
| Approvals | `/admin/approvals` | `GET /api/approvals`, `POST /api/approvals/{id}`, `POST /api/approvals/{id}/modify`, `POST /api/decisions/{id}` |
| Data Quality | `/admin/data-quality` | `GET /api/data-quality`, `POST /api/data-quality/cleanup/*` (4 types), `GET /api/data-quality/preview/{type}`, `POST /api/data-quality/recalculate-priorities`, `GET /api/control-room/fix-data`, `POST /api/control-room/fix-data/{type}/{id}/resolve` |

Also wired (no dedicated page):
- Bundle audit: `GET /api/bundles/*` (4 read), `POST /api/bundles/rollback*` (2 write) — accessed from Task Detail and Governance
- Calibration: `GET /api/calibration`, `POST /api/calibration/run` — button in Governance
- Search: `GET /api/search` — global search in nav bar

Components: GovernanceDomainCards, EmergencyBrakeToggle, ApprovalQueue, ApprovalDecisionDialog, DataQualityHealthScore, CleanupPreviewConfirm, FixDataList, BundleTimeline, SearchOverlay.

~5-6 PRs.

**Phase 12: Project Enrollment**
Project detection, candidate review, enrollment actions.

| Page | Route | Endpoints wired |
|------|-------|----------------|
| Enrollment | `/projects/enrollment` | `GET /api/projects/candidates`, `GET /api/projects/enrolled`, `GET /api/projects/detect`, `POST /api/projects/{id}/enrollment`, `POST /api/projects/propose` |

Also enhances existing project list: `GET /api/projects`, `GET /api/projects/{id}`.

Components: CandidateList, EnrollmentActionBar (enroll/reject/snooze/internal), DetectedProjectsAlert, ProjectProposalForm.

~2-3 PRs.

**Phase 13: Collector Data Depth**
Surface the 20 write-only collector tables. This requires new backend work — query_engine methods and API endpoints don't exist for these tables yet.

| Existing page | New tab/section | Collector tables surfaced | New endpoint needed |
|--------------|----------------|--------------------------|-------------------|
| Client Detail | Email Participants | gmail_participants | `GET /api/v2/clients/{id}/email-participants` |
| Client Detail | Attachments | gmail_attachments | `GET /api/v2/clients/{id}/attachments` |
| Client Detail | Xero Detail | xero_line_items, xero_credit_notes | `GET /api/v2/clients/{id}/invoice-detail` |
| Team Detail | Calendar Detail | calendar_attendees, calendar_recurrence_rules | `GET /api/v2/team/{id}/calendar-detail` |
| Task Detail | Asana Detail | asana_custom_fields, asana_subtasks, asana_stories, asana_task_dependencies, asana_attachments | `GET /api/v2/tasks/{id}/asana-detail` |
| Task Detail | Dependencies | asana_task_dependencies | (combined with above) |
| Operations | Chat Analytics | chat_reactions, chat_attachments, chat_space_metadata, chat_space_members | `GET /api/v2/chat/analytics` |
| Portfolio | Financial Detail | xero_contacts, xero_bank_transactions, xero_tax_rates | `GET /api/v2/financial/detail` |
| Operations | Asana Portfolio & Goals | asana_portfolios, asana_goals | `GET /api/v2/projects/asana-context` |
| Client Detail | Email Labels | gmail_labels | (combined with email-participants) |

Backend work: ~10 new query_engine methods, ~10 new spec_router endpoints.

Components: ParticipantNetwork (who talks to whom), AttachmentTimeline, InvoiceLineItemTable, CalendarAttendeeList, AsanaDetailPanel (subtasks + stories + custom fields), ChatSpaceOverview.

~5-6 PRs.

### Totals

| Metric | Phases 0-5 (foundation + redesign) | Phases 6-13 (new capabilities) | Full buildout |
|--------|--------------------------|-------------------|---------------|
| Pages | 14 (7 redesigned, 7 new sections) | ~12 new pages + tabs on existing | ~26 pages |
| Components | 9 new shared + page-specific | ~30 new | ~40+ new components |
| Endpoints wired to UI | 45 existing + 19 newly wired = ~64 | ~113 newly wired (T3-T10 sum) | ~177 of ~285 reachable (~62%) |
| Hooks | 16 existing + new | ~45+ new | ~60+ |
| New backend endpoints | 1 | ~10 (collector depth) | ~11 |
| PRs | ~15-20 | ~30-38 | ~50-58 |
| Estimated sessions | ~8-12 | ~15-20 | ~25-35 |

Note: The remaining ~108 unwired endpoints are duplicates (v2 shadows server.py), stubs (501), deferred (GDPR/SAR, paginated variants), or system internals (health, metrics, debug, sync triggers) that don't need frontend views.

---

## 3. Session Architecture

### Session types

Every Cowork session is one of four types. The type determines what the session does and how it proves it's done.

**Type A: Build Session**
Writes code. Produces 1-3 PRs. Each PR is a self-contained change with passing pre-commit.

**Type B: Verification Session**
Reads code. Runs tests, linters, visual checks. Produces a verification report. No code changes unless fixing what it finds.

**Type C: Plan Update Session**
Reads the current state of BUILD_PLAN.md and BUILD_STRATEGY.md. Updates them based on what's been completed, what's changed, or what new information has been discovered. Produces updated documents.

**Type D: Investigation Session**
Explores a specific technical question needed before a build session can start. Produces findings that feed into plan updates.

### Session contract

Every session begins by reading this section and executing the checklist.

#### Entry checklist (MANDATORY — do this before writing any code)

```
0. Read HANDOFF.md FIRST — it has the exact next task, file paths, rules, and reading order
1. Read CLAUDE.md — coding standards, sandbox rules, verification requirements
2. Read BUILD_STRATEGY.md (this file) §3 — entry/exit checklists, session contract
3. Read BUILD_PLAN.md — the section referenced by HANDOFF.md "What's Next"
4. Read SESSION_LOG.md — what's done, current state, lessons learned
5. Read the SOURCE FILES for the assigned work (all files listed in HANDOFF.md)
6. Verify preconditions for the assigned work:
   a. Are prerequisite phases marked complete? (SESSION_LOG.md + BUILD_PLAN.md)
   b. Are blocking PRs merged? (check git log --oneline -20)
   c. Are there uncommitted changes? (git status)
7. Read CLAUDE.md "Documentation Rules" section — understand what triggers doc updates
8. State what this session will do (session type + specific deliverables)
9. Only then begin work — DO NOT claim readiness without completing steps 0-7
```

#### Exit checklist (MANDATORY — do this before session ends)

```
1. Run pre-commit on all changed files
2. List PRs created or code ready for commit
3. List what was completed vs what was planned
4. Update SESSION_LOG.md:
   a. Add entry for this session (date, type, what was done, PRs, lessons learned)
   b. Update "Current phase" and "Current track" if phase completed
   c. Update "Blocked by" if state changed
   d. Write "Next session" instructions (specific, actionable, with file paths)
5. Update HANDOFF.md:
   a. Rewrite "What Just Happened" for this session's work
   b. Rewrite "What's Next" for the next session's task (batch plan, file list, verification steps)
   c. Update "Key Rules" if new lessons were learned
   d. Update "Documents to Read" to point at the correct BUILD_PLAN.md section
6. Update CLAUDE.md if any new rules or patterns were discovered
7. If a phase completed, mark it ✅ COMPLETE in BUILD_PLAN.md
8. If anything else in BUILD_PLAN.md needs updating, update it
9. Give Molham the commit/push commands
10. VERIFY: all three doc files (SESSION_LOG.md, HANDOFF.md, CLAUDE.md) are in git add
11. VERIFY: re-read HANDOFF.md top to bottom — would a fresh session know exactly what to do?
```

### SESSION_LOG.md format

This file is the living record. Each session reads it first and writes to it last.

```markdown
# Session Log

## Current State
- **Current phase:** Phase 3 (Page Redesign)
- **Current track:** T2 (Existing Page Redesign)
- **Blocked by:** nothing
- **Next session:** Type A build session — Portfolio page (§3.1). Start with
  PortfolioPage.tsx. Wire usePortfolioOverview, usePortfolioRisks, useFinancialAging hooks.
  Components needed: PortfolioHealthScore, RiskList, ARAgingSummary.
  Reference: BUILD_PLAN.md §3.1 lines 519-545.

## Session History

### Session 12 — 2026-03-08
- **Type:** A (Build)
- **Phase:** Phase 3
- **Work done:** Created PortfolioPage.tsx, wired 3 new hooks, created
  PortfolioHealthScore and RiskList components
- **PRs:** Ready for commit — `git add ... && git commit -m "..."`
- **Remaining:** ARAgingSummary component, loading/error states
- **Next session:** Type A — Complete Portfolio page (ARAgingSummary,
  loading/error/empty states, responsive layout). Then start Inbox enhancement (§3.2).
```

---

## 4. Drift Prevention Rules

These rules exist because sessions don't share memory. Without them, each session reinvents patterns, creates inconsistencies, and drifts from the plan.

### Rule 1: Follow existing patterns

Before writing any new component, hook, or utility:
- Grep for similar existing implementations
- Match the pattern exactly (naming, file location, export style, error handling)
- If the pattern is wrong, fix the pattern everywhere — don't create a second pattern

### Rule 2: One session, one phase section

A build session works on ONE section of one phase. It does not jump ahead, skip around, or "quickly fix" something in another phase. If it discovers work needed elsewhere, it notes it in SESSION_LOG.md under "Discovered work" and moves on.

### Rule 3: No architectural changes without a plan update session

If a session discovers that the plan's approach won't work (wrong endpoint, missing data, component doesn't compose), it stops, documents the issue in SESSION_LOG.md, and flags it for a Type C session. It does NOT improvise an alternative.

### Rule 4: Components go in the right place

```
time-os-ui/src/
  components/
    shared/          ← Reusable across pages (PageLayout, Card, Badge, etc.)
    auth/            ← Auth context (don't touch)
  pages/             ← Page-level components (one per route)
  hooks/             ← Shared hooks (if created)
  lib/
    api.ts           ← Control room fetch functions
    hooks.ts         ← Control room hooks
  intelligence/
    api.ts           ← Intelligence fetch functions
    hooks.ts         ← Intelligence hooks
  design/system/
    tokens.css       ← Design tokens (single source)
```

New hooks for server.py endpoints go in `lib/api.ts` + `lib/hooks.ts` (same pattern as existing control room hooks). New hooks for intelligence endpoints go in `intelligence/api.ts` + `intelligence/hooks.ts`.

### Rule 5: Naming conventions

| Thing | Convention | Example |
|-------|-----------|---------|
| Page component | `{Name}Page.tsx` | `TaskListPage.tsx` |
| Shared component | `{Name}.tsx` in `components/shared/` | `DataGrid.tsx` |
| Hook | `use{Resource}()` | `useCommitments()` |
| Fetch function | `fetch{Resource}()` | `fetchCommitments()` |
| Route | lowercase-kebab | `/admin/data-quality` |
| CSS class (new) | Use tokens.css custom properties | `var(--accent)` |
| CSS class (Tailwind) | `slate-*` equivalents only | `text-slate-400` |

### Rule 6: Backend changes require protected files check

Before any PR that modifies files in `api/`:
1. Check `protected-files.txt` in Fleezyflo/enforcement
2. If the target file is listed, stop and request blessing from Molham
3. Document the check in the PR description

### Rule 7: Response shape verification before wiring

Before wiring any endpoint to the frontend, the session must read the actual endpoint implementation and verify the response shape. Do not trust docstrings, comments, or BUILD_PLAN.md descriptions alone. If the shape doesn't match what the plan says, update the plan and adjust the frontend code.

### Rule 8: No silent error handling

Every hook must surface errors to the UI. No `catch (e) {}`. No `|| []` without a loading/error state that explains what happened. The `except Exception: pass` patterns in spec_router are bugs — don't replicate them in the frontend.

### Rule 9: No inline suppressions — fix root causes

Never add `nosec`, `noqa`, or `# type: ignore` to bypass a linter/scanner/type-checker. Every warning is a real issue until proven otherwise. Fix the root cause:

| Warning | Wrong response | Right response |
|---------|---------------|----------------|
| B324/S324 (MD5) | `# nosec B324` | Replace with `hashlib.sha256` |
| B108/S108 (/tmp) | `# nosec B108` | Use `tempfile.gettempdir()` |
| B310/S310 (urlopen) | `# nosec B310` | Use `httpx.get/post` with timeout |
| S113 (no timeout) | `# noqa: S113` | Add `timeout=30` parameter |
| S110/S112 (silent except) | `# noqa: S110` | Add `logging.debug()` with context |
| mypy type error | `# type: ignore` | Fix the type annotation or add proper guard |

If a tool is genuinely wrong (confirmed false positive), explain why in a comment and get Molham's approval before suppressing.

### Rule 10: Verify all gates before committing

Before giving Molham a commit command:
1. Run `ruff check` on changed files — must be clean
2. Run `ruff format --check` on changed files — must be clean
3. Stage ALL modified files (prevents stash conflicts when pre-commit runs ruff-format)

Before giving Molham a push command:
1. Confirm all 7 pre-push gates will pass: ruff lint, ruff format, fast tests, mypy (zero baseline), secrets scan, UI typecheck, guardrails
2. If unsure about mypy, run `python scripts/check_mypy_baseline.py` first

### Rule 11: Document as you go

1. Update SESSION_LOG.md after EACH commit, not at session end
2. If you discover a new coding rule, add it to CLAUDE.md immediately
3. If you complete a phase, mark it in BUILD_PLAN.md immediately
4. Never defer documentation to "later" -- it doesn't happen

### Rule 12: Commit message format (Session 7)

Commit messages must follow these rules exactly:

- **Subject line max 72 characters.** Longer subjects fail CI governance checks.
- **Lowercase after prefix:** `feat: wrap 9 pages` not `feat: Wrap 9 pages`.
- **Format:** `type: short description` where type is `feat`, `fix`, `refactor`, `docs`, `chore`.
- **Use `--` not em dash** in commit messages to avoid encoding issues.
- **Pre-commit failure = commit didn't happen.** Never `--amend` after a hook failure -- fix and commit fresh.
- **Check branch first.** `git branch --show-current` before creating. If branch is in a worktree, `git branch -D` fails -- check `git worktree list`.
- **Only prettier specific files.** Never `prettier --write src/` -- only the files changed.
- **Auto-merge PRs.** Always `gh pr merge --merge --auto` after creating. Watch with `gh pr checks <N> --watch`.
- **Force-push after amend.** If amending a pushed commit, use `git push --force-with-lease`.

---

## 5. Quality Gates

### Per-PR gate

Every PR must pass before Molham commits:

- [ ] `ruff check` clean on all changed Python files
- [ ] `ruff format --check` clean on all changed Python files
- [ ] `bandit -r` clean on all changed Python files
- [ ] TypeScript compiles (`npx tsc --noEmit` — run on Mac, not sandbox)
- [ ] No new `except Exception: pass`
- [ ] No new `return {}` or `return []` on error paths
- [ ] No `shell=True` in subprocess
- [ ] No f-string SQL
- [ ] No hardcoded colors (use tokens.css)
- [ ] Loading, error, and empty states for every data-fetching component
- [ ] Response shape verified against actual endpoint code

### Per-phase gate

Before a phase can be marked complete:

- [ ] All PRs in the phase are merged to main
- [ ] Visual check: every page in the phase renders correctly
- [ ] No console errors in browser dev tools
- [ ] All endpoints wired in this phase are reachable (manual curl or browser network tab)
- [ ] SESSION_LOG.md updated with completion status
- [ ] BUILD_PLAN.md verification log updated

### Milestone gates

| After phase | Gate |
|-------------|------|
| Phase 5 | Full visual audit of all 14 redesigned pages. Every page uses PageLayout, tokens.css, consistent loading/error/empty states. No hardcoded colors remain. |
| Phase 8 | Task management, priorities, and time/capacity all functional. Core operational workflow works end-to-end: create task → prioritize → schedule → delegate → complete. |
| Phase 11 | Governance and admin tools functional. Approval flow works: governance triggers decision → user approves/rejects → side effects execute. |
| Phase 13 | All 20 collector tables surfaced. Full buildout complete. Endpoint coverage >70% of reachable endpoints. |

---

## 6. Parallel Work Opportunities

Some phases can run in parallel if Molham is working with multiple sessions or wants to interleave:

```
After Phase 5 completes, these can run in parallel:
  ├── Phase 6 (Task Management) ← highest priority
  ├── Phase 9 (Commitments) ← independent
  ├── Phase 10 (Notifications) ← independent
  └── Phase 11 (Governance) ← independent

After Phase 6 completes:
  ├── Phase 7 (Priorities) ← needs task components
  └── Phase 8 (Time & Capacity) ← needs task references

After Phase 5 + T2 client/project pages:
  ├── Phase 12 (Project Enrollment)
  └── Phase 13 (Collector Depth) ← needs detail pages to exist
```

---

## 7. Risk Register

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Protected files block backend PRs | Delays phases with API changes | Check protected-files.txt before starting any backend work. Batch API changes to minimize blessing requests. |
| server.py endpoint returns unexpected shape | Frontend wires to wrong data | Rule 7 — verify response shape firsthand before wiring. Phases 0-5 endpoints already verified (see BUILD_PLAN.md Appendix C). Phase 6-13 endpoints need verification in their build sessions. |
| Session drift — new session reinvents existing patterns | Inconsistent codebase, wasted effort | Rules 1-5, SESSION_LOG.md "Next session" instructions. |
| Scope creep within sessions | PRs grow too large, harder to review | Rule 2 — one phase section per session. If PR exceeds ~300 lines changed, split it. |
| Collector tables have stale/bad data | New endpoints surface garbage | Phase 13 includes data quality check per table before wiring. |
| Auth bypass means no permission UI | Governance/approvals work but anyone can do anything | Acknowledged. Single-user system. Auth is a future track, not in this buildout. |
| 20 new query_engine methods (Phase 13) could have schema drift | Queries fail at runtime | Write methods against live DB schema, not schema.py (live has 121 tables vs 73 declared). |

---

## 8. Files This Strategy Governs

| File | Purpose | Who updates it |
|------|---------|---------------|
| `BUILD_STRATEGY.md` | This file. Sequencing, rules, session architecture. | Type C sessions only. |
| `BUILD_PLAN.md` | Detailed specs per phase. Endpoint maps, component specs, verification log. | Type C sessions, or build sessions that discover spec corrections. |
| `SESSION_LOG.md` | Living record of session history and next-session instructions. | Every session (exit checklist). |
| `time-os-ui/src/` | All frontend code. | Type A sessions. |
| `api/spec_router.py` | New endpoints (Phase 13). | Type A sessions (with protected files check). |
| `lib/query_engine.py` | New query methods (Phase 13). | Type A sessions. |

---

## 9. How to Start a New Session

Copy-paste this to the start of every new Cowork session:

```
Read these files in order:
1. HANDOFF.md — the exact next task, file paths, rules, and reading order
2. CLAUDE.md — coding standards, sandbox rules, verification requirements
3. BUILD_STRATEGY.md §3 — entry/exit checklists, session contract
4. BUILD_PLAN.md — the section referenced by HANDOFF.md's "What's Next"
5. SESSION_LOG.md — what's done, current state, lessons learned

Then execute the entry checklist from BUILD_STRATEGY.md §3.
Do NOT start work until all 5 files are read and all source files for the assigned task are read.
```

This is the single instruction that prevents drift. Every session starts from the same anchor point.
