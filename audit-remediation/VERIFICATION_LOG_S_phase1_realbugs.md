# Verification Log — Phase 1a real-bug fixes (one PR each)

**Session:** phase1-realbugs (2026-06-04)
**Base:** origin/main @ 8ea24b8
**Driver:** triage report audit-remediation/TEST_SUITE_TRIAGE_2026-06-04.md

Each bug is its own branch + PR (One-PR-One-Purpose). This log accumulates per-bug Pre-Edit/Pre-Commit rows.

---

## BUG-3 — threshold_adjuster calls nonexistent `day_context()`  [branch: fix/threshold-adjuster-day-context]

### Root cause
`lib/intelligence/threshold_adjuster.py:198,249` call `self._calendar.day_context(ref_date)`.
`self._calendar` is a `BusinessCalendar` (threshold_adjuster.py:162). `BusinessCalendar` defines
`get_day_context(d)` (temporal.py:161) returning `DayContext` with `.is_ramadan` (temporal.py:193) —
there is NO `day_context` method anywhere (grep: 0 `def day_context`; the only 2 `.day_context(`
call sites are these two bugs). Production-reachable: `ThresholdAdjuster` is used by
`calibration_reporter.py`. Crashes `run_adjustment_cycle` + `get_seasonal_modifiers` whenever
Ramadan-modifier logic runs.

### Fix
`day_context` → `get_day_context` at both production call sites (threshold_adjuster.py:198, 249).
The `.is_ramadan` access on the returned `DayContext` is already correct. ALSO: the 5 test patch
sites in `tests/test_adaptive_thresholds.py` (lines 248,264,278,291,431) used `patch.object(...,
"day_context", return_value=Mock(is_ramadan=...))` — they mocked the same wrongly-named method.
Updated all 5 to `"get_day_context"` so the mock intercepts the now-correct call. This is part of
the same single defect (production + tests both encoded the wrong method name).

### Pre-Edit Verification
| File edited | Method called | Defined at | Signature confirmed | Return type matches usage | Callers checked |
|-------------|--------------|-----------|--------------------|--------------------------|-----------------|
| threshold_adjuster.py:198,249 | `BusinessCalendar.get_day_context(d: date\|None)` | temporal.py:161 | yes — takes a `date`; `ref_date` is a `date` | yes — returns `DayContext` with `.is_ramadan` (temporal.py:193) | yes — only callers of these adjuster methods are calibration_reporter.py + tests; `.day_context(` appears nowhere else |

### Pre-Commit Verification
| Check | Result | Output |
|-------|--------|--------|
| TDD red (before fix, on main) | CONFIRMED | `13 failed, 11 passed` test_adaptive_thresholds |
| TDD green (after fix) | PASS | `24 passed` test_adaptive_thresholds |
| ruff check (threshold_adjuster.py) | PASS | `All checks passed!` |
| ruff format --check | PASS | `1 file already formatted` |
| bandit | PASS | exit 0 |
| no regressions (temporal + calendar + recency + lifecycle scope) | PASS | `126 passed` across 6 files |

Files in this commit: `lib/intelligence/threshold_adjuster.py`, `tests/test_adaptive_thresholds.py`, this log. One purpose (BUG-3). Does NOT touch other bugs.

**BUG-3 status: MERGED — PR #145.**

---

## BUG-1 — chat collector dropped per-space failures + crashed on tuple mock  [branch: fix/chat-collector-partial-failures]

### Root cause
`lib/collectors/chat.py` `collect()` called `_list_messages()` (which returned a bare `list`) and
indexed each item with `msg["_space_name"]` at line 109. The v3-behavioral tests
(`TestChatPartialFailureBehavioral`, 5 tests) specify a **partial-failure contract**: `_list_messages`
must return `(messages, error)`, and `collect()`/`sync()` must surface a `partial_failures` list +
`partial_failure_count` (omitted when all succeed). The contract was never implemented, so when the
tests mocked `_list_messages` to return the `(messages, error)` tuple, `collect()` iterated the tuple
and `msg` became the inner list → `TypeError: list indices must be integers or slices, not str`. The
same TypeError fires as a LIVE runtime error during chat collection (seen in the suite run).

