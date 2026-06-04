# Test-Suite Triage — main @ 8ea24b8 (2026-06-04)

Full run: `python -m pytest tests/ -q` → **158 failed, 3584 passed, 2 xfailed, 113 errors** / 3857 collected (60.9s).

---

## ✅ PHASE 1a (real bugs) — COMPLETE (PRs #145–#150, all merged or auto-merging)

| Bug | PR | Fix |
|-----|-----|-----|
| BUG-3 | #145 ✅merged | `threshold_adjuster` `day_context()` → `get_day_context()` (live Ramadan-logic crash) |
| BUG-1 | #146 ✅merged | chat collector partial-failure contract (`_list_messages` tuple; live `TypeError` in daemon) |
| BUG-4 | #148 ✅merged | proposals test contradiction retargeted + `list_proposals` surfaces `pattern_detection_errors` |
| BUG-5 | #149 ✅merged | engine stages return `StageResult`; `generate_intelligence_snapshot` no longer hardcodes `success=True` (was masking total failure) |
| BUG-2 | #147 ✅merged | `correlation_confidence._temporal_proximity` naive/aware datetime `TypeError` → `_as_utc` normalization |
| BUG-5b | #150 ⏳auto-merge | `get_critical_items` returns `{success,errors,items,generated_at}` (was silent-failure list); SIGNAL_CATALOG count 22→23 (stale) |

