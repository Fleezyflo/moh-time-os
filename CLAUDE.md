# MOH Time OS — Agent Instructions

## Sandbox Boundary

The Cowork sandbox is Linux x86. Molham's machine is macOS ARM. They share this repo folder. Any execution from the sandbox creates incompatible binaries, bytecode, or cache files that corrupt the project.

**Sandbox can:** read files, write/edit source code, read-only git (status, diff, log, branch).

**Sandbox cannot run anything else.** No Python (pytest, ruff, mypy, bandit, uv, pip, python). No Node (pnpm, npm, npx). No scripts. No servers. No git commit or git push.

All execution happens on Molham's Mac. When work is done, provide a single copy-paste command block for him to run.

## Project

**Stack:** Python 3.11 (FastAPI, SQLite), React/TypeScript (time-os-ui/). uv for Python, pnpm for JS.

**Repo:** `Fleezyflo/moh-time-os` at `~/clawd/moh_time_os`

**Task queue:** `HEARTBEAT.md` in repo root. Numbered. Work in order unless redirected.

## Directory Map

- `lib/intelligence/` — pipeline engine, signals, patterns, scoring
- `lib/collectors/` — data collectors (Gmail, calendar, tasks, etc.)
- `lib/ui_spec_v21/` — UI specification and state machine
- `lib/safety/` — safety checks and guardrails
- `lib/contracts/` — data contracts and schemas
- `lib/observability/` — tracing, logging
- `lib/executor/` — legacy action execution (not in maintained scope)
- `lib/query_engine.py` — parameterized SQL query builder (use for all SQL)
- `api/` — FastAPI server, routes, intelligence router
- `api/auth.py` — Bearer token authentication
- `scripts/` — CI check scripts, migration tools, code generation
- `tests/` — contract, golden, negative, property, scenario, smoke tests
- `time-os-ui/` — React frontend

## Maintained Scope

Lint, format, and bandit are scoped to:

```
lib/ui_spec_v21/  lib/collectors/  lib/safety/
lib/contracts/    lib/observability/  api/
```

Plus `tests/` for pre-commit.

Everything outside is legacy. Don't scan it, don't fix it, don't reference it as a pattern. Only read it to trace call chains.

If pre-commit shows "Skipped" on a changed test file, the file fell outside scope. Flag it to Molham.

## CI Checks

Required: Enforcement Integrity, Enforcement Gate, Python Quality, Python Tests, Drift Detection, UI Quality, System Invariants, Security Audit, API Smoke Test, Governance Checks, Reproducibility Pins, Golden Scenarios, Extended Tests, DB Migration Rehearsal

## Enforcement System

Private repo `Fleezyflo/enforcement` protects critical files. The protected files list lives at `protected-files.txt` in that repo. Do not maintain a separate list.

**CI restore:** Every CI job overwrites protected files with blessed copies after checkout, before running checks. Branch versions are ignored.

**Enforcement Gate:** Independent workflow compares PR branch against blessed copies. Posts failure status if they differ. Main Gate requires this status to merge.

**Defense in depth:** Branch modifications to protected files are both ignored by CI (restore) and blocked from merging (Gate).

**Rules:**

- Branch having a different version of a protected file than blessed is normal. CI ignores it. Do not "fix" it.
- Never copy blessed files into a branch manually.
- If blessed is ahead of main, a blessed PR hasn't merged yet. Find and merge it.
- Changing a protected file requires Molham. Stop, explain what needs to change and why. He runs the blessing workflow.
- If Enforcement Integrity fails and no protected file was touched, likely a token expiry. Tell Molham.

## Commands for Molham

All commands below are for Molham to run on his Mac.

**Before pushing:**

```bash
uv run ruff check <changed-dirs> --fix && uv run ruff format <changed-dirs>
uv run bandit -r <changed-dirs> -ll --skip B101,B608
uv run pytest <relevant-tests> -v --tb=short
uv run python scripts/check_system_invariants.py
uv run python scripts/export_openapi.py && uv run python scripts/export_schema.py && uv run python scripts/generate_system_map.py && git diff --exit-code docs/
uv run pre-commit run -a
```

**After pushing:**

```bash
gh pr checks <PR#> 2>&1
```

**Debugging failed CI:**

```bash
gh run view --log-failed -R Fleezyflo/moh-time-os $(gh run list -R Fleezyflo/moh-time-os --branch <branch> --status failure --json databaseId --jq '.[0].databaseId') 2>&1 | tail -60
```
