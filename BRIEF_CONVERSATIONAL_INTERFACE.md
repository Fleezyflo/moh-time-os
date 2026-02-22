# Brief 25: Conversational Interface

## Status: DESIGNED
## Priority: P2 — Natural interaction layer on top of all intelligence
## Dependencies: Brief 18 (Intelligence Depth — entity profiles, narratives, cross-domain synthesis), Brief 22 (Strategic Memory — decision history), Brief 24 (Prepared Intelligence — action routing), Brief 23 (Predictive Foresight — scenario queries)

## What Brief 18 Provides

Brief 18's `EntityIntelligenceProfile` is the primary data source for conversational responses. When you ask "How's Client X doing?", the conversational interface doesn't need to query scorecard, signals, patterns, trajectory, cost-to-serve, and correlations separately — it reads the entity profile which already synthesizes all of these into a structured object with a human-readable narrative. The profile's `narrative` field is the starting point for the answer; the `attention_level`, `recommended_actions`, and dimension breakdowns provide the detail.

Without Brief 18, this interface would need to re-implement cross-domain synthesis inside the query engine — duplicating work and producing inconsistent answers compared to entity pages.

## Problem Statement

All system intelligence is accessed by navigating pages. To understand a client's full picture, you visit the client page. To check cash flow, you visit the cash view. To see predictions, you visit the prediction view. This works, but it forces you to know where to look. The most powerful use of this system would be to just ask it a question and get an answer that draws from everything it knows — all 107 tables, all intelligence engines, all predictions, all memory.

"How's Client X doing?" should return a synthesized answer pulling from health score, revenue trajectory, recent communications, outstanding invoices, project status, and your interaction history with that client. "What should I worry about this week?" should combine predictive foresight, current signals, and stale follow-ups into a ranked answer. "Draft a follow-up to Client Y about the overdue invoice" should produce a context-rich email draft that flows into the preparation engine.

This is the layer where you talk to your business.

## Success Criteria

- Natural language queries answered by synthesizing data across all domains
- Questions about clients, projects, cash, capacity, calendar return comprehensive answers with sources cited
- Comparative queries: "Compare Client X and Client Y" or "How does this month compare to last"
- Predictive queries: "What happens if Client X leaves?" routed to scenario engine
- Action requests: "Draft an email to Client X" creates a prepared action (Brief 24)
- Contextual awareness: conversation maintains context ("What about their invoices?" after asking about a client)
- History queries: "What did I decide about Client X last time this happened?" pulls from decision journal (Brief 22)
- Response format: concise answers with data points, not raw table dumps

## Scope

### Phase 1: Query Engine & Intent Classification (CI-1.1)
Build a query engine that classifies natural language into intent categories: entity_lookup (client/project/invoice), metric_query (revenue/utilization/health), comparison, prediction, action_request, history_lookup. Route each intent to the appropriate data source or intelligence engine. Build the data access layer that can query across all 107 tables with parameterized, safe queries. Handle ambiguity: "Client X" should fuzzy-match to the right client even with partial names.

### Phase 2: Cross-Domain Synthesis (CI-2.1)
Build the synthesis layer that combines data from multiple domains into coherent answers. A query about a client should pull from: client health engine, revenue data (Xero), project status (Asana), communication frequency (Gmail/Chat/Calendar), predictions (Brief 23), and interaction history (Brief 22). Format responses as structured intelligence — not raw numbers, but interpreted context: "Client X: revenue is strong at 340K YTD, but engagement is declining — meeting frequency down 40% over 6 weeks and their last 3 emails were notably shorter than usual."

### Phase 3: Action Routing & Conversational Context (CI-3.1)
Wire action requests into the preparation engine (Brief 24). "Draft a follow-up to Client X" creates a prepared email draft. "Create a task for the brand guidelines delivery" creates a prepared Asana task. "Schedule a review meeting with Client Y next week" creates a prepared calendar event. Build conversational context: maintain state within a session so follow-up questions reference the current subject without re-specifying.

### Phase 4: Conversational UI & Validation (CI-4.1)
Build the chat interface within the React SPA. Input bar with natural language, response area showing formatted answers with source citations. Prepared actions from conversational requests appear as inline cards (approve/edit/dismiss). Validate: test 20+ query types across all domains, verify synthesis accuracy against raw data, verify action routing produces correct prepared actions.

## Architecture

```
Conversational Pipeline:
  User Input → Intent Classifier
    ├─ entity_lookup → EntityResolver → DataFetcher → Synthesizer → Response
    ├─ metric_query → MetricResolver → DataFetcher → Synthesizer → Response
    ├─ comparison → ComparisonBuilder → DataFetcher → Synthesizer → Response
    ├─ prediction → ScenarioEngine (Brief 11) → Synthesizer → Response
    ├─ action_request → PreparationEngine (Brief 24) → ActionCard → Response
    ├─ history_lookup → DecisionJournal (Brief 22) → Synthesizer → Response
    └─ ambiguous → Clarification prompt

Intent Classification:
  Rule-based + keyword matching (no ML dependency):
    ├─ "how is [entity]" → entity_lookup
    ├─ "what's my [metric]" → metric_query
    ├─ "compare [A] and [B]" → comparison
    ├─ "what if [scenario]" → prediction
    ├─ "draft/create/schedule [action]" → action_request
    ├─ "what did I [decide/do] about [entity]" → history_lookup
    └─ "what should I [worry about/focus on]" → ranked intelligence summary

Cross-Domain Synthesis:
  Synthesizer
    ├─ collect relevant data points from multiple sources
    ├─ weight by recency and relevance
    ├─ format as structured prose (not tables)
    ├─ attach source references (which table/engine produced each data point)
    └─ include actionable suggestions where appropriate

Conversational Context:
  SessionState (in-memory per session)
    ├─ current_entity (the thing being discussed)
    ├─ query_history (last N queries for context)
    └─ pending_actions (prepared actions from this conversation)
```

## Task Files
- `tasks/TASK_CI_1_1_QUERY_ENGINE.md`
- `tasks/TASK_CI_2_1_CROSS_DOMAIN_SYNTHESIS.md`
- `tasks/TASK_CI_3_1_ACTION_ROUTING_CONTEXT.md`
- `tasks/TASK_CI_4_1_CONVERSATIONAL_UI_VALIDATION.md`

## Estimated Effort
Very Large — 4 tasks, ~3,500 lines total. Query engine, synthesis layer, action routing, conversational UI, comprehensive validation.
