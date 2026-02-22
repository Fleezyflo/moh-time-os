# IW-4.1: Event Hook System

## Objective
Build a simple event table that records intelligence findings (signals, patterns, proposals) so that downstream systems can consume them asynchronously. This bridges intelligence (Brief 17) to the preparation engine (Brief 24) without tight coupling.

## Implementation

### New Tables
```sql
CREATE TABLE intelligence_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    -- Valid types: 'signal_new', 'signal_escalated', 'signal_cleared',
    --              'pattern_detected', 'proposal_generated'
    severity TEXT NOT NULL,
    -- 'CRITICAL', 'WARNING', 'INFO'
    entity_type TEXT,
    -- 'client', 'project', 'engagement', null for system-level
    entity_id TEXT,
    event_data TEXT NOT NULL,
    -- JSON object with full event details
    created_at TEXT NOT NULL,
    consumed_at TEXT,
    -- When a consumer read this event
    consumer TEXT
    -- Which system/component consumed it ('preparation_engine', 'notification_system', etc)
);

CREATE INDEX idx_intelligence_events_unconsumed
    ON intelligence_events(event_type, severity)
    WHERE consumed_at IS NULL;

CREATE INDEX idx_intelligence_events_created
    ON intelligence_events(created_at DESC);

CREATE INDEX idx_intelligence_events_entity
    ON intelligence_events(entity_type, entity_id, created_at DESC);

-- Auto-cleanup: events consumed more than 30 days ago
CREATE TABLE intelligence_events_archive (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    event_data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    consumed_at TEXT,
    consumer TEXT,
    archived_at TEXT NOT NULL
);
```

### Event Emitter (`lib/intelligence/events.py`)
```python
import json
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime
from lib.query_engine import QueryEngine

logger = logging.getLogger(__name__)

@dataclass
class IntelligenceEvent:
    id: str
    event_type: str  # 'signal_new', 'signal_escalated', 'signal_cleared', 'pattern_detected', 'proposal_generated'
    severity: str    # 'CRITICAL', 'WARNING', 'INFO'
    entity_type: Optional[str]  # 'client', 'project', 'engagement'
    entity_id: Optional[str]
    event_data: Dict[str, Any]
    created_at: str
    consumed_at: Optional[str] = None
    consumer: Optional[str] = None

class IntelligenceEventEmitter:
    """Emit intelligence events to the events table."""

    def __init__(self, query_engine: QueryEngine):
        self.query_engine = query_engine

    def emit_signal_event(self, event_type: str, signal: Any,
                         severity: str) -> str:
        """
        Emit an event when a signal is generated, escalated, or cleared.
        
        Args:
            event_type: 'signal_new', 'signal_escalated', 'signal_cleared'
            signal: SignalStateRecord or similar
            severity: 'CRITICAL', 'WARNING', 'INFO'
        
        Returns:
            Event ID
        """
        event_data = {
            'signal_key': signal.signal_key,
            'signal_type': signal.signal_type,
            'entity_type': signal.entity_type,
            'entity_id': signal.entity_id,
            'first_detected_at': signal.first_detected_at,
            'last_detected_at': signal.last_detected_at,
            'detection_count': signal.detection_count,
        }
        return self._emit(event_type, severity, signal.entity_type,
                         signal.entity_id, event_data)

    def emit_pattern_event(self, event_type: str, pattern: Any,
                          severity: str) -> str:
        """
        Emit an event when a pattern is detected.
        
        Args:
            event_type: 'pattern_detected'
            pattern: PatternSnapshot or similar
            severity: 'CRITICAL', 'WARNING', 'INFO'
        
        Returns:
            Event ID
        """
        # Extract first entity from pattern.entities_involved
        entities = json.loads(pattern.entities_involved)
        entity_id = entities[0]['entity_id'] if entities else None
        entity_type = entities[0]['entity_type'] if entities else None
        
        event_data = {
            'pattern_id': pattern.pattern_id,
            'pattern_name': pattern.pattern_name,
            'entities_involved': entities,
            'evidence': json.loads(pattern.evidence),
            'detected_at': pattern.detected_at,
            'cycle_id': pattern.cycle_id,
        }
        return self._emit(event_type, severity, entity_type, entity_id, event_data)

    def emit_proposal_events(self, proposals: list) -> list[str]:
        """
        Emit events for generated proposals.
        
        Args:
            proposals: List of proposal objects
        
        Returns:
            List of event IDs
        """
        event_ids = []
        for proposal in proposals:
            event_data = {
                'proposal_id': proposal.id,
                'proposal_type': proposal.type,
                'entity_type': proposal.entity_type,
                'entity_id': proposal.entity_id,
                'recommendation': proposal.recommendation,
                'confidence': proposal.confidence,
            }
            event_id = self._emit(
                'proposal_generated',
                'INFO',  # Proposals always INFO severity
                proposal.entity_type,
                proposal.entity_id,
                event_data
            )
            event_ids.append(event_id)
        return event_ids

    def _emit(self, event_type: str, severity: str,
             entity_type: Optional[str], entity_id: Optional[str],
             event_data: Dict[str, Any]) -> str:
        """
        Internal method to persist an event to the database.
        
        Args:
            event_type: Type of event
            severity: Severity level
            entity_type: Type of entity affected
            entity_id: ID of entity affected
            event_data: Event details as dict
        
        Returns:
            Generated event ID
        """
        from lib.uuid_generator import generate_id
        
        event_id = generate_id('evt')
        now = datetime.utcnow().isoformat()
        event_data_json = json.dumps(event_data)
        
        query = """
        INSERT INTO intelligence_events
        (id, event_type, severity, entity_type, entity_id, event_data, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        try:
            self.query_engine.execute(query, [
                event_id, event_type, severity, entity_type, entity_id,
                event_data_json, now
            ])
            logger.info(f"Emitted {event_type} event {event_id}")
            return event_id
        except Exception as e:
            logger.error(f"Failed to emit {event_type} event: {e}")
            raise

class IntelligenceEventConsumer:
    """Consume intelligence events from the events table."""

    def __init__(self, query_engine: QueryEngine):
        self.query_engine = query_engine

    def get_unconsumed_events(self, event_type: str = None,
                             severity: str = None) -> list[IntelligenceEvent]:
        """
        Retrieve unconsumed events, optionally filtered by type/severity.
        
        Args:
            event_type: Optional filter by event type
            severity: Optional filter by severity
        
        Returns:
            List of unconsumed IntelligenceEvent objects
        """
        query = "SELECT * FROM intelligence_events WHERE consumed_at IS NULL"
        params = []
        
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        
        query += " ORDER BY created_at DESC"
        
        rows = self.query_engine.fetch_all(query, params)
        events = []
        for row in rows:
            event = IntelligenceEvent(
                id=row['id'],
                event_type=row['event_type'],
                severity=row['severity'],
                entity_type=row['entity_type'],
                entity_id=row['entity_id'],
                event_data=json.loads(row['event_data']),
                created_at=row['created_at'],
                consumed_at=row['consumed_at'],
                consumer=row['consumer']
            )
            events.append(event)
        return events

    def mark_consumed(self, event_id: str, consumer: str) -> None:
        """
        Mark an event as consumed by a specific system.
        
        Args:
            event_id: ID of event to mark
            consumer: Name of consuming system (e.g., 'preparation_engine')
        """
        now = datetime.utcnow().isoformat()
        query = """
        UPDATE intelligence_events
        SET consumed_at = ?, consumer = ?
        WHERE id = ?
        """
        try:
            self.query_engine.execute(query, [now, consumer, event_id])
            logger.debug(f"Marked event {event_id} as consumed by {consumer}")
        except Exception as e:
            logger.error(f"Failed to mark event {event_id} as consumed: {e}")
            raise

    def archive_old_events(self, days: int = 30) -> int:
        """
        Archive events consumed more than N days ago.
        Returns count of archived events.
        
        Args:
            days: Number of days to keep consumed events
        
        Returns:
            Number of archived events
        """
        from datetime import timedelta
        cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
        
        # Move to archive
        query = """
        INSERT INTO intelligence_events_archive
        SELECT *, ? as archived_at FROM intelligence_events
        WHERE consumed_at IS NOT NULL AND consumed_at < ?
        """
        self.query_engine.execute(query, [datetime.utcnow().isoformat(), cutoff_date])
        
        # Delete from main table
        delete_query = """
        DELETE FROM intelligence_events
        WHERE consumed_at IS NOT NULL AND consumed_at < ?
        """
        self.query_engine.execute(delete_query, [cutoff_date])
        
        logger.info(f"Archived consumed events from before {cutoff_date}")
        return self.query_engine.row_count()
```

