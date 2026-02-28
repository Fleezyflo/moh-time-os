# Session Handoff

**Last updated:** 2026-02-28, Session 12 (all PRs merged, main clean)
**Branch:** `main` (Phases -1 through 5 complete, bypass remediation complete, working tree clean)

## What Just Happened

Session 12: Landed both Phase 5 (PR #40) and bypass remediation (PR #39). Fixed multiple CI blockers along the way.

### PR #39 — Bypass Remediation (MERGED)
- Centralized `lib/safe_sql.py` replacing 141+ inline noqa/nosec comments across 34 files
- Fixed B108 (hardcoded /tmp) in 5 test files with `tempfile.gettempdir()`
- Fixed B314 (XML parse) in test_sync_schedule.py with `defusedxml.ElementTree`
- Fixed pre-existing lint issues: E741 (cli_v4.py), F841 (setup.py), E402 (tools/db_exec.py)
- Fixed 11 markdown files missing trailing newlines
- Fixed ruff format drift in cli.py
- Created ADR-0007 (required by Governance Checks for lib/safety/ and api/server.py changes)
- Rebased to resolve merge conflicts before auto-merge could fire

### PR #40 — Phase 5 Accessibility (MERGED)
- Keyboard navigation on 9 clickable card divs (role=button, tabIndex, onKeyDown)
- Focus trap in RoomDrawer matching IssueDrawer pattern
- ARIA labels on EvidenceViewer close button
- Centralized chart colors in chartColors.ts (20 rgb() values eliminated)
- Standardized loading/error states with SkeletonCardList and ErrorState
- Rebased on main after PR #39 merged to pick up lint/format fixes

### PR #41 — Session 12 Cleanup (MERGED)
- Phase 4 route cleanup in router.tsx (removed Snapshot, ColdClients, RecentlyActiveDrilldown)
- Removed Snapshot export from pages/index.ts
- Updated system-map.json (20→18 routes)
- Marked Phase 4+5 complete in BUILD_PLAN.md
- Updated SESSION_LOG.md, HANDOFF.md, CLAUDE.md

## What's Next

### Phase 6: Task Management
Per BUILD_PLAN step 6.1-6.9:
- Fix `useTasks()` response shape bug (`.tasks` vs `.items`)
- New fetch functions and hooks for tasks, priorities, delegations, dependencies
- Task List page with filter/group/delegation views
- Task Detail page with edit, notes, blockers, delegation/escalation/recall
- New components: TaskForm, TaskActions, BlockerList, DependencyGraph, DelegationSplit
- Governance approval dialog
- Routes: `/tasks`, `/tasks/:taskId`

**Starting state:** Main is clean. No unstaged changes. All Phases -1 through 5 merged. Ready to branch and build.

## Key Rules (learned hard way in Sessions 1-12)

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
31. **Cross-file consistency on every doc update.** After updating any doc, verify all four files (SESSION_LOG, HANDOFF, CLAUDE, BUILD_PLAN) are consistent. Session 12 left Phases 1-3 unmarked in BUILD_PLAN.md and stale "unstaged changes" in HANDOFF.md because checks were per-file, not cross-file.
32. **BUILD_PLAN.md is a documentation file.** Mark phases ✅ COMPLETE with session number the moment the phase PR merges. Don't defer. Sessions 6-8 completed Phases 1-3 but never marked them.

## Documents to Read (in order)

1. **This file (HANDOFF.md)** -- you're reading it, now follow the order below
2. `CLAUDE.md` -- coding standards, sandbox rules, verification requirements
3. `BUILD_STRATEGY.md` §3 -- entry/exit checklists, session contract
4. `BUILD_PLAN.md` "Phase 6: Task Management" (line ~1160) -- the full spec
5. `SESSION_LOG.md` -- what's done, current state, lessons learned

## Quick Reference

- **Repo:** `moh-time-os` on branch `main`
- **Main is protected.** Cannot push directly. ALL changes need a feature branch + PR + CI green + merge.
- **SQL builder:** `lib/safe_sql.py` -- use for all dynamic SQL identifier interpolation
- **UI root:** `time-os-ui/src/`
- **Design tokens:** `design/system/tokens.css`
- **Chart colors:** `time-os-ui/src/intelligence/components/chartColors.ts`
- **Layout components:** `time-os-ui/src/components/layout/` (PageLayout, SummaryGrid, MetricCard, TabContainer)
- **Accent color (D1):** `#3b82f6` (blue)
- **Tertiary text (D2):** `slate-400` / `#94a3b8` (now `var(--grey-light)`)
- **Do NOT run:** `uv sync`, `pnpm install`, `ruff format`, `npx`, or dev servers from the sandbox
- **To format Python files:** give Molham `uv run pre-commit run ruff-format --files <paths>`
- **To format TS/TSX files:** give Molham `cd time-os-ui && pnpm exec prettier --write <paths> && cd ..`
- **To verify types:** give Molham `cd time-os-ui && npx tsc --noEmit && cd ..` (Mac only)
