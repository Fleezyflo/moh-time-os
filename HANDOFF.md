# Session Handoff

**Last updated:** 2026-03-02, Session 19 (Phase 13 built, pending commit)
**Branch:** `main` (need feature branch for Phase 13)

## What Just Happened

Session 19: Built Phase 13 (Collector Data Depth). Phases 9-12 confirmed merged via PR #47.

### Phase 13 Summary
- **13.1 (investigation):** All 22 collector secondary tables already exist in schema.py and the live database. No migrations needed. Xero has 7,802 rows; other collectors empty but tables present.
- **13.2:** Added 8 query_engine methods (client_email_participants, client_attachments, client_invoice_detail, person_calendar_detail, task_asana_detail, chat_analytics, financial_detail, asana_portfolio_context).
- **13.3:** Added 8 spec_router endpoints using QueryEngine lazy singleton.
- **13.4:** Added ~250 lines of types + 8 fetch functions to api.ts, 8 hooks to hooks.ts.
- **13.5-13.7:** Added 3 new tabs to ClientDetailSpec: Email Participants, Attachments, Invoice Detail.
- **13.8:** Added Calendar Detail tab to TeamDetail (TabContainer wrapping existing content).
- **13.9:** Added Asana Detail tab to TaskDetail (TabContainer wrapping existing content).
- **13.10:** Added Chat Analytics tab to Operations (4th tab).
- **13.11-13.12:** Added Financial Detail + Asana Context collapsible sections to Portfolio.

## What's Next

### Commit Phase 13

Run from `~/clawd/moh_time_os`:

```bash
# 1. Switch to main and pull
git checkout main && git pull

# 2. Create feature branch
git checkout -b phase-13-collector-depth

# 3. Verify types compile
cd time-os-ui && npx tsc --noEmit && cd ..

# 4. Format all changed files
cd time-os-ui && pnpm exec prettier --write \
  src/lib/api.ts \
  src/lib/hooks.ts \
  src/pages/ClientDetailSpec.tsx \
  src/pages/TeamDetail.tsx \
  src/pages/TaskDetail.tsx \
  src/pages/Operations.tsx \
  src/pages/Portfolio.tsx \
  && cd ..

# 5. Regenerate system map (no new routes, but verify)
uv run python scripts/generate_system_map.py

# 6. Stage files
git add \
  lib/query_engine.py \
  api/spec_router.py \
  time-os-ui/src/lib/api.ts \
  time-os-ui/src/lib/hooks.ts \
  time-os-ui/src/pages/ClientDetailSpec.tsx \
  time-os-ui/src/pages/TeamDetail.tsx \
  time-os-ui/src/pages/TaskDetail.tsx \
  time-os-ui/src/pages/Operations.tsx \
  time-os-ui/src/pages/Portfolio.tsx \
  docs/system-map.json \
  SESSION_LOG.md \
  HANDOFF.md \
  BUILD_PLAN.md

# 7. Commit
git commit -m "$(cat <<'EOF'
feat: add collector data depth -- 8 new endpoints, tabs on 5 pages

Phase 13 -- surface collector secondary table data in the UI.

Backend: 8 new query_engine methods querying 20 collector tables
(gmail_participants, asana_custom_fields, xero_line_items, etc).
8 new spec_router endpoints under /api/v2/*.

Frontend: 3 new tabs on Client Detail (email participants,
attachments, invoice detail). Calendar tab on Team Detail.
Asana tab on Task Detail. Chat Analytics tab on Operations.
Financial + Asana sections on Portfolio.

All tables already exist in schema -- no migrations needed.
Xero tables have live data; others populate when collectors run.

large-change

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"

# 8. Push and create PR
git push -u origin phase-13-collector-depth
gh pr create --title "feat: phase 13 -- collector data depth" --body "$(cat <<'EOF'
## Summary
- 8 new `query_engine.py` methods for cross-entity collector data queries
- 8 new `spec_router.py` endpoints: email-participants, attachments, invoice-detail, calendar-detail, asana-detail, chat/analytics, financial/detail, projects/asana-context
- 8 new fetch functions + 8 new hooks in api.ts/hooks.ts
- 3 new tabs on Client Detail: Email Participants, Attachments, Invoice Detail
- Calendar Detail tab on Team Detail
- Asana Detail tab on Task Detail (custom fields, subtasks, stories, dependencies, attachments)
- Chat Analytics tab on Operations (spaces, reactions, attachments)
- Financial Detail + Asana Context sections on Portfolio

## Files
- `lib/query_engine.py` — 8 new methods (~270 lines)
- `api/spec_router.py` — 8 new endpoints + QueryEngine singleton (~160 lines)
- `lib/api.ts` — types + fetch functions (~270 lines)
- `lib/hooks.ts` — 8 new hooks (~55 lines)
- 5 pages modified: ClientDetailSpec, TeamDetail, TaskDetail, Operations, Portfolio

## Test plan
- [ ] Client Detail: Email Participants tab shows participants and labels
- [ ] Client Detail: Attachments tab shows attachment list with file sizes
- [ ] Client Detail: Invoice Detail tab shows line items and credit notes
- [ ] Team Detail: Calendar tab shows attendees and recurrence rules
- [ ] Task Detail: Asana tab shows custom fields, subtasks, stories, deps, attachments
- [ ] Operations: Chat Analytics tab shows spaces, reactions, attachments
- [ ] Portfolio: Financial Detail section shows contacts, transactions, tax rates
- [ ] Portfolio: Asana Context section shows portfolios and goals
- [ ] Empty tables show meaningful empty states (not errors)
- [ ] Backend endpoints return 200 with empty arrays when tables have no data

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
gh pr merge --merge --auto
gh pr checks --watch
```

## Key Rules (learned hard way in Sessions 1-19)

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
4. `BUILD_PLAN.md` -- all phases complete, review final state
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