**Real production bugs fixed beyond test-pass:** BUG-1 (live chat-collection crash), BUG-5 (intelligence snapshot reported success even on total failure), BUG-5b (`get_critical_items` hid failures as "no items"), BUG-4 (proposals didn't surface detection errors).

**NEW finding (Phase-1b candidate, not in original 271 census signatures):** `tests/test_consumer_truthfulness.py::TestDigestDegradationReporting::test_non_degraded_digest_has_no_warning` fails on pristine main — digest degradation reporting. Own PR.

**Next:** Phase 1b (TEST ROT — the ~137 DB_PATH/BUNDLES_DIR/STATE_FILE/BACKUP_DIR patch-target fixes + determinism/fixture isolation), then Phase 1c (DEBT decisions), then Phase 3 (expand CI to gate `tests/`), then Phase 4 (operator items). **Lesson for 1b: use one verification-log file PER PR** — the shared log caused repeated merge conflicts across #145–#149.

---

**None of these are CI-gated.** CI's Python Tests job runs only `tests/contract`, `test_safety.py`, auth subset, `tests/negative`, `tests/golden`, `tests/ui_spec_v21`, `tests/property` (see `ci.yml`). The 271 failures/errors live outside that set, which is why main is green.

Classification below is by **root-cause signature**, verified against production source. Each row tagged:
- **ROT** = test-only defect (patches/calls a symbol production never had or that moved); fix is in the test/fixture.
- **BUG** = genuine production defect the test correctly catches; fix is in `lib/`.
- **DEBT** = intentional defect-tracking test asserting a not-yet-done refactor (fails on purpose until the refactor lands).

---

## REAL PRODUCTION BUGS (fix these first — they are live defects)

| # | Bug | Location | Evidence | Tests affected |
|---|-----|----------|----------|----------------|
| BUG-1 | `collect()` indexes a list with a string key | `lib/collectors/chat.py:109` | `TypeError: list indices must be integers or slices, not str` — fires as a live runtime ERROR during chat collection, not just in tests | ~20 (`test_audit_remediation_v3_behavioral`) + live daemon |
| BUG-2 | `_temporal_proximity` subtracts naive vs aware datetimes | `lib/intelligence/correlation_confidence.py:175` (via `.calculate` line 107) | `TypeError: can't subtract offset-naive and offset-aware datetimes` | 12 (`test_correlation_confidence`) |
| BUG-3 | `ThresholdAdjuster` calls `self._calendar.day_context(...)` but `BusinessCalendar` only defines `get_day_context()` | `lib/intelligence/threshold_adjuster.py:198,249` | `AttributeError: 'BusinessCalendar' object has no attribute 'day_context'`; production-reachable via `calibration_reporter.py`. temporal.py:449 calls the correct `get_day_context()` | ~25 (`test_adaptive_thresholds` 15 + part of correlation/temporal 10) |
| BUG-4 | `get_intelligence_proposals` not importable from `api.spec_router` | `api/spec_router.py` | `ImportError: cannot import name 'get_intelligence_proposals'` | 2 |
| BUG-5? | `intelligence_engine` pipeline stages return wrong shape (list/dict not `StageResult`) | `lib/intelligence/engine.py` (TBD) | `AssertionError: Expected StageResult with .data` / `Expected dict with items key` | 7 (`test_intelligence_engine`) + 2 (`test_intelligence_api`) — needs source confirm whether contract or impl is wrong |

**BUG-1 and BUG-3 are the priority** — both are reachable in the live daemon (chat collection; Ramadan threshold modifiers). BUG-2 corrupts correlation confidence scoring.

---

## TEST ROT (stale patch/call targets — fix in tests, ~one fixture line per file)

Root cause: a config/path refactor moved module-level constants to `lib/paths.py` (confirmed by `test_cross_cutting_correctness`'s own assertion *"Found module-level DB_PATH … Use paths.d"* — the refactor is the intended direction). These tests still `patch("lib.X.CONST")` the old location.

| File | Count | Stale target | Likely fix |
|------|-------|-------------|------------|
| `test_key_manager.py` | 47 | `lib.store.DB_PATH` (removed) | patch `lib.paths.db_path` or inject temp DB via the documented fixture recipe |
| `test_change_bundles.py` | 46 | `lib.change_bundles.BUNDLES_DIR` (removed) | patch the new location / inject dir |
| `test_daemon_resilience.py` | 20 | `lib.daemon.STATE_FILE` (removed) | patch new location |
| `test_backup.py` | 15 | `lib.backup.BACKUP_DIR` + `lib.backup.DB_PATH` (removed) | patch new location |
| `test_audit_remediation_v4_implementations.py` | 7 | `StateStore.execute_write` / `.transaction` (never existed in prod — `StateStore` only has `query()`) | rewrite to the real StateStore API |
| `test_asana_writer.py` | 2 | `argument of type 'Mock' is not iterable` | fixture mock shape |

Subtotal ROT ≈ **137**.

---

## DETERMINISM / FIXTURE ISOLATION (test-harness; ~one conftest/fixture pattern)

Per memory `moh-test-client-fixture-recipe`: tests importing modules that touch the DB need fixture-DB + `lib.paths` patch + `StateStore._instance` reset, else the conftest determinism guard fires.

| Signature | Count | Cause |
|-----------|-------|-------|
| `DETERMINISM VIOLATION: live DB at ~/.moh_time_os/...` | 20 | fixture doesn't isolate the DB |
| `sqlite3.OperationalError: no such table: drift_baselines/drift_alerts/tasks/feedback/foo/test` | ~40 | fixture doesn't create schema before the test (`test_drift_detection` 14, `test_audit_trail` 4, others) |
| `FileNotFoundError: Database not found: /nonexistent/path.db` | 17 | mix of intentional-negative and fixture path drift — needs per-test check |

Subtotal harness ≈ **77** (some overlap with ROT files above).

---

## DEBT (intentional defect-tracking tests — refactor not done)

| File | Count | Asserts | Disposition |
|------|-------|---------|-------------|
| `test_audit_remediation_v3.py` | 21 | `task_project_linker.py still uses sqlite3.connect` / `still imports sqlite3` / `link_* does not accept store=` / `should use store.query()` | Either DO the `task_project_linker` → store refactor (closes 21 + the v3_behavioral store= TypeErrors), OR these stay red as tracked debt. Production `task_project_linker.py` takes `(db_path, dry_run)`, callers consistent — so the refactor is genuinely pending, not broken. |
| `test_cross_cutting_correctness.py` | 3 | `Found module-level DB_PATH in 1 location` / schema defect markers | Tracks the same paths refactor + schema additions (`watchers`, `issue_notes` added to schema.py — test says "update this test and remove the defect tracking") |
| `test_runtime_payload_compatibility.py` | 11 | `KeyError: 'data'` | NEEDS CHECK — could be real API payload-shape drift (BUG) or stale expectation. Not yet classified. |

---

## Recommended sequence (Molham approved: "ALL IN ORDER")

1. **Phase 2 (this doc) — DONE.** Triage complete.
2. **Phase 1a — REAL BUGS first** (one PR each, per One-PR-One-Purpose): BUG-1 chat.py, BUG-3 threshold_adjuster (trivial: `day_context`→`get_day_context`), BUG-2 correlation tz, BUG-4 spec_router import, then confirm/fix BUG-5. These are live defects + unblock the most "BUG-shaped" test clusters.
3. **Phase 1b — TEST ROT** (one PR per file or per shared-root cluster): the DB_PATH/BUNDLES_DIR/STATE_FILE/BACKUP_DIR patch-target fixes + StateStore-API test rewrites + determinism/fixture isolation. Largest count, lowest risk.
4. **Phase 1c — DEBT decision** (Molham's call): do the `task_project_linker` store-refactor (closes v3 + v3_behavioral) or leave as tracked debt; confirm `runtime_payload_compatibility` is rot vs bug.
5. **Phase 3 — GATE in CI.** Once green, expand `ci.yml` Python Tests to run full `tests/` (or a curated core) so rot can't re-accumulate silently.
6. **Phase 4 — Production-readiness** (operator items): Xero OAuth refresh token, rotate leaked GCP SA key, Chip B Xero pagination.

**Verified-stale memory note:** `moh-xero-accrec-empty-wipe` is OBSOLETE — the S3.1 destructive-delete guard (`lib/collectors/xero.py:311-349`) now returns STALE before the DELETE for both empty-fetch and zero-ACCREC cases. The hole is closed.
