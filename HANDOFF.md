# Session Handoff

**Last updated:** 2026-03-02, Session 18 (Phase 9 + Phase 10 + Phase 11 built, pending commits)
**Branch:** `main` (need feature branches for Phase 9, then Phase 10, then Phase 11)

## What Just Happened

Session 18: Built Phase 11 (Governance & Admin) in parallel with Session 10. Phases 9, 10, and 11 all pending commit from Sessions 16-18.

### Phase 11 Summary
- **11.1:** Added ~20 fetch/mutation functions + `deleteJson<T>()` helper + ~16 types to `lib/api.ts`
- **11.2:** Added 11 hooks to `lib/hooks.ts`
- **11.3:** Created Governance page (~155 lines) with 4 tabs, SummaryGrid, EmergencyBrakeToggle
- **11.4:** Created Approvals page (~85 lines) with risk-level cards, ApprovalQueue, pending actions
- **11.5:** Created DataQuality page (~65 lines) with health score, cleanup preview, recalculate
- **11.6:** Created 6 governance components (DomainCards, EmergencyBrake, BundleTimeline, ApprovalQueue, DataQualityHealthScore, CleanupPreviewConfirm)
- **11.7:** Created SearchOverlay with Cmd/Ctrl+K, debounced search, keyboard navigation
- **11.9:** Added 3 routes + Admin nav item + SearchOverlay in RootLayout
- **11.8:** Deferred (export buttons on list pages)

### Phase 10 Summary
- **10.1:** Added 8 fetch/mutation functions to `lib/api.ts`: `fetchNotifications()`, `fetchNotificationStats()`, `dismissNotification()`, `dismissAllNotifications()`, `fetchWeeklyDigest()`, `fetchEmails()`, `markEmailActionable()`, `dismissEmail()`. 6 new types.
- **10.2:** Added 4 hooks: `useNotifications()`, `useNotificationStats()`, `useWeeklyDigest()`, `useEmails()`.
- **10.3:** Created Notifications page (~90 lines) with stats bar, show-dismissed toggle, dismiss-all button.
- **10.4:** Created Digest page (~110 lines) with Weekly Digest + Email Triage tabs, email filter dropdown.
- **10.5:** Created 4 components: NotificationList (type icons, dismiss), NotificationBadge (unread count), WeeklyDigestView (period stats, item lists), EmailTriageList (actionable/dismiss actions).
- **10.6:** Added NotificationBadge to nav bar (desktop + mobile, non-lazy).
- **10.7:** Added `/notifications` and `/digest` routes, nav items between Commitments and Clients.

## What's Next

### Step 1: Commit Phase 9

Run from `~/clawd/moh_time_os`:

```bash
# 1. Verify types compile
cd time-os-ui && npx tsc --noEmit && cd ..

# 2. Format new/changed files (Phase 9 files only)
cd time-os-ui && pnpm exec prettier --write \
  src/lib/api.ts \
  src/lib/hooks.ts \
  src/pages/Commitments.tsx \
  src/components/commitments/CommitmentList.tsx \
  src/components/commitments/LinkToTaskDialog.tsx \
  src/router.tsx \
  && cd ..

# 3. Regenerate system map (new routes added)
uv run python scripts/generate_system_map.py

# 4. Create branch and commit
git checkout -b phase-9-commitments
git add \
  time-os-ui/src/lib/api.ts \
  time-os-ui/src/lib/hooks.ts \
  time-os-ui/src/pages/Commitments.tsx \
  time-os-ui/src/components/commitments/CommitmentList.tsx \
  time-os-ui/src/components/commitments/LinkToTaskDialog.tsx \
  time-os-ui/src/router.tsx \
  docs/system-map.json \
  SESSION_LOG.md \
  HANDOFF.md

git commit -m "$(cat <<'EOF'
feat: add commitments page with list, untracked alert, link-to-task

Phase 9 -- commitments tracking UI. Wires 6 server.py endpoints:
GET /api/commitments, /api/commitments/untracked,
/api/commitments/due, /api/commitments/summary,
POST /api/commitments/{id}/link, POST /api/commitments/{id}/done.

New page with three tabs (All, Untracked, Due Soon), summary cards,
status filter, untracked alert banner, and LinkToTaskDialog.

Components: CommitmentList, LinkToTaskDialog.
Route: /commitments (nav between Capacity and Clients).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"

# 5. Push and create PR
git push -u origin phase-9-commitments
gh pr create --title "feat: phase 9 -- commitments page" --body "$(cat <<'EOF'
## Summary
- Wires 6 commitment endpoints from server.py
- New Commitments page with All/Untracked/Due tabs, summary cards, status filter
- CommitmentList component with status dots, link/done actions
- LinkToTaskDialog for linking untracked commitments to tasks
- Nav item between Capacity and Clients, system-map regenerated

## Files
- `lib/api.ts` — 4 fetch + 2 mutation functions, 3 new types
- `lib/hooks.ts` — 4 new hooks
- `pages/Commitments.tsx` — new page (~190 lines)
- `components/commitments/CommitmentList.tsx` — new component
- `components/commitments/LinkToTaskDialog.tsx` — new component
- `router.tsx` — route + nav item

## Test plan
- [ ] Commitments page loads at /commitments
- [ ] All/Untracked/Due tabs render commitment lists
- [ ] Status filter dropdown filters by status
- [ ] Untracked alert shows when untracked count > 0
- [ ] Link Task button opens dialog, linking updates list
- [ ] Done button marks commitment done, list refreshes
- [ ] Nav shows Commitments between Capacity and Clients
EOF
)"
gh pr merge --merge --auto
gh pr checks --watch
```

