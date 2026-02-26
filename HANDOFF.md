# Session Handoff

**Last updated:** 2026-02-27, end of Session 5
**Branch:** `main` (PR #30 merged)

## What Just Happened

Phase 0 (Design System Foundation) is complete. PR #30 merged with all 26 CI checks passing. Key work in Session 5:

1. Updated 5 neutral tokens to slate equivalents, added 3 new tokens (`--grey-mid`, `--grey-muted`, `--grey-subtle`), switched accent from red to blue (`#3b82f6`)
2. Removed orphan `:root` override block from `time-os-ui/src/index.css`
3. Created 3 layout components: `PageLayout`, `SummaryGrid`, `MetricCard` in `time-os-ui/src/components/layout/`
4. Extracted shared issue styles into `time-os-ui/src/lib/issueStyles.ts` (IssueCard + IssueDrawer now import from it)
5. Deduped 6 inline components from intelligence pages — Signals, Patterns, Proposals now use shared components from `intelligence/components/`
6. Fixed 4 incorrect `tokens.css` path references in BUILD_PLAN.md and HANDOFF.md
7. Added prettier rule to CLAUDE.md (new `.tsx`/`.ts` files must be prettier-formatted on Mac before commit)

## What's Next

**Phase 1: Slate Migration** — Type A build session.

Read BUILD_PLAN.md "Phase 1: Slate Migration" section (line 949) for the full spec. This is a mechanical find-and-replace phase — no new components, no new logic. Replace 396 hardcoded `slate-*` Tailwind classes across 51 files with `var(--token)` equivalents.

### Batch plan

| Batch | Target | Count | Files | Example replacement |
|-------|--------|-------|-------|-------------------|
| 1a | `bg-slate-*` | 140 | 40 | `bg-slate-800` → `bg-[var(--grey-dim)]` |
| 1b | `text-slate-*` | 261 | 44 | `text-slate-400` → `text-[var(--grey-light)]` |
| 1c | `border-slate-*` | 75 | 26 | `border-slate-700` → `border-[var(--grey)]` |

### Replacement mapping

| Tailwind Class | CSS Variable | Hex Value |
|---------------|-------------|-----------|
| `slate-900` | `var(--black)` | `#0f172a` |
| `slate-800` | `var(--grey-dim)` | `#1e293b` |
| `slate-700` | `var(--grey)` | `#334155` |
| `slate-600` | `var(--grey-mid)` | `#475569` |
| `slate-500` | `var(--grey-muted)` | `#64748b` |
| `slate-400` | `var(--grey-light)` | `#94a3b8` |
| `slate-300` | `var(--grey-subtle)` | `#cbd5e1` |
| `slate-200` | `var(--white)` | `#f1f5f9` |

### Priority files (highest slate counts)

1. `RoomDrawer.tsx` — 48 refs
2. `IssueDrawer.tsx` — 22 refs
3. `ProposalCard.tsx` (intelligence) — 21 refs
4. `Proposals.tsx` — 21 refs
5. `ConnectedEntities.tsx` — 17 refs
6. `Briefing.tsx` — 16 refs

### Execution approach

1. **Discover actual counts first.** Run `grep -r "bg-slate-" time-os-ui/src/ --include="*.tsx" --include="*.ts" | wc -l` (and same for `text-slate-`, `border-slate-`). The BUILD_PLAN.md counts (140, 261, 75) were from Session 0 — they may have shifted after Phase 0 dedup.
2. **Replace one batch at a time.** Do all `bg-slate-*` first, verify, then `text-slate-*`, verify, then `border-slate-*`.
3. **Verify after each batch:** `tsc --noEmit` on Mac. Colors should be visually identical since token values = slate hex values.
4. **After all batches:** `grep -r "slate-" time-os-ui/src/ --include="*.tsx" --include="*.ts"` must return 0 hits.
5. **Prettier:** Run `cd time-os-ui && pnpm exec prettier --write src/ && cd ..` after all replacements (since this touches many files).

### Verification

- `npx tsc --noEmit` — must compile clean after each batch
- `grep -r "slate-" time-os-ui/src/ --include="*.tsx" --include="*.ts"` → 0 hits after all batches
- Visual check: open app, pages should look identical (tokens match slate hex values)

## Key Rules (learned hard way in Sessions 1-5)

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
11. **Discovery before fix commands.** Investigate actual state before giving fix commands. Never use placeholders in command blocks. (Session 5: `<new files>` placeholder caused parse error.)
12. **Don't claim readiness without reading all files.** Read HANDOFF.md, CLAUDE.md, BUILD_STRATEGY.md, BUILD_PLAN.md, SESSION_LOG.md, AND the source files for the assigned work before starting.

## Documents to Read (in order)

1. **This file (HANDOFF.md)** — you're reading it, now follow the order below
2. `CLAUDE.md` — coding standards, sandbox rules, verification requirements
3. `BUILD_STRATEGY.md` §3 — entry/exit checklists, session contract
4. `BUILD_PLAN.md` "Phase 1: Slate Migration" (line 949) — the full spec with replacement mapping
5. `SESSION_LOG.md` — what's done, current state, lessons learned

## Quick Reference

- **Repo:** `moh-time-os` on branch `main`
- **UI root:** `time-os-ui/src/`
- **Design tokens:** `design/system/tokens.css`
- **Accent color (D1):** `#3b82f6` (blue)
- **Tertiary text (D2):** `slate-400` / `#94a3b8`
- **Do NOT run:** `uv sync`, `pnpm install`, `ruff format`, `npx`, or dev servers from the sandbox
- **To format Python files:** give Molham `uv run pre-commit run ruff-format --files <paths>`
- **To format TS/TSX files:** give Molham `cd time-os-ui && pnpm exec prettier --write <paths> && cd ..`
- **To verify types:** give Molham `npx tsc --noEmit` (Mac only)
