# Brief 17: Intelligence Wiring & Persistence

## Status: DESIGNED
## Priority: P0 — Nothing downstream works until intelligence outputs are integrated
## Dependencies: Brief 11 (Intelligence Expansion — modules built), Brief 10 (Autonomous Operations — daemon running)

## Problem Statement

The intelligence layer has real computation — signals with anomaly detection, 14 structural patterns, cost-to-serve analysis, trajectory regression, correlation mapping, ranked proposals — but none of it connects to anything. The intelligence pipeline runs, produces output, and the output vanishes.

Specific problems discovered in code audit:

1. **Missing tables.** `signal_state` is referenced throughout `signals.py` (lines 1646-1870) but the table doesn't exist in production migrations. `signals.py` tries to read/write signal state for escalation tracking, cooldown management, and history — all of which silently fail. Same for pattern persistence: `detect_all_patterns()` returns results that are never stored anywhere.

2. **Parallel scoring systems.** `engine.py` runs `score_all_clients()` through `scorecard.py`, producing composite health scores. Meanwhile, `agency_snapshot/` has its own completely independent health scoring (delivery 35%, comms 25%, cash 25%, relationship 15% — different weights, different logic). The truth cycle's `_run_client_truth()` calls a third health calculator in `lib/client_truth/health_calculator.py`. Three systems compute "client health" independently and none of them shares results with the others.

3. **Intelligence island.** `generate_intelligence_snapshot()` in `engine.py` runs a 4-stage pipeline (score → signal → pattern → proposal) and returns a complete dict. But the only consumer is the REST API. The truth cycle doesn't call it. The daemon doesn't call it. The agency snapshot doesn't read from it. Intelligence runs in isolation.

4. **No persistence for patterns or cost-to-serve.** Patterns detected by `detect_all_patterns()` are returned as dicts but never written to the database. The `patterns` table exists but `engine.py` doesn't write to it. `CostToServeEngine.compute_portfolio_profitability()` returns a `PortfolioProfitability` dataclass that's never persisted — it's computed on demand every API call.

5. **No event system.** When a critical signal fires, nothing happens downstream. There's no mechanism for the preparation engine (Brief 24) or any future consumer to react to intelligence events. The daemon runs collectors → truth cycle → snapshot → notify, but intelligence is not in this pipeline.

## What This Brief Does

Wire what exists into the system. No new intelligence computation — just connecting the modules that are already built and making their outputs persistent, unified, and consumable.

## Success Criteria

- Signal state persisted: escalation, cooldown, history all written to real tables that survive restarts
- Pattern results persisted: each detection cycle writes detected patterns to DB with timestamp
- Cost-to-serve persisted: portfolio profitability snapshots stored daily
- Single health scoring system: agency snapshot and truth cycle consume intelligence scorecard, not their own parallel calculation
- Intelligence pipeline integrated into daemon cycle: collect → truth → **intelligence** → snapshot → notify
- Event hooks: when intelligence detects a new critical/warning signal, pattern, or proposal, downstream consumers can subscribe and react
- Score history reliable: `score_history` table populated every cycle with all entity scores

## Scope

### Phase 1: Create Missing Tables & Fix Persistence (IW-1.1)

Create the tables that `signals.py` already expects:

```sql
CREATE TABLE signal_state (
    signal_key TEXT PRIMARY KEY,    -- entity_type:entity_id:signal_type
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    first_detected_at TEXT NOT NULL,
    last_detected_at TEXT NOT NULL,
    escalated_at TEXT,
    cleared_at TEXT,
    detection_count INTEGER DEFAULT 1,
    cooldown_until TEXT,
    state TEXT NOT NULL DEFAULT 'active'  -- 'active' | 'escalated' | 'cleared' | 'suppressed'
);

CREATE TABLE pattern_snapshots (
    id TEXT PRIMARY KEY,
    detected_at TEXT NOT NULL,
    pattern_id TEXT NOT NULL,
    pattern_name TEXT NOT NULL,
    severity TEXT NOT NULL,
    entities_involved TEXT NOT NULL,  -- JSON
    evidence TEXT NOT NULL,           -- JSON
    cycle_id TEXT                     -- which daemon cycle detected it
);

CREATE TABLE cost_snapshots (
    id TEXT PRIMARY KEY,
    computed_at TEXT NOT NULL,
    snapshot_type TEXT NOT NULL,      -- 'portfolio' | 'client'
    entity_id TEXT,                   -- NULL for portfolio
    data TEXT NOT NULL                -- JSON: full profitability result
);
```

