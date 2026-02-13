# Table Drop Log — 2026-02-13

## Summary
- Dropped: 3 tables
- Skipped: 0 tables
- Table count before: 83
- Table count after: 80
- Test suite: 297 passing

## Dropped
| Table | Column Count | Reason |
|-------|-------------|--------|
| `canonical_projects` | (unknown) | Empty + unreferenced |
| `canonical_tasks` | (unknown) | Empty + unreferenced |
| `change_bundles` | (unknown) | Empty + unreferenced |

## Skipped (safety check failed)
| Table | Reason |
|-------|--------|
| _(none)_ | — |

## Notes
- Database backup created: `data/moh_time_os.db.backup_20260213`
- All tables verified to have 0 rows before drop
- Full test suite passed after drops