### Step 2: After Phase 9 merges, commit Phase 10

```bash
# 1. Switch to main and pull
git checkout main && git pull

# 2. Verify types compile (Phase 10 changes now on top of merged Phase 9)
cd time-os-ui && npx tsc --noEmit && cd ..

# 3. Format Phase 10 files
cd time-os-ui && pnpm exec prettier --write \
  src/lib/api.ts \
  src/lib/hooks.ts \
  src/pages/Notifications.tsx \
  src/pages/Digest.tsx \
  src/components/notifications/NotificationList.tsx \
  src/components/notifications/NotificationBadge.tsx \
  src/components/notifications/WeeklyDigestView.tsx \
  src/components/notifications/EmailTriageList.tsx \
  src/router.tsx \
  && cd ..

# 4. Regenerate system map (new /notifications and /digest routes)
uv run python scripts/generate_system_map.py

# 5. Create branch and commit
git checkout -b phase-10-notifications-digest
git add \
  time-os-ui/src/lib/api.ts \
  time-os-ui/src/lib/hooks.ts \
  time-os-ui/src/pages/Notifications.tsx \
  time-os-ui/src/pages/Digest.tsx \
  time-os-ui/src/components/notifications/NotificationList.tsx \
  time-os-ui/src/components/notifications/NotificationBadge.tsx \
  time-os-ui/src/components/notifications/WeeklyDigestView.tsx \
  time-os-ui/src/components/notifications/EmailTriageList.tsx \
  time-os-ui/src/router.tsx \
  docs/system-map.json \
  SESSION_LOG.md \
  HANDOFF.md

git commit -m "$(cat <<'EOF'
feat: add notifications and digest pages with email triage

Phase 10 -- notifications, weekly digest, email triage UI.
Wires 8 server.py endpoints: GET /api/notifications,
GET /api/notifications/stats, POST dismiss/dismiss-all,
GET /api/digest/weekly, GET /api/emails,
POST mark-actionable, POST dismiss.

Notifications page: stats bar, show-dismissed toggle, dismiss-all.
Digest page: weekly summary tab + email triage tab.
NotificationBadge in nav shows unread count.

Components: NotificationList, NotificationBadge,
WeeklyDigestView, EmailTriageList.
Routes: /notifications, /digest.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"

# 6. Push and create PR
git push -u origin phase-10-notifications-digest
gh pr create --title "feat: phase 10 -- notifications and digest pages" --body "$(cat <<'EOF'
## Summary
- Wires 8 notification/digest/email endpoints from server.py
- New Notifications page with stats bar, dismiss actions, show-dismissed toggle
- New Digest page with Weekly Digest and Email Triage tabs
- NotificationBadge component shows unread count in nav bar
- 4 new components: NotificationList, NotificationBadge, WeeklyDigestView, EmailTriageList

## Files
- `lib/api.ts` — 8 fetch/mutation functions, 6 new types
- `lib/hooks.ts` — 4 new hooks
- `pages/Notifications.tsx` — new page (~90 lines)
- `pages/Digest.tsx` — new page (~110 lines)
- `components/notifications/` — 4 new components
- `router.tsx` — 2 routes + 2 nav items + NotificationBadge

## Test plan
- [ ] Notifications page loads at /notifications
- [ ] Stats bar shows total/unread/dismissed counts
- [ ] Dismiss button removes notification, stats update
- [ ] Dismiss All clears all, stats update
- [ ] Show dismissed toggle includes dismissed notifications
- [ ] NotificationBadge shows unread count in nav
- [ ] Digest page loads at /digest
- [ ] Weekly Digest tab shows completed/slipped/archived
- [ ] Email Triage tab lists emails with filter dropdown
- [ ] Mark Actionable button updates email state
- [ ] Dismiss email removes from unread list
EOF
)"
gh pr merge --merge --auto
gh pr checks --watch
```

