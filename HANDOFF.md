# Session Handoff

**Last updated:** 2026-02-27, end of Session 6
**Branch:** `main` (Phase 2 PR pending merge)

## What Just Happened

Session 6 completed Phase 1 (Slate Migration) and Phase 2 (Layout Adoption).

### Phase 1 — Slate Migration (PR #33, merged)
- 466 replacements across 51 files — all hardcoded `slate-*` Tailwind classes → `var(--token)` equivalents
- Extended mapping: added `slate-100` → `var(--white)`, `slate-750` → `var(--grey)`
- Fixed 1 test (`priority.test.ts` expected "slate" string, updated to `var(--grey)`)
- Fixed governance check (added deletion rationale for 417 symmetric deletions)

### Phase 2 — Layout Adoption (PR pending)
- Wrapped 9 pages with `PageLayout` + `SummaryGrid` + `MetricCard`
- Pages: Inbox, Issues, ClientIndex, Team, FixData, Signals, Patterns, ClientDetail, TeamDetail
- Replaced hand-built summary banners in Issues (5-card grid) and Team (stats row)
- Fixed 6 invalid `variant` → `severity` props on MetricCard
- Fixed 2 tsc errors: removed unused `TIER_COLORS` in ClientDetailSpec, added Blocked MetricCard in Issues

## What's Next

**Phase 3: Page Redesign — Core** — Type A build session.

Read BUILD_PLAN.md "Phase 3: Page Redesign — Core" section (line 1013) for the full spec. This is a large phase: 2 new pages, 3 enhanced pages, 9 new components, 16 new hooks.

### Sub-phases

#### 3.1 Portfolio Page (new)
- New `Portfolio.tsx` page with PageLayout, SummaryGrid, and 5 new components
- Hooks: `usePortfolioScore()`, `usePortfolioIntelligence()`, `useCriticalItems()`, `useClients()` (exist) + 3 new hooks
- Components: `CriticalItemList`, `TrajectorySparkline`, `ClientDistributionChart`, `RiskList`, `ARAgingSummary`

#### 3.2 Inbox Enhancement
- New `InboxCategoryTabs` component, enhanced item cards
- Wire additional inbox endpoints

#### 3.3 Issues Enhancement
- Enhanced hierarchy view, issue timeline

#### 3.4 Intelligence Command Center Enhancement
- Wire additional intelligence endpoints

#### 3.5 Client Detail Enhancement
- Wire engagement, financial, signal detail tabs

### Execution approach
- Phase 3 is large — likely needs multiple sessions (3A, 3B, etc.)
- Start with 3.1 (Portfolio page) — it's the most self-contained new page
- Each sub-phase should be its own PR

## Key Rules (learned hard way in Sessions 1-6)

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
15. **Update ALL docs after each change.** SESSION_LOG.md + HANDOFF.md + CLAUDE.md (if new rules). Don't defer. Read "Documentation Rules" in CLAUDE.md — it has a trigger table showing exactly when each file must be updated. No exceptions, no batching, no deferring.

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
