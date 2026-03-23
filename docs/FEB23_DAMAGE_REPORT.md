# Feb 23 Damage Report

**Commit:** `e8b334ec` — "feat: full system — 30 briefs, mypy clean, 3043 tests (#24)"
**Date:** 2026-02-23 02:59:55 +0400
**Scope:** 711 files changed, +113,032 / -16,684 lines
**Co-authored by:** Claude

---

## 1. Daemon Gutted — Scheduler Turned Into Broken Pipeline Copy

**Before (Feb 11, commit `000d89f4`):** 475 lines, 3 jobs via subprocess.

```python
# Line 124 — daemon called the REAL pipeline
command=[str(VENV_PYTHON), "-m", "lib.autonomous_loop", "run"]
```

The daemon was a thin scheduler: collect every 30m, call autonomous_loop every 15m, backup daily.

**After (Feb 23):** 689 lines, 4 inline handlers. The subprocess call to `autonomous_loop` was deleted. Replaced with:

- `_handle_collect()` — calls `collect_all()` directly
- `_handle_truth_cycle()` — calls `TruthCycle(db_path).run()` directly, NO gate checks
- `_handle_snapshot()` — calls `AgencySnapshotGenerator` directly
- `_handle_notify()` — stub

**Missing from daemon after rewrite:** normalization, commitment_extraction, gate checks, resolution_queue, auto_resolution, lane_assignment, detection, intelligence, analyze, surface, reason, execute, staleness_alert, morning_brief. 14 phases.

**Then on Mar 16 (commit `bca3b415`):** 4 more handlers added (lane_assignment, detection, intelligence, morning_brief) but still missing normalization, commitment_extraction, gates, resolution_queue, auto_resolution, staleness_alert, and the entire analyze→surface→reason→execute chain.

**Evidence:** `grep -c 'normalization\|commitment_extract\|_check_gates\|resolution_queue\|auto_resolv\|_surface_\|reasoner\|executor.process' lib/daemon.py` returns 0.

**Impact:** The daemon (the only scheduled runner) executes ~50% of the pipeline. Truth modules run without gate checks. Detection findings are never analyzed. Intelligence is signal-only (no scoring, patterns, or proposals). The analyze→surface→reason→execute chain never runs.

---

## 2. Asana Collector — API Call Bomb

**Before:** 114 lines. `completed=False` filter. `projects[:15]` limit. No per-task API calls.

```python
# Line 40 — only incomplete tasks, limited projects
tasks = list_tasks_in_project(proj_gid, completed=False)
```

**After:** 638 lines. Line 67-68: `# Collect ALL tasks (not just incomplete)`. For EVERY task, 4 extra API calls:

- Line 90: `subtasks = list_subtasks(task_gid)`
- Line 98: `stories = list_stories(task_gid)`
- Line 106: `deps = list_task_dependencies(task_gid)`
- Line 114: `attachments = list_task_attachments(task_gid)`

**Impact:** 17,129 incomplete Asana tasks × 4 API calls = 68,516 API calls per sync. The old collector did ~15 project-level fetches. The daemon's Asana sync now takes hours and may never complete within the 30-minute interval.

---

## 3. All Collectors Bloated 2-5x

| Collector | Before | After | Factor |
|-----------|--------|-------|--------|
| Asana     | 114    | 638   | 5.6x   |
| Gmail     | 303    | 705   | 2.3x   |
| Calendar  | 166    | 532   | 3.2x   |
| Xero      | 312    | 539   | 1.7x   |
| Chat      | (new)  | 487   | —      |

Gmail `max_results` default raised from 200 to 500 (line 99).

---

## 4. 73 Dead Modules — 25,000+ Lines Never Wired

94 new `lib/` files added (31,902 lines total). Only 21 are imported by server.py, daemon.py, or autonomous_loop.py. The other 73 have no callers from any entry point.

**Largest dead modules:**