Wire `signals.py` state management functions to actually read/write `signal_state`. Wire pattern detection in `engine.py` to persist results to `pattern_snapshots`. Wire cost-to-serve to write daily snapshots.

### Phase 2: Unify Health Scoring (IW-2.1)

Identify all three health scoring codepaths:
1. `lib/intelligence/scorecard.py` — `score_client()` with 5 weighted dimensions
2. `lib/agency_snapshot/` — client health blend (delivery 35%, comms 25%, cash 25%, relationship 15%)
3. `lib/client_truth/health_calculator.py` — used by truth cycle

Designate `scorecard.py` as the authoritative scorer (it's the most complete — 5 dimensions, proper weighting, data from all sources). Modify `agency_snapshot` to read from `score_history` table instead of computing its own scores. Modify `client_truth` to call `scorecard.score_client()` and persist results. Document the scoring formula in one place.

### Phase 3: Wire Intelligence into Daemon Cycle (IW-3.1)

Add intelligence as a daemon stage between truth cycle and snapshot:

```
collect (30 min) → truth_cycle (15 min) → intelligence (15 min) → snapshot (15 min) → notify (60 min)
```

The intelligence stage calls `generate_intelligence_snapshot()` and:
- Persists signal state changes
- Persists pattern snapshots
- Persists score history
- Stores the latest proposal set
- Emits events for any new CRITICAL/WARNING findings

### Phase 4: Event Hook System (IW-4.1)

Simple event system — not pub/sub infrastructure, just a hook table:

```sql
CREATE TABLE intelligence_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,      -- 'signal_new' | 'signal_escalated' | 'signal_cleared' | 'pattern_detected' | 'proposal_generated'
    severity TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    event_data TEXT NOT NULL,      -- JSON: signal/pattern/proposal details
    created_at TEXT NOT NULL,
    consumed_at TEXT,              -- NULL until a downstream consumer processes it
    consumer TEXT                  -- which system consumed it
);

CREATE INDEX idx_intelligence_events_unconsumed
    ON intelligence_events(event_type, severity)
    WHERE consumed_at IS NULL;
```

When Brief 24's preparation engine runs, it reads unconsumed events and prepares actions in response. When Brief 22's decision journal records a dismissal, it writes back. This is the bridge between intelligence and action.

### Phase 5: Integration Validation (IW-5.1)

Verify:
- Daemon cycle includes intelligence stage and completes successfully
- Signal state survives daemon restart (persisted to DB)
- Patterns from last cycle retrievable from `pattern_snapshots`
- Score history grows by one row per entity per cycle
- Agency snapshot health scores match scorecard health scores (±2 points tolerance for rounding)
- Intelligence events emitted for critical findings
- Event hook table doesn't grow unbounded (auto-expire consumed events after 30 days)

## Files Created
- Migration: `migrations/v31_intelligence_wiring.sql`
- `lib/intelligence/persistence.py` — write signal_state, pattern_snapshots, cost_snapshots
- `lib/intelligence/events.py` — event emission and consumption
- `lib/intelligence/health_unifier.py` — adapter that makes agency_snapshot use scorecard
- Modified: `lib/daemon.py` — add intelligence stage
- Modified: `lib/agency_snapshot/` — consume unified scores
- Modified: `lib/client_truth/health_calculator.py` — delegate to scorecard
- `tests/test_intelligence_wiring.py`
- `tests/test_health_unification.py`

## Estimated Effort
Large — ~900 lines (migrations + persistence layer + daemon wiring + health unification + event hooks + validation)
