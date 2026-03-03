# ADR-0014: Detection Engine Tables and Detectors

**Date:** 2026-03-03
**Status:** Accepted
**Context:** Phase 15b

## Decision

Add four detection-related tables and six detector modules to power the factual detection system (collision, drift, bottleneck).

## Changes

### Schema (lib/schema.py)
- SCHEMA_VERSION 13 to 14
- `detection_findings`: main findings table with detector type, entity, severity/adjacent data, timestamps for lifecycle (detected, resolved, notified, acknowledged, suppressed)
- `detection_findings_preview`: identical schema for dry-run week
- `task_weight_rules`: pattern-based weight derivation (keyword/project -> quick/standard/heavy)
- `task_weight_overrides`: per-task manual weight corrections

### Detectors (lib/detectors/)
- `collision.py`: Path A (time_blocks) for Molham, Path B (events JOIN calendar_attendees) for team
- `drift.py`: clients with overdue tasks + zero completions in 5 days, revenue via COALESCE
- `bottleneck.py`: load/throughput detection with absence exclusion
- `task_weight.py`: pattern-based weight engine with learning loop
- `correlator.py`: cross-finding entity overlap pass
- `__init__.py`: orchestrator, wired into autonomous_loop as dry-run

## Rationale

Detection system needs persistent storage for findings lifecycle and task weights for accurate collision ratios. Dry-run preview table allows safe rollout before activating real findings.
