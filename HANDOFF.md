# Session Handoff

**Last updated:** 2026-02-27, Session 7 (Phase 3.1 complete)
**Branch:** `feat/phase-2-layout-adoption` (Phase 2 PR pending merge, Phase 3.1 code on top)

## What Just Happened

Session 7 completed Phase 3.1 (Portfolio Page) and added commit/push/merge rules to all documentation.

### Phase 3.1 -- Portfolio Page (code ready, needs commit)
- Created `Portfolio.tsx` page with PageLayout, SummaryGrid, 4 MetricCards (Health Score, Critical Items, Active Signals, Structural Patterns)
- Wired 5 hooks: `usePortfolioScore()`, `useCriticalItems()`, `usePortfolioIntelligence()` (all intelligence), `usePortfolioOverview()`, `usePortfolioRisks()` (new lib hooks)
- Created 4 new components in `components/portfolio/`: CriticalItemList, ClientDistributionChart, RiskList, ARAgingSummary
- Added 3 new fetch functions + 3 new hooks in `lib/api.ts` and `lib/hooks.ts`
- Wired `/portfolio` route in router.tsx, added to NAV_ITEMS
- Response shapes verified against actual server.py endpoints

### Documentation updates
- Added comprehensive commit/push/merge rules to CLAUDE.md, HANDOFF.md, BUILD_STRATEGY.md

## What's Next

### Immediate: merge Phase 2, then commit Phase 3.1

Phase 2 PR needs to merge first. Then:

1. Create new branch from main for Phase 3.1
2. Cherry-pick or re-apply Phase 3.1 changes
3. Run tsc + prettier on new files
4. Commit, push, create PR

### After Phase 3.1 merges: Phase 3.2 (Inbox Enhancement)
- New `InboxCategoryTabs` component (tabs for risk/opportunity/anomaly/maintenance)
- Wire `useInbox()`, `useInboxCounts()` hooks
- Enhanced InboxItemCard with unread indicator, richer metadata
- See BUILD_PLAN.md line 1044

### Remaining Phase 3 sub-phases
- **3.3** Client Detail Enhancement -- tabs, financials, signals, team
- **3.4** Team Detail Enhancement -- workload distribution
- **3.5** Operations Page (new) -- data quality, watchers, couplings tabs

## Key Rules (learned hard way in Sessions 1-7)

1. **No bypasses.** Never add `nosec`, `noqa`, or `type: ignore`. Fix the root cause.
2. **Stage everything.** Before committing, `git add` all modified files to prevent ruff-format stash conflicts.
3. **Verify gates.** Run ruff check + ruff format + tests locally before giving commit commands.
4. **Document immediately.** Update SESSION_LOG.md after each commit, not at session end.
5. **Zero mypy baseline.** `.mypy-baseline.txt` is empty. Keep it that way.
6. **Never format from sandbox.** Use `uv run pre-commit run ruff-format --files` on Mac. Sandbox ruff version differs.
7. **Protected files need blessing.** Changes to ci.yml, pyproject.toml, .pre-commit-config.yaml only take effect after blessing in enforcement repo.
8. **Governance keywords on HEAD.** Large PRs need "large-change" and deletion rationale in the latest commit message.
9. **Prettier for new/modified .tsx/.ts files.** CI runs `prettier --check` on `src/**/*.{ts,tsx,css}`. Sandbox can't run prettier. Include `cd time-os-ui && pnpm exec prettier --write <files> && cd ..` in commit commands. (Session 5: PR #30 failed CI until prettier was applied.)
10. **Conventional commit casing.** Description starts lowercase after type prefix: `feat: phase 1` not `feat: Phase 1`.
11. **Discovery before fix commands.** Investigate actual state before giving fix commands. Never use placeholders in command blocks.
12. **Don't claim readiness without reading all files.** Read HANDOFF.md, CLAUDE.md, BUILD_STRATEGY.md, BUILD_PLAN.md, SESSION_LOG.md, AND the source files for the assigned work before starting.
13. **Script-based migration for bulk replacements.** For 400+ changes, write a script with dry-run mode, verify output, then apply. (Session 6: slate migration.)
14. **Run tsc before giving commit commands.** Can't run from sandbox (no node_modules) but must verify types compile on Mac before claiming done. (Session 6: 2 tsc errors caught post-commit.)
15. **Update ALL docs after each change.** SESSION_LOG.md + HANDOFF.md + CLAUDE.md (if new rules). Don't defer. Read "Documentation Rules" in CLAUDE.md -- it has a trigger table showing exactly when each file must be updated. No exceptions, no batching, no deferring.
16. **Commit subject max 72 chars.** Session 6 failed at 87. Format: `type: short description` (lowercase after prefix).
17. **Use `--` not em dash in commits.** Avoids encoding issues in commit messages.
18. **Pre-commit failure means commit didn't happen.** Don't use `--amend` after a hook failure -- fix and commit fresh.
19. **Check branch before creating.** `git branch --show-current` first. If branch is in a worktree, `git branch -D` fails.
20. **Only prettier specific files.** Never `prettier --write src/` -- only the files you changed.
21. **Auto-merge PRs.** Always `gh pr merge --merge --auto` after creating. Watch with `gh pr checks <N> --watch`.
22. **Force-push after amend.** If you amend a pushed commit, use `git push --force-with-lease`.

## Documents to Read (in order)

1. **This file (HANDOFF.md)** — you're reading it, now follow the order below
2. `CLAUDE.md` — coding standards, sandbox rules, verification requirements
3. `BUILD_STRATEGY.md` §3 — entry/exit checklists, session contract
4. `BUILD_PLAN.md` "Phase 3: Page Redesign — Core" (line 1013) — the full spec
5. `SESSION_LOG.md` — what's done, current state, lessons learned

## Quick Reference

- **Repo:** `moh-time-os` on branch `main`
- **Main is protected.** Cannot push directly. ALL changes (including docs) need a feature branch + PR + CI green + merge. Use `gh pr merge <N> --merge --auto` to auto-merge once checks pass.
- **UI root:** `time-os-ui/src/`
- **Design tokens:** `design/system/tokens.css`
- **Layout components:** `time-os-ui/src/components/layout/` (PageLayout, SummaryGrid, MetricCard)
- **Accent color (D1):** `#3b82f6` (blue)
- **Tertiary text (D2):** `slate-400` / `#94a3b8` (now `var(--grey-light)`)
- **Do NOT run:** `uv sync`, `pnpm install`, `ruff format`, `npx`, or dev servers from the sandbox
- **To format Python files:** give Molham `uv run pre-commit run ruff-format --files <paths>`
- **To format TS/TSX files:** give Molham `cd time-os-ui && pnpm exec prettier --write <paths> && cd ..`
- **To verify types:** give Molham `cd time-os-ui && npx tsc --noEmit && cd ..` (Mac only)
