# Verification Log — Session 23

**Task:** Phase C2 — fix the N×M scoring blowup in `detect_all_signals` so the
autonomous loop can finish a cycle.

**Root cause (confirmed):** the `composite_score` branch in `_evaluate_threshold`
(`lib/intelligence/signals.py`) called the single-client `score_client(entity_id,
cache.db_path)` once per entity. Each `score_client()` builds a fresh `QueryEngine`
and runs `client_portfolio_overview()` which scans ALL 160 clients → O(N×M).

**Implemented fix (matches handoff prescription):**
1. `DetectionCache.__init__` gains `self.score_map: dict[str, dict] | None = None`.
2. `detect_all_signals`, when `not quick`, builds the map ONCE:
   `cache.score_map = {s["entity_id"]: s for s in score_all_clients(db_path) if s.get("entity_id")}`.
   `score_all_clients` loads all data in one bulk pass and scores in memory.
3. The `composite_score` branch reads `getattr(cache, "score_map", None)`:
   if primed → `score_map.get(entity_id, {})` (O(1)); if `None` (any unprimed
   direct caller) → lazy `score_client(entity_id, cache.db_path)` fallback,
   preserving the exact pre-fix behavior for those paths.

**Note:** an earlier attempt routed the branch through `cache.get_scorecard()`.
That method does NOT exist — `def get_scorecard`=0, and the only cache class is
`DetectionCache` (no `ScorecardCache`); the "ScorecardCache.get_scorecard"
I briefly thought I saw was a tool-output duplication artifact. A runtime
`AttributeError` caught it; the approach above replaced it entirely.

## Pre-Edit Gate (verified against the worktree this session)

| Symbol called / touched | Read `def`? (verified) | Return / shape | Caller(s) checked | Compatible? |
|---|---|---|---|---|
| `score_all_clients(db_path)` (scorecard.py:82) | YES — read full body 82-146 | `list[dict]`; each via `_build_scorecard` (scorecard.py:460-469) → has `entity_id` + `composite_score`; entries with no `client_id` skipped (105-106) | Existing callers scorecard.py:395/496/515/635; new caller in `detect_all_signals` is additive, same signature | YES |
| `score_client(entity_id, db_path)` (scorecard.py:38) | YES — read full body 38-79 | dict with `composite_score` (same `_build_scorecard` shape) | Used ONLY as the lazy fallback in the composite branch (unprimed caches); semantics unchanged | YES |
| `DetectionCache.__init__` (signals.py:919) | YES — read 919-931 (traceback-confirmed at :920) | sets engine, db_path, `_clients…_last_comm_days`; I appended `self.score_map=None` | Every `DetectionCache()` instance now carries `score_map`; branch also `getattr`-guards | YES |
| composite branch in `_evaluate_threshold` (signals.py:~1099) | YES — read pre- and post-edit | reads `getattr(cache,"score_map",None)`; sets `current_value` | `_evaluate_threshold` reached via `evaluate_signal`→`detect_signals_for_entity` (5 sites 1569/1631/1688/1699/1710, all in `detect_all_signals`, primed cache) + its own `if cache is None` fallback (unprimed→lazy) | YES |
| entity_id key namespace | YES | `detect_all_signals` loops `cache.clients`→`client_id` (from `client_portfolio_overview`); `score_all_clients` keys on the SAME `client_portfolio_overview` `client_id` and sets `entity_id=client_id` | keys align; client entities all present in map | YES |
| quick-mode gate | YES — read `detect_signals_for_entity` 1569-1599 | `if fast_only: keep only s.fast_eval` (1598-1599). `SIG_CLIENT_SCORE_CRITICAL` (THRESHOLD, metric composite_score) has `fast_eval=False` → skipped in quick mode; `SIG_CLIENT_DECLINING` is TREND (dropped by `cats=[THRESHOLD]`) | priming gated `if not quick`; quick mode never runs composite branch, so `score_map=None` is harmless there | YES |

### Second bottleneck found by stack-sampling profiler (after composite fix)

The composite_score map fix was necessary but NOT sufficient — `detect_all_signals`
still pegged 1 CPU and never finished. A stack-sampler (`/tmp/s23_profile.py`,
samples the worker thread every 8s) caught the hot path:
`_evaluate_compound:1383 → evaluate_signal → _evaluate_threshold:1074 →
cache.get_client → clients → engine.client_portfolio_overview()` (full scan).
Root cause: `_evaluate_compound` did NOT receive `cache` and forwarded none to its
recursive `evaluate_signal` (1383) or inline `_evaluate_threshold` (1395), so every
compound ref-signal built a fresh `DetectionCache` and re-ran the full
`client_portfolio_overview` scan — a second N×M.