### Step 3: After Phase 10 merges, commit Phase 11

```bash
# 1. Switch to main and pull
git checkout main && git pull

# 2. Verify types compile (Phase 11 changes now on top of merged Phases 9+10)
cd time-os-ui && npx tsc --noEmit && cd ..

# 3. Format Phase 11 files
cd time-os-ui && pnpm exec prettier --write \
  src/lib/api.ts \
  src/lib/hooks.ts \
  src/pages/Governance.tsx \
  src/pages/Approvals.tsx \
  src/pages/DataQuality.tsx \
  src/components/governance/GovernanceDomainCards.tsx \
  src/components/governance/EmergencyBrakeToggle.tsx \
  src/components/governance/BundleTimeline.tsx \
  src/components/governance/ApprovalQueue.tsx \
  src/components/governance/DataQualityHealthScore.tsx \
  src/components/governance/CleanupPreviewConfirm.tsx \
  src/components/governance/SearchOverlay.tsx \
  src/router.tsx \
  && cd ..

# 4. Regenerate system map (new /admin/* routes)
uv run python scripts/generate_system_map.py

# 5. Create branch and commit
git checkout -b phase-11-governance-admin
git add \
  time-os-ui/src/lib/api.ts \
  time-os-ui/src/lib/hooks.ts \
  time-os-ui/src/pages/Governance.tsx \
  time-os-ui/src/pages/Approvals.tsx \
  time-os-ui/src/pages/DataQuality.tsx \
  time-os-ui/src/components/governance/GovernanceDomainCards.tsx \
  time-os-ui/src/components/governance/EmergencyBrakeToggle.tsx \
  time-os-ui/src/components/governance/BundleTimeline.tsx \
  time-os-ui/src/components/governance/ApprovalQueue.tsx \
  time-os-ui/src/components/governance/DataQualityHealthScore.tsx \
  time-os-ui/src/components/governance/CleanupPreviewConfirm.tsx \
  time-os-ui/src/components/governance/SearchOverlay.tsx \
  time-os-ui/src/router.tsx \
  docs/system-map.json \
  SESSION_LOG.md \
  HANDOFF.md \
  BUILD_PLAN.md

git commit -m "$(cat <<'EOF'
feat: add governance, approvals, data quality pages with search

Phase 11 -- governance and admin UI. Wires ~30 endpoints across
governance_router, action_router, export_router, and server.py.

New pages: Governance (domains, brake, history, bundles, calibration),
Approvals (queue, risk levels, pending actions),
Data Quality (health score, cleanup preview, recalculate).

SearchOverlay with Cmd/Ctrl+K global shortcut.
7 new components in components/governance/.
Routes: /admin/governance, /admin/approvals, /admin/data-quality.

large-change

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"

# 6. Push and create PR
git push -u origin phase-11-governance-admin
gh pr create --title "feat: phase 11 -- governance and admin pages" --body "$(cat <<'EOF'
## Summary
- Wires ~30 governance/approval/data-quality/search/action endpoints
- New Governance page with domain cards, emergency brake, history, bundles, calibration
- New Approvals page with approval queue, risk levels, pending actions
- New Data Quality page with health score gauge, cleanup preview, recalculate
- SearchOverlay component with Cmd/Ctrl+K keyboard shortcut
- 7 new components in components/governance/
- 11 new hooks, ~20 new fetch/mutation functions, deleteJson helper

## Files
- `lib/api.ts` — ~480 lines added (types, fetch/mutation functions, deleteJson)
- `lib/hooks.ts` — 11 new hooks (~55 lines)
- `pages/Governance.tsx` — new page (~155 lines)
- `pages/Approvals.tsx` — new page (~85 lines)
- `pages/DataQuality.tsx` — new page (~65 lines)
- `components/governance/` — 7 new components
- `router.tsx` — 3 routes, nav item, SearchOverlay in layout

## Test plan
- [ ] Governance page loads at /admin/governance
- [ ] Domain cards show mode selector and threshold editor
- [ ] Emergency brake toggle activates/releases
- [ ] History tab shows governance action log
- [ ] Bundles tab shows bundle timeline with rollback
- [ ] Calibration tab runs calibration and shows results
- [ ] Approvals page loads at /admin/approvals
- [ ] Approval queue shows approve/reject buttons
- [ ] Data Quality page loads at /admin/data-quality
- [ ] Health score gauge renders with color coding
- [ ] Cleanup preview shows items then confirms
- [ ] Cmd/Ctrl+K opens search overlay
- [ ] Search returns results with type icons
- [ ] Arrow keys navigate, Enter selects result
- [ ] Admin nav item appears in navigation

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
gh pr merge --merge --auto
gh pr checks --watch
```

