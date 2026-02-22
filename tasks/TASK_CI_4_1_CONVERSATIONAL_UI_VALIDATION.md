# CI-4.1: Conversational UI & Validation

## Objective
Build the chat interface within the React SPA. Input bar with natural language, response area showing formatted answers with source citations. Prepared actions from conversational requests appear as inline cards. Validate the entire conversational pipeline: 20+ query types across all domains, synthesis accuracy, action routing correctness.

## Implementation

### Chat Interface Components
```typescript
// ConversationalView.tsx — main chat page
// Layout:
//   Chat history area (scrollable)
//   Input bar (fixed bottom)
//   Optional: entity context sidebar (shows current entity being discussed)

interface ConversationalViewProps {
  sessionId: string;
}

// Components:
//   ChatInput — text input + send button + keyboard shortcuts (Enter to send)
//   ChatMessage — user message or system response
//   ResponseCard — formatted system response with:
//     - Headline
//     - Summary text
//     - Data points (collapsible detail)
//     - Source badges (which engines/tables contributed)
//     - Action cards (if response includes prepared actions)
//   ActionCard — inline prepared action:
//     - Type icon (email/task/event/message)
//     - Preview of draft content
//     - Approve / Edit / Dismiss buttons
//   ClarificationPrompt — when query is ambiguous:
//     - "Did you mean Client X or Client X2?"
//     - Clickable options
//   ContextIndicator — shows current entity in context:
//     - "Discussing: Client X" (dismissable)
```

### Chat Input Features
```typescript
// Quick-access shortcuts in the input:
//   "/" prefix for common actions:
//     /email [client] — start drafting
//     /task [description] — create task
//     /meeting [client] — schedule meeting
//     /brief — show daily briefing
//     /priorities — what should I worry about
//
// Autocomplete for entity names:
//   Typing "Client" → dropdown of matching clients
//   Typing a project name → dropdown of matching projects
//
// Recent queries accessible via up-arrow key

interface ChatInputProps {
  onSubmit: (query: string) => void;
  onEntityAutocomplete: (partial: string) => Promise<EntitySuggestion[]>;
  recentQueries: string[];
}
```

### Response Rendering
```typescript
// Different response formats based on intent type:
//
// entity_lookup → EntityResponseCard
//   Health badge + key metrics + trend arrows + open items
//
// metric_query → MetricResponseCard
//   Large number + trend + comparison context
//
// comparison → ComparisonResponseCard
//   Two columns with vs. indicators
//
// prediction → PredictionResponseCard
//   Scenario description + probability + timeline
//
// action_request → ActionResponseCard
//   Draft preview + approve/edit/dismiss + entity context
//
// history_lookup → HistoryResponseCard
//   Timeline of past decisions with outcomes
//
// ranked_summary → PriorityResponseCard
//   Numbered list with severity badges

interface ResponseCardProps {
  response: FormattedResponse;
  onActionApprove: (actionId: string) => void;
  onActionEdit: (actionId: string) => void;
  onActionDismiss: (actionId: string) => void;
  onEntityClick: (entityType: string, entityId: string) => void;
  onSourceClick: (source: string) => void;
}
```

