# Session Handoff

**Last updated:** 2026-02-27, end of Session 6
**Branch:** `main` (Phase 1 PR pending merge)

## What Just Happened

Phase 1 (Slate Migration) is complete. 466 replacements across 51 files — all hardcoded `slate-*` Tailwind classes replaced with `var(--token)` equivalents. Key work in Session 6:

1. Discovered actual counts: 130 bg + 238 text + 68 border + extras = 466 total replacements across 51 files
2. Built regex-based migration script handling all Tailwind variant prefixes (hover, focus, disabled, [&.active]) and property prefixes (bg, text, border, ring, placeholder, fill, focus:ring, focus:ring-offset)
3. Extended mapping beyond BUILD_PLAN spec: added `slate-100` → `var(--white)` and `slate-750` → `var(--grey)`
4. Preserved opacity modifiers: `bg-[var(--grey)]/50`, `bg-[var(--grey-dim)]/90`, etc.
5. Zero remaining Tailwind `slate-*` classes (3 inline RGB values in SVG components deferred)
6. Updated SESSION_LOG.md with full Session 6 record

## What's Next

**Phase 2: Layout Adoption** — Type A build session.

Read BUILD_PLAN.md "Phase 2: Layout Adoption" section (line 990) for the full spec. Wrap 9 pages with `PageLayout` + `SummaryGrid` + `MetricCard` components created in Phase 0. ~15 page files modified, ~30 lines added per file.

### Steps

| Step | Page | SummaryGrid Metrics | Data Source |
|------|------|-------------------|------------|
| 2.1 | Inbox (`/`) | Total, Unread, Critical, Categories | Wire `fetchInboxCounts()` (new) |
| 2.2 | Issues (`/issues`) | Open, Investigating, Critical, Total | Derived from `useIssues()` |
| 2.3 | Client Index (`/clients`) | Total, Active, At-risk, Overdue AR | Derived from `useClients()` |
| 2.4 | Team Index (`/team`) | Team size, Avg score, Overloaded | Derived from `useTeam()` |
| 2.5 | Fix Data (Ops) | Fix items, Identity issues, Link issues | From `useFixData()` |
| 2.6 | Signals (`/intel/signals`) | Total active, Critical, Warning, Watch | From `useSignalSummary()` (exists) |
| 2.7 | Patterns (`/intel/patterns`) | Total detected, Structural, Operational | Derived from `usePatterns()` |
| 2.8 | Client Detail | Health score, AR total, Active projects, Open issues | From `useClientProfile()` (exists) |
| 2.9 | Team Detail | Health score, Active tasks, Overdue, Projects | From `usePersonProfile()` (exists) |

### Verification

- Every page renders with consistent header positioning and max-width
- SummaryGrid shows real numbers from API
- No layout shift on page transitions
- `npx tsc --noEmit` clean

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
10. **Conventional commit casing.** Description starts lowercase after type prefix: `feat: phase 1` not `feat: Phase 1`. (Session 5: linter flagged uppercase.)
11. **Discovery before fix commands.** Investigate actual state before giving fix commands. Never use placeholders in command blocks.
12. **Don't claim readiness without reading all files.** Read HANDOFF.md, CLAUDE.md, BUILD_STRATEGY.md, BUILD_PLAN.md, SESSION_LOG.md, AND the source files for the assigned work before starting.
13. **Script-based migration for bulk replacements.** For 400+ changes, write a script with dry-run mode, verify output, then apply. (Session 6: slate migration.)

## Documents to Read (in order)

1. **This file (HANDOFF.md)** — you're reading it, now follow the order below
2. `CLAUDE.md` — coding standards, sandbox rules, verification requirements
3. `BUILD_STRATEGY.md` §3 — entry/exit checklists, session contract
4. `BUILD_PLAN.md` "Phase 2: Layout Adoption" (line 990) — the full spec
5. `SESSION_LOG.md` — what's done, current state, lessons learned

## Quick Reference

- **Repo:** `moh-time-os` on branch `main`
- **Main is protected.** Cannot push directly. ALL changes (including docs) need a feature branch + PR + CI green + merge. Use `gh pr merge <N> --merge --auto` to auto-merge once checks pass.
- **UI root:** `time-os-ui/src/`
- **Design tokens:** `design/system/tokens.css`
- **Accent color (D1):** `#3b82f6` (blue)
- **Tertiary text (D2):** `slate-400` / `#94a3b8`
- **Do NOT run:** `uv sync`, `pnpm install`, `ruff format`, `npx`, or dev servers from the sandbox
- **To format Python files:** give Molham `uv run pre-commit run ruff-format --files <paths>`
- **To format TS/TSX files:** give Molham `cd time-os-ui && pnpm exec prettier --write <paths> && cd ..`
- **To verify types:** give Molham `npx tsc --noEmit` (Mac only)