### After Phase 11 merges: Phase 12 (Project Enrollment)
Phase 12 api.ts and hooks.ts code already exists (added by parallel session). Need page + components + routes.

## Key Rules (learned hard way in Sessions 1-18)

1. **No bypasses.** Never add `nosec`, `noqa`, or `type: ignore`. Fix the root cause.
2. **Stage everything.** Before committing, `git add` all modified files to prevent ruff-format stash conflicts.
3. **Verify gates.** Run ruff check + ruff format + tests locally before giving commit commands.
4. **Document immediately.** Update SESSION_LOG.md after each commit, not at session end.
5. **Zero mypy baseline.** `.mypy-baseline.txt` is empty. Keep it that way.
6. **Never format from sandbox.** Use `uv run pre-commit run ruff-format --files` on Mac. Sandbox ruff version differs.
7. **Protected files need blessing.** Changes to ci.yml, pyproject.toml, .pre-commit-config.yaml only take effect after blessing in enforcement repo.
8. **Governance keywords on HEAD.** Large PRs need "large-change" and deletion rationale in the latest commit message.
9. **Prettier for ALL modified .tsx/.ts files.** CI runs `prettier --check` on `src/**/*.{ts,tsx,css}`. Sandbox can't run prettier. Include `cd time-os-ui && pnpm exec prettier --write <files> && cd ..` in commit commands.
10. **Conventional commit casing.** Description starts lowercase after type prefix: `feat: phase 1` not `feat: Phase 1`.
11. **Discovery before fix commands.** Investigate actual state before giving fix commands. Never use placeholders in command blocks.
12. **Don't claim readiness without reading all files.** Read HANDOFF.md, CLAUDE.md, BUILD_STRATEGY.md, BUILD_PLAN.md, SESSION_LOG.md, AND the source files for the assigned work before starting.
13. **Script-based migration for bulk replacements.** For 400+ changes, write a script with dry-run mode, verify output, then apply.
14. **Run tsc before giving commit commands.** Can't run from sandbox (no node_modules) but must verify types compile on Mac before claiming done.
15. **Update ALL docs after each change.** SESSION_LOG.md + HANDOFF.md + CLAUDE.md (if new rules). Don't defer.
16. **Commit subject max 72 chars.** Format: `type: short description` (lowercase after prefix).
17. **Use `--` not em dash in commits.** Avoids encoding issues in commit messages.
18. **Pre-commit failure means commit didn't happen.** Don't use `--amend` after a hook failure -- fix and commit fresh.
19. **Check branch before creating.** `git branch --show-current` first.
20. **Only prettier specific files.** Never `prettier --write src/` -- only the files you changed.
21. **Auto-merge PRs.** Always `gh pr merge --merge --auto` after creating. Watch with `gh pr checks <N> --watch`.
22. **Force-push after amend.** If you amend a pushed commit, use `git push --force-with-lease`.
23. **Regenerate system-map after adding/removing UI routes.** `uv run python scripts/generate_system_map.py` then include `docs/system-map.json` in the commit.
24. **Never run git from sandbox.** Creates stale `.git/index.lock` that blocks Mac operations.
25. **React hooks before early returns.** ESLint `react-hooks/rules-of-hooks` catches hooks called after `if (...) return`. Always place hooks at the top of the component body.
26. **When removing file-level noqa, check ALL lines.** Removing S608 from a file-level suppression exposes every f-string SQL in that file. Convert them all before removing the suppression.
27. **CI runs pre-commit on ALL files.** Pre-existing lint/format/end-of-file issues in any file will block your PR, even if you didn't touch that file. Run `uv run pre-commit run -a` locally to catch these.
28. **Governance Checks require ADR.** Changes to lib/safety/, lib/migrations/, or api/server.py trigger the ADR requirement check. Add a `docs/adr/NNNN-*.md` file to the PR.
29. **Check mergeable state when auto-merge stalls.** `gh pr view N --json mergeStateStatus,mergeable` -- CONFLICTING means rebase needed.
30. **Always run commands from the correct directory.** Session 12 wasted time because commit commands ran from ~/enforcement instead of ~/clawd/moh_time_os.
31. **Cross-file consistency on every doc update.** After updating any doc, verify all four files (SESSION_LOG, HANDOFF, CLAUDE, BUILD_PLAN) are consistent.
32. **BUILD_PLAN.md is a documentation file.** Mark phases complete with session number the moment the phase PR merges.
33. **Wrap derived arrays in useMemo.** `const items = data?.items || []` creates unstable references. Use `useMemo(() => data?.items ?? [], [data])` to prevent react-hooks/exhaustive-deps warnings.
34. **Prettier api.ts after Phase changes.** api.ts accumulates additions across phases. Always include it in the prettier step even if you think only "small" changes were made.

