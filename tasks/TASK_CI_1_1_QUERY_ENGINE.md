# CI-1.1: Query Engine & Intent Classification

## Objective
Build a query engine that classifies natural language into intent categories and routes each to the appropriate data source or intelligence engine. Handle entity resolution with fuzzy matching. Build the data access layer for safe, parameterized queries across all system tables. No ML dependencies — rule-based classification.

## Implementation

### IntentClassifier (`lib/conversational/intent_classifier.py`)
```python
class IntentClassifier:
    """Rule-based intent classification from natural language queries."""

    INTENT_PATTERNS = {
        'entity_lookup': [
            r'(?:how|what)(?:\'s| is) (?:up with |going on with |happening with )?(.+?)(?:\?|$)',
            r'(?:tell me about|show me|pull up|what about) (.+)',
            r'(?:status of|update on|info on) (.+)',
        ],
        'metric_query': [
            r'(?:what\'?s? (?:my|our|the)) (.+?)(?:\?|$)',
            r'(?:how much|how many) (.+?)(?:\?|$)',
            r'(?:total|current|average) (.+)',
        ],
        'comparison': [
            r'compare (.+?) (?:and|vs|versus|with|to) (.+)',
            r'(?:how does|how do) (.+?) compare (?:to|with|against) (.+)',
            r'(.+?) (?:vs|versus) (.+)',
        ],
        'prediction': [
            r'what (?:if|happens if|would happen if) (.+)',
            r'(?:predict|forecast|project) (.+)',
            r'(?:will|when will|is .+ going to) (.+)',
        ],
        'action_request': [
            r'(?:draft|write|compose|create|send|schedule|prepare) (.+)',
            r'(?:email|message|task|meeting|event) (?:for|to|about|regarding) (.+)',
        ],
        'history_lookup': [
            r'(?:what did I|when did I|last time I) (.+)',
            r'(?:history|decisions|actions) (?:for|on|about|regarding) (.+)',
            r'(?:previous|past|earlier) (.+?) (?:for|on|about) (.+)',
        ],
        'ranked_summary': [
            r'what should I (?:worry about|focus on|prioritize|look at)',
            r'(?:top|biggest|most (?:urgent|important)) (?:concerns|issues|priorities|items)',
            r'(?:what needs|anything need) (?:my )?attention',
        ],
    }

    def classify(self, query: str) -> ClassifiedIntent:
        """
        Classify a natural language query into an intent.
        Returns intent type, extracted entities/parameters, and confidence.
        Falls back to 'ambiguous' if no pattern matches.
        """

    def extract_entities(self, query: str) -> List[EntityReference]:
        """
        Extract entity references from the query.
        Handles: client names, project names, invoice numbers, date references.
        Returns fuzzy-matched candidates with confidence scores.
        """

    def extract_time_range(self, query: str) -> TimeRange | None:
        """
        Extract time references: 'this month', 'last week', 'Q4 2025',
        'since January', 'in the last 30 days'.
        """
```

### EntityResolver (`lib/conversational/entity_resolver.py`)
```python
class EntityResolver:
    """Resolve ambiguous entity references to specific entities."""

    def resolve(self, reference: str, entity_type: str = None) -> List[ResolvedEntity]:
        """
        Fuzzy match a reference to known entities.
        e.g., 'Client X' → client_id 'cli_123' (confidence 0.95)
        e.g., 'the brand project' → project_id 'prj_456' (confidence 0.72)

        Uses: LIKE matching, trigram similarity, alias matching.
        Returns top 3 candidates ranked by confidence.
        If top candidate > 0.85 confidence, auto-select.
        If ambiguous, return candidates for clarification.
        """

    def build_entity_index(self) -> None:
        """
        Build/refresh the in-memory entity index for fast lookup.
        Sources: clients, projects, engagements, team members, invoices.
        Includes aliases and common abbreviations.
        """

    def resolve_pronoun(self, pronoun: str, session_state: 'SessionState') -> ResolvedEntity | None:
        """
        Resolve 'they', 'it', 'them', 'that client', 'their invoice'
        from conversational context.
        """
```

