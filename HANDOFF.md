# Session Handoff

**Last updated:** 2026-02-27, Session 7 continued (Phase 3.2 complete, pending commit)
**Branch:** `main` (Phase 3.1 merged as PR #35)

## What Just Happened

Session 7 continued: Phase 3.1 (Portfolio Page) merged as PR #35. Phase 3.2 (Inbox Enhancement) code complete, pending commit.

### Phase 3.1 -- Portfolio Page (MERGED, PR #35)
- All 26 CI checks green after regenerating `docs/system-map.json`
- New rule: always regenerate system-map when adding UI routes to `router.tsx`

### Phase 3.2 -- Inbox Enhancement (code ready, needs commit)
- New fetch functions in `lib/api.ts`: `fetchInbox()`, `fetchInboxCounts()`, `fetchInboxRecent()`, `executeInboxAction()` with typed `InboxFilters` interface
- New hooks in `lib/hooks.ts`: `useInbox()`, `useInboxCounts()`, `useInboxRecent()`
- New `components/inbox/InboxCategoryTabs.tsx` -- pill-style category tabs for filtering by `InboxItemType`, with counts from API
- Refactored `pages/Inbox.tsx` to use `api.*` functions instead of raw `fetch()`, added category filter with server-side type filtering

## What's Next

### Immediate: commit and merge Phase 3.2

1. Create branch `feat/phase-3-inbox-hooks` from main
2. Run prettier on new files: `cd time-os-ui && pnpm exec prettier --write src/components/inbox/InboxCategoryTabs.tsx src/components/inbox/index.ts && cd ..`
3. Run tsc: `cd time-os-ui && npx tsc --noEmit && cd ..`
4. Commit, push, create PR, auto-merge
5. No system-map regen needed (no new routes)

### After Phase 3.2 merges: Phase 3.3+3.4 (Client + Team Enhancement)
- Create reusable `TabContainer` component (extracted from inline tab patterns)
- Create `TrajectorySparkline` component (reusable sparkline for health scores)
- Refactor `ClientDetailSpec.tsx` to use named hook instead of inline fetch
- Wire `useTeamWorkload()` hook to `/api/team/workload` endpoint
- See BUILD_PLAN.md line 1061

### After 3.3+3.4: Phase 3.5 (Operations Page)
- New `Operations.tsx` page at `/ops` with tabs for data quality, watchers, couplings
- **Must regenerate system-map** (new route)

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
23. **Regenerate system-map after adding UI routes.** `uv run python scripts/generate_system_map.py` then include `docs/system-map.json` in the commit. (Session 7: PR #35 CI failed until system-map was regenerated.)

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
