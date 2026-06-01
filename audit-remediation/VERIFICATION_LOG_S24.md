# Verification Log — claude/fervent-germain-af8e0f (C2b)

**Session:** 24
**Date:** 2026-06-01
**Agent:** C2b — bulk-trajectory path

**Task:** Phase C2b — eliminate the TREND/ANOMALY N×~12-query explosion in
`detect_all_signals(quick=False)`. The trend/anomaly client+person signals each call
`engine.client_trajectory()` / `person_trajectory()` per entity; each trajectory runs
`client_metrics_in_period` once per window (`num_windows`), and each of those fires 3
queries (`tasks/invoices/communications_in_period`) on a fresh `mode=ro` connection.
For one full-mode pass that is ~12 queries × 134 clients for SIG_CLIENT_DECLINING alone,
plus the 6-window anomaly and the 3-window engagement signals, plus the person variants
— ~1,600+ fresh-connection queries. C2 fixed the composite_score (THRESHOLD) blowup;
this is the remaining trend/anomaly bottleneck the C2 commit deferred as C2b.

**Fix shape (mirrors C2's score_map pattern, two files):**
1. `lib/query_engine.py`: add `bulk_client_trajectories()` and `bulk_person_trajectories()`
   next to `client_trajectory()`. Each runs the full-window-span period queries ONCE with
   no per-entity filter, buckets rows by (entity, window) in memory, and builds the same
   per-window metrics + `_compute_trend` output as the per-entity trajectory functions —
   at the MAXIMUM window count (num_windows=6, window_size=30) so any signal's smaller
   request is the most-recent-N slice of the same 30-day grid.
2. `lib/intelligence/signals.py`: `DetectionCache` gains `trajectory_map` + a
   `get_trajectory()` accessor that slices the primed map (recomputing trends on the slice)
   and falls back to the lazy per-entity `engine.*_trajectory()` when unprimed.
   `detect_all_signals(not quick)` primes the map once. `_evaluate_trend` / `_evaluate_anomaly`
   gain a `cache` param (the exact gap C2 closed for `_evaluate_compound`) and read the
   cache when present, else keep the current per-entity engine call (behavior unchanged
   for unprimed direct callers).

---

## Pre-Edit Verification

For EVERY method call added or modified, one row. No blank/no cells.

| File edited | Method called | Defined at (file:line) | Signature confirmed | Return type matches usage | Callers checked |
|-------------|--------------|----------------------|--------------------|--------------------------|-----------------|
| query_engine.py | `tasks_in_period(since, until, client_id=None)` | query_engine.py:642 | YES — read 642-675; `client_id` optional → omit for bulk | `list[dict]` rows from `v_task_with_client` (cols incl. `client_id`,`created_at`,`task_status`) verified via PRAGMA on live-copy | new bulk callers additive; existing `client_metrics_in_period:748` unchanged |
| query_engine.py | `invoices_in_period(since, until, client_id=None)` | query_engine.py:677 | YES — read 677-708 | `list[dict]` from `v_invoice_client_project` (cols incl. `client_id`,`issue_date`,`amount`,`invoice_status`) verified | additive |
| query_engine.py | `communications_in_period(since, until, client_id=None)` | query_engine.py:710 | YES — read 710-736 | `list[dict]` from `v_communication_client_link` (cols incl. `client_id`,`occurred_at`); live-copy rows=0 (still bucketed for correctness) | additive |
| query_engine.py | `_compute_trend(values)` | query_engine.py:1337 | YES — read 1337-1394; takes `list[float]` oldest-first | `dict{direction,magnitude_pct,confidence}` — exact shape `_evaluate_trend` reads (`trends[metric][direction|magnitude_pct|confidence]`) | reused as-is; bulk path computes identical trends |
| query_engine.py | `client_metrics_in_period(client_id, since, until)` | query_engine.py:738 | YES — read 738-776; defines the per-window metric dict the bulk path must reproduce | `dict{tasks_created,tasks_completed,invoices_issued,amount_invoiced,amount_paid,communications_count,...}` | NOT called by bulk path; bulk path replicates its aggregation in Python keyed by client |
| query_engine.py | `client_portfolio_overview(order_by, desc)` | query_engine.py:177 | YES — read 177-194; default query filters `project_count>0 OR invoice_count>0` (134 of 160 on live-copy) | `list[dict]` with `client_id`,`client_name` | bulk client path iterates this for the client universe (same universe DetectionCache.clients uses) |
| query_engine.py | `resource_load_distribution()` | query_engine.py:196 | YES — read 196-218; `assigned_tasks>0` filter | `list[dict]` with `person_id`,`person_name` | bulk person path iterates this for the person universe (same as DetectionCache.persons) |
| query_engine.py | `person_load_in_period(person_name, since, until)` | query_engine.py:921 | YES — read 921-946; matches `LOWER(assignee)=LOWER(name)`, counts tasks_assigned/completed | `dict{tasks_assigned,tasks_completed,completion_rate}` | NOT called by bulk path; bulk person path replicates by bucketing tasks on `LOWER(assignee)` |
| query_engine.py | `_execute(sql, params)` | query_engine.py:75 | YES — read 75-80; opens FRESH `mode=ro` conn per call (line 77) — this per-call cost IS the bottleneck | `list[dict]` | bulk path calls the *_in_period wrappers (3 calls total per entity-class) instead of 3×windows×N |
| signals.py | `DetectionCache.__init__` | signals.py:919 | YES — read 919-934; C2 added `score_map=None` at 934 | appended `self.trajectory_map: dict\|None = None` | every `DetectionCache()` carries it; accessor getattr-guards |
| signals.py | `DetectionCache.get_trajectory` (NEW) | signals.py (new, in class) | N/A new method | returns `dict` same shape as `engine.client_trajectory`/`person_trajectory` (`windows`,`trends`,...) | called only by `_evaluate_trend`/`_evaluate_anomaly` when `cache` present |
| signals.py | `QueryEngine.bulk_client_trajectories` (NEW) | query_engine.py (new) | N/A new method | `dict{client_id: trajectory_dict}` | called by `DetectionCache` priming (in `detect_all_signals` not-quick) |
| signals.py | `QueryEngine.bulk_person_trajectories` (NEW) | query_engine.py (new) | N/A new method | `dict{person_id: trajectory_dict}` | called by `DetectionCache` priming |
| signals.py | `_evaluate_trend(condition, entity_type, entity_id, db_path, cache=None)` | signals.py:1209 | YES — read 1209-1272; currently NO cache param, builds own engine, calls `engine.client_trajectory`(1225)/`person_trajectory`(1229)/`portfolio_trajectory`(1234) | returns `dict\|None` evidence — unchanged | sole caller `evaluate_signal:1476` (currently passes no cache) → will pass `cache` |
| signals.py | `_evaluate_anomaly(condition, entity_type, entity_id, db_path, cache=None)` | signals.py:1275 | YES — read 1275-1348; NO cache param, calls `engine.client_trajectory`(1299) with `num_windows=baseline_days//30`=6 | returns `dict\|None` evidence — unchanged | sole caller `evaluate_signal:1478` → will pass `cache` |
| signals.py | `evaluate_signal` TREND/ANOMALY branches | signals.py:1476,1478 | YES — read 1472-1482; already receives `cache` (used for THRESHOLD:1474, COMPOUND:1481) | passes `cache` to the two evaluators | self; `cache` already in scope |
| signals.py | `detect_all_signals` priming block | signals.py:1682-1688 | YES — read; C2 primes `score_map` here under `if not quick` | adds `cache.trajectory_map = {...}` prime in same block | only full-mode caller is autonomous_loop.py:724 (verified via grep: every other caller passes quick=True) |

### Window-slice equivalence (load-bearing correctness claim)

`client_trajectory` (qe:858-873) builds window `i` as `window_end = now - i*window_size_days`,
`window_start = window_end - window_size_days`, inserted at position 0 → list ordered
oldest→newest. Window `i`'s boundaries depend ONLY on `i`, `window_size_days`, and `now` —
NOT on `num_windows`. Therefore the most-recent `k` windows of a 6-window trajectory are
byte-for-byte the windows of a freshly-built `k`-window trajectory (same `now` within the
run). `get_trajectory(num_windows=k)` returns `windows[-k:]` and recomputes `trends` on
that slice via `_compute_trend` — identical to calling `client_trajectory(num_windows=k)`.
The signals needing k=3 (engagement), k=4 (declining), k=6 (anomaly) are all served from
one k=6 prime. `now` is captured once per bulk build so all entities share the same grid.

## Pre-Commit Verification

| Check | Result | Output snippet |
|-------|--------|---------------|
| `ruff check` on changed files | PASS | `All checks passed!` (ruff 0.15.1, == pre-commit pinned v0.15.1) |
| `ruff format --check` on changed files | PASS | `2 files already formatted` (format applied to query_engine.py: one line collapsed) |
| `bandit -r` on changed files | PASS | exit 0, no findings |
| `python -m py_compile` both files | PASS | `PYCOMPILE_OK` |
| `pytest` signals/scoring/query_engine/lifecycle | PASS | `126 passed` (test_query_engine 43, test_intelligence_signals 29, test_intelligence_scoring 41, test_signal_lifecycle 13) |
| Every method call in changed files resolves to a real `def` | PASS | bulk_client_trajectories/bulk_person_trajectories/_trajectory_windows/_window_index (qe), get_trajectory/_slice_trajectory (signals), `_compute_trend` import = module-level def qe:1574 |
| Bulk vs per-entity trajectory EQUIVALENCE on live-copy | PASS | 402 client checks (134×k∈{3,4,6}) + 36 person checks (18×k∈{4,6}) → 0 mismatches. Includes same-name "Dana Oraibi" collision (two person_ids, identical counts) handled correctly. |
| Query-count reduction (trajectory load, live-copy) | PASS | legacy per-entity = **5,514** `_execute` calls / 83.4s → bulk = **6** calls / 3.5s (**919× fewer queries, ~24× faster**) |
| Runtime: full-mode detect_all_signals(quick=False) on live-copy | PASS | **24.3s**, `success=True`, `evaluation_errors=0`, total_signals=169 (client 140 / project 20 / person 9). UNDER_120S=True, DONE_OK=True. Logs: "Primed 134 client + 18 person trajectories". |
| Pre-existing failures isolated | PASS | test_trajectory.py 48 errors (conftest determinism guard on TrajectoryEngine() w/o db_path) + test_daemon_intelligence.py 11 fails (`AutonomousLoop.cycle_count` missing) BOTH reproduce identically on pristine origin/main with my 2 files reverted. My diff touches neither autonomous_loop.py/daemon.py nor any function in those tracebacks. |
| Verification log included in `git add` | YES | `audit-remediation/VERIFICATION_LOG_S24.md` staged in the S24 commit |

## PR Scope Check

| Planned PR | Files in this commit | Matches plan? |
|-----------|---------------------|--------------|
| C2b bulk-trajectory | `lib/query_engine.py`, `lib/intelligence/signals.py`, `audit-remediation/VERIFICATION_LOG_S24.md` | YES — one purpose (trajectory bulk-load); no other concern bundled |
