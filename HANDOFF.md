# Session Handoff

**Last updated:** 2026-03-02, Session 20 (Phase 14 built, pending commit)
**Branch:** `main` (need feature branch for Phase 14)

## What Just Happened

Session 20: Built Phase 14 (Cleanup, Bug Fixes & Hardening) -- the FINAL phase. All 9 sub-steps complete. Phase 13 PR #48 confirmed MERGED before starting.

### Phase 14 Summary
- **14.1:** Removed 3 dead intelligence page re-exports from index.ts. Files marked for Mac deletion (~485 lines).
- **14.2:** Added `GET /api/v2/proposals/{proposal_id}` to spec_router.py (~140 lines). Ported from server.py with 4 bug fixes + extracted `_build_signal_description()` helper.
- **14.3:** Migrated `fetchProposalDetailLegacy` → `fetchProposalDetail` in api.ts. URL changed from `/api/control-room/proposals/{id}` to `/api/v2/proposals/{id}`. Added proper TypeScript types.
- **14.4:** Migrated `fetchTasks` from `/api/tasks` to `/api/v2/priorities`. Removed response shape translation. Fixes TeamDetail `.items` bug.
- **14.5:** Fixed 6 stale `slate-*` Tailwind classes in 4 governance files. Zero remain.
- **14.6:** Created `ExportButton.tsx` (client-side CSV). Wired to TaskList, Priorities, Issues, Commitments.
- **14.7:** Added 12 `--chart-*` CSS custom properties to tokens.css. Updated chartColors.ts to read from CSS vars with fallbacks.
- **14.8:** Replaced `/fix-data` route with redirect to `/ops`. FixData.tsx marked for deletion.
- **14.9:** Verification passed: 0 slate-* classes, 0 legacy API calls in api.ts, ruff clean, bandit clean.

## What's Next

### FULL BUILDOUT COMPLETE

After committing Phase 14, all 16 phases (-1 through 14) are done. The product is shippable.

### Commit Phase 14

Run from `~/clawd/moh_time_os`:

