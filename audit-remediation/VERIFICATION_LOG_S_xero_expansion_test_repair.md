# Verification Log — test/repair-stale-xero-expansion-result-schema

**Session:** spawned chip session (owner of tests/test_xero_collector_expansion.py per memory moh-chip-owns-xero-expansion-test)
**Date:** 2026-06-02
**Agent:** Claude Opus 4.8 (1M context)

---

## Context

Three tests in `tests/test_xero_collector_expansion.py` fail on clean `main`
(HEAD bf60dc1), independently of any WS3 change. They pin a `sync()` result
schema (`invoices_stored`, `secondary`) that `CollectorResult.to_dict()` no
longer produces. The real schema is `status / success / collected / stored /
secondary_tables / secondary_failures`. This is a test-only repair — NO
production code changes.

Failing tests (confirmed via `pytest -q`, 3 failed / 25 passed):
- `TestSyncMultiTable::test_sync_stores_all_secondary_tables`
- `TestSyncMultiTable::test_sync_handles_secondary_failures_gracefully`
- `TestBackwardCompatibility::test_sync_with_only_invoices`

---

## Pre-Edit Verification

For EVERY method call you add or modify, fill in one row.

| File edited | Method called | Defined at (file:line) | Signature confirmed | Return type matches usage | Callers checked |
|-------------|--------------|----------------------|--------------------|--------------------------|-----------------|
| tests/test_xero_collector_expansion.py | `XeroCollector.sync()` | lib/collectors/xero.py:~270 (returns `cr.to_dict()` at :329/:619/:639) | yes — no-arg method, returns `dict` | yes — returns `CollectorResult.to_dict()` dict; asserted keys verified below | yes — only these tests assert on the dict; callers in lib/daemon use `status`/`success` |
| tests/test_xero_collector_expansion.py | `CollectorResult.to_dict()` | lib/collectors/result.py:104 | yes | yes — emits `source,status,success,timestamp,collected,transformed,stored,duration_ms`; conditional `secondary_tables` (shape `{name:{stored,error}}` at :128-131), `secondary_failures` (:133-134) | n/a (read-only assertion) |
| tests/test_xero_collector_expansion.py | `COLLECTOR_ERRORS` (mock side_effect type) | lib/collectors/resilience.py:35-63 | yes — tuple incl. `RuntimeError` (:43); does NOT include bare `Exception` | yes — `except COLLECTOR_ERRORS` at xero.py:341/350/359/368 catches `RuntimeError` fetch failures → graceful PARTIAL | yes — fetch try/except blocks at xero.py:337-371 |

### Evidence — empirically probed result values (all via `.venv/bin/python`)

- **Case A** (insert_many=5, all secondaries `[]`): `status="success"`, `success=True`,
  `collected=2`, `stored=2`, `secondary_tables` has all 5 keys each `{stored:0,error:None}`,
  no `secondary_failures` key.
- **Case B** (insert_many=0, all secondaries `[]`): identical to Case A.
- **Failure case** (list_contacts/credit_notes/bank_transactions/tax_rates raise
  `RuntimeError`): `status="partial"`, `success=False`, `stored=2`,
  `secondary_failures=["bank_transactions","contacts","credit_notes","tax_rates"]`,
  `secondary_tables["contacts"]={stored:0,error:"fetch failed: API error"}`.
  (line_items has no failure — it is derived locally from invoices, not fetched.)

Why the `Exception` → `RuntimeError` change is test-only and correct: the test's
intent (docstring "Should not fail if secondary data fetch fails") is graceful
degradation on a secondary FETCH failure. Bare `Exception` is not in
`COLLECTOR_ERRORS`, so it escapes `sync()`'s try/except and crashes — exercising
no production path. `RuntimeError` IS in `COLLECTOR_ERRORS`, so it exercises the
real fetch-failure → PARTIAL path the test was written to cover. No production
code changes.

## Pre-Commit Verification

| Check | Result | Output snippet |
|-------|--------|---------------|
| `ruff check` on changed files | PASS | `All checks passed!` |
| `ruff format --check` on changed files | PASS | `1 file already formatted` |
| `bandit -r` on changed files | N/A (test file, no security surface) | |
| `pytest tests/test_xero_collector_expansion.py` | PASS | `28 passed in 0.27s` (was 25 passed / 3 failed) |
| `pytest -k xero` (regression) | PASS | `54 passed, 3746 deselected, 1 error` — the 1 error is a pre-existing determinism leak in tests/test_missed_surface_closure.py, reproduced with my change stashed; out of scope |
| Every method call in changed files resolves to a real `def` | yes | sync/to_dict/COLLECTOR_ERRORS verified above |
| Verification log included in `git add` | yes | included in commit block below |

## PR Scope Check

| Planned PR | Files in this commit | Matches plan? |
|-----------|---------------------|--------------|
| test: repair stale Xero expansion result-schema assertions | tests/test_xero_collector_expansion.py + this log | yes — one file, one purpose |

If this commit contains files from more than one planned PR: **STOP. Split the commit.**
