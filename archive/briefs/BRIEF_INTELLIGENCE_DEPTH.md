# Brief 18: Intelligence Depth & Cross-Domain Synthesis

## Status: DESIGNED
## Priority: P0 — Intelligence must be genuinely deep before anything consumes it
## Dependencies: Brief 17 (Intelligence Wiring — persistence, events, unified scoring), Brief 11 (base modules)

## Problem Statement

Brief 17 connects the intelligence modules to the system. This brief deepens the intelligence itself. The code audit revealed that while the modules are well-engineered structurally, the actual computation is shallow in several critical areas:

### What's strong (leave alone)

- **Trajectory engine** (`trajectory.py`): Real linear regression with R², velocity/acceleration derivatives, autocorrelation-based seasonality detection, forward projection with ±1.96σ confidence bands. This is production-quality statistical analysis. Minimum 7-10 data points required.

- **Signal detection** (`signals.py`): 28+ signal types with proper severity classification, detection caching to avoid O(n²), state management (escalation, cooldown). The detection logic itself is threshold-based but well-calibrated with configurable parameters.

- **Proposal ranking** (`proposals.py`): Multi-factor priority scoring (0.40×urgency + 0.30×impact + 0.15×recency + 0.15×confidence), evidence synthesis, deduplication by entity. Good evidence gathering.

### What's shallow (this brief fixes)

1. **Correlation engine uses hardcoded confidence.** Every `CrossDomainCorrelation` object gets `confidence=0.7` regardless of evidence. The compound risk rules check if patterns/signals are present (boolean) but don't measure how strongly they correlate. There's no actual statistical correlation computed — just "these two things are both firing → compound risk." This means the system can't distinguish between a genuine causal chain (resource overload → quality decline → client churn) and coincidental co-occurrence.

2. **Cost-to-serve uses task count as effort proxy.** The effort formula is `(active_tasks × 2) + (overdue_tasks × 3) + (completed_tasks × 0.5)`. All tasks are weighted equally. A 30-minute admin task counts the same as a 40-hour brand strategy project. `avg_task_duration_days` is hardcoded to `0.0` because the system has no duration data. Communication count is raw volume with no distinction between a 2-line email and a detailed project proposal. The profitability band defaults to "MED" and is only adjusted by portfolio percentile comparison, not actual cost analysis.

3. **No cross-domain narrative.** The system detects that Client X has: low health score (scorecard), overdue invoices (signal), declining communication (signal), resource concentration (pattern), and declining trajectory. But nowhere does it synthesize these into: "Client X is in trouble — they've gone quiet, their invoices are piling up, and 80% of their work runs through one person who's overloaded. This looks like a relationship that's about to end unless you intervene." Each module produces its piece but there's no interpretive layer.

4. **No outcome tracking.** When the system raises a signal and you act on it, there's no mechanism to see whether the action worked. Did the health score improve? Did the client re-engage? Did the payment come in? Without this, the system can't learn which signals actually matter and which are noise.

5. **Patterns lack temporal context.** Pattern detection is point-in-time: "right now, revenue is concentrated" or "right now, resources are concentrated." There's no tracking of whether a pattern is new (just emerged), persistent (been there for weeks), or resolving (was worse, now improving). Brief 17 adds pattern persistence — this brief uses that persistence to add temporal awareness.

## What This Brief Does

Deepen the computation where it's shallow. Add the interpretation layer. Build outcome tracking. Make intelligence genuinely useful for the preparation engine (Brief 24) and conversational interface (Brief 25) that sit on top.

## Success Criteria

- Correlation engine computes evidence-based confidence: compound risks that fire with strong evidence score higher than coincidental co-occurrence
- Cost-to-serve uses best-available effort proxies from actual data (task age, assignee count, project scope, communication effort)
- Entity narratives: any entity (client, project, person) can produce a 2-3 sentence synthesis of its current state drawing from all intelligence modules
- Outcome tracking: when a signal is raised and later cleared, the system records what happened in between (what action was taken, how long resolution took, whether the entity improved)
- Pattern trending: patterns carry a direction (new/persistent/resolving/worsening) based on historical snapshots from Brief 17
- Cross-domain synthesis: for any entity, produce a unified intelligence profile that combines scorecard, signals, patterns, trajectory, cost, and correlation findings into one structured object

## Scope

### Phase 1: Evidence-Based Correlation (ID-1.1)

