# HANDOFF — Audit Remediation

**Generated:** 2026-03-06
**Current Phase:** phase-01 (Python Compatibility + Bug Fixes)
**Current Session:** 0 (not started)
**Track:** T1

---

## What Just Happened

Project initialized from WORKSTREAM_AUDIT.md findings. 43 tasks across 24 workstreams organized into 13 phases on 2 parallel tracks. No work started yet.

---

## What's Next

### Phase 01: Python Compatibility + Bug Fixes

**Session goal:** Complete all 4 tasks in a single session.

**Task 01:** Fix `from datetime import UTC` in 29 files.
- Create `lib/compat.py` with `UTC = timezone.utc` shim
- Replace all imports
- Verify: `grep -r "from datetime import UTC"` returns empty

**Task 02:** Fix `from enum import StrEnum` in 15 files.
- Add StrEnum backport to `lib/compat.py`
- Replace all imports
- Verify: `grep -r "from enum import StrEnum"` returns empty

**Task 03:** Fix `t.lane` to `t.lane_id` in `lib/lane_assigner.py:190`.

**Task 04:** Wrap hardcoded email in `lib/integrations/chat.py:31` with `os.environ.get()`.

**Branch:** `fix/python310-compat`

---

## Key Rules

1. Never run git from sandbox (creates .git/index.lock)
2. Never format from sandbox (ruff version mismatch)
3. Read actual module signatures before wiring (phases 02-05)
4. ScenarioEngine is API-only, never in loop
5. Verification phases report DONE or GAP, never fix inline
6. All rules from CLAUDE.md apply

---

## Documents to Read

1. `audit-remediation/AGENT.md` -- Engineering standards for this project
2. `audit-remediation/plan/phase-01.yaml` -- Current phase specification
3. `audit-remediation/state.json` -- Current project state
4. `CLAUDE.md` -- Repo-level engineering rules
5. `tasks/TASK_TR_1_1_FIX_DATETIME_UTC_IMPORTS.md` -- Detailed task brief for task-01
6. `tasks/TASK_TR_1_2_FIX_STRENUM_IMPORTS.md` -- Detailed task brief for task-02
