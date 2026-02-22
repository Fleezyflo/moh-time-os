# AO-2.1: Wire Change Bundles into Every Loop Action

## Objective
Integrate `lib/change_bundles.py` into the autonomous loop so every state mutation is tracked and rollback-capable.

## Context
`lib/change_bundles.py` provides rollback infrastructure — it can track changes and reverse them. But `lib/autonomous_loop.py` never calls it. State mutations happen silently: truth values overwritten, signals updated, snapshots replaced. If a bad data cycle corrupts truth values, there's no way back.

## Implementation

### Change Bundle Wrapping
```python
# In autonomous_loop.py, each job wrapped:
bundle = change_bundles.start_bundle(
    cycle_id=cycle.id,
    job_name="truth_cycle",
    description="Truth module computation cycle"
)
try:
    result = truth_cycle.run()
    change_bundles.commit_bundle(bundle, result.summary)
except Exception as e:
    change_bundles.rollback_bundle(bundle)
    raise
```

### What Gets Tracked
- **Truth values**: before/after for every truth module output
- **Signal writes**: new signals created, old signals updated
- **Snapshot data**: previous snapshot preserved before overwrite
- **Notification state**: what was sent, to whom

### Rollback Capability
- On cycle failure: auto-rollback current bundle
- On manual trigger: rollback last N bundles via CLI command
- Bundle metadata: cycle_id, timestamp, job_name, rows_affected, duration

### Storage
- Bundles stored in `change_bundles` table (or whatever existing table structure is)
- Retention: keep last 30 days of bundles, archive older
- Size management: only store diffs, not full snapshots

## Validation
- [ ] Every loop job creates a change bundle
- [ ] Bundle contains before/after state for mutations
- [ ] Failed job auto-rolls back its bundle
- [ ] Manual rollback via CLI restores previous state
- [ ] Bundle metadata queryable (which cycle, when, what changed)
- [ ] 30-day retention enforced

## Files Modified
- `lib/autonomous_loop.py` — wrap each job in bundle
- `lib/change_bundles.py` — extend if needed for truth/signal tracking
- CLI command for manual rollback (if not already present)

## Estimated Effort
Medium — wiring existing infrastructure, not building from scratch
