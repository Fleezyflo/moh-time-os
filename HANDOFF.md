# Session Handoff

**Last updated:** 2026-03-02, Session 16 (Phase 9 built, pending commit)
**Branch:** `main` (need to create feature branch for Phase 9)

## What Just Happened

Session 16: Built Phase 9 (Commitments). All code written, pending commit/PR/CI.

### Phase 9 Summary
- **9.1:** Added 4 fetch + 2 mutation functions to `lib/api.ts`: `fetchCommitments()`, `fetchUntrackedCommitments()`, `fetchCommitmentsDue()`, `fetchCommitmentsSummary()`, `linkCommitment()`, `markCommitmentDone()`. New types: `Commitment`, `CommitmentsResponse`, `CommitmentsSummaryResponse`.
- **9.2:** Added 4 hooks: `useCommitments()`, `useUntrackedCommitments()`, `useCommitmentsDue()`, `useCommitmentsSummary()`.
- **9.3:** Created Commitments page (~190 lines) with three tabs (All, Untracked, Due Soon), summary cards, status filter, untracked alert banner, LinkToTaskDialog.
- **9.4:** Created 2 components: CommitmentList (status dots, actions), LinkToTaskDialog (modal for linking to task ID).
- **9.5:** Added `/commitments` route, "Commitments" nav item (between Capacity and Clients).

## What's Next

### Immediate: Commit Phase 9

Run the commit block below from `~/clawd/moh_time_os`. System-map must be regenerated before commit.

```bash
# 1. Verify types compile
cd time-os-ui && npx tsc --noEmit && cd ..

# 2. Format new/changed files
cd time-os-ui && pnpm exec prettier --write \
  src/lib/api.ts \
  src/lib/hooks.ts \
  src/pages/Commitments.tsx \
  src/components/commitments/CommitmentList.tsx \
  src/components/commitments/LinkToTaskDialog.tsx \
  src/router.tsx \
  && cd ..

# 3. Regenerate system map (new /commitments route)
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

### After Phase 9 merges: Phase 10 (Notifications, Digest & Email)
Per BUILD_PLAN step 10.1-10.7.

## Key Rules (learned hard way in Sessions 1-16)

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
4. `BUILD_PLAN.md` "Phase 10: Notifications, Digest & Email" -- the next spec
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
- **Accent color (D1):** `#3b82f6` (blue)
- **Tertiary text (D2):** `slate-400` / `#94a3b8` (now `var(--grey-light)`)
- **Do NOT run:** `uv sync`, `pnpm install`, `ruff format`, `npx`, or dev servers from the sandbox
- **To format Python files:** give Molham `uv run pre-commit run ruff-format --files <paths>`
- **To format TS/TSX files:** give Molham `cd time-os-ui && pnpm exec prettier --write <paths> && cd ..`
- **To verify types:** give Molham `cd time-os-ui && npx tsc --noEmit && cd ..` (Mac only)