| File | Lines | Wired? |
|------|-------|--------|
| lib/intelligence/scenario_engine.py | 1,190 | No |
| lib/intelligence/auto_resolution.py | 975 | No |
| lib/intelligence/conversational_intelligence.py | 874 | No |
| lib/governance/subject_access.py | 726 | No |
| lib/intelligence/trajectory.py | 713 | No |
| lib/intelligence/temporal.py | 711 | No |
| lib/intelligence/correlation_engine.py | 679 | No |
| lib/intelligence/unified_intelligence.py | 676 | No |
| lib/intelligence/data_governance.py | 674 | No |
| lib/data_lifecycle.py | 603 | No |
| lib/governance/retention_engine.py | 579 | No |
| lib/intelligence/cost_to_serve.py | 568 | No |
| lib/intelligence/signal_lifecycle.py | 525 | No |
| lib/integrations/calendar_writer.py | 523 | No |
| lib/integrations/gmail_writer.py | 492 | No |

---

## 5. 37 Silent Exception Handlers

`except Exception: pass` or `except: continue` — errors swallowed with no logging.

| File | Count | Lines |
|------|-------|-------|
| engine/heartbeat_pulse.py | 6 | 135, 158, 229, 279, 323, 339 |
| engine/discovery.py | 2 | 181, 189 |
| engine/xero_client.py | 1 | 38 |
| lib/collectors/gmail.py | 2 | 270, 393 |
| lib/commitment_truth/detector.py | 1 | 240 |
| lib/governance/anonymizer.py | 1 | 131 |
| lib/agency_snapshot/* | 4 | various |
| lib/collectors/* | 5 | various |
| lib/intelligence/* | 2 | various |
| Others | 13 | various |

---

## 6. 36 Return-Empty-On-Failure Patterns

Functions catch errors and return `{}` or `[]`, disguising failures as "no data."

| File | Count | Lines |
|------|-------|-------|
| lib/collectors/chat.py | 3 | 141, 152, 161 |
| lib/db_opt/query_optimizer.py | 3 | 125, 189, 210 |
| lib/governance/retention_engine.py | 3 | 229, 519, 577 |
| lib/governance/subject_access.py | 2 | 240, 290 |
| lib/intelligence/* | 5 | various |
| lib/governance/* | 3 | various |
| Others | 17 | various |

---

## 7. Agency Snapshot Pages Gutted

8 of 12 page generators had 60-75% of code deleted:

| File | Deleted | Added | % Gutted |
|------|---------|-------|----------|
| client360.py | 36 | 12 | 75% |
| client360_page10.py | 55 | 19 | 74% |
| comms_commitments.py | 69 | 24 | 74% |
| cash_ar.py | 72 | 24 | 69% |
| comms_commitments_page11.py | 92 | 42 | 69% |
| capacity_command_page7.py | 58 | 26 | 69% |
| cash_ar_page12.py | 74 | 33 | 69% |
| delivery.py | 30 | 10 | 75% |
| deltas.py | 15 | 5 | 75% |
| scoring.py | 6 | 2 | 75% |

---

## 8. Misattributed Canonical Status

After the rewrite, `autonomous_loop.py` was given this header (lines 4-10):

```
NON-CANONICAL ORCHESTRATOR — see CANONICALIZATION.md §9.
The canonical automatic runtime is lib/daemon.py (TimeOSDaemon)...
Do not invest in keeping this in sync with the daemon.
The daemon is the source of truth for the production pipeline order.
```

This labeled the COMPLETE 16-phase pipeline as "non-canonical" and the STRIPPED 4-handler copy as "the source of truth." The label is backwards.

---

## Remediation Plan

**Priority 1 — Restore daemon→loop delegation (the original design):**
- Delete the 8 inline handlers from daemon.py
- Restore the subprocess call (or in-process call) to `AutonomousLoop.run_cycle()`
- Remove the "non-canonical" header from autonomous_loop.py

**Priority 2 — Fix the Asana N+1 bomb:**
- Restore `completed=False` filter
- Restore `projects[:15]` limit (or use pagination with rate limiting)
- Remove per-task subtask/story/dependency/attachment calls (or make them opt-in)

**Priority 3 — Fix silent error handlers (37 instances):**
- Replace `except: pass` with `except Exception: logger.debug(...)` minimum

**Priority 4 — Fix return-empty-on-failure (36 instances):**
- Raise or return typed error results instead of `{}` / `[]`

**Priority 5 — Audit dead modules:**
- Identify which of the 73 unwired modules have value
- Delete the rest (or move to an `_archive/` directory)

**Priority 6 — Restore agency snapshot pages:**
- Compare pre-Feb23 versions against current
- Restore gutted logic where the original was correct
