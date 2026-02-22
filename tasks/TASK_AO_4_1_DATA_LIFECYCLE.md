# AO-4.1: Data Lifecycle Management

## Objective
Implement retention policies, archival, and cleanup for sync data, change bundles, and logs to prevent unbounded DB growth.

## Context
The SQLite database is 556MB and growing. Every collector run adds rows. Change bundles (AO-2.1) will add more. No retention policy exists — old sync records, stale signals, and expired snapshots accumulate indefinitely. Without lifecycle management, the DB will degrade in performance.

## Implementation

### Retention Policies
| Data Type | Retention | Archive Strategy |
|-----------|-----------|------------------|
| Raw collector data (messages, events) | 365 days | Export to JSON, delete from DB |
| Change bundles | 30 days | Delete (rollback only useful short-term) |
| Snapshots (agency_snapshot.json) | 90 days | Archive to dated files |
| Signals | 180 days | Aggregate old signals into summary rows |
| Truth module outputs | 90 days | Keep latest + monthly snapshots |
| Cycle logs | 30 days | Export to log files, delete from DB |
| Collector run metadata | 90 days | Delete |

### Implementation Approach
```python
# lib/data_lifecycle.py

class DataLifecycleManager:
    def __init__(self, db_path: str, archive_dir: str):
        self.db_path = db_path
        self.archive_dir = archive_dir

    def run_retention(self):
        """Execute all retention policies."""
        self.archive_old_collector_data(days=365)
        self.purge_change_bundles(days=30)
        self.archive_snapshots(days=90)
        self.aggregate_old_signals(days=180)
        self.purge_cycle_logs(days=30)
        self.vacuum_db()

    def archive_old_collector_data(self, days: int):
        """Export old rows to JSON, then DELETE from DB."""
        ...

    def vacuum_db(self):
        """VACUUM to reclaim space after deletions."""
        ...
```

### Scheduling
- Run lifecycle management once per day (during low-activity hours)
- Wire into autonomous loop as a daily maintenance job
- Log bytes reclaimed, rows archived, rows deleted

### Safety
- Archive BEFORE delete — always
- Dry-run mode: report what would be deleted without executing
- Never delete data less than 24 hours old
- VACUUM only after significant deletions (>1000 rows)

## Validation
- [ ] Retention policies execute without error
- [ ] Archived data readable from JSON files
- [ ] DB size decreases after retention + VACUUM
- [ ] No data less than retention window is touched
- [ ] Dry-run mode produces accurate report without mutations
- [ ] Daily schedule integrated into autonomous loop

## Files Modified
- New: `lib/data_lifecycle.py`
- `lib/autonomous_loop.py` — add daily maintenance job

## Estimated Effort
Medium — ~200 lines, careful validation needed to prevent data loss
