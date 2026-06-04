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
