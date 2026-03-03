# AGENT.md -- MOH Time OS Detection System Build

This file defines the engineering standards, environment constraints, and verification gates for the Detection System build (Phase 15a-15f).

**Location:** `detection-system/AGENT.md`
**Updated:** Pre-session
**Scope:** Backend (Python), Frontend (React/TypeScript), API (FastAPI)

---

## Environment

**Language & Runtime:**
- Backend: Python 3.11+
- Frontend: Node.js (with pnpm)
- Database: SQLite (file-based, managed by StateStore)
- API: FastAPI via uvicorn

**Key Dependencies:**
- Backend: FastAPI, httpx, google-api-python-client, google-auth
- Frontend: React 18.x, TypeScript, Vite, React Router
- Tools: ruff (lint + format), mypy, bandit, prettier

**Shared Environment:**
- Developer Mac (Darwin ARM) and sandbox Linux x86 share the same repo folder
- `.venv/` and `node_modules/` are platform-specific; binaries are incompatible
- **Sandbox CANNOT:** `uv sync`, `uv pip install`, `pip install`, `pnpm install`, `npm install`, `uvicorn`, `vite`, `pnpm dev`, `npx`, `git` commands. These MUST run on Mac.
- **Sandbox CAN:** read files, write/edit source code, run ruff/mypy/bandit via system Python, run pytest.
- **Sandbox CANNOT format files.** The sandbox ruff version (0.15.2) differs from pre-commit's pinned version (0.15.1). Always give Molham the format command to run on Mac.
- **Sandbox CANNOT run prettier.** No node_modules. Always include prettier step in commit commands for Molham.
- **Sandbox CANNOT run git.** Any git command creates `.git/index.lock` which blocks Molham's next git operation.

---

## Code Rules

**No-Bypass Rule:** Never add `noqa`, `nosec`, or `# type: ignore` to suppress warnings. Fix the root cause.

### Backend (Python)

1. **No bare except blocks.** Catch explicitly, log with context:
   ```python
   except ValueError as e:
       logging.error(f"Invalid input: {e}")
       return ErrorResponse(code="INVALID_INPUT", message=str(e))
   ```

2. **No silent failures.** Never return `{}` or `[]` on failure. Return typed error results.

3. **No f-string SQL.** Use parameterized queries or `lib/query_engine.py`.

4. **No `shell=True`** in subprocess. Use list arguments.

5. **No `hashlib.md5()`.** Use `hashlib.sha256()` (B324/S324).

6. **No hardcoded `/tmp`.** Use `tempfile.gettempdir()` (B108/S108).

7. **No `urllib.request.urlopen`.** Use `httpx.get/post` with `timeout=` (B310/S310).

8. **No `requests.get/post` without `timeout=`.** Always pass `timeout=30` (S113).

9. **No silent `except: pass` or `except: continue`.** Always `logging.debug()` with context (S110/S112).

10. **Use `isinstance(x, A | B)` not `isinstance(x, (A, B))`.** Python 3.11+ syntax (UP038).

### Detection-Specific Rules

11. **All calendar queries use `events JOIN calendar_attendees`.** NEVER use `calendar_events` table -- it doesn't exist. The correct pattern:
    ```sql
    SELECT e.id FROM events e
    JOIN calendar_attendees ca ON ca.event_id = e.id
    WHERE ca.email = ?
    ```

12. **Revenue queries use COALESCE with try/except.** Revenue columns may not exist in the schema yet:
    ```python
    try:
        revenue = db.execute(
            "SELECT COALESCE(ytd_revenue, 0) FROM clients WHERE id = ?", (client_id,)
        ).fetchone()
    except OperationalError:
        revenue = None  # Column doesn't exist yet -- graceful fallback
    ```

13. **Task-to-person matching:** `tasks.assignee = team_members.name` (string match, existing pattern from command_center.py line 337).

14. **Task-to-client linking:** `tasks.project_id` -> `projects.client_id` (both in schema.py).

15. **Micro-sync storage:** `collect_calendar_for_user()` fetches but does NOT persist. Must use `CalendarCollector.sync()` which calls `transform()` -> `store.insert_many()`.

### Frontend (React/TypeScript)

1. **No `any` types.** All functions and components must have explicit types.
2. **No silent errors in async.** Always catch and log.
3. **No hardcoded API URLs.** Use environment variables or relative paths.
4. **No scored lists or color-coded status labels.** The detection system replaces scoring with factual findings.

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
3. `cd time-os-ui && pnpm exec prettier --check <changed files>` -- verify format

### Both

1. Stage ALL modified files before committing (prevents ruff-format stash conflicts)
2. `uv run pre-commit run -a` -- must pass repo-wide before push
3. No protected file changes (checked by Enforcement Gate)

---

