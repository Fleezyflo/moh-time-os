# Brief 22: Strategic Memory & Decision Journal

## Status: DESIGNED
## Priority: P1 — Makes every other intelligence module smarter over time
## Dependencies: Brief 17 (Intelligence Wiring — persistence, events, unified scoring), Brief 18 (Intelligence Depth — entity profiles, outcome tracking, signal_outcomes table)

## What Brief 17/18 Provide

Brief 17 creates the persistence layer this brief needs: `signal_state` table (signal escalation/cooldown/history), `pattern_snapshots` (detected patterns over time), `intelligence_events` (hook system for downstream consumers), and intelligence integrated into the daemon cycle.

Brief 18 creates the outcome tracking this brief extends: `signal_outcomes` table (what happened when signals cleared), entity intelligence profiles (unified view per entity), and pattern trending (new/persistent/resolving/worsening).

This brief builds the HUMAN layer on top: recording YOUR decisions, YOUR interaction history, and YOUR behavioral patterns — so the system learns from you, not just from data.

## Problem Statement

The system has no memory between cycles. It detects that Client X's health dropped, surfaces a signal, and then next week it surfaces the same signal again — unaware that you already saw it, called the client, gave them a discount, and the situation is stabilizing. Every insight arrives context-free. The system doesn't know what you've already acted on, what you decided to ignore, what worked in similar situations before, or what your preferences are.

This makes the system repetitive and shallow. A true intelligence system should accumulate knowledge about its operator: what signals you care about, how you respond to different situations, which recommendations you consistently dismiss, and what your decision patterns look like over time. Every signal, every recommendation, every prepared action should arrive with your history attached.

## Success Criteria

- Decision journal: every action you take (dismiss signal, approve draft, modify recommendation) is recorded with timestamp and context
- Entity memory: every client, project, and engagement carries a timeline of your interactions and decisions about it
- Signal deduplication: if you've seen and acted on a signal, the system doesn't resurface it unless conditions materially change
- Pattern recognition on YOUR behavior: "Last time a client showed this pattern, you did X and it worked" or "You usually dismiss signals of this type"
- Stale suppression: items you've already reviewed get deprioritized, not repeated
- Context enrichment: every intelligence output includes relevant history from the decision journal
- Preference learning: system adapts its severity thresholds, surfacing frequency, and framing based on your actual behavior over time

## Scope

### Phase 1: Decision Journal (SM-1.1)
Build a persistent decision log that captures every meaningful interaction: signal dismissed, signal escalated, draft approved, draft modified, draft scrapped, recommendation followed, recommendation ignored. Each entry records: what was presented, what you decided, timestamp, and the entity context (which client, project, etc.). This is the foundation that all other memory features build on.

### Phase 2: Entity Memory & Interaction Timeline (SM-2.1)
Attach a memory layer to every entity (client, project, engagement). When you view a client, you see not just the current health score but a timeline of your decisions about that client: when you last reviewed them, what you decided, what signals have been raised before, what actions you took. This turns every entity page from a data display into an intelligence brief with institutional memory.

### Phase 3: Signal Lifecycle & Stale Suppression (SM-3.1)
Extend the signal_state (Brief 17) and signal_outcomes (Brief 18) tables with user-facing lifecycle states: raised → seen → acted_on → resolved | dismissed | expired. Brief 17/18 track the system side (detection, clearing, outcomes). This phase adds the USER side: when you SAW the signal, when you ACTED on it, what action you took, and whether you want to suppress it. Signals you've already seen and acted on don't re-surface unless the underlying condition materially worsens (e.g., health drops another 15 points). Signals you consistently dismiss for a category get auto-deprioritized. The system stops being noisy and starts being precise.

### Phase 4: Behavioral Pattern Learning & Validation (SM-4.1)
Analyze the decision journal to learn your operational patterns. Which signal types do you always act on? Which do you ignore? When you see a declining client, do you typically call, email, or adjust pricing? Use this to rank and frame future intelligence: "Based on your pattern, you usually respond to this type of signal with a direct call — want me to prepare talking points?" Validate that memory enrichment improves signal relevance.

## Architecture

```
Decision Journal:
  decision_log table
    ├─ id, timestamp, decision_type
    ├─ entity_type, entity_id (what it's about)
    ├─ presented_context (what the system showed you)
    ├─ action_taken (approved/modified/dismissed/escalated/scrapped)
    ├─ user_notes (optional annotation)
    └─ outcome (what happened afterward — filled in retrospectively)

Entity Memory:
  entity_memory table
    ├─ entity_type, entity_id
    ├─ last_reviewed_at
    ├─ last_action_at
    ├─ review_count
    ├─ decision_summary (rolling summary of decisions about this entity)
    └─ linked to decision_log entries

Signal Lifecycle:
  signal_states table (extends existing signals)
    ├─ signal_id, state (raised/seen/acted_on/resolved/dismissed/expired)
    ├─ seen_at, acted_on_at, resolved_at
    ├─ suppressed_until (for stale suppression)
    └─ reactivation_threshold (what change would re-raise it)

Behavioral Patterns:
  decision_patterns (computed, not stored)
    ├─ action_distribution per signal_type
    ├─ avg_response_time per severity
    ├─ dismiss_rate per category
    └─ preferred_action per entity_pattern
```

## Task Files
- `tasks/TASK_SM_1_1_DECISION_JOURNAL.md`
- `tasks/TASK_SM_2_1_ENTITY_MEMORY.md`
- `tasks/TASK_SM_3_1_SIGNAL_LIFECYCLE.md`
- `tasks/TASK_SM_4_1_BEHAVIORAL_PATTERNS_VALIDATION.md`

## Estimated Effort
Large — 4 tasks, ~2,500 lines total. New tables, integration with existing signal/intelligence systems, behavioral analysis.