### Usage Example
```python
# In daemon intelligence_phase()
emitter = IntelligenceEventEmitter(query_engine)
emitter.emit_signal_event('signal_new', signal, 'CRITICAL')

# In Brief 24 preparation engine
consumer = IntelligenceEventConsumer(query_engine)
events = consumer.get_unconsumed_events(event_type='signal_new', severity='CRITICAL')
for event in events:
    # Process event
    prepare_action_for_signal(event)
    # Mark consumed
    consumer.mark_consumed(event.id, 'preparation_engine')

# Periodic cleanup (run nightly)
consumer.archive_old_events(days=30)
```

### Migration File
Add to `migrations/v31_intelligence_wiring.sql`:
```sql
CREATE TABLE intelligence_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    event_data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    consumed_at TEXT,
    consumer TEXT
);

CREATE INDEX idx_intelligence_events_unconsumed
    ON intelligence_events(event_type, severity)
    WHERE consumed_at IS NULL;

CREATE INDEX idx_intelligence_events_created
    ON intelligence_events(created_at DESC);

CREATE INDEX idx_intelligence_events_entity
    ON intelligence_events(entity_type, entity_id, created_at DESC);

CREATE TABLE intelligence_events_archive (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    event_data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    consumed_at TEXT,
    consumer TEXT,
    archived_at TEXT NOT NULL
);
```

## Validation
- [ ] intelligence_events table created with indexes
- [ ] intelligence_events_archive table created
- [ ] IntelligenceEventEmitter emits events to database
- [ ] Emitted events have correct event_type, severity, entity_type, entity_id
- [ ] IntelligenceEventConsumer retrieves unconsumed events
- [ ] mark_consumed() sets consumed_at and consumer
- [ ] get_unconsumed_events() filters by event_type and severity
- [ ] archive_old_events() moves events consumed >30 days ago to archive table
- [ ] Events don't accumulate indefinitely (cleanup runs)
- [ ] Event data is valid JSON
- [ ] All queries parameterized (no f-strings)

## Files Created
- `lib/intelligence/events.py`

## Files Modified
- `lib/daemon.py` — use IntelligenceEventEmitter in intelligence_phase()

## Estimated Effort
Small — ~150 lines
