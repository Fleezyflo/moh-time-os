# CI-3.1: Action Routing & Conversational Context

## Objective
Wire conversational action requests into the preparation engine (Brief 24). "Draft a follow-up to Client X" creates a prepared email draft. "Create a task for brand guidelines delivery" creates a prepared Asana task. Build conversational context so follow-up questions reference the current subject without re-specifying.

## Implementation

### ActionRouter (`lib/conversational/action_router.py`)
```python
class ActionRouter:
    """Route conversational action requests to the preparation engine."""

    def route_action(self, intent: 'ClassifiedIntent',
                     session_state: 'SessionState') -> ActionRoutingResult:
        """
        Parse an action request and create a prepared action via Brief 24.
        Examples:
          "Draft a follow-up to Client X" →
            CommunicationDrafter.draft_email(client, 'warm_followup')
          "Create a task for the brand guidelines delivery" →
            AsanaIntelligence.prepare_task_creation(project, 'deliverable_task')
          "Schedule a review meeting with Client Y next week" →
            CommunicationDrafter.draft_calendar_event(client, 'review_meeting')
          "Message the team about the deadline change" →
            CommunicationDrafter.draft_chat_message(project, 'quick_update')
        """

    def parse_action_details(self, query: str, intent: 'ClassifiedIntent') -> ActionDetails:
        """
        Extract from the query:
          - action_type: email | task | meeting | message
          - target_entity: who/what it's about
          - intent/purpose: follow-up, reminder, status update, etc.
          - specific_instructions: any additional detail from the query
          - time_reference: 'next week', 'tomorrow', 'by Friday'
        """

    def confirm_action(self, details: ActionDetails,
                       session_state: 'SessionState') -> str:
        """
        Generate a confirmation prompt:
        "I'll draft a follow-up email to Client X about the overdue invoice.
         The email will reference their outstanding balance of 15,200 AED
         and their health score trend. Ready to prepare it?"
        """
```

### SessionState (`lib/conversational/session_state.py`)
```python
class SessionState:
    """Maintain conversational context within a session."""

    def __init__(self):
        self.session_id: str = generate_id()
        self.started_at: str = now_iso()
        self.current_entity: ResolvedEntity | None = None
        self.query_history: List[QueryHistoryEntry] = []
        self.pending_actions: List[PreparedAction] = []
        self.context_stack: List[ContextFrame] = []

    def update_context(self, intent: 'ClassifiedIntent', result: 'QueryResult') -> None:
        """
        After each query, update the session context.
        Sets current_entity if a specific entity was discussed.
        Pushes to query history for reference resolution.
        """

    def resolve_reference(self, reference: str) -> ResolvedEntity | None:
        """
        Resolve contextual references:
          "their invoices" → current_entity's invoices
          "that project" → last mentioned project
          "what about the email?" → last prepared email action
          "and Client Y?" → switch context to Client Y, repeat last query type
        """

    def get_conversation_context(self) -> dict:
        """
        Return context needed for informed responses:
          - current entity being discussed
          - last N queries and results (summaries)
          - pending actions from this conversation
        """

    def clear(self) -> None:
        """Reset session state for a new conversation."""
```

### Context Resolution
```python
class ContextResolver:
    """Resolve ambiguous references using conversational context."""

    REFERENCE_PATTERNS = {
        'pronoun': ['they', 'them', 'their', 'it', 'its', 'that', 'this'],
        'relative': ['the same', 'that client', 'that project', 'the invoice',
                     'the email', 'the task', 'the meeting'],
        'continuation': ['what about', 'and', 'also', 'how about', 'same for'],
        'action_reference': ['send it', 'approve it', 'dismiss it', 'edit that',
                            'the draft', 'that email'],
    }

    def resolve(self, query: str, session_state: SessionState) -> ResolvedQuery:
        """
        Rewrite query with resolved references:
          Original: "What about their invoices?"
          Context: current_entity = Client X
          Resolved: "What about Client X's invoices?"
            intent_type: entity_lookup
            entity: Client X
            focus: invoices
        """

    def detect_continuation(self, query: str) -> bool:
        """Is this query a continuation of the previous one?"""

    def detect_entity_switch(self, query: str, session_state: SessionState) -> str | None:
        """Is this query switching to a different entity? Return new entity reference."""
```

### Data Schemas
```python
@dataclass
class ActionDetails:
    action_type: str           # 'email' | 'task' | 'meeting' | 'message'
    target_entity: EntityReference
    intent: str                # 'follow_up' | 'reminder' | 'status_update' | 'custom'
    specific_instructions: str | None
    time_reference: str | None # 'next week', 'by Friday'
    urgency: str               # 'normal' | 'urgent'

@dataclass
class ActionRoutingResult:
    success: bool
    prepared_action: PreparedAction | None
    confirmation_message: str
    error: str | None

@dataclass
class QueryHistoryEntry:
    timestamp: str
    raw_query: str
    intent_type: str
    entity_discussed: ResolvedEntity | None
    result_summary: str        # brief summary of the answer

@dataclass
class ContextFrame:
    entity: ResolvedEntity | None
    topic: str                 # 'invoices' | 'projects' | 'health' | etc.
    timestamp: str

@dataclass
class ResolvedQuery:
    original: str
    resolved: str              # query with references resolved
    context_used: List[str]    # which context elements were used
```

### Session Storage
```sql
CREATE TABLE conversation_sessions (
    session_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    last_active_at TEXT NOT NULL,
    query_count INTEGER DEFAULT 0,
    actions_prepared INTEGER DEFAULT 0,
    actions_dispatched INTEGER DEFAULT 0,
    context_snapshot TEXT          -- JSON: last entity, topic, etc.
);

CREATE INDEX idx_conversation_sessions_active ON conversation_sessions(last_active_at DESC);
```

### API Endpoints
```
POST /api/v2/conversation/query      (body: {query, session_id})
POST /api/v2/conversation/action     (body: {action_details, session_id})
GET  /api/v2/conversation/context    (current session context)
POST /api/v2/conversation/reset      (clear session state)
GET  /api/v2/conversation/history    (session history for reference)
```

## Validation
- [ ] Action routing creates correct prepared action type for each request
- [ ] "Draft email to X" → email_draft prepared action with correct entity
- [ ] "Create task for Y" → asana_task prepared action with correct project
- [ ] "Schedule meeting with Z" → calendar_event prepared action
- [ ] Conversational context maintained across queries within session
- [ ] Pronoun resolution correctly references current entity
- [ ] "What about their invoices?" after Client X query → Client X invoices
- [ ] Entity switch detected: "And Client Y?" → switches context
- [ ] Action references work: "Send it" after drafting → dispatches prepared action
- [ ] Session state persists across API calls via session_id
- [ ] Stale sessions cleaned up (no unbounded growth)

## Files Created
- `lib/conversational/action_router.py`
- `lib/conversational/session_state.py`
- `lib/conversational/context_resolver.py`
- `tests/test_action_router.py`
- `tests/test_session_state.py`
- `tests/test_context_resolver.py`

## Estimated Effort
Large — ~800 lines (action routing + session state + context resolution + tests)
