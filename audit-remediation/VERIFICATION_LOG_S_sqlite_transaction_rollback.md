# Verification Log — fix/transaction-rollback-all-exceptions

**Session:** transaction rollback fix, both DB adapters (ad-hoc task)
**Date:** 2026-06-02
**Agent:** Opus 4.8 (1M context)

---

## Scope

One file, one bug class, two sibling methods. `SQLiteAdapter.transaction()` and
`PostgreSQLAdapter.transaction()` in `lib/db_opt/db_adapter.py` both caught only
`(sqlite3.Error, ValueError, OSError)`, so any other exception raised inside the
`with adapter.transaction():` block skipped the except, the rollback never ran, and
the open transaction was left dangling / partially applied (SQLite) or in an
aborted-transaction state (PostgreSQL) — a data-integrity bug in both. Both widened
to `except Exception:` → rollback → re-raise (error logged, not swallowed).

Shipped as one branch, two commits (one per adapter) so each is independently
revertable via `git revert <sha>`. Same logical change applied to two sibling
methods — satisfies "One PR, One Purpose" (this is one concern, not unrelated
bundling like the Session 21 incident).

## Pre-Edit Verification

No new method calls were introduced in either edit; both only widen the caught
exception type. The rollback/commit calls already existed in the prior code.

| File edited | Method/attr relied on | Defined at (file:line) | Confirmed | Matches usage | Callers checked |
|-------------|-----------------------|------------------------|-----------|---------------|-----------------|
| lib/db_opt/db_adapter.py | `self.conn` (sqlite3.Connection \| None, None-guarded) | db_adapter.py:73, guard 179-181 | yes | yes | grep `.transaction()` → only tests/test_db_adapter.py:112,121 call SQLite path |
| lib/db_opt/db_adapter.py | `self.conn.execute("ROLLBACK")` (SQLite, already present) | sqlite3.Connection.execute (stdlib) | yes | yes | N/A |
| lib/db_opt/db_adapter.py | `self.conn` (psycopg2 connection, None-guarded) | db_adapter.py:229, guard 282-283 | yes | yes | no in-repo caller of PG path (PG adapter not instantiated outside tests; psycopg2 not installed) |
| lib/db_opt/db_adapter.py | `self.conn.commit()` / `self.conn.rollback()` (psycopg2, already present) | PEP 249 DB-API; psycopg2 conn (autocommit=False set at db_adapter.py:234) | yes | yes (only except widened, calls unchanged) | N/A |
| (test exercising SQLite path) | `with adapter.transaction():` raising RuntimeError | tests/test_db_adapter.py:117-127 | yes | yes (RuntimeError now triggers ROLLBACK) | N/A |

**Changes (both at lib/db_opt/db_adapter.py):**
- SQLite (~line 187): `except (sqlite3.Error, ValueError, OSError) as e:` → `except Exception as e:` (logger.error kept, ROLLBACK, re-raise)
- PostgreSQL (~line 287): `except (sqlite3.Error, ValueError, OSError):` → `except Exception:` (rollback, re-raise)

`import sqlite3` (module level) remains required — SQLiteAdapter uses it throughout;
ruff did not flag it as unused after removing the two `sqlite3.Error` references.

## Pre-Commit Verification

| Check | Result | Output snippet |
|-------|--------|---------------|
| `ruff check` on changed file | PASS | "All checks passed!" |
| `ruff check` repo-wide (concise) | PASS | "All checks passed!" |
| `ruff format --check` on changed file | PASS | "1 file already formatted" |
| `bandit -ll --skip B101,B608` on changed file | PASS | exit 0, no findings |
| SQLite target test (previously FAILING) | PASS | `test_adapter_transaction_rollback` now passes |
| full file `pytest tests/test_db_adapter.py` | PASS | "67 passed" |
| Every method call in changed file resolves | PASS | `self.conn.execute` / `.commit` / `.rollback` (stdlib + psycopg2 DB-API) + `logger.error`; no new prod-interface calls |
| Verification log included in `git add` | PASS | this file staged with the commit |

**PG fix test coverage — honest limitation:** there is NO test exercising
`PostgreSQLAdapter.transaction()`. The only PG tests (tests/test_db_adapter.py:623-637)
assert it raises ImportError because psycopg2 is not installed in this environment. The
PG fix is therefore verified by **reading + symmetry** with the test-proven SQLite fix
(identical bug, identical structure, same `except` widening), NOT by a passing test. It
cannot be test-proven here without psycopg2.

## PR Scope Check

| Planned change | Files in this commit | Matches plan? |
|-----------|---------------------|--------------|
| Widen transaction rollback to all exceptions, both adapters | lib/db_opt/db_adapter.py, this log | yes — one file, one bug class, two sibling methods, two revertable commits |

## ADR note

No ADR created or required. CI Governance (`.github/workflows/ci.yml:251-252`) runs
`scripts/check_adr_required.sh`, whose trigger list (lines 21-29) is `lib/safety/schema.py`,
`lib/migrations/`, `docs/schema.sql`, `api/server.py`, `api/spec_router.py`, `lib/v5/`,
`scripts/generate_system_map.py`. **`lib/db_opt/` is not a trigger.** The task brief
referenced `docs/adr/0026-ws3-destructive-migration-idempotency-guards.md`, which does
NOT exist — ADR-0026 is reserved by the WS3 plan (`audit-remediation/wf_ws3.js:101,119`)
for task T2 (migration idempotency, `lib/migrations/`), and WS3 is unstarted
(`VERIFICATION_LOG_S_ws1-5_autonomous.md:43,57`). Creating it here would collide with
that reserved number.

## Result summary

- `tests/test_db_adapter.py::TestSQLiteAdapter::test_adapter_transaction_rollback`:
  was FAILING on main/HEAD (`assert 1 == 0`), now PASSES.
- Full `tests/test_db_adapter.py`: 67 passed, 0 failed.
- Both adapters: any exception type raised inside `with ...transaction():` now triggers
  rollback and re-raises; no data left partially applied. PG fix verified by reading +
  symmetry (no psycopg2 in env to test-prove).
