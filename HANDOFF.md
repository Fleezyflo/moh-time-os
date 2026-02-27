# Session Handoff

**Last updated:** 2026-02-27, Session 8 (Phase 3 complete, 3.5 pending commit)
**Branch:** `main` (Phases 3.1-3.4 merged as PR #35, #36, #37)

## What Just Happened

Session 8: All Phase 3 sub-phases complete.

### Phase 3.3+3.4 -- Client + Team Enhancement (MERGED, PR #37)
- TabContainer, TrajectorySparkline, 5 API functions, 5 hooks
- ClientDetailSpec refactored, TeamDetail enhanced
- CI fix: moved hooks before early returns (react-hooks/rules-of-hooks)

### Phase 3.5 -- Operations Page (code ready, needs commit)
- New `Operations.tsx` at `/ops` -- consolidates Fix Data + Watchers + Couplings
- TabContainer with 3 tabs (Data Quality, Watchers, Couplings) and badge counts
- SummaryGrid: Fix Items, Active Watchers, Couplings, System Health
- New `useHealth()` hook in hooks.ts
- Route added, NAV_ITEMS updated, system-map regenerated (20 UI routes)

## What's Next

### Immediate: commit and merge Phase 3.5

1. Pull latest main (PR #37 merged), create branch `feat/phase-3-ops`
2. Run prettier on new/modified files
3. Run tsc: `cd time-os-ui && npx tsc --noEmit && cd ..`
4. Commit, push, create PR, auto-merge

### After 3.5 merges: Phase 4 (Route Consolidation)
Per BUILD_PLAN step 4.1-4.4:
- Add redirects: `/snapshot` -> `/portfolio`, `/intel` -> `/portfolio`, etc.
- Remove routes: `/clients/cold`, `/clients/:id/recently-active`
- Update NAV_ITEMS: `['/', '/portfolio', '/clients', '/issues', '/team', '/intel/signals', '/ops']`

## Key Rules (learned hard way in Sessions 1-8)

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
23. **Regenerate system-map after adding UI routes.** `uv run python scripts/generate_system_map.py` then include `docs/system-map.json` in the commit.
24. **Never run git from sandbox.** Creates stale `.git/index.lock` that blocks Mac operations.
25. **React hooks before early returns.** ESLint `react-hooks/rules-of-hooks` catches hooks called after `if (...) return`. Always place hooks at the top of the component body.

## Documents to Read (in order)

1. **This file (HANDOFF.md)** — you're reading it, now follow the order below
2. `CLAUDE.md` — coding standards, sandbox rules, verification requirements
3. `BUILD_STRATEGY.md` §3 — entry/exit checklists, session contract
4. `BUILD_PLAN.md` "Phase 4: Route Consolidation" (line ~1120) — the full spec
5. `SESSION_LOG.md` — what's done, current state, lessons learned

## Quick Reference

- **Repo:** `moh-time-os` on branch `main`
- **Main is protected.** Cannot push directly. ALL changes need a feature branch + PR + CI green + merge.
- **UI root:** `time-os-ui/src/`
- **Design tokens:** `design/system/tokens.css`
- **Layout components:** `time-os-ui/src/components/layout/` (PageLayout, SummaryGrid, MetricCard, TabContainer)
- **Accent color (D1):** `#3b82f6` (blue)
- **Tertiary text (D2):** `slate-400` / `#94a3b8` (now `var(--grey-light)`)
- **Do NOT run:** `uv sync`, `pnpm install`, `ruff format`, `npx`, or dev servers from the sandbox
- **To format Python files:** give Molham `uv run pre-commit run ruff-format --files <paths>`
- **To format TS/TSX files:** give Molham `cd time-os-ui && pnpm exec prettier --write <paths> && cd ..`
- **To verify types:** give Molham `cd time-os-ui && npx tsc --noEmit && cd ..` (Mac only)
