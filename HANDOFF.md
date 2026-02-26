# Session Handoff

**Last updated:** 2026-02-26, end of Session 4
**Branch:** `main` (PR #28 merged)

## What Just Happened

Phase -1 (Backend Cleanup) is complete. PR #28 merged with all 26 CI checks passing. Key work across Sessions 1-4:

1. Narrowed 593 `except Exception` blocks to specific types, fixed SQL injection, removed 6 duplicate routes, deleted wave2_router.py
2. Enforced S110/S112/S113 everywhere (22 violations fixed), resolved all 53 mypy errors (baseline emptied), formatted 264 files
3. Eliminated all nosec/noqa bypass comments with root-cause fixes (MD5→SHA256, /tmp→tempfile, urllib→httpx)
4. Pinned ruff 0.15.1 and bandit 1.9.3, added types-PyYAML, deduplicated B608/S608, fixed CI test paths

## What's Next

**Phase 0: Design System Foundation** — Type A build session.

Read BUILD_PLAN.md "Phase 0: Design System Foundation" section for the full spec. Each step has exact values, file paths, and before/after. Summary:

| Step | What | Files |
|------|------|-------|
| 0.1 | Update neutral token values (5 values) | `design/system/tokens.css` |
| 0.2 | Add 3 new tokens (`--grey-mid`, `--grey-muted`, `--grey-subtle`) | `design/system/tokens.css` |
| 0.3 | Update accent color + fix hardcoded accent refs | `design/system/tokens.css` |
| 0.4 | Remove `:root` override block (lines 46-52) | `src/index.css` |
| 0.5 | Create PageLayout component | `src/components/layout/PageLayout.tsx` (new) |
| 0.6 | Create SummaryGrid component | `src/components/layout/SummaryGrid.tsx` (new) |
| 0.7 | Create MetricCard component | `src/components/layout/MetricCard.tsx` (new) |
| 0.8 | Extract issueStyles.ts | `src/lib/issueStyles.ts` (new) |
| 0.9 | Delete 6 inline component duplicates | `Signals.tsx`, `Patterns.tsx`, `Proposals.tsx` |

**Verification:** `npx tsc --noEmit` (Mac only). Ruff/bandit for any Python changes.

## Key Rules (learned hard way in Sessions 2-4)

1. **No bypasses.** Never add `nosec`, `noqa`, or `type: ignore`. Fix the root cause.
2. **Stage everything.** Before committing, `git add` all modified files to prevent ruff-format stash conflicts.
3. **Verify gates.** Run ruff check + ruff format + tests locally before giving commit commands.
4. **Document immediately.** Update SESSION_LOG.md after each commit, not at session end.
5. **Zero mypy baseline.** `.mypy-baseline.txt` is empty. Keep it that way.
6. **Never format from sandbox.** Use `uv run pre-commit run ruff-format --files` on Mac. Sandbox ruff version differs.
7. **Protected files need blessing.** Changes to ci.yml, pyproject.toml, .pre-commit-config.yaml only take effect after blessing in enforcement repo.
8. **Governance keywords on HEAD.** Large PRs need "large-change" and deletion rationale in the latest commit message.

## Documents to Read (in order)

1. **This file (HANDOFF.md)** — you're reading it, now follow the order below
2. `CLAUDE.md` — coding standards, sandbox rules, verification requirements
3. `BUILD_STRATEGY.md` §3 — entry/exit checklists, session contract
4. `BUILD_PLAN.md` "Phase 0: Design System Foundation" — the full spec with exact values
5. `SESSION_LOG.md` — what's done, current state, lessons learned

## Quick Reference

- **Repo:** `moh-time-os` on branch `main`
- **UI root:** `time-os-ui/src/`
- **Design tokens:** `design/system/tokens.css`
- **Accent color (D1):** `#3b82f6` (blue)
- **Tertiary text (D2):** `slate-400` / `#94a3b8`
- **Do NOT run:** `uv sync`, `pnpm install`, `ruff format`, `npx`, or dev servers from the sandbox
- **To format files:** give Molham `uv run pre-commit run ruff-format --files <paths>`
- **To verify types:** give Molham `npx tsc --noEmit` (Mac only)
