# TASK: Wire All 4 Truth Modules into Orchestrated Cycle
> Brief: USER_READINESS | Phase: 2 | Sequence: 2.1 | Status: PENDING

## Context

Four truth modules exist with real implementations:
- **time_truth**: BlockManager, CalendarSync, Scheduler, Rollover
- **commitment_truth**: CommitmentManager, Detector, LLMExtractor
- **capacity_truth**: LaneBootstrap, Calculator, DebtTracker
- **client_truth**: HealthCalculator, Linker

But nothing orchestrates them together. The intelligence engine (`lib/intelligence/engine.py`) runs scoring→signals→patterns→proposals but doesn't invoke truth modules first. The daemon runs collect + autonomous_loop but doesn't run truth computation.

## Objective

Create `lib/truth_cycle.py` — a single orchestrator that runs all 4 truth modules in dependency order and produces a unified truth state that the intelligence engine and agency snapshot can consume.

## Instructions

1. Read each truth module's public API:
   ```bash
   grep -n "def " lib/time_truth/*.py lib/commitment_truth/*.py lib/capacity_truth/*.py lib/client_truth/*.py | grep -v "def _"
   ```

2. Design the dependency order:
   - **Step 1**: Time Truth — sync calendar, manage blocks, run scheduler
   - **Step 2**: Commitment Truth — detect commitments from recent communications, update lifecycle
   - **Step 3**: Capacity Truth — calculate lane utilization, track debt
   - **Step 4**: Client Truth — compute health scores using signals + capacity + commitments

3. Create `lib/truth_cycle.py`:
   ```python
   class TruthCycle:
       def __init__(self, db_path: str):
           self.db_path = db_path

       def run(self) -> TruthCycleResult:
           """Execute all truth modules in dependency order."""
           results = {}
           results["time"] = self._run_time_truth()
           results["commitments"] = self._run_commitment_truth()
           results["capacity"] = self._run_capacity_truth()
           results["client_health"] = self._run_client_truth()
           return TruthCycleResult(
               stages=results,
               errors=[],
               timestamp=datetime.now(timezone.utc)
           )
   ```

4. Each `_run_*_truth()` method:
   - Wraps the module's public API
   - Catches and logs errors (never swallows)
   - Returns a typed result with counts and status
   - Continues to next module even if one fails (graceful degradation)

5. Wire into the daemon's job registry (will be finalized in UR-5.1).

6. Write tests for the orchestrator:
   - Test that all 4 stages run in order
   - Test graceful degradation when one stage fails
   - Test that result contains all stage outputs

## Preconditions
- [ ] Phase 1 complete (dead code removed)

## Validation
1. `python3 -c "from lib.truth_cycle import TruthCycle"` succeeds
2. `TruthCycle(db_path).run()` executes all 4 stages (may warn on missing data — that's OK)
3. Each stage returns a typed result, not None or empty dict
4. `pytest tests/ -q` — passes

## Acceptance Criteria
- [ ] `lib/truth_cycle.py` created with TruthCycle class
- [ ] 4 truth modules wired in dependency order
- [ ] Graceful degradation (one failure doesn't block others)
- [ ] Tests written and passing
- [ ] No test regressions

## Output
- Created: `lib/truth_cycle.py`
- Created: `tests/test_truth_cycle.py`
