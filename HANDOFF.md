# Session Handoff

**Last updated:** 2026-03-02, Session 21 (collector consolidation committed, UI fixes pending)
**Branch:** `fix/collector-consolidation` (pushed, pending format fix on api/server.py)

## What Just Happened

Session 21: Fixed Tasks page issues and consolidated the collector architecture.

### Collector Consolidation (committed, PR pending)
- `collect_asana()` now calls `AsanaCollector.sync()` (8-table DB write) instead of `asana_ops.generate_asana_report()` (JSON file only, no DB)
- `collect_tasks()` now calls `TasksCollector.sync()` (Google Tasks via gog CLI) instead of broken `from tasks import` (module was a markdown folder, always failed silently)
- Registry `tables_written` updated to reflect actual tables written by each collector
- Commit `9451e92` on branch `fix/collector-consolidation`
- **Blocked:** pre-push failed on `ruff format api/server.py` (pre-existing issue). Fix: `uv run ruff format api/server.py`, amend or new commit, then push.

### UI Fixes (unstaged, pending commit)
- TaskCard.tsx: `<div onClick>` → `<Link>`, `parsePriority()` for string/numeric priority
- TaskList.tsx: Filter logic uses `ACTIVE_STATUSES`/`BLOCKED_STATUSES` arrays matching collector output
- TaskDetail.tsx: Same `parsePriority()`, expanded status options
- TeamDetail.tsx: Priority/status maps expanded
- api.ts: `Task.priority` type changed to `number | string`

### Investigation Findings
- THREE parallel Asana paths existed: `collect_tasks()` (dead import), `collect_asana()` (JSON only), `AsanaCollector.sync()` (proper but never called)
- Mystery `tasks` module: `from tasks import collect_tasks` resolved to `tasks/` directory containing only TASK_*.md files. No Python code. Always failed silently.
- Root cause of "all Low" priority: `parsePriority(string)` fell through all numeric comparisons → always "Low"
- Root cause of "Active 0": filters checked wrong status strings

## What's Next

### 1. Land the collector consolidation PR
Fix the format issue and push:
```bash
cd ~/clawd/moh_time_os
uv run ruff format api/server.py
git add api/server.py
git commit -m "style: format api/server.py"
git push -u origin fix/collector-consolidation
```
Then create PR if not already created, set auto-merge.

### 2. Commit UI fixes
Create a new branch for the Tasks page UI fixes:
```bash
cd ~/clawd/moh_time_os
git checkout main && git pull

git checkout -b fix/tasks-page-ui

# Prettier on changed .tsx/.ts files
cd time-os-ui && pnpm exec prettier --write \
  src/types/api.ts \
  src/components/tasks/TaskCard.tsx \
  src/pages/TaskList.tsx \
  src/pages/TaskDetail.tsx \
  src/pages/TeamDetail.tsx \
  && cd ..

# Typecheck
cd time-os-ui && npx tsc --noEmit && cd ..

git add \
  time-os-ui/src/types/api.ts \
  time-os-ui/src/components/tasks/TaskCard.tsx \
  time-os-ui/src/pages/TaskList.tsx \
  time-os-ui/src/pages/TaskDetail.tsx \
  time-os-ui/src/pages/TeamDetail.tsx \
  SESSION_LOG.md \
  HANDOFF.md

git commit -m "$(cat <<'EOF'
fix: tasks page -- priority display, filter counters, clickable cards

Priority display showed all "Low" because collector writes string
priority ("high"/"normal") but UI expected numeric (0-100). Added
parsePriority() that handles both via STRING_PRIORITY_MAP lookup.

Filter counters showed 0 because UI checked "pending"/"in_progress"
but collector writes "active"/"overdue". Added ACTIVE_STATUSES and
BLOCKED_STATUSES arrays covering both collector and manual values.

Tasks now use <Link> instead of <div onClick> for proper navigation
(accessibility, right-click, browser back button).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"

git push -u origin fix/tasks-page-ui
gh pr create --title "fix: tasks page priority, filters, and navigation" --body "$(cat <<'EOF'
## Summary
- Fix priority display: parsePriority() handles both string and numeric values
- Fix filter counters: ACTIVE_STATUSES/BLOCKED_STATUSES arrays match collector output
- Fix navigation: TaskCard uses <Link> instead of <div onClick>
- Fix TeamDetail: priority/status maps expanded for collector values

## Root cause
Asana collector writes `priority: "high" | "normal"` (strings) and `status: "active" | "overdue"`,
but the UI expected `priority: number` and `status: "pending" | "in_progress" | "blocked"`.

## Test plan
- [ ] Tasks page shows correct priority labels (High, Normal) not all "Low"
- [ ] Active/Blocked/Overdue counters are non-zero
- [ ] Clicking a task card navigates to task detail
- [ ] Right-click on task card shows browser context menu with "Open in new tab"
- [ ] TeamDetail tasks tab shows correct priority colors

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
gh pr merge --merge --auto
```

### 3. Future: Display preferences system
Scoped but not started. User wants view-layer configuration: project visibility toggles, staleness cutoff, sort/grouping defaults, default tab, card field selection. Stored in DB `preferences` table, applied client-side. This is NOT collection config -- what gets collected stays stable.

## Key Rules (learned hard way in Sessions 1-21)

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
35. **Collector tables already exist.** All 22 secondary tables are defined in lib/schema.py and created by schema_engine.py on startup. No migrations needed for collector depth work.
36. **Verify collector call chains end-to-end.** Class-based collectors can be initialized but never called if the orchestrator delegates to function-based wrappers. Always trace from API endpoint → orchestrator → scheduled_collect → actual collector class.

## Documents to Read (in order)

1. **This file (HANDOFF.md)** -- you're reading it, now follow the order below
2. `CLAUDE.md` -- coding standards, sandbox rules, verification requirements
3. `BUILD_STRATEGY.md` §3 -- entry/exit checklists, session contract
4. `BUILD_PLAN.md` -- ALL PHASES COMPLETE, review final state
5. `SESSION_LOG.md` -- what's done, current state, lessons learned

## Quick Reference

- **Repo:** `moh-time-os` on branch `fix/collector-consolidation` (collector fix) / `main` (UI fixes pending)
- **Main is protected.** Cannot push directly. ALL changes need a feature branch + PR + CI green + merge.
- **SQL builder:** `lib/safe_sql.py` -- use for all dynamic SQL identifier interpolation
- **UI root:** `time-os-ui/src/`
- **Design tokens:** `design/system/tokens.css`
- **Chart colors:** `time-os-ui/src/intelligence/components/chartColors.ts`
- **Layout components:** `time-os-ui/src/components/layout/` (PageLayout, SummaryGrid, MetricCard, TabContainer)
- **Do NOT run:** `uv sync`, `pnpm install`, `ruff format`, `npx`, or dev servers from the sandbox
- **To format Python files:** give Molham `uv run pre-commit run ruff-format --files <paths>`
- **To format TS/TSX files:** give Molham `cd time-os-ui && pnpm exec prettier --write <paths> && cd ..`
- **To verify types:** give Molham `cd time-os-ui && npx tsc --noEmit && cd ..` (Mac only)