## Documents to Read (in order)

1. **This file (HANDOFF.md)** -- you're reading it, now follow the order below
2. `CLAUDE.md` -- coding standards, sandbox rules, verification requirements
3. `BUILD_STRATEGY.md` §3 -- entry/exit checklists, session contract
4. `BUILD_PLAN.md` "Phase 12: Project Enrollment" -- the next spec
5. `SESSION_LOG.md` -- what's done, current state, lessons learned

## Quick Reference

- **Repo:** `moh-time-os` on branch `main`
- **Main is protected.** Cannot push directly. ALL changes need a feature branch + PR + CI green + merge.
- **SQL builder:** `lib/safe_sql.py` -- use for all dynamic SQL identifier interpolation
- **UI root:** `time-os-ui/src/`
- **Design tokens:** `design/system/tokens.css`
- **Chart colors:** `time-os-ui/src/intelligence/components/chartColors.ts`
- **Layout components:** `time-os-ui/src/components/layout/` (PageLayout, SummaryGrid, MetricCard, TabContainer)
- **Task components:** `time-os-ui/src/components/tasks/` (TaskCard, TaskActions, ApprovalDialog, DelegationPanel, TaskNotesList)
- **Priority components:** `time-os-ui/src/components/priorities/` (PriorityFilters, GroupedPriorityView, BulkActionBar, SavedFilterSelector)
- **Schedule components:** `time-os-ui/src/components/schedule/` (TimeBlockGrid, WeekView, ScheduleTaskDialog)
- **Capacity components:** `time-os-ui/src/components/capacity/` (CapacityGauge, ForecastChart)
- **Commitment components:** `time-os-ui/src/components/commitments/` (CommitmentList, LinkToTaskDialog)
- **Notification components:** `time-os-ui/src/components/notifications/` (NotificationList, NotificationBadge, WeeklyDigestView, EmailTriageList)
- **Governance components:** `time-os-ui/src/components/governance/` (GovernanceDomainCards, EmergencyBrakeToggle, BundleTimeline, ApprovalQueue, DataQualityHealthScore, CleanupPreviewConfirm, SearchOverlay)
- **Accent color (D1):** `#3b82f6` (blue)
- **Tertiary text (D2):** `slate-400` / `#94a3b8` (now `var(--grey-light)`)
- **Do NOT run:** `uv sync`, `pnpm install`, `ruff format`, `npx`, or dev servers from the sandbox
- **To format Python files:** give Molham `uv run pre-commit run ruff-format --files <paths>`
- **To format TS/TSX files:** give Molham `cd time-os-ui && pnpm exec prettier --write <paths> && cd ..`
- **To verify types:** give Molham `cd time-os-ui && npx tsc --noEmit && cd ..` (Mac only)
