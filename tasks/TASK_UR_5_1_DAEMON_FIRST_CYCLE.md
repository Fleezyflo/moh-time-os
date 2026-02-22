# TASK: Fix Daemon and Run First Complete Cycle
> Brief: USER_READINESS | Phase: 5 | Sequence: 5.1 | Status: PENDING

## Context

`lib/daemon.py` defines `TimeOSDaemon` with `run()` and `run_once()` methods but has never completed a cycle. Known issues:
- `PROJECT_ROOT` not imported (line 122)
- Job registry references functions that may import removed code (morning brief, Clawdbot)
- No evidence of a successful `daemon_state.json` ever existing

The daemon should orchestrate: **Collect → Truth Cycle → Agency Snapshot → Notification**.

## Objective

Fix all daemon issues and execute one complete cycle that produces real output.

## Instructions

1. Read `lib/daemon.py` fully — understand the job registry, scheduling, state persistence.

2. Fix the `PROJECT_ROOT` import issue.

3. Update the job registry to reflect the new architecture:
   ```python
   JOBS = [
       Job("collect", interval_minutes=30, handler=run_collectors),
       Job("truth_cycle", interval_minutes=15, handler=run_truth_cycle),
       Job("snapshot", interval_minutes=15, handler=run_snapshot, depends_on="truth_cycle"),
       Job("notify", interval_minutes=60, handler=run_notification, depends_on="snapshot"),
   ]
   ```

4. Wire each handler:
   - `run_collectors()` → calls `lib.collectors.scheduled_collect` (already exists)
   - `run_truth_cycle()` → calls `lib.truth_cycle.TruthCycle.run()` (created in UR-2.1)
   - `run_snapshot()` → calls `lib.agency_snapshot.generator.AgencySnapshotGenerator.generate()` + saves to `data/agency_snapshot.json`
   - `run_notification()` → calls NotificationEngine with snapshot summary via Google Chat

5. Remove any references to morning brief, Clawdbot, or tier checks from daemon code.

6. Add `run-once` CLI mode that executes all jobs sequentially regardless of schedule:
   ```bash
   python -m lib.daemon run-once
   ```

7. Execute `run-once`:
   ```bash
   cd /sessions/loving-blissful-keller/mnt/clawd/moh_time_os
   python3 -m lib.daemon run-once
   ```

8. Capture and document output:
   - Did each stage complete?
   - What errors occurred?
   - Was `data/agency_snapshot.json` created?
   - Was a notification sent (dry-run)?

9. Fix any remaining issues until `run-once` completes without error.

## Preconditions
- [ ] Phases 1-4 all complete
- [ ] Truth cycle created (UR-2.1)
- [ ] Snapshot builders upgraded (UR-3.1)
- [ ] Google Chat channel wired (UR-4.1)

## Validation
1. `python3 -m lib.daemon run-once` exits 0
2. `data/agency_snapshot.json` exists and is valid JSON
3. Snapshot passes all 4 validation gates
4. Google Chat notification sent (dry-run or live)
5. `daemon_state.json` updated with last-run timestamps
6. `pytest tests/ -q` — passes

## Acceptance Criteria
- [ ] Daemon fixed — no import errors
- [ ] Job registry reflects new architecture
- [ ] run-once completes all 4 stages
- [ ] agency_snapshot.json produced with real data
- [ ] Notification delivered
- [ ] State persisted
- [ ] No test regressions

## Output
- Modified: `lib/daemon.py` (major update)
- Created: `data/agency_snapshot.json` (first real snapshot)
- Created: `data/daemon_state.json` (first state)
