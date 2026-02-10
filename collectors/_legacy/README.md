# Legacy Collectors

**DO NOT IMPORT FROM THIS DIRECTORY**

These collectors were moved here during the collector cleanup (2025-02-10).
They are kept for reference but are NOT wired into the canonical collection path.

## Contents

- `team_calendar.py` — Multi-user calendar collector (superseded by scheduled_collect.py + V5)
- `asana_sync.py` — Standalone Asana sync script (superseded by scheduled_collect.py + V4 ingest)

## Why they were deprecated

1. Not in `lib/collectors/orchestrator.py`'s `collector_map`
2. Overlapping functionality with `collectors/scheduled_collect.py`
3. Not wired into V4/V5 pipeline

## Canonical path

All collection now goes through:
```
collectors/scheduled_collect.py → out/*.json → V5 detectors → v29 tables → API
```

See `COLLECTOR_AUDIT.md` for full documentation.