Replace hardcoded `confidence=0.7` with computed confidence based on:
- **Co-occurrence strength**: How many of the expected compound risk components are actually firing? If a rule requires pattern A + signal B + signal C, and all three are present, confidence is higher than if only A + B are present.
- **Severity alignment**: If all components are CRITICAL, compound confidence is higher than mixed CRITICAL + WATCH.
- **Temporal proximity**: If components were detected within the same cycle (or within 48 hours of each other), confidence is higher than if one was detected 2 weeks ago and the other today. Use `detected_at` from signal_state (Brief 17) and `detected_at` from pattern_snapshots.
- **Historical recurrence**: If this compound risk has been detected in 3 of the last 5 cycles, confidence is higher than first-time detection.

The formula doesn't need machine learning — a weighted scoring function is fine:
```
confidence = (
    0.35 × component_completeness +   # what fraction of required components are present
    0.25 × severity_alignment +         # are components similarly severe
    0.20 × temporal_proximity +          # did they fire close together
    0.20 × recurrence_factor            # has this compound risk appeared before
)
```

This replaces the static 0.7 with a 0.0-1.0 score that actually means something.

### Phase 2: Improved Cost-to-Serve Proxies (ID-2.1)

The system genuinely doesn't have time-tracking data. But it has better proxies than raw task count:

- **Task age as effort proxy**: A task open for 45 days has consumed more effort than one open for 2 days. Use `(today - created_at)` weighted by status (active tasks count full duration, completed tasks count `completed_at - created_at`).
- **Assignee diversity**: Tasks with multiple assignees or reassignments indicate higher coordination effort. Count distinct assignees per client.
- **Communication effort weighting**: Instead of raw email count, weight by: thread depth (multi-reply threads indicate more effort), message length buckets (short < 100 chars, medium, long > 500 chars), channel mix (emails weigh more than chat messages).
- **Project scope factor**: Clients with more projects impose higher context-switching overhead. Weight by `sqrt(project_count)` rather than linear.
- **Invoice complexity**: Clients with many small invoices cost more operationally than clients with few large invoices. Factor: `invoice_count / total_invoiced` (higher = more overhead per dollar).

Replace the current formula with:
```
effort_score = (
    weighted_task_age_sum +          # sum of (task_age × status_weight) per client
    assignee_diversity_factor +       # sqrt(distinct_assignees)
    weighted_comm_effort +            # comm count × depth × length factor
    project_overhead +                # sqrt(project_count) × 10
    invoice_overhead                  # (invoice_count / max(total_invoiced, 1)) × 100
)
```

This uses data that actually exists in the database. Validate by checking that profitability bands shift meaningfully from the current raw-task-count calculation.

### Phase 3: Entity Intelligence Profiles (ID-3.1)

Build a synthesis layer that produces a unified intelligence profile for any entity. For a client:

```python
@dataclass
class EntityIntelligenceProfile:
    entity_type: str
    entity_id: str
    entity_name: str
    generated_at: str

    # From scorecard (Brief 11)
    health_score: float
    health_classification: str     # HEALTHY / AT_RISK / CRITICAL
    score_dimensions: dict         # per-dimension breakdown

    # From signals (Brief 11)
    active_signals: list[dict]     # currently firing
    signal_trend: str              # 'increasing' | 'stable' | 'decreasing' (from signal_state history)

    # From patterns (Brief 11 + 17)
    active_patterns: list[dict]    # currently detected
    pattern_direction: dict        # pattern_id → 'new' | 'persistent' | 'resolving' | 'worsening'

    # From trajectory (Brief 11)
    trajectory_direction: str      # from trajectory engine
    projected_score_30d: float | None
    confidence_band: tuple | None  # (low, high)

    # From cost-to-serve (this brief)
    cost_profile: dict | None      # effort score, efficiency ratio, profitability band
    cost_drivers: list[str]

    # From correlation (this brief)
    compound_risks: list[dict]     # risks that involve this entity
    cross_domain_issues: list[str] # domains where problems exist

    # Synthesis (new)
    narrative: str                 # 2-3 sentence human-readable summary
    attention_level: str           # 'urgent' | 'elevated' | 'normal' | 'stable'
    recommended_actions: list[str] # top 3 suggested actions based on all findings
```

The `narrative` field is the key new capability. Built from templates that combine findings:

