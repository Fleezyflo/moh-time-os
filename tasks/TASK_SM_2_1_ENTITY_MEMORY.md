# SM-2.1: Entity Memory & Interaction Timeline

## Objective
Attach a memory layer to every entity (client, project, engagement) so when you view any entity, you see not just current data but your full history with it: when you last reviewed it, what decisions you made, what signals have been raised, what actions you took.

## Implementation

### New Table
```sql
CREATE TABLE entity_memory (
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    last_reviewed_at TEXT,           -- last time you viewed this entity's page
    last_action_at TEXT,             -- last time you took an action on this entity
    review_count INTEGER DEFAULT 0,
    action_count INTEGER DEFAULT 0,
    attention_level TEXT DEFAULT 'normal',  -- 'high' | 'normal' | 'low' | 'stale'
    last_signal_at TEXT,             -- last time a signal was raised about this entity
    active_signal_count INTEGER DEFAULT 0,
    summary TEXT,                    -- auto-generated rolling summary
    summary_updated_at TEXT,
    PRIMARY KEY (entity_type, entity_id)
);

CREATE INDEX idx_entity_memory_attention ON entity_memory(attention_level, last_reviewed_at);
CREATE INDEX idx_entity_memory_stale ON entity_memory(last_action_at);
```

### EntityMemoryManager (`lib/memory/entity_memory.py`)
```python
class EntityMemoryManager:
    """Track your interaction history with every entity."""

    def record_view(self, entity_type: str, entity_id: str) -> None:
        """Called when you navigate to an entity page. Updates last_reviewed_at."""

    def record_action(self, entity_type: str, entity_id: str) -> None:
        """Called when you take an action on an entity. Updates last_action_at."""

    def get_memory(self, entity_type: str, entity_id: str) -> EntityMemory:
        """Full memory snapshot for an entity."""

    def get_timeline(self, entity_type: str, entity_id: str, limit: int = 15) -> List[TimelineEntry]:
        """
        Combined timeline for an entity:
          - Your decisions (from decision_journal)
          - Signals raised
          - Predictions generated
          - Key data changes (health score shift, payment received, etc.)
        Sorted chronologically, most recent first.
        """

    def get_stale_entities(self, days_since_review: int = 14) -> List[EntityMemory]:
        """Entities you haven't reviewed in N days that have active signals."""

    def compute_attention_level(self, entity_type: str, entity_id: str) -> str:
        """
        'high' — active signals + recent action (you're on it)
        'normal' — reviewed recently, no urgent signals
        'low' — no signals, reviewed recently
        'stale' — not reviewed in 14+ days OR has signals you haven't seen
        """

    def generate_summary(self, entity_type: str, entity_id: str) -> str:
        """
        Auto-generate a brief summary:
        'Client X: last reviewed 3 days ago. Health declining (58, was 72 two weeks ago).
         You dismissed a health warning on Feb 15. Invoice #1234 is 28 days overdue.
         Last action: approved follow-up email on Feb 18.'
        """
```

### Timeline Entry Schema
```python
@dataclass
class TimelineEntry:
    timestamp: str
    entry_type: str  # 'decision' | 'signal' | 'prediction' | 'data_change' | 'communication'
    title: str       # human-readable summary
    detail: str      # context
    source: str      # where this came from
    entity_type: str
    entity_id: str
```

### UI Integration
```
Client page header addition:
  [Last reviewed: 3 days ago] [Actions: 4 this month] [Attention: ⚡ High]

Entity timeline component:
  Collapsible section showing chronological memory entries
  Each entry: icon + timestamp + summary + expand for detail
```

### API Endpoints
```
GET  /api/v2/memory/entity/:type/:id
GET  /api/v2/memory/entity/:type/:id/timeline?limit=15
GET  /api/v2/memory/stale?days=14
POST /api/v2/memory/entity/:type/:id/view    (record a view)
```

## Validation
- [ ] Page views update last_reviewed_at and review_count
- [ ] Actions update last_action_at and action_count
- [ ] Timeline combines decisions, signals, and data changes
- [ ] Stale detection correctly identifies entities not reviewed in N days
- [ ] Attention level computed correctly from signal state + review recency
- [ ] Summary generation produces readable, accurate text
- [ ] Entities with no memory return sensible defaults (not errors)

## Files Created
- `lib/memory/entity_memory.py`
- `tests/test_entity_memory.py`

## Estimated Effort
Medium — ~600 lines