## Git Workflow

**Branches:** Always work on feature branches. Main is protected -- cannot push directly.

```bash
git checkout -b <type>/<short-description>
# Example: git checkout -b feat/detection-collision-detector
```

**Commit format:**
- Subject max 72 characters
- First letter after prefix lowercase: `feat: add collision detector`
- Use `--` (double hyphen) not `---` (em dash) in messages
- Include `Deletion rationale:` for 20+ line removals
- Include `large-change` for significant scope

**Push & PR:**
```bash
git push -u origin <branch>
gh pr create --title "feat: ..." --body "..."
gh pr merge <N> --merge --auto
gh pr checks <N> --watch
```

**CI Failure Recovery:**
1. Identify the failure (ruff, mypy, bandit, tests, prettier, tsc)
2. Fix locally, verify with that specific tool
3. Commit fresh (NEVER amend -- the previous commit didn't happen)
4. Push and watch CI again

---

## Enforcement System

A private repo (Fleezyflo/enforcement) protects critical files:

- `pyproject.toml`
- `.pre-commit-config.yaml`
- `.github/workflows/ci.yml`
- `scripts/check_mypy_baseline.py`

**What this means:** CI restores blessed copies of protected files before running checks. Your branch's version is overwritten. The Enforcement Gate blocks PRs that modify protected files.

**If you need to change a protected file:** STOP. Tell Molham what needs to change and why. He runs the blessing workflow.

---

## ADR Requirements

Governance Checks require an ADR (`docs/adr/NNNN-*.md`) when modifying:
- `lib/safety/`
- `lib/migrations/`
- `api/server.py`

Phase 15c modifies `api/server.py` -- ADR `docs/adr/0013-detection-system.md` is required.

---

## System Map

When adding UI routes to `router.tsx` or new `fetch('/api/...')` calls with literal URLs:
1. Run `uv run python scripts/generate_system_map.py`
2. Include `docs/system-map.json` in the git add
3. Drift Detection CI will fail without it

Changes to `fetchJson()` wrapper calls do NOT trigger system map drift.

---

## Common Issues & Fixes

### Pre-commit stash conflicts
**Fix:** Stage ALL modified files before committing.

### ruff format version mismatch
**Fix:** Never format from sandbox. Give Molham: `uv run pre-commit run ruff-format --files <paths>`

### prettier not found
**Fix:** Sandbox has no node_modules. Include in Mac commands: `cd time-os-ui && pnpm exec prettier --write <files>`

### tsc errors after commit
**Fix:** Always run `npx tsc --noEmit` on Mac BEFORE committing. Session 6 learned this.

### git index.lock from sandbox
**Fix:** Never run git from sandbox. Use Read/Glob/Grep tools instead.

### Sub-agent prop mismatches
**Fix:** Always grep for component interfaces before claiming sub-agent work is done. Session 6: agents used `variant` prop instead of `severity`.

---

## Session Output Format

Every session MUST produce a commit-ready output block with this structure:

```
## Session Output

### Changes Made
- File: path/to/file.py -- what changed and why
- File: path/to/other.py -- what changed and why

### Verification Results
- ruff check: PASS (zero errors)
- ruff format --check: PASS
- bandit: PASS (zero findings)
- pytest: PASS (N tests, 0 failures)
- [if UI] tsc: PASS
- [if UI] prettier: PASS

### Commit Commands for Molham
```bash
cd ~/clawd/moh_time_os
# [Mac-only verification steps]
cd time-os-ui && npx tsc --noEmit && cd ..  # if UI changes
cd time-os-ui && pnpm exec prettier --write <files> && cd ..  # if new .tsx/.ts
uv run pre-commit run ruff-format --files <paths>  # format on Mac

git checkout -b feat/<branch-name>
git add <specific files>
git commit -m "$(cat <<'EOF'
feat: short description

Body with details.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
git push -u origin feat/<branch-name>
gh pr create --title "feat: short description" --body "..."
gh pr merge <N> --merge --auto
gh pr checks <N> --watch
```

### State Updates
- state.json: what to update (task completions, PR number)
- plan/index.yaml: any phase status changes

### Errors Encountered (if any)
- Error: description
- Root cause: why it happened
- Fix: what was done
- Prevention: rule for future sessions
```

This format ensures Molham can take the output directly and execute commands without interpretation.

---

## Documents to Read

- `detection-system/plan/phase-NN.yaml` -- Current phase specification
- `detection-system/state.json` -- Current project state
- `detection-system/HANDOFF.md` -- What happened last and what's next
- `detection-system/commit-workflow.md` -- Error recovery protocol
- `docs/design/DETECTION_SYSTEM_DESIGN.md` -- Full design document (source of truth)
- `CLAUDE.md` -- Repo-level engineering rules (always applies)