- If health declining + signals active: "Client X's health has declined to {score} ({classification}). Key concerns: {top_signal_descriptions}. Trajectory shows {direction} trend with projected score of {projected} in 30 days."
- If healthy but costly: "Client X is operationally healthy ({score}) but cost-intensive — efficiency ratio of {ratio} places them in the {band} profitability band. Primary cost drivers: {drivers}."
- If no issues: "Client X is stable at {score}. No active signals or concerning patterns. Last reviewed {days} days ago."

The `attention_level` is computed from:
- `urgent`: any CRITICAL signal or structural compound risk
- `elevated`: any WARNING signal or operational pattern
- `normal`: WATCH signals only
- `stable`: no active findings

### Phase 4: Outcome Tracking (ID-4.1)

When a signal clears (transitions from active → cleared in signal_state), record what happened:

```sql
CREATE TABLE signal_outcomes (
    id TEXT PRIMARY KEY,
    signal_key TEXT NOT NULL,      -- from signal_state
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    detected_at TEXT NOT NULL,     -- when signal first fired
    cleared_at TEXT NOT NULL,      -- when signal cleared
    duration_days REAL NOT NULL,   -- how long it was active
    health_before REAL,            -- entity health score when signal fired
    health_after REAL,             -- entity health score when signal cleared
    health_improved INTEGER,       -- 1 if health_after > health_before
    actions_taken TEXT,            -- JSON: list of actions taken during signal lifetime (from decision_journal when Brief 22 exists, from intelligence_events for now)
    resolution_type TEXT           -- 'natural' (cleared on its own) | 'addressed' (action taken) | 'expired' | 'unknown'
);

CREATE INDEX idx_signal_outcomes_entity ON signal_outcomes(entity_type, entity_id);
CREATE INDEX idx_signal_outcomes_type ON signal_outcomes(signal_type, resolution_type);
```

This gives the system its first feedback loop. Over time, you can query: "Which signal types resolve naturally vs. which require intervention?" and "When I act on signal X, does the entity actually improve?"

### Phase 5: Pattern Trending (ID-5.1)

Use the `pattern_snapshots` table from Brief 17 to compute pattern direction:

- **New**: Pattern detected in current cycle but not in any of the last 5 cycles
- **Persistent**: Pattern detected in current cycle AND in 3+ of the last 5 cycles
- **Resolving**: Pattern detected in 3+ of the last 5 cycles but NOT in the current cycle
- **Worsening**: Pattern detected in current cycle, and the entity count or evidence strength has increased compared to the average of the last 5 cycles

Store the trending result in the entity intelligence profile. This transforms patterns from static observations ("revenue is concentrated") to dynamic intelligence ("revenue concentration is worsening" vs. "revenue concentration is persistent but stable").

### Phase 6: Synthesis & Validation (ID-6.1)

- Build `EntityIntelligenceProfile` assembly function that pulls from all modules
- Generate narratives for all clients and verify they're coherent and accurate
- Verify outcome tracking captures signal lifecycle correctly
- Verify pattern trending correctly classifies new/persistent/resolving/worsening
- Verify correlation confidence varies meaningfully (not all 0.7)
- Verify cost-to-serve profitability bands shift when using improved proxies
- Performance: entity profile generation < 500ms per entity, full portfolio < 10 seconds

## Files Created
- `lib/intelligence/correlation_confidence.py` — evidence-based confidence computation
- `lib/intelligence/cost_proxies.py` — improved effort scoring using real data
- `lib/intelligence/entity_profile.py` — EntityIntelligenceProfile synthesis
- `lib/intelligence/narrative.py` — template-based narrative generation
- `lib/intelligence/outcome_tracker.py` — signal outcome recording
- `lib/intelligence/pattern_trending.py` — pattern direction computation
- Migration: `migrations/v32_intelligence_depth.sql` — signal_outcomes table
- Modified: `lib/intelligence/correlation_engine.py` — use computed confidence
- Modified: `lib/intelligence/cost_to_serve.py` — use improved proxies
- `tests/test_entity_profile.py`
- `tests/test_correlation_confidence.py`
- `tests/test_cost_proxies.py`
- `tests/test_outcome_tracker.py`
- `tests/test_pattern_trending.py`

## Estimated Effort
Very Large — ~1,200 lines (6 new modules + 2 modified modules + migration + validation)