### Fix (implements the partial-failure resilience contract)
1. `_list_messages` → returns `tuple[list[dict], str | None]` (`(messages, None)` ok; `([], str(e))` on failure).
2. `collect()` → unpacks the tuple; records `{"space","component":"messages","error"}` on message failure
   and `{"space","component":"members","error"}` on member failure (the existing member try/except now
   records instead of only logging); adds `partial_failures`/`partial_failure_count` to the result ONLY
   when non-empty.
3. `sync()` → propagates `partial_failures`/`partial_failure_count` from `raw_data` into the result dict;
   `success` stays True (these are sub-operation failures, status stays SUCCESS).
4. `tests/test_chat_collector_expansion.py::test_collect_basic` mocked `_list_messages` with the OLD
   single-list return → updated to the `(messages, None)` tuple (same defect class: test encoded old shape).

### Pre-Edit Verification
| File edited | Method called | Defined at | Signature confirmed | Return type matches usage | Callers checked |
|-------------|--------------|-----------|--------------------|--------------------------|-----------------|
| chat.py `collect()` | `self._list_messages(service, space_name, max)` | chat.py:147 (this PR makes it return `(list, str\|None)`) | yes | yes — unpacked as `messages, msg_error` | yes — only caller is `collect()`; transform/sync iterate `raw_data["messages"]` (flat list, unchanged) |
| chat.py `collect()` | `self._list_members(service, space_name)` | chat.py:159 (returns `list`) | yes — unchanged | yes | yes |
| chat.py `sync()` | `cr.to_dict()` | result.py:104 | yes — returns plain dict; safe to add keys | yes | n/a |
| chat.py `sync()` | `raw_data.get("partial_failures"/"partial_failure_count")` | produced by `collect()` above | yes | yes | n/a |

### Pre-Commit Verification
| Check | Result | Output |
|-------|--------|--------|
| TDD red (before fix) | CONFIRMED | `TypeError: list indices...` at chat.py:109 in the 5 behavioral tests |
| TDD green (after fix) | PASS | `TestChatPartialFailureBehavioral` 5 passed |
| chat regression | PASS | test_chat_collector_expansion 24 passed; test_collector_silent_failures + registry 64 passed |
| ruff check (chat.py) | PASS | `All checks passed!` |
| ruff format --check | PASS | `1 file already formatted` |
| bandit | PASS | exit 0 |
| NOT my regressions (confirmed pre-existing) | NOTED | v4 `TestStateStoreTransaction`/`TestSchemaOwnership` (StateStore bucket) + `test_xero_collector_expansion` (Chip A) fail independently of this chat-only change |

Files in this commit: `lib/collectors/chat.py`, `tests/test_chat_collector_expansion.py`, this log. One purpose (BUG-1).

**BUG-1 status: MERGED — PR #146.** (BUG-2 shipped as PR #147 on its own branch; its log section lives there.)

---

## BUG-4 — proposals "missing handler" was a test contradiction + an unmet detection-health gap  [branch: fix/proposals-surface-detection-errors]

### Root cause
`test_audit_remediation_v3.py:268` did `from api.spec_router import get_intelligence_proposals` →
`ImportError` (no such symbol). Two tests CONTRADICT: this one asserts the handler MUST exist in
spec_router, while `test_canonical_pipeline.py:329` (`test_spec_router_no_longer_has_duplicate_handlers`)
asserts it must NOT — proposals were deliberately consolidated into `intelligence_router.list_proposals`
(intelligence_router.py:856, which exists and serves `/proposals`). So the v3 test is STALE (points at
the pre-consolidation location). Separately, the v3 test's *intent* —
`assert "pattern_detection_errors" in src` — was a REAL unmet gap: `list_proposals` called
`detect_all_patterns()` but discarded its `errors`, so a partial pattern-detection failure was invisible
and proposals looked authoritative when missing inputs.

