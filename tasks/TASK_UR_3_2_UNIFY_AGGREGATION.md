# TASK: Consolidate Aggregator into Agency Snapshot Output
> Brief: USER_READINESS | Phase: 3 | Sequence: 3.2 | Status: PENDING

## Context

Two separate aggregation systems produce overlapping outputs:
- `lib/aggregator.py` → `snapshot.json` (gates, risks, domains, deltas)
- `lib/agency_snapshot/generator.py` → `agency_snapshot.json` (full operational dashboard)

The aggregator computes gate status, cross-domain risks, and resolution queue items that the agency snapshot also needs. Rather than running both, the aggregator's gate/risk/queue logic should feed INTO the agency snapshot as a pre-computation step.

## Objective

Integrate the aggregator's unique capabilities (gate evaluation, cross-domain risk ranking, delta tracking) into the agency snapshot pipeline. The agency snapshot becomes the single canonical output. The standalone aggregator can remain as infrastructure but is no longer a separate output.

## Instructions

1. Read both generators side by side:
   ```bash
   # Aggregator's unique sections
   grep -n "def _build_gates\|def _build_risks\|def _build_deltas\|def _build_queue" lib/aggregator.py
   # Snapshot's existing sections
   grep -n "def _build_\|def _extract_" lib/agency_snapshot/generator.py
   ```

2. Identify what the aggregator computes that the snapshot doesn't:
   - **Gate evaluation** with blocking/quality distinction
   - **Cross-domain risk ranking** with time-to-consequence
   - **Resolution queue** item counts
   - **Delta tracking** (comparison to previous snapshot)

3. Integration approach:
   - Add a `_compute_system_health()` step to the snapshot generator that calls the aggregator's gate logic
   - Feed gate results into the snapshot's `trust` section
   - Include top risks in the snapshot's `exceptions` section
   - Add delta tracking to the snapshot's `meta` section

4. Do NOT delete `lib/aggregator.py` — it's useful infrastructure. Just wire its output into the snapshot pipeline.

5. Update the daemon to produce only `agency_snapshot.json` (not both files).

6. Verify the unified output:
   ```python
   from lib.agency_snapshot.generator import AgencySnapshotGenerator
   g = AgencySnapshotGenerator(db_path="data/moh_time_os.db")
   snapshot = g.generate()
   # Should now include: trust.gates, trust.risks, meta.deltas
   assert "gates" in snapshot.get("trust", {})
   ```

## Preconditions
- [ ] UR-3.1 complete (snapshot builders upgraded)

## Validation
1. Agency snapshot output includes gate status, risks, and deltas
2. `trust` section has explicit confidence level (healthy/degraded/blocked)
3. Snapshot still passes all 4 validation gates
4. Only one output file needed (agency_snapshot.json)
5. `pytest tests/ -q` — passes

## Acceptance Criteria
- [ ] Aggregator gate/risk logic feeds into agency snapshot
- [ ] Single canonical output (agency_snapshot.json)
- [ ] Trust section includes confidence model
- [ ] Delta tracking integrated
- [ ] No test regressions

## Output
- Modified: `lib/agency_snapshot/generator.py` (integration)
- Modified: daemon job config (single output)
- Not deleted: `lib/aggregator.py` (kept as infrastructure)
