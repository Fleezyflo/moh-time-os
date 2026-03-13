# HANDOFF -- Audit Remediation

**Generated:** 2026-03-12
**Current Phase:** systemic-remediation (VERIFIED -- READY TO COMMIT)
**Current Session:** 22
**Track:** Systemic audit remediation (post-audit)

---

## Status: All 9 Files Verified and Bug-Fixed

Session 22 completed full verification of all 9 files edited in Session 21. Found and fixed 4 bugs:

1. **`state_tracker.py` line 79** — `sqlite3.Row` doesn't support `.get()`. Fixed: bracket access with None guard.
2. **`backup.py`** — No SQLite version guard for `VACUUM INTO`. Fixed: runtime version check with fallback to checkpoint + copy.
3. **`xero_client.py` line 117** — Logged 8 chars of refresh token. Fixed: removed token prefix from log message.
4. **`health.py` line 15** — Module-level `import httpx` breaks test isolation. Fixed: moved import inside `_alert_on_degradation()` with ImportError guard.

Verification log: `audit-remediation/VERIFICATION_LOG_S22.md`

**All files pass ruff check, ruff format (except xero_client.py needs Mac formatting), and bandit with zero issues.**

**None of this has been committed. All changes are in the working tree. Ready for the 4-PR commit sequence below.**

---

## What Just Happened

### Session 20 (completed)

PR #95 merged (branch: `fix/sync-calendar-asana`):
1. Calendar attendees PK mismatch fixed (INTEGER → TEXT)
2. Asana sequential pagination: RateLimiter + ThreadPoolExecutor
3. Test fixes for sys.modules pollution and exception types
4. ADR-0020 documents the schema change

### Session 21 (completed -- code written, not committed)

Systemic audit identified 10 architectural issues. A 5-PR remediation plan was approved. Implementation done across 9 files but without proper verification. Session 21 also added Pre-Edit Gate, verification log template, and Session 21 incident report to CLAUDE.md.

### Session 22 (current)

Verified all 9 files. Fixed 4 bugs found during verification. Created VERIFICATION_LOG_S22.md. Ready for commit sequence.

---

## What's Next — Exact PR Sequence

**You must follow this sequence exactly. One PR per row. No bundling. No reordering.**

### PR 1: Credentials to env vars
| File | Status |
|------|--------|
| `engine/asana_client.py` | VERIFIED — env var loading correct |
| `engine/xero_client.py` | FIXED — removed token prefix from log |

Branch: `fix/credentials-env-vars`

### PR 2: Data loss + write lock + state tracker
| File | Status |
|------|--------|
| `lib/collectors/base.py` | VERIFIED — COLLECTOR_ERRORS imported, update_sync_state signature matches |
| `lib/state_store.py` | VERIFIED — _write_lock correct for singleton with per-call connections |
| `lib/state_tracker.py` | FIXED — sqlite3.Row bracket access instead of .get() |

Branch: `fix/data-loss-write-safety`

### PR 3: Backup VACUUM INTO
| File | Status |
|------|--------|
| `lib/backup.py` | FIXED — SQLite version guard with fallback to checkpoint + copy |

Branch: `fix/backup-vacuum-into`

### PR 4: Schema + alerting + API handler
| File | Status |
|------|--------|
| `lib/schema_engine.py` | VERIFIED — standard SQLite savepoint pattern |
| `lib/observability/health.py` | FIXED — httpx import moved inside method with ImportError guard |
| `api/server.py` | VERIFIED — standard FastAPI pattern, Request/JSONResponse/os imported |

Branch: `fix/schema-alerting-api-handler`

### For each PR:
1. Molham runs `uv run pre-commit run ruff-format --files <files>` to format
2. Molham runs `uv run python -m pytest tests/ -x` to verify
3. Commit ONLY that PR's files + verification log
4. Push, create PR, set auto-merge, watch CI
5. Wait for merge before starting next PR

---

## Key Rules

1. You write code. You never run anything.
2. Commit subject under 72 chars, valid types only
3. **READ BEFORE YOU WRITE (Session 21).** Before editing any function, read every function your new code calls. Grep for `def <name>`. Read the source. Confirm signature and return type. No exceptions.
4. **NEVER CALL UNVERIFIED INTERFACES (Session 21).** If you haven't read `def function_name` in this session, you don't call it.
5. **ONE PR, ONE PURPOSE (Session 21).** If a plan says 5 PRs, you produce 5 PRs. Never bundle.
6. If 20+ deletions, include "Deletion rationale:" in body
7. Match existing patterns obsessively
8. No comments in command blocks
9. `lib/governance/` has REAL production classes -- `lib/intelligence/data_governance.py` has toy in-memory versions.
10. Intelligence error responses must use `JSONResponse(content=_error_response(...))`, NOT `raise HTTPException(detail=...)` for 500 errors.

---

## Documents to Read

1. `audit-remediation/AGENT.md` -- This brief
2. `audit-remediation/state.json` -- Current project state
3. `CLAUDE.md` -- Repo-level engineering rules (UPDATED Session 21 with pre-edit gate, never-assume rule, one-PR-one-purpose rule)
4. `audit-remediation/VERIFICATION_LOG_S22.md` -- Verification log for this session
