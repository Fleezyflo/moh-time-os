# IE-7.1: Intelligence Integration Validation

## Objective
End-to-end validation that all intelligence modules work together: cost-to-serve feeds scenario modeling, patterns use trajectories, resolution queue acts on insights, and the unified signal model serves everything.

## Context
Brief 11 builds 6 independent intelligence modules. They must work as a system, not as isolated components. This task validates the integration.

## Validation Matrix

### Data Flow Verification
```
collectors → truth modules → trajectories → pattern engine → resolution queue
                ↓                  ↓              ↓
           cost-to-serve    scenario engine   notifications
                ↓                  ↓              ↓
           unified signals → agency snapshot → Google Chat
```

### Test Scenarios

1. **Full Cycle Test**: Run complete cycle with all intelligence modules. Verify:
   - Trajectories computed from latest truth values
   - Patterns detected using latest signals + trajectories
   - Resolution items created from critical patterns
   - Automations execute on new resolution items
   - Snapshot includes all intelligence outputs

2. **Cost-to-Serve → Scenario Integration**: Compute cost for client A, then simulate removing client A. Verify freed capacity matches cost-to-serve labor hours.

3. **Pattern → Resolution Integration**: Inject data that triggers a client_risk pattern. Verify resolution item created and escalation notification fires.

4. **Trajectory → Pattern Integration**: Inject declining trajectory data. Verify pattern engine detects engagement_drop pattern from trajectory signals.

5. **Unified Signals Consistency**: After full cycle, verify all signals in `signals_unified` — no orphaned V4/V5 signals.

### Quantitative Checks
- [ ] Cost-to-serve computed for ≥90% of active clients
- [ ] Trajectories computed for all 7 defined metrics
- [ ] Pattern engine runs all 6 detectors without error
- [ ] Scenario engine handles all 5 scenario types
- [ ] Resolution queue processes items with ≥3 automation types
- [ ] Snapshot contains live (not hardcoded) intelligence data
- [ ] Zero data integrity errors in unified signal table

## Deliverables
- Integration test report with pass/fail per scenario
- Data flow diagram verified against actual execution
- Performance baseline: time to run full intelligence cycle
- List of any cross-module issues discovered and resolved

## Estimated Effort
Medium — mostly running tests and validating outputs, fixing integration issues as found