### Fix (Molham-approved: retarget test + add error surfacing)
1. `api/intelligence_router.py` `list_proposals`: extract `patterns.get("errors", [])` into
   `pattern_detection_errors` and surface it via `_wrap_response(result, {... "pattern_detection_errors": ...})`
   (`params` is `dict[str, Any]` on `IntelligenceResponse`, so it passes the response_model). Mirrors how
   `spec_router.get_intelligence_patterns` surfaces `detection_errors`.
2. `tests/test_audit_remediation_v3.py`: retarget the proposals test to
   `from api.intelligence_router import list_proposals` (resolving the contradiction with canonical-pipeline)
   and keep the `pattern_detection_errors` source assertion.

### Pre-Edit Verification
| File edited | Symbol used | Defined at | Confirmed | Notes |
|-------------|------------|-----------|-----------|-------|
| intelligence_router.py `list_proposals` | `patterns.get("errors", [])` | `patterns` = `detect_all_patterns()` (line 881) | yes — same key `get_intelligence_patterns` reads (`detection.get("errors", [])`) | surfaced via existing `_wrap_response` |
| intelligence_router.py | `_wrap_response(data, params)` | intelligence_router.py:45 | yes — params→`{status,data,computed_at,params}` | `IntelligenceResponse.params: dict[str,Any]` (response_models.py:29) — not stripped |
| test_audit_remediation_v3.py | `list_proposals` | intelligence_router.py:856 | yes — `inspect.getsource` works on it | replaces stale `spec_router.get_intelligence_proposals` import |

ADR: not required — `check_adr_required.sh` covers `api/server.py` + `api/spec_router.py`, NOT `api/intelligence_router.py` (and Governance is non-blocking).

### Pre-Commit Verification
| Check | Result | Output |
|-------|--------|--------|
| TDD red (before) | CONFIRMED | `ImportError: cannot import name 'get_intelligence_proposals' from api.spec_router` |
| TDD green (after) | PASS | retargeted proposals test 1 passed |
| contradiction resolved | PASS | `test_spec_router_no_longer_has_duplicate_handlers` still passes (nothing added to spec_router) |
| regression (intelligence proposals + router) | PASS | `test_intelligence_proposals` + 58 passed |
| ruff check | PASS | `All checks passed!` |
| ruff format --check | PASS | `2 files already formatted` |
| bandit | PASS | exit 0 |
| NOT my regressions (pre-existing) | NOTED | `test_intelligence_api` 2 failures (`Expected dict with items key`) are BUG-5 (stage-shape), not in `list_proposals` traceback |

Files in this commit: `api/intelligence_router.py`, `tests/test_audit_remediation_v3.py`, this log. One purpose (BUG-4).

**BUG-4 status: shipped — PR #148.**

---

## BUG-5 — intelligence engine stages discarded errors + snapshot hardcoded success  [branch: fix/intelligence-engine-stageresult]

### Root cause
`engine.py` defines `StageResult`/`StageError` to track per-stage success/errors, but the four stage
runners (`_run_scoring_stage`, `_run_signal_stage`, `_run_pattern_stage`, `_run_proposal_stage`)
accumulated an `errors` list and then `return data` (a bare dict), **discarding** it. The 7
`test_intelligence_engine` tests (`TestPipelineStages`, `TestErrorIsolation`) expect a `StageResult`
with `.success`/`.data`/`.errors`. WORSE: `generate_intelligence_snapshot` HARDCODED
`pipeline_success: True, errors: [], stages_failed: 0` for every stage (engine.py:482-530), so the
snapshot reported total success even when every stage failed — a stub-returning-success violation that
hides outages (CLAUDE.md: "No stubs returning success").

### Fix (Molham-approved FULL scope: StageResult + real success propagation)
1. All four stage runners now `return StageResult(success=not errors, data=data, errors=errors,
   partial=...)`. `partial` = had errors but not every sub-component failed (per-stage component counts).
