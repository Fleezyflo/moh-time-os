# Session Handoff

**Last updated:** 2026-02-28, Session 13 (Phase 6 code complete, pending commit)
**Branch:** `main` (Phase 6 code ready to commit on new branch)

## What Just Happened

Session 13: Built Phase 6 (Task Management) -- all 9 steps complete (6.1-6.9).

### Phase 6 Summary
- **6.1:** Fixed `useTasks()` response shape bug -- remapped `{tasks: [...]}` to `{items: [...]}` in `fetchTasks()`
- **6.2:** Added 13 new fetch functions + `putJson` helper to `lib/api.ts` covering task CRUD, delegation, escalation, recall, notes, priorities/advanced, priorities/grouped, bulk actions, bundle detail
- **6.3:** Added 5 new hooks to `lib/hooks.ts` (useTaskDetail, useDelegations, usePrioritiesAdvanced, usePrioritiesGrouped, useBundleDetail)
- **6.4:** Created TaskList page with search, metrics grid, tabbed views (All/Active/Blocked/Delegated/Completed)
- **6.5:** Created TaskDetail page with view/edit modes, metadata grid, notes, delegation sidebar
- **6.6:** Created 5 components: TaskCard, TaskActions, ApprovalDialog, DelegationPanel, TaskNotesList
- **6.7:** ApprovalDialog handles governance blocks on delegate/escalate/update
- **6.8-6.9:** Added `/tasks` and `/tasks/$taskId` routes, "Tasks" nav item, system-map regenerated (20 routes)

### Expanded Task type
The `Task` interface now includes delegation fields (delegated_by, delegated_at, delegated_note, delegation_status), escalation fields (escalated_to, escalation_level, escalation_reason), and metadata (description, urgency, source, tags, notes, completed_at). Priority changed from string enum to `number` (0-100 score). Status changed from string enum to `string`.

## What's Next

### Immediate: Commit and PR Phase 6

All code is written but not committed. Molham needs to:

1. **Verify types compile:**
   ```bash
   cd ~/clawd/moh_time_os/time-os-ui && npx tsc --noEmit && cd ..
   ```

2. **Format new files:**
   ```bash
   cd time-os-ui && pnpm exec prettier --write \
     src/components/tasks/TaskCard.tsx \
     src/components/tasks/TaskActions.tsx \
     src/components/tasks/ApprovalDialog.tsx \
     src/components/tasks/DelegationPanel.tsx \
     src/components/tasks/TaskNotesList.tsx \
     src/components/tasks/index.ts \
     src/pages/TaskList.tsx \
     src/pages/TaskDetail.tsx \
     src/pages/index.ts \
     src/router.tsx \
     src/lib/api.ts \
     src/lib/hooks.ts \
     src/types/api.ts && cd ..
   ```

3. **Run pre-commit:**
   ```bash
   uv run pre-commit run -a
   ```

4. **Commit and push:**
   ```bash
   cd ~/clawd/moh_time_os
   git checkout -b feat/phase-6-task-management
   git add \
     time-os-ui/src/types/api.ts \
     time-os-ui/src/lib/api.ts \
     time-os-ui/src/lib/hooks.ts \
     time-os-ui/src/router.tsx \
     time-os-ui/src/pages/index.ts \
     time-os-ui/src/pages/TaskList.tsx \
     time-os-ui/src/pages/TaskDetail.tsx \
     time-os-ui/src/components/tasks/TaskCard.tsx \
     time-os-ui/src/components/tasks/TaskActions.tsx \
     time-os-ui/src/components/tasks/ApprovalDialog.tsx \
     time-os-ui/src/components/tasks/DelegationPanel.tsx \
     time-os-ui/src/components/tasks/TaskNotesList.tsx \
     time-os-ui/src/components/tasks/index.ts \
     docs/system-map.json \
     SESSION_LOG.md \
     HANDOFF.md \
     BUILD_PLAN.md
   git commit -m "$(cat <<'EOF'
   feat: phase 6 -- task management pages and components

   Task List page with search, metrics, tabbed views (All/Active/Blocked/
   Delegated/Completed). Task Detail page with view/edit modes, delegation
   sidebar, notes, and governance approval handling.

   - Fix useTasks() response shape bug (.tasks vs .items remapping)
   - 13 new fetch functions (task CRUD, delegate, escalate, recall, notes,
     priorities/advanced/grouped, bulk actions, bundle detail)
   - 5 new hooks (useTaskDetail, useDelegations, usePrioritiesAdvanced,
     usePrioritiesGrouped, useBundleDetail)
   - 5 new components (TaskCard, TaskActions, ApprovalDialog,
     DelegationPanel, TaskNotesList)
   - Routes: /tasks, /tasks/:taskId with nav item
   - System map: 18 -> 20 UI routes

   large-change
   EOF
   )"
   git push -u origin feat/phase-6-task-management
   gh pr create --title "feat: phase 6 -- task management" --body "## Phase 6: Task Management

   ### Changes
   - Fix useTasks() response shape bug (.tasks vs .items)
   - 13 new API fetch functions for task CRUD, delegation, escalation, priorities
   - 5 new React hooks
   - TaskList page with search, metrics grid, 5 tabbed views
   - TaskDetail page with view/edit modes, governance approval
   - 5 new components: TaskCard, TaskActions, ApprovalDialog, DelegationPanel, TaskNotesList
   - Routes: /tasks, /tasks/:taskId
   - Nav: Tasks added between Portfolio and Clients
   - System map: 18 → 20 UI routes

   ### Verification
   - [x] All imports verified (no missing references)
   - [x] All prop types verified (match interfaces)
   - [x] Response shapes verified against server.py endpoints
   - [x] System map regenerated with both task routes
   - [ ] tsc --noEmit
   - [ ] prettier
   - [ ] CI green"
   gh pr merge --merge --auto
   gh pr checks --watch
   ```

### After Phase 6 merges: Phase 7 (Priorities Workspace)
Per BUILD_PLAN step 7.1-7.5: Priorities page with advanced filters, grouping, bulk actions, saved filters.

## Key Rules (learned hard way in Sessions 1-13)

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

## Documents to Read (in order)

1. **This file (HANDOFF.md)** -- you're reading it, now follow the order below
2. `CLAUDE.md` -- coding standards, sandbox rules, verification requirements
3. `BUILD_STRATEGY.md` §3 -- entry/exit checklists, session contract
4. `BUILD_PLAN.md` "Phase 7: Priorities Workspace" (line ~1187) -- the next spec
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
- **Accent color (D1):** `#3b82f6` (blue)
- **Tertiary text (D2):** `slate-400` / `#94a3b8` (now `var(--grey-light)`)
- **Do NOT run:** `uv sync`, `pnpm install`, `ruff format`, `npx`, or dev servers from the sandbox
- **To format Python files:** give Molham `uv run pre-commit run ruff-format --files <paths>`
- **To format TS/TSX files:** give Molham `cd time-os-ui && pnpm exec prettier --write <paths> && cd ..`
- **To verify types:** give Molham `cd time-os-ui && npx tsc --noEmit && cd ..` (Mac only)