### Validation Suite
```python
class ConversationalInterfaceValidation:
    """Comprehensive validation of the entire conversational pipeline."""

    # --- Intent Classification (20+ query types) ---

    def test_entity_lookup_by_name(self):
        """'How is Client X doing?' → entity_lookup for Client X."""

    def test_entity_lookup_informal(self):
        """'What's up with the Acme project?' → entity_lookup for project."""

    def test_entity_lookup_status(self):
        """'Status of engagement 45?' → entity_lookup for engagement."""

    def test_metric_query_revenue(self):
        """'What's my revenue this month?' → metric_query for revenue."""

    def test_metric_query_utilization(self):
        """'How's utilization looking?' → metric_query for utilization."""

    def test_metric_query_ar(self):
        """'How much is outstanding?' → metric_query for AR."""

    def test_comparison_clients(self):
        """'Compare Client X and Client Y' → comparison."""

    def test_comparison_periods(self):
        """'How does this month compare to last?' → comparison."""

    def test_prediction_whatif(self):
        """'What if Client X leaves?' → prediction via scenario engine."""

    def test_prediction_deadline(self):
        """'Will the brand project finish on time?' → prediction."""

    def test_action_email(self):
        """'Draft a follow-up to Client X' → email_draft prepared action."""

    def test_action_task(self):
        """'Create a task for the delivery milestone' → asana_task prepared."""

    def test_action_meeting(self):
        """'Schedule a review with Client Y next week' → calendar_event."""

    def test_action_message(self):
        """'Message the team about the delay' → chat_message."""

    def test_history_decision(self):
        """'What did I decide about Client X last time?' → history_lookup."""

    def test_history_actions(self):
        """'What actions have I taken on this project?' → history_lookup."""

    def test_ranked_priorities(self):
        """'What should I worry about this week?' → ranked_summary."""

    def test_ranked_urgent(self):
        """'What needs my attention?' → ranked_summary."""

    # --- Contextual Resolution ---

    def test_pronoun_resolution(self):
        """After asking about Client X: 'What about their invoices?' → Client X invoices."""

    def test_continuation_query(self):
        """After asking about Client X: 'And their projects?' → Client X projects."""

    def test_entity_switch(self):
        """After Client X: 'How about Client Y?' → switches context."""

    def test_action_after_lookup(self):
        """After asking about Client X: 'Draft them an email' → email to Client X."""

    # --- Synthesis Accuracy ---

    def test_entity_synthesis_complete(self):
        """Entity response includes data from all relevant sources."""

    def test_metric_synthesis_has_context(self):
        """Metric response includes trend and comparison, not just raw number."""

    def test_comparison_highlights_differences(self):
        """Comparison response correctly identifies which entity is better per metric."""

    def test_ranked_ordering_correct(self):
        """Priority ranking matches actual severity × recency × impact."""

    # --- Action Routing ---

    def test_email_action_creates_prepared_action(self):
        """'Draft email to X' → PreparedAction in staging with correct content."""

    def test_task_action_uses_asana_intelligence(self):
        """'Create task for Y' → routes through AsanaIntelligence."""

    def test_approve_via_conversation(self):
        """'Send it' after preparing → dispatches via correct writer."""

    # --- Edge Cases ---

    def test_ambiguous_entity(self):
        """Query with multiple matching entities → clarification prompt."""

    def test_unknown_entity(self):
        """Query about non-existent entity → helpful error, not crash."""

    def test_empty_query(self):
        """Empty or meaningless query → graceful response."""

    def test_complex_multi_part_query(self):
        """'How is Client X and what about their invoices?' → handles both."""

    def test_no_data_available(self):
        """Query about entity with minimal data → partial response with noted gaps."""
```

### API Endpoints
```
POST /api/v2/chat                        (body: {query, session_id})
GET  /api/v2/chat/suggestions            (autocomplete suggestions)
GET  /api/v2/chat/session/:id            (session history)
DELETE /api/v2/chat/session/:id          (clear session)
```

## Validation
- [ ] All 20+ query types correctly classified and routed
- [ ] Entity autocomplete returns relevant suggestions within 200ms
- [ ] Conversational context maintained across 5+ query exchanges
- [ ] Prepared actions from conversation appear as inline actionable cards
- [ ] Approve/Edit/Dismiss on action cards works correctly
- [ ] Source citations link to correct data origins
- [ ] Clarification prompts offer correct disambiguation options
- [ ] Response rendering handles all 7 response types correctly
- [ ] Chat history scrollable and searchable
- [ ] Session cleanup prevents unbounded memory growth
- [ ] Performance: query → response in under 2 seconds for standard queries
- [ ] Synthesis accuracy: spot-check 10 entity responses against raw data

## Files Created
- `time-os-ui/src/pages/conversation/ConversationalView.tsx`
- `time-os-ui/src/pages/conversation/components/ChatInput.tsx`
- `time-os-ui/src/pages/conversation/components/ResponseCard.tsx`
- `time-os-ui/src/pages/conversation/components/ActionCard.tsx`
- `time-os-ui/src/pages/conversation/components/ClarificationPrompt.tsx`
- `api/chat_router.py`
- `tests/test_conversational_e2e.py`

## Estimated Effort
Very Large — ~1,000 lines (UI components + API + comprehensive validation suite)
