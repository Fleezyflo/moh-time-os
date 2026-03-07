# AGENT.md -- MOH Time OS Audit Remediation

This file defines the engineering standards, environment constraints, and verification gates for the Audit Remediation build (phases 01-13).

**Location:** `audit-remediation/AGENT.md`
**Updated:** 2026-03-06
**Scope:** Backend (Python), Frontend (React/TypeScript), API (FastAPI)
**Source:** WORKSTREAM_AUDIT.md findings -- 43 tasks across 24 workstreams

---

## Project Overview

The audit remediation addresses findings from a comprehensive 24-workstream audit. Work is organized into two parallel tracks:

- **Track T1 (phases 01-06):** Fix bugs, wire 20+ unwired intelligence modules, audit error masking. Sequential -- each phase depends on the one before it (except 02-05 which run in parallel after 01).
- **Track T2 (phases 07-13):** Verification-only phases. Mostly independent. Some blocked on T1 wiring completion.

**Dependency graph:**
```
phase-01 (compat + bugs) ──┬── phase-02 (data quality + deepening) ──┐
                           ├── phase-03 (memory + observability) ─────┤
                           ├── phase-04 (notifications + governance) ─┤
                           └── phase-05 (scenario + temporal + routing)┤
                                                                       └── phase-06 (error masking audit)

phase-07 (verify foundation)     -- T2, no deps
phase-08 (verify cleanup + API)  -- T2, no deps
phase-09 (verify operations)     -- T2, no deps
phase-10 (verify intelligence)   -- T2, depends on phase-05
phase-11 (verify infrastructure) -- T2, no deps
phase-12 (verify UI + arch)      -- T2, depends on phase-02
phase-13 (verify integration)    -- T2, no deps
```

---

## Environment

Inherits from the repo-level `CLAUDE.md`. Key points:

**Shared Environment:**
- Developer Mac (Darwin ARM) and sandbox Linux x86 share the same repo folder.
- **Sandbox CANNOT:** `uv sync`, `uv pip install`, `pip install`, `pnpm install`, `npm install`, `uvicorn`, `vite`, `pnpm dev`, `npx`, `git`.
- **Sandbox CAN:** read files, write/edit source code, run ruff/mypy/bandit via system Python, run pytest.
- **Sandbox CANNOT format files.** ruff version mismatch. Give Molham format commands.
- **Sandbox CANNOT run prettier.** No node_modules.
- **Sandbox CANNOT run git.** Creates .git/index.lock.

---

## Hard Rules — Violations Fail the Session

**These are non-negotiable. Breaking any of these means the session output is rejected.**

1. **Commit subject line MUST be under 72 characters.** Count them. `type: description` total. Session 6 failed at 87 chars. If your subject is too long, shorten it. No exceptions.

2. **Never bypass a failing check.** No `noqa`, `nosec`, `# type: ignore`, `# pragma: no cover`, `continue-on-error: true`, `|| true`, `--no-verify`, `-x` to skip remaining tests, or any other suppression. If a test fails, fix the code. If a linter flags something, fix the code. If you cannot fix it, stop and tell Molham. Never make the tool shut up.

3. **Never force tests to pass.** Do not modify test assertions to match wrong output. Do not delete failing tests. Do not mark tests as `@pytest.mark.skip`. Do not catch exceptions in tests to swallow failures. If a test fails, the code is wrong — fix the code, not the test.

4. **Never add dead code to satisfy a check.** Do not add unused imports, empty functions, or dummy implementations just to make a linter or type checker happy.

---

## Code Rules

Inherits ALL rules from `CLAUDE.md`. Additionally:

### Wiring Rules (phases 02-05)

1. **Read actual method signatures before wiring.** The task files provide templates -- adapt method names to match what actually exists in each module's class. `grep` for the class, read its `__init__` and public methods.

2. **Intelligence pipeline insertion order matters.**
   - Temporal normalization → BEFORE scoring
   - Scoring → step 1
   - Data quality → AFTER scoring, BEFORE signals
   - Signals → step 2
   - Patterns → step 3
   - Cost → step 4
   - Entity profiles → AFTER scoring (aggregates everything)
   - Outcome tracking → AFTER signals (records prediction accuracy)
   - Pattern trending → AFTER patterns (tracks evolution)
   - Memory modules → END of pipeline (accumulate knowledge)
   - Audit trail → WRAPS entire pipeline (start + end)
   - Drift detection → VERY END (compares distributions)

