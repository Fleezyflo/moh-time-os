# Session Handoff

**Last updated:** 2026-03-01, Session 14 (Phase 7 code complete, pending commit)
**Branch:** `main` (Phase 7 code ready to commit on new branch)

## What Just Happened

Session 14: Built Phase 7 (Priorities Workspace) -- all 5 steps complete (7.1-7.5).

### Phase 7 Summary
- **7.1:** Added 5 new fetch functions to `lib/api.ts`: `fetchPrioritiesFiltered()`, `fetchSavedFilters()`, `completePriority()`, `snoozePriority()`, `archiveStalePriorities()`. New types: `PriorityFilteredParams`, `SavedFilter`. Reused Phase 6's `fetchPrioritiesAdvanced()`, `fetchPrioritiesGrouped()`, `bulkPriorityAction()`.
- **7.2:** Added 2 new hooks: `usePrioritiesFiltered(filters)`, `useSavedFilters()`
- **7.3:** Created Priorities page (~370 lines) with SummaryGrid (4 metrics), PriorityFilters bar, TabContainer (List/Grouped views), bulk actions, single-item quick actions (complete/snooze), archive-stale button, saved filter selector
- **7.4:** Created 4 components: PriorityFilters (filter bar with search/due/assignee/project), GroupedPriorityView (grouped display with selection), BulkActionBar (floating bottom bar), SavedFilterSelector (dropdown preset)
- **7.5:** Added `/priorities` route, "Priorities" nav item (between Tasks and Clients), system-map regenerated (21 routes)

## What's Next

### Immediate: Commit and PR Phase 7

All code is written but not committed. Molham needs to:

1. **Verify types compile:**
   ```bash
   cd ~/clawd/moh_time_os/time-os-ui && npx tsc --noEmit && cd ..
   ```

2. **Format new files:**
   ```bash
   cd time-os-ui && pnpm exec prettier --write \
     src/components/priorities/PriorityFilters.tsx \
     src/components/priorities/GroupedPriorityView.tsx \
     src/components/priorities/BulkActionBar.tsx \
     src/components/priorities/SavedFilterSelector.tsx \
     src/components/priorities/index.ts \
     src/pages/Priorities.tsx \
     src/pages/index.ts \
     src/router.tsx \
     src/lib/api.ts \
     src/lib/hooks.ts && cd ..
   ```

3. **Run pre-commit:**
   ```bash
   uv run pre-commit run -a
   ```

4. **Commit and push:**
   ```bash
   cd ~/clawd/moh_time_os
   git checkout -b feat/phase-7-priorities-workspace
   git add \
     time-os-ui/src/lib/api.ts \
     time-os-ui/src/lib/hooks.ts \
     time-os-ui/src/router.tsx \
     time-os-ui/src/pages/index.ts \
     time-os-ui/src/pages/Priorities.tsx \
     time-os-ui/src/components/priorities/PriorityFilters.tsx \
     time-os-ui/src/components/priorities/GroupedPriorityView.tsx \
     time-os-ui/src/components/priorities/BulkActionBar.tsx \
     time-os-ui/src/components/priorities/SavedFilterSelector.tsx \
     time-os-ui/src/components/priorities/index.ts \
     docs/system-map.json \
     SESSION_LOG.md \
     HANDOFF.md \
     BUILD_PLAN.md
   git commit -m "$(cat <<'EOF'
   feat: phase 7 -- priorities workspace page and components

   Priorities page with filtered list view, grouped view (by project/
   assignee/source), bulk actions (complete/snooze/archive), single-item
   quick actions, saved filter presets, and archive-stale utility.

   - 5 new API functions (filtered priorities, saved filters, complete,
     snooze, archive-stale) + 2 new hooks
   - 4 new components (PriorityFilters, GroupedPriorityView,
     BulkActionBar, SavedFilterSelector)
   - Route: /priorities with nav item
   - System map: 20 -> 21 UI routes

   large-change
   EOF
   )"
   git push -u origin feat/phase-7-priorities-workspace
   gh pr create --title "feat: phase 7 -- priorities workspace" --body "## Phase 7: Priorities Workspace

   ### Changes
   - 5 new API fetch functions + 2 types (PriorityFilteredParams, SavedFilter)
   - 2 new React hooks (usePrioritiesFiltered, useSavedFilters)
   - Priorities page with filtered list, grouped view, bulk actions
   - 4 new components: PriorityFilters, GroupedPriorityView, BulkActionBar, SavedFilterSelector
   - Route: /priorities with nav item between Tasks and Clients
   - System map: 20 → 21 UI routes

   ### Verification
   - [x] All imports verified (no missing references)
   - [x] All prop types verified (match interfaces)
   - [x] Response shapes verified against server.py endpoints
   - [x] React hooks before early returns
   - [x] System map regenerated with priorities route
   - [ ] tsc --noEmit
   - [ ] prettier
   - [ ] CI green"
   gh pr merge --merge --auto
   gh pr checks --watch
   ```

### After Phase 7 merges: Phase 8 (Time & Capacity)
Per BUILD_PLAN step 8.1-8.6: Schedule page with day/week views, Capacity page with utilization gauges and forecast chart.

## Key Rules (learned hard way in Sessions 1-14)

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
4. `BUILD_PLAN.md` "Phase 8: Time & Capacity" (line ~1209) -- the next spec
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
- **Accent color (D1):** `#3b82f6` (blue)
- **Tertiary text (D2):** `slate-400` / `#94a3b8` (now `var(--grey-light)`)
- **Do NOT run:** `uv sync`, `pnpm install`, `ruff format`, `npx`, or dev servers from the sandbox
- **To format Python files:** give Molham `uv run pre-commit run ruff-format --files <paths>`
- **To format TS/TSX files:** give Molham `cd time-os-ui && pnpm exec prettier --write <paths> && cd ..`
- **To verify types:** give Molham `cd time-os-ui && npx tsc --noEmit && cd ..` (Mac only)