| Symbol called / touched | Read `def`? (verified) | Change | Caller(s) checked | Compatible? |
|---|---|---|---|---|
| `_evaluate_compound` (signals.py:1351) | YES — read full body 1351-1425 | added `cache: DetectionCache = None` param | sole caller is `evaluate_signal` (1476); now passes `cache=cache` | YES |
| recursive `evaluate_signal` in `_evaluate_compound` (1383) | YES — `evaluate_signal` sig 1433-1440 (`cache` is 6th param) | now forwards `cache=cache` (kw) past positional `_evaluated` | self-recursion; `cache` flows to ref-signal threshold eval | YES |
| inline `_evaluate_threshold` in `_evaluate_compound` (1395) | YES — `_evaluate_threshold` sig 1040-1046 (`cache` 5th positional) | now passes `cache` positionally | matches signature | YES |
| `evaluate_signal` COMPOUND branch (1476) | YES — read 1468-1476 | now passes `cache=cache` to `_evaluate_compound` | `evaluate_signal` already receives `cache` and used it for THRESHOLD (1470) | YES |
| `_evaluate_trend` (1209) / `_evaluate_anomaly` (1275) | YES — read both | LEFT UNCHANGED | use their own `engine` for trajectory/baseline queries the cache does not serve; not the bottleneck; widening scope avoided per One-PR-One-Purpose | n/a |

## Pre-Commit Gate

| Check | Result | Evidence |
|---|---|---|
| `python -m py_compile signals.py` | PASS | `SYNTAX_OK` |
| `ruff check signals.py` | PASS | exit 0 (`RUFF=0`) |
| `ruff format --check signals.py` | PASS | exit 0 (`FMT=0`) |
| `bandit -q signals.py` | PASS | exit 0 (`BANDIT=0`) |
| Every method call resolves to a real `def` | PASS | `cache.get_scorecard`=0, `cache.prime_client_scorecards`=0 (both removed); `score_all_clients` import=1; lazy `score_client` fallback=1 (intentional) |
| Runtime: stack-sampling profiler on a copy of the live DB (160 clients) | PASS (for the two shipped fixes) | "Primed 134 client scorecards" logged; the composite_score `client_portfolio_overview` repeat is GONE and the compound-ref full-scan is GONE (no longer in any stack sample). Run then spends its time in `_evaluate_trend → client_trajectory` — the THIRD bottleneck, out of scope for this PR (see below). |
| `pytest` signals/scoring/detection | PASS | `test_intelligence_signals.py` 29, `test_intelligence_scoring.py` 41, `test_signal_lifecycle.py` 13 — all pass against my edited signals.py |
| Pre-existing failures isolated | PASS | Full run: 97 passed, 27 failed. The 27 (`test_signal_suppression.py` ×20 = `no such table: signal_dismiss_log/signal_suppressions`; `test_intelligence_engine.py` ×7 = StageResult return-type + `/nonexistent/path.db` fixture) reproduce IDENTICALLY (27 failed, 14 passed) when I overlay pristine `origin/main:signals.py` — so they pre-date this change. No failure traceback touches `score_map`/`prime`/`getattr(cache`. My diff is signals.py-only (39+/6-). |
| Verification log staged with commit | PENDING | include `audit-remediation/VERIFICATION_LOG_S23.md` in `git add` |

## Out of scope for this PR — follow-up (Phase C2b)

`detect_all_signals(quick=False)` still does NOT finish quickly: the dominant
remaining cost is the TREND path — `SIG_CLIENT_DECLINING` (category=TREND, metric
composite_score) calls `engine.client_trajectory()` per client (qe:842), which calls
`client_metrics_in_period()` once per window (`num_windows=consecutive+1=4`), each
firing 3 queries (`tasks/invoices/communications_in_period`) on a fresh mode=ro
connection ⇒ ~12 queries × 160 clients for one signal; persons get the same via
`person_trajectory`. Fix needs a bulk/batched trajectory path or a trajectory cache
on `DetectionCache` — a real change, deliberately deferred per Molham's scope call
(2026-06-01). **Daemon/API stay STOPPED until C2b lands.**

## PR Scope

Single PR (Phase C2, fixes 1+2). Files: `lib/intelligence/signals.py` +
`audit-remediation/VERIFICATION_LOG_S23.md`. No other concerns bundled.
Two independently-valuable fixes that share one file and one root theme
(detection cache reuse), so one PR; the trend rework is a separate PR.

## Tooling note (Session 23)
Tool output this session intermittently duplicated/scrambled large blocks (Read
ranges >~30 lines, multi-line Bash stdout). It was a rendering/transport artifact,
never file corruption — `py_compile` passing and `grep -Fc` counts on the real file
are the trustworthy signals, and bounded reads (≤45 lines) + single-pattern
`grep -nF` were used for every line-number claim above.