2. `generate_intelligence_snapshot` consumes each result's `.data`, passes `.data` to downstream stages
   (`_run_pattern_stage`/`_run_proposal_stage`), and DERIVES `pipeline_success`/`pipeline_partial`/
   `pipeline_errors`/`stages_failed` + per-stage `success`/`partial`/`errors` from the StageResults
   instead of hardcoding. Output dict keys unchanged (external callers unaffected).
3. `FileNotFoundError` is a subclass of `OSError`, so the existing `except (sqlite3.Error, ValueError,
   OSError)` already catches the missing-DB case — no except-widening needed; the bug was purely the
   discarded result + hardcoded snapshot.

### Pre-Edit Verification
| File edited | Symbol | Defined at | Confirmed | Callers checked |
|-------------|--------|-----------|-----------|-----------------|
| engine.py 4 stage runners | `StageResult(success,data,errors,partial)` | engine.py:51 | yes — dataclass already existed | only callers are inside `generate_intelligence_snapshot` (grep: 447-456) — all updated to `.data` |
| engine.py `generate_intelligence_snapshot` | `_count_entities(scores)`,`_compute_data_completeness(scores)` | engine.py:418,390 | yes — take bare dict | now passed `scoring_result.data` |
| (external) `generate_intelligence_snapshot` return | output dict keys | unchanged | yes | snapshot consumers (persistence/scoring/signals/daemon) — 110 passed |

### Pre-Commit Verification
| Check | Result | Output |
|-------|--------|--------|
| TDD red (before) | CONFIRMED | `Expected StageResult with .data` / `Expected StageResult` (6 of 7) |
| TDD green (after) | PASS | test_intelligence_engine 20 passed, 1 failed (`get_critical_items` shape = BUG-5b, deferred) |
| Behavioral: success-masking fixed | VERIFIED | snapshot on `/nonexistent/path.db` → `pipeline_success=False, stages_failed=2, pipeline_errors=6, scores.success=False` (was hardcoded True) |
| regression (snapshot consumers) | PASS | persistence+scoring+signals+daemon_intelligence `110 passed` |
| ruff check | PASS | `All checks passed!` |
| ruff format --check | PASS | `1 file already formatted` |
| bandit | PASS | exit 0 |

Files in this commit: `lib/intelligence/engine.py`, this log. One purpose (BUG-5). NO test file changed (the 6 fixed tests were already correct; the 7th — `get_critical_items` dict shape — is BUG-5b, a separate PR).

**BUG-5 status: shipped — PR #149.**

---

## BUG-2 — correlation_confidence subtracts naive vs aware datetimes  [branch: fix/correlation-confidence-naive-aware-tz]

### Root cause
`CorrelationConfidenceCalculator._temporal_proximity` (correlation_confidence.py:175) computed
`reference_time - signal.detected_at`. `reference_time` defaults to `datetime.now(timezone.utc)`
(aware) while `signal.detected_at` can be **naive** (test helper builds naive `datetime(...)`;
production `persistence.py:271` reads a stored value that may lack tz). Subtracting mixed-awareness
datetimes raises `TypeError: can't subtract offset-naive and offset-aware datetimes`. The 12 failing
tests are exactly those that omit `reference_time` (→ aware default vs naive `detected_at`).

### Fix
Added module-level `_as_utc(dt)`: naive → assume UTC (tag), aware → convert to UTC. Normalize BOTH
operands before subtraction. Production robustness fix; the tests already correctly exercise the
default-`reference_time` path (no test change).

### Pre-Commit Verification
| Check | Result | Output |
|-------|--------|--------|
| TDD red (before) | CONFIRMED | `12 failed, 7 passed` test_correlation_confidence |
| TDD green (after) | PASS | `19 passed` test_correlation_confidence |
| regression (correlation_engine) | PASS | `62 passed` |
| ruff / ruff format / bandit | PASS | clean |

Files in this commit: `lib/intelligence/correlation_confidence.py`, this log. One purpose (BUG-2).
(Note: PR #147 was rebased twice as parallel PRs #145/#146/#148/#149 merged ahead of it; the only
conflict each time was this shared log file, resolved by taking main's sections + re-appending BUG-2.
The BUG-2 production fix never conflicted.)