### QueryRouter (`lib/conversational/query_router.py`)
```python
class QueryRouter:
    """Route classified intents to the correct data source."""

    def route(self, intent: ClassifiedIntent) -> QueryResult:
        """
        Route by intent type:
          entity_lookup → DataFetcher (comprehensive entity data)
          metric_query → MetricResolver (aggregation query)
          comparison → ComparisonBuilder (side-by-side)
          prediction → ScenarioEngine (Brief 11)
          action_request → PreparationEngine (Brief 24)
          history_lookup → DecisionJournal (Brief 22)
          ranked_summary → IntelligenceSummarizer (priority ranking)
          ambiguous → ClarificationPrompt
        """

    def build_query_plan(self, intent: ClassifiedIntent) -> QueryPlan:
        """
        For complex queries, plan which data sources to hit.
        e.g., entity_lookup for a client needs:
          - client table (basic info)
          - health engine (health score + trend)
          - revenue data (Xero)
          - project data (Asana)
          - communication data (Gmail/Chat)
          - predictions (Brief 23)
          - memory (Brief 22)
        Returns ordered list of data fetches.
        """
```

### Data Schemas
```python
@dataclass
class ClassifiedIntent:
    intent_type: str          # entity_lookup, metric_query, comparison, etc.
    raw_query: str
    entities: List[EntityReference]
    parameters: dict          # extracted params (metric name, time range, etc.)
    confidence: float
    needs_clarification: bool
    clarification_prompt: str | None

@dataclass
class EntityReference:
    raw_text: str
    entity_type: str | None   # inferred type
    entity_id: str | None     # resolved ID
    confidence: float
    alternatives: List[dict]  # other possible matches

@dataclass
class ResolvedEntity:
    entity_type: str
    entity_id: str
    name: str
    confidence: float

@dataclass
class QueryResult:
    intent: ClassifiedIntent
    data: dict                # structured result data
    sources: List[str]        # which tables/engines contributed
    formatted_response: str   # human-readable answer
    prepared_actions: List[PreparedAction] | None  # if action_request
    clarification_needed: bool
    clarification_options: List[str] | None

@dataclass
class TimeRange:
    start: str               # ISO date
    end: str                 # ISO date
    label: str               # 'this month', 'last 30 days', etc.
```

### Safe Data Access Layer
```python
class ConversationalDataAccess:
    """Safe, parameterized data access for conversational queries."""

    def get_entity_comprehensive(self, entity_type: str, entity_id: str) -> dict:
        """Pull ALL relevant data about an entity from all tables."""

    def get_metric(self, metric_name: str, time_range: TimeRange = None,
                   entity_filter: dict = None) -> dict:
        """Query a specific metric with optional time and entity filters."""

    def get_comparison(self, entity_a: ResolvedEntity, entity_b: ResolvedEntity,
                       metrics: List[str] = None) -> dict:
        """Side-by-side comparison of two entities."""

    # All queries use parameterized SQL via lib/query_engine.py
    # No f-string SQL anywhere in this module
```

### API Endpoints
```
POST /api/v2/query                             (body: {query: "natural language"})
POST /api/v2/query/classify                    (body: {query: "..."} — classification only, no execution)
GET  /api/v2/query/entities/resolve?q=...      (entity resolution)
GET  /api/v2/query/metrics/available           (list queryable metrics)
```

## Validation
- [ ] Intent classification correctly identifies all 7 intent types
- [ ] Fuzzy entity matching resolves partial names (>0.85 confidence auto-selects)
- [ ] Ambiguous entities return candidates for clarification
- [ ] Time range extraction handles natural language dates
- [ ] Pronoun resolution works within conversational context
- [ ] Query routing hits correct data source for each intent type
- [ ] Data access uses only parameterized queries (no f-string SQL)
- [ ] Unknown intents gracefully return clarification prompt, not errors
- [ ] Metric queries handle all existing metrics (revenue, health, utilization, etc.)

## Files Created
- `lib/conversational/intent_classifier.py`
- `lib/conversational/entity_resolver.py`
- `lib/conversational/query_router.py`
- `lib/conversational/data_access.py`
- `api/query_router.py`
- `tests/test_intent_classifier.py`
- `tests/test_entity_resolver.py`

## Estimated Effort
Large — ~900 lines (classifier + resolver + router + data access + tests)