3. **Error handling for each wired module:**
   ```python
   try:
       from lib.intelligence.MODULE import MainClass
       instance = MainClass(db_path)  # or adapt to actual constructor
       result = instance.method()
       results["key"] = len(result) if isinstance(result, list) else 1
   except (sqlite3.Error, ValueError, OSError) as e:
       logger.error(f"Intelligence: MODULE failed: {e}")
   ```
   Never use bare `except`. Never silently swallow errors.

4. **Expensive modules run periodically, not every cycle.**
   ComplianceReporter, ScenarioEngine: add a cycle counter or timestamp check.

5. **ScenarioEngine is API-only.** Never wire into the loop -- it's user-triggered.

### Verification Phase Rules (phases 07-13)

6. **Verification produces DONE or GAP.** For each check:
   - DONE: the feature works as specified
   - GAP: describe what's missing, severity, and which phase should fix it

7. **Verification does NOT fix code.** If a gap is found, file it as a new task. Do not fix inline during verification.

8. **Reference original task specs.** Each verification task references a `tasks/TASK_P3_*.md` file with the original specification.

---

## Session Pipeline

Every session follows this pipeline:

1. **Read state.json** -- what phase and session are we on?
2. **Read HANDOFF.md** -- what happened last, what's next?
3. **Read the phase YAML** -- exact tasks, files, verification criteria.
4. **Update state.json** -- mark phase in_progress, increment session.
5. **Do the work** -- follow task descriptions.
6. **Verify locally** -- run all verification checks from the task.
7. **Update state.json** -- mark tasks complete.
8. **Write session record** -- `sessions/session-NNN.yaml`
9. **Give Molham commit commands** -- single copy-paste block.

---

## Verification Requirements

Before giving Molham a commit command, verify ALL of the following locally:

### Backend (Python)

1. `ruff check <changed files>` -- zero lint errors
2. `ruff format --check <changed files>` -- zero format issues
3. `bandit -r <changed files>` -- zero security findings
4. `python -m pytest tests/ -x` -- tests pass
5. `python scripts/check_mypy_baseline.py --strict-only` -- zero mypy errors in strict islands

### Frontend (React/TypeScript) -- Mac Only

1. `cd time-os-ui && npx tsc --noEmit` -- zero type errors
2. `cd time-os-ui && pnpm exec prettier --write <changed files>` -- format new files

### Both

1. Stage ALL modified files before committing
2. `uv run pre-commit run -a` -- must pass repo-wide before push
3. No protected file changes

---

## Git Workflow

**Branches:** Always work on feature branches. Main is protected.

**Naming convention:**
- Bug fixes: `fix/python310-compat`, `fix/lane-column-ref`
- Wiring: `feat/wire-data-quality`, `feat/wire-system-memory`
- Verification: `verify/data-foundation`, `verify/ui-completeness`

**Commit format:**
- **Subject MUST be under 72 characters.** Count before writing. `feat: wire 7 memory and observability modules` = 48 chars. Good. `feat: wire decision journal, entity memory, signal lifecycle, behavioral patterns, audit trail, explainability, and drift detection` = 130 chars. Rejected.
- First letter after prefix lowercase: `feat: wire` not `feat: Wire`
- Use `--` not `---` in messages (encoding issues)
- Body includes what was wired/verified and why

---

## Session Output Format

Every session MUST produce a commit-ready output block:

```
## Session Output

### Changes Made
- File: path/to/file.py -- what changed and why

### Verification Results
- ruff check: PASS
- bandit: PASS
- pytest: PASS
- [if verification phase] Findings: N DONE, M GAP

### Commit Commands for Molham
```bash
cd ~/clawd/moh_time_os
uv run pre-commit run ruff-format --files <paths>
git checkout -b <branch-name>
git add <specific files>
git commit -m "$(cat <<'EOF'
type: short description

Body with details.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
git push -u origin <branch-name>
gh pr create --title "type: short description" --body "..."
gh pr merge <N> --merge --auto
gh pr checks <N> --watch
```

### State Updates
- state.json: what to update
- plan/index.yaml: any phase status changes
```

---

## Documents to Read

- `audit-remediation/plan/phase-NN.yaml` -- Current phase specification
- `audit-remediation/state.json` -- Current project state
- `audit-remediation/HANDOFF.md` -- What happened last and what's next
- `tasks/TASK_*.md` -- Original detailed task briefs (reference)
- `WORKSTREAM_AUDIT.md` -- Source audit findings
- `CLAUDE.md` -- Repo-level engineering rules (always applies)
- `TASK_BRIEFS.md` -- Task index with execution order and dependencies
