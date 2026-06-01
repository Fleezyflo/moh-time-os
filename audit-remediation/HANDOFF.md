# HANDOFF -- Audit Remediation

**Generated:** 2026-06-01
**Current Phase:** post-audit (all structural repair complete; perf hardening continuing)
**Current Session:** 25
**Track:** Post-audit perf — detection pipeline (C2 → C2b)

---

## What Just Happened

### Session 24 -- Phase C2b: bulk-trajectory path

Branch: `claude/fervent-germain-af8e0f` (rebased onto new main `a74b2a9`; C2 already merged via PR #114). PR: #TBD.

C2b closes the LAST `detect_all_signals(quick=False)` bottleneck — the TREND/ANOMALY
trajectory N×M that C2 deferred. The autonomous loop's Phase 1f hung because each
trend/anomaly client+person signal called `engine.client_trajectory()` /
`person_trajectory()` per entity, and each trajectory ran `client_metrics_in_period`
once per window, firing 3 queries (`tasks/invoices/communications_in_period`) on a fresh
`mode=ro` connection ⇒ ~5,514 `_execute` calls / 83s for the trajectory load alone.

**Two files:**
- `lib/query_engine.py` (+~210): `bulk_client_trajectories()` + `bulk_person_trajectories()`
  (next to `client_trajectory()`), plus static helpers `_trajectory_windows()` /
  `_window_index()`. Each runs the 3 period views ONCE across the full window span (no
  per-entity filter) and buckets rows by (entity, window) in memory, reproducing the
  per-entity metric aggregation + `_compute_trend` byte-for-byte. Built at the MAX window
  count (num_windows=6, window_size=30); smaller requests are the most-recent-N slice of
  the same 30-day grid. Person path accumulates per lowercased name then assigns to EVERY
  person_id bearing it (matches the existing many-to-one `LOWER(assignee)=name` behavior,
  incl. same-name dupes).
- `lib/intelligence/signals.py` (+~150): `DetectionCache.trajectory_map` + `get_trajectory()`
  (slices the primed map, recomputes trends on the slice, lazy fallback to the per-entity
  engine call when unprimed) + `_slice_trajectory()`. `detect_all_signals(not quick)` primes
  the map once (mirrors the C2 `score_map` prime). `_evaluate_trend`/`_evaluate_anomaly` gain
  a `cache` param (the gap C2 closed for `_evaluate_compound`) and read the cache when present.

**Result (live-DB copy, 160 clients):** full-mode `detect_all_signals(quick=False)` now
finishes in **23.9–24.3s**, `success=True`, 0 errors, 169 signals — DONE_OK. Trajectory
load **5,514 → 6 `_execute` calls (919×), 83.4s → 3.5s**. Bulk vs per-entity EQUIVALENCE
proven: 402 client + 36 person checks, 0 mismatches.

**Verification:** ruff (repo-wide) / ruff-format / bandit / py_compile / mypy strict-island
all clean; `test_query_engine`(43)+`test_intelligence_signals`(29)+`test_intelligence_scoring`(41)+`test_signal_lifecycle`(13) = 126 passed. Pre-existing
`test_trajectory.py` (48 errors, determinism guard on `TrajectoryEngine()`) and
`test_daemon_intelligence.py` (11 fails, `AutonomousLoop.cycle_count`) reproduce on pristine
main with my files reverted — not caused by C2b. Full log: `VERIFICATION_LOG_S24.md`.

---

## What's Next

1. **Merge the C2b PR.**
2. **Restart daemon/API — but the daemon plist runs `lib.daemon` FROM the main checkout**
   `/Users/molhamhomsi/clawd/moh_time_os`, which is on the dirty `fix/portfolio-progressive-render`
   branch whose `lib/` has neither C2 nor C2b. Restarting now reruns the hang. Gate: merge C2b →
   move main checkout to `origin/main` (touches the off-limits dirty branch — Molham's call) →
   re-install/load `~/Library/LaunchAgents/com.mohtime.daemon.plist` + `com.mohtimeos.api.plist` →
   verify one cycle (`daemon_state.json` `autonomous.last_success` advances, `consecutive_failures`
   168→0, cycle < 2 min). A full cycle still logs Xero `invalid_client` (dead token, separate from
   detection).
3. Phase B data freshness, Phase D intelligence verification — see root `HANDOFF.md` §Now.

The authoritative resume doc is the **root** `/Users/molhamhomsi/clawd/moh_time_os/HANDOFF.md`
(untracked, main-checkout-only). This file mirrors its C2b summary.

---

## Key Rules

1. This shell runs on Molham's Mac — run git/sqlite/gh/pre-commit yourself; ask before push/PR/merge and destructive live-DB ops.
2. Commit subject under 72 chars, valid types only.
3. "HANDOFF.md removed and rewritten" required in commit body.
4. If 20+ deletions, include "Deletion rationale:" in body.
5. Match existing patterns obsessively (C2b mirrors C2's score_map prime + cache-param threading exactly).
6. No comments in command blocks.
7. `store.query()` reads only; writes via `store.insert/update/delete`.
8. Schema lives in `lib/schema.py` only.
9. macOS: no `timeout` (use Python `signal.alarm`); system `python3` lacks `yaml` — use the main checkout's `.venv/bin/python` (3.11.13) for anything importing `lib/`; local ruff is 0.15.1 == pre-commit pinned, so formatting from here is safe.
10. The daemon runs code from the MAIN CHECKOUT, not the worktree — a worktree-only fix is not "live" until the main checkout is on main.
11. Test against a COPY of the live DB, never the live DB (daemon may touch it); pass a `Path` to `QueryEngine`/`detect_all_signals`, not a `str`.

---

## Documents to Read

1. `audit-remediation/AGENT.md` -- This brief
2. `/Users/molhamhomsi/clawd/moh_time_os/HANDOFF.md` -- Authoritative resume doc (root, untracked)
3. `audit-remediation/VERIFICATION_LOG_S24.md` -- C2b verification log
4. `audit-remediation/state.json` -- Current project state
5. `CLAUDE.md` -- Repo-level engineering rules