```bash
# 1. Switch to main and pull
git checkout main && git pull

# 2. Create feature branch
git checkout -b phase-14-cleanup-hardening

# 3. Delete dead files (sandbox couldn't delete)
rm time-os-ui/src/intelligence/pages/CommandCenter.tsx \
   time-os-ui/src/intelligence/pages/Briefing.tsx \
   time-os-ui/src/intelligence/pages/Proposals.tsx \
   time-os-ui/src/pages/FixData.tsx

# 4. Verify types compile
cd time-os-ui && npx tsc --noEmit && cd ..

# 5. Format all changed/new files
cd time-os-ui && pnpm exec prettier --write \
  src/lib/api.ts \
  src/components/RoomDrawer.tsx \
  src/intelligence/pages/index.ts \
  src/components/governance/GovernanceDomainCards.tsx \
  src/components/governance/DataQualityHealthScore.tsx \
  src/components/governance/BundleTimeline.tsx \
  src/components/governance/ApprovalQueue.tsx \
  src/components/ExportButton.tsx \
  src/pages/TaskList.tsx \
  src/pages/Priorities.tsx \
  src/pages/Commitments.tsx \
  src/pages/Issues.tsx \
  src/intelligence/components/chartColors.ts \
  src/router.tsx \
  && cd ..

# 6. Regenerate system map (route change: /fix-data removed, redirect added)
uv run python scripts/generate_system_map.py

# 7. Stage files
git add \
  api/spec_router.py \
  design/system/tokens.css \
  time-os-ui/src/lib/api.ts \
  time-os-ui/src/components/RoomDrawer.tsx \
  time-os-ui/src/intelligence/pages/index.ts \
  time-os-ui/src/intelligence/pages/CommandCenter.tsx \
  time-os-ui/src/intelligence/pages/Briefing.tsx \
  time-os-ui/src/intelligence/pages/Proposals.tsx \
  time-os-ui/src/pages/FixData.tsx \
  time-os-ui/src/components/governance/GovernanceDomainCards.tsx \
  time-os-ui/src/components/governance/DataQualityHealthScore.tsx \
  time-os-ui/src/components/governance/BundleTimeline.tsx \
  time-os-ui/src/components/governance/ApprovalQueue.tsx \
  time-os-ui/src/components/ExportButton.tsx \
  time-os-ui/src/pages/TaskList.tsx \
  time-os-ui/src/pages/Priorities.tsx \
  time-os-ui/src/pages/Commitments.tsx \
  time-os-ui/src/pages/Issues.tsx \
  time-os-ui/src/intelligence/components/chartColors.ts \
  time-os-ui/src/router.tsx \
  docs/system-map.json \
  SESSION_LOG.md \
  HANDOFF.md \
  BUILD_PLAN.md

# 8. Commit
git commit -m "$(cat <<'EOF'
feat: phase 14 cleanup -- kill dead code, migrate legacy APIs, harden design system

Phase 14 -- Cleanup, Bug Fixes & Hardening (final phase).

Backend: Add GET /api/v2/proposals/{id} with signal enrichment
(ported from server.py with 4 bug fixes, ~140 lines).

Frontend: Migrate fetchProposalDetail and fetchTasks to v2 endpoints.
Delete 4 dead page files (~800 lines). Fix 6 stale slate-* classes
in governance components. Add ExportButton (client-side CSV) to 4
list pages. Migrate chart colors to CSS custom properties. Replace
/fix-data route with redirect to /ops.

Deletion rationale: 4 dead page files (~800 lines total). 3 intelligence
pages replaced by Portfolio/Inbox in Phase 3 with redirect rules. 1
FixData page replaced by Operations tab in Phase 3.

large-change

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"

# 9. Push and create PR
git push -u origin phase-14-cleanup-hardening
gh pr create --title "feat: phase 14 -- cleanup, bug fixes & hardening" --body "$(cat <<'EOF'
## Summary
- Add `GET /api/v2/proposals/{id}` endpoint with signal enrichment (4 bug fixes from legacy)
- Migrate `fetchProposalDetail` and `fetchTasks` to v2 endpoints (zero legacy API calls remain)
- Delete 4 dead page files (~800 lines): CommandCenter, Briefing, Proposals, FixData
- Fix 6 stale `slate-*` Tailwind classes in governance components (zero remain)
- Add `ExportButton` component (client-side CSV) to TaskList, Priorities, Issues, Commitments
- Migrate chart colors to CSS custom properties in tokens.css (12 new vars)
- Replace `/fix-data` standalone route with redirect to `/ops`

## Verification
- `grep -r "slate-" src/ --include="*.tsx" --include="*.ts"` → 0 results
- `grep -r "control-room" src/lib/api.ts` → 0 results
- `ruff check api/spec_router.py` → 0 errors
- `bandit -r api/spec_router.py` → 0 findings

## Test plan
- [ ] TaskList renders tasks from `/api/v2/priorities`
- [ ] TeamDetail tasks tab shows data (`.items` fix)
- [ ] Proposal detail drawer loads via `/api/v2/proposals/{id}`
- [ ] Export CSV buttons download correct data on all 4 list pages
- [ ] Governance components render with correct token colors (no slate)
- [ ] Chart colors resolve from CSS custom properties
- [ ] `/fix-data` redirects to `/ops`
- [ ] `/intel/briefing`, `/intel/proposals` redirects still work
- [ ] CI passes (tsc, prettier, ruff, bandit, tests)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
gh pr merge --merge --auto
gh pr checks --watch
```

## Key Rules (learned hard way in Sessions 1-20)

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

## Documents to Read (in order)

1. **This file (HANDOFF.md)** -- you're reading it, now follow the order below
2. `CLAUDE.md` -- coding standards, sandbox rules, verification requirements
3. `BUILD_STRATEGY.md` §3 -- entry/exit checklists, session contract
4. `BUILD_PLAN.md` -- ALL PHASES COMPLETE, review final state
5. `SESSION_LOG.md` -- what's done, current state, lessons learned

## Quick Reference

- **Repo:** `moh-time-os` on branch `main`
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
