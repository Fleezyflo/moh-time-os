# Verification Log — BUG-5b: intelligence_api stragglers

**Session:** phase1-realbugs (2026-06-04)
**Base:** origin/main @ 0e975dc
**Branch:** fix/intelligence-api-stragglers
**Driver:** triage report; deferred stragglers from BUG-5.

(Per-PR log file — NOT the shared `VERIFICATION_LOG_S_phase1_realbugs.md`. The shared file caused
repeated merge conflicts across parallel PRs #145–#149; using a dedicated file here avoids that.)

---

## Two independent stragglers (both surfaced by the triage)

### Straggler 1 — SIGNAL_CATALOG count: TEST ROT
`test_intelligence_api.py::test_signal_catalog_has_all_signals` asserted `len(SIGNAL_CATALOG) == 22`,
but the catalog has 23 (all distinct, legitimate definitions). `git log -L` on `SIGNAL_CATALOG` shows
commit `2efb17a "feat: add intelligence expansion -- phase C"` expanded the catalog; the hardcoded
test count was not updated. Fix: assertion `22 → 23` + docstring note. (Test-only.)

### Straggler 2 — get_critical_items returned a bare list and swallowed errors: REAL BUG
`get_critical_items` (engine.py:828) returned a `list` and, on exception, logged + `return items`
(the empty pre-try list) — so a failure was indistinguishable from "no critical items" (silent-failure
hiding outages — same anti-pattern as BUG-5's snapshot). Both `test_intelligence_api` and
`test_intelligence_engine` assert it returns `{success, errors, items, generated_at}`.

Fix:
- `get_critical_items` → returns `{success, errors, items, generated_at}`; on exception records
  `{error_type, message}` in `errors` and `success=False`.
- `/critical` endpoint (`api/intelligence_router.py:601` `critical_items`) → unwraps `["items"]` for
  the response `data` (preserving the external API shape: `data` stays the items list) and surfaces
  `errors` + `computation_success` via `_wrap_response`'s params.

### Pre-Edit Verification
| File edited | Symbol | Defined/used at | Confirmed | Callers checked |
|-------------|--------|-----------------|-----------|-----------------|
| engine.py `get_critical_items` | returns dict now (was list) | engine.py:828 | yes | callers: `/critical` endpoint (updated) + `__init__.py:21-22` (docstring EXAMPLE, not executed) + re-export (`__init__.py:34,94`, name only). `daily_briefing` does NOT call it (grep). |
| intelligence_router.py `critical_items` | `_wrap_response(data, params)` | intelligence_router.py:45 | yes — `IntelligenceResponse.params: dict[str,Any]` | n/a |
| test_intelligence_api.py | `SIGNAL_CATALOG` len | signals.py:650 (23 entries) | yes — verified 23 distinct | n/a |
| `datetime`/`timezone` | for `generated_at` | engine.py:20 import | yes — already imported | n/a |

### Pre-Commit Verification
| Check | Result | Output |
|-------|--------|--------|
| TDD red (before) | CONFIRMED | 3 stragglers failed (`==22`; `Expected dict with items key` ×2) |
| TDD green (after) | PASS | 3 stragglers pass; test_intelligence_api 15 + test_intelligence_engine 21 = 36 passed |
| broad regression (proposals/signals/scoring/daemon) | PASS | `128 passed` |
| /critical-endpoint-touching files | PASS (1 pre-existing unrelated) | `172 passed`; the 1 failure (`test_consumer_truthfulness::test_non_degraded_digest_has_no_warning`) is PRE-EXISTING — fails identically with my changes stashed on `0e975dc` (proven), separate digest-degradation bucket |
| ruff check | PASS | `All checks passed!` |
| ruff format --check | PASS | `3 files already formatted` |
| bandit | PASS | exit 0 |

Files in this commit: `lib/intelligence/engine.py`, `api/intelligence_router.py`,
`tests/test_intelligence_api.py`, this log. One purpose (BUG-5b: the two intelligence-api stragglers).

### Flagged for a later phase (NOT fixed here)
`tests/test_consumer_truthfulness.py::TestDigestDegradationReporting::test_non_degraded_digest_has_no_warning`
fails on pristine main (digest degradation reporting) — separate concern, own PR.
