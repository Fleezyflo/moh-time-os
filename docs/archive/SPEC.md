# MOH TIME OS — COMPLETE SYSTEM SPECIFICATION

**Version:** 2.0 — Wired System Architecture  
**Standard:** Elite, Zero Exceptions  
**Core Principle:** User-facilitated autonomous intelligence, not chatbot dependency

---

## PART I: SYSTEM PHILOSOPHY

### What This System IS

A **personal operating system** that:
- Runs autonomously 24/7 without human prompting
- Provides direct user interfaces for all interactions
- Wires all components into a unified intelligence layer
- Removes the AI from the critical path of user workflows
- Learns, adapts, and improves through continuous operation

### What This System IS NOT

- A chatbot you have to ask things
- Disconnected tools that require manual coordination
- Components that exist but don't talk to each other
- A system that waits for instructions
- Anything that requires "checking in" with an AI

### The Bottleneck Problem (What We're Solving)

**Current State (Broken):**
```
User → Ask AI → AI checks tools → AI synthesizes → AI responds → User acts
```
Every action requires AI mediation. AI is bottleneck. System is reactive.

**Target State (Correct):**
```
┌─────────────────────────────────────────────────────────────────┐
│                     MOH TIME OS                                  │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │ Collector│───▶│ Analyzer │───▶│ Reasoner │───▶│ Executor │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│       │               │               │               │         │
│       ▼               ▼               ▼               ▼         │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    STATE STORE                              ││
│  │  (Single source of truth for all system knowledge)          ││
│  └─────────────────────────────────────────────────────────────┘│
│       │               │               │               │         │
│       ▼               ▼               ▼               ▼         │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    USER INTERFACE                           ││
│  │  Dashboard │ CLI │ Notifications │ Voice │ Mobile           ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
         │                                              │
         ▼                                              ▼
    Data Sources                                   User Actions
    (Asana, Gmail,                                (Direct control,
     Calendar, etc.)                               no AI needed)
```

User interacts with system directly. AI is background intelligence, not gatekeeper.

---

## PART II: SYSTEM COMPONENTS (WIRED)

### 1. DATA LAYER — The Foundation

#### 1.1 State Store (SQLite + JSON)

**Location:** `data/state.db` + `data/cache/`

**Tables:**
```sql
-- Core entities
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,              -- 'asana', 'calendar', 'email', 'manual'
    source_id TEXT,                    -- ID in source system
    title TEXT NOT NULL,
    status TEXT NOT NULL,              -- 'pending', 'in_progress', 'blocked', 'done'
    priority INTEGER DEFAULT 50,       -- 0-100, computed
    due_date TEXT,
    due_time TEXT,
    assignee TEXT,
    project TEXT,
    tags TEXT,                         -- JSON array
    dependencies TEXT,                 -- JSON array of task IDs
    blockers TEXT,                     -- JSON array of blocker descriptions
    context TEXT,                      -- JSON metadata
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    synced_at TEXT                     -- Last sync with source
);

CREATE TABLE events (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_id TEXT,
    title TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT,
    location TEXT,
    attendees TEXT,                    -- JSON array
    status TEXT,                       -- 'confirmed', 'tentative', 'cancelled'
    prep_required TEXT,                -- JSON: what needs to happen before
    context TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE communications (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,              -- 'email', 'slack', 'whatsapp'
    source_id TEXT,
    thread_id TEXT,
    from_address TEXT,
    to_addresses TEXT,                 -- JSON array
    subject TEXT,
    snippet TEXT,
    priority INTEGER,                  -- Computed: 0-100
    requires_response BOOLEAN,
    response_deadline TEXT,
    sentiment TEXT,                    -- 'urgent', 'normal', 'fyi'
    labels TEXT,                       -- JSON array
    processed BOOLEAN DEFAULT FALSE,
    created_at TEXT NOT NULL
);

CREATE TABLE people (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    company TEXT,
    role TEXT,
    relationship TEXT,                 -- 'client', 'team', 'vendor', 'personal'
    importance INTEGER DEFAULT 50,     -- 0-100
    last_contact TEXT,
    contact_frequency_days INTEGER,
    notes TEXT,
    context TEXT                       -- JSON
);

CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    source TEXT,
    source_id TEXT,
    name TEXT NOT NULL,
    status TEXT,                       -- 'active', 'on_hold', 'completed'
    health TEXT,                       -- 'green', 'yellow', 'red'
    owner TEXT,
    deadline TEXT,
    tasks_total INTEGER,
    tasks_done INTEGER,
    blockers TEXT,                     -- JSON array
    next_milestone TEXT,
    context TEXT
);

-- Intelligence layer
CREATE TABLE insights (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,                -- 'pattern', 'anomaly', 'prediction', 'recommendation'
    domain TEXT NOT NULL,              -- 'tasks', 'time', 'communication', 'projects'
    title TEXT NOT NULL,
    description TEXT,
    confidence REAL,                   -- 0-1
    data TEXT,                         -- JSON supporting data
    actionable BOOLEAN,
    action_taken BOOLEAN DEFAULT FALSE,
    created_at TEXT NOT NULL,
    expires_at TEXT
);

CREATE TABLE decisions (
    id TEXT PRIMARY KEY,
    domain TEXT NOT NULL,
    decision_type TEXT NOT NULL,       -- 'prioritization', 'scheduling', 'delegation', 'escalation'
    input_data TEXT,                   -- JSON: what triggered decision
    options TEXT,                      -- JSON: options considered
    selected_option TEXT,
    rationale TEXT,
    confidence REAL,
    requires_approval BOOLEAN,
    approved BOOLEAN,
    executed BOOLEAN DEFAULT FALSE,
    outcome TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE notifications (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,                -- 'alert', 'reminder', 'insight', 'decision'
    priority TEXT NOT NULL,            -- 'critical', 'high', 'normal', 'low'
    title TEXT NOT NULL,
    body TEXT,
    action_url TEXT,                   -- Deep link into UI
    action_data TEXT,                  -- JSON for programmatic action
    channels TEXT,                     -- JSON: ['push', 'sms', 'email']
    sent_at TEXT,
    read_at TEXT,
    acted_on_at TEXT,
    created_at TEXT NOT NULL
);

-- Execution layer
CREATE TABLE actions (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,                -- 'task_create', 'task_update', 'email_send', 'calendar_create'
    target_system TEXT,                -- 'asana', 'gmail', 'calendar'
    payload TEXT NOT NULL,             -- JSON
    status TEXT DEFAULT 'pending',     -- 'pending', 'approved', 'executing', 'done', 'failed'
    requires_approval BOOLEAN,
    approved_by TEXT,
    approved_at TEXT,
    executed_at TEXT,
    result TEXT,                       -- JSON
    error TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

-- Learning layer
CREATE TABLE feedback (
    id TEXT PRIMARY KEY,
    decision_id TEXT,
    insight_id TEXT,
    action_id TEXT,
    feedback_type TEXT,                -- 'positive', 'negative', 'correction'
    details TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE patterns (
    id TEXT PRIMARY KEY,
    domain TEXT NOT NULL,
    pattern_type TEXT NOT NULL,
    description TEXT,
    data TEXT,                         -- JSON pattern definition
    confidence REAL,
    occurrences INTEGER,
    last_seen TEXT,
    created_at TEXT NOT NULL
);

-- Indexes
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_due ON tasks(due_date);
CREATE INDEX idx_tasks_priority ON tasks(priority DESC);
CREATE INDEX idx_events_start ON events(start_time);
CREATE INDEX idx_communications_priority ON communications(priority DESC);
CREATE INDEX idx_notifications_created ON notifications(created_at DESC);
CREATE INDEX idx_actions_status ON actions(status);
```

#### 1.2 Cache Layer

**Location:** `data/cache/`

```
data/cache/
├── api_responses/           # Raw API responses (TTL: varies by source)
│   ├── asana/
│   ├── gmail/
│   ├── calendar/
│   └── apollo/
├── computed/                # Processed/aggregated data (TTL: 5min-1hr)
│   ├── daily_summary.json
│   ├── priority_queue.json
│   ├── time_blocks.json
│   └── project_health.json
└── embeddings/              # Vector embeddings for semantic search
    ├── tasks.db
    └── communications.db
```

#### 1.3 Configuration

**Location:** `config/`

```yaml
# config/sources.yaml
sources:
  asana:
    enabled: true
    sync_interval: 300  # seconds
    workspaces:
      - id: "workspace_id"
        projects:
          - id: "project_id"
            name: "HRMNY Operations"
            sync_completed: false
    priority_rules:
      - field: "custom_field.priority"
        mapping:
          "High": 90
          "Medium": 60
          "Low": 30
  
  gmail:
    enabled: true
    sync_interval: 120
    labels_to_sync:
      - "INBOX"
      - "IMPORTANT"
    priority_senders:
      - pattern: "@hrmny.co"
        boost: 20
      - pattern: "@client-domain.com"
        boost: 30
    
  calendar:
    enabled: true
    sync_interval: 60
    calendars:
      - id: "primary"
        importance: 100
      - id: "team@hrmny.co"
        importance: 80
    prep_time_default: 15  # minutes

  apollo:
    enabled: true
    sync_interval: 600
    
# config/intelligence.yaml
intelligence:
  priority_weights:
    due_date: 0.3
    explicit_priority: 0.25
    sender_importance: 0.2
    project_criticality: 0.15
    recency: 0.1
  
  time_analysis:
    work_hours:
      start: "09:00"
      end: "22:00"
    deep_work_preferred:
      start: "10:00"
      end: "14:00"
    meeting_buffer: 15
    
  escalation:
    overdue_threshold_hours: 24
    response_expected_hours: 48
    
# config/governance.yaml
governance:
  domains:
    tasks:
      mode: observe  # observe | propose | auto_low | auto_high
      auto_threshold: 0.9
    calendar:
      mode: observe
    email:
      mode: observe
    notifications:
      mode: auto_low
      
  approval_required:
    - domain: tasks
      action: create
      condition: "priority > 70"
    - domain: email
      action: send
      condition: "always"
    - domain: calendar
      action: create
      condition: "duration > 60"
      
  rate_limits:
    notifications_per_hour: 5
    actions_per_hour: 20
```

---

### 2. COLLECTION LAYER — Data Acquisition

#### 2.1 Collector Service

**Location:** `lib/collectors/`

```python
# lib/collectors/base.py
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional
import asyncio
import logging

class BaseCollector(ABC):
    """Base class for all data collectors."""
    
    def __init__(self, config: Dict, state_store: 'StateStore'):
        self.config = config
        self.state = state_store
        self.logger = logging.getLogger(self.__class__.__name__)
        self.last_sync: Optional[datetime] = None
        self.sync_interval: int = config.get('sync_interval', 300)
        
    @abstractmethod
    async def collect(self) -> Dict[str, Any]:
        """Collect data from source. Returns collected items."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if collector can reach its source."""
        pass
    
    async def sync(self) -> Dict[str, Any]:
        """Full sync cycle: collect, transform, store."""
        try:
            # Collect raw data
            raw_data = await self.collect()
            
            # Transform to canonical format
            transformed = self.transform(raw_data)
            
            # Store in state
            stored = await self.store(transformed)
            
            # Update sync timestamp
            self.last_sync = datetime.now()
            
            return {
                'source': self.source_name,
                'collected': len(raw_data),
                'stored': stored,
                'timestamp': self.last_sync.isoformat()
            }
        except Exception as e:
            self.logger.error(f"Sync failed: {e}")
            raise
    
    @abstractmethod
    def transform(self, raw_data: Dict) -> List[Dict]:
        """Transform raw API data to canonical format."""
        pass
    
    async def store(self, items: List[Dict]) -> int:
        """Store transformed items in state store."""
        return await self.state.upsert_many(self.target_table, items)
    
    @property
    @abstractmethod
    def source_name(self) -> str:
        pass
    
    @property
    @abstractmethod
    def target_table(self) -> str:
        pass


# lib/collectors/asana.py
class AsanaCollector(BaseCollector):
    """Collects tasks and projects from Asana."""
    
    source_name = 'asana'
    target_table = 'tasks'
    
    async def collect(self) -> Dict[str, Any]:
        """Fetch tasks from configured Asana projects."""
        tasks = []
        for workspace in self.config['workspaces']:
            for project in workspace['projects']:
                project_tasks = await self._fetch_project_tasks(
                    project['id'],
                    include_completed=project.get('sync_completed', False)
                )
                tasks.extend(project_tasks)
        return {'tasks': tasks}
    
    async def _fetch_project_tasks(self, project_id: str, include_completed: bool) -> List[Dict]:
        """Fetch all tasks for a project with full details."""
        # Uses gog asana or direct API
        cmd = f"gog asana tasks --project {project_id} --json"
        if not include_completed:
            cmd += " --incomplete"
        result = await self._run_command(cmd)
        return json.loads(result)
    
    def transform(self, raw_data: Dict) -> List[Dict]:
        """Transform Asana tasks to canonical format."""
        transformed = []
        for task in raw_data['tasks']:
            transformed.append({
                'id': f"asana_{task['gid']}",
                'source': 'asana',
                'source_id': task['gid'],
                'title': task['name'],
                'status': self._map_status(task),
                'priority': self._compute_priority(task),
                'due_date': task.get('due_on'),
                'due_time': task.get('due_at'),
                'assignee': task.get('assignee', {}).get('name'),
                'project': task.get('projects', [{}])[0].get('name'),
                'tags': json.dumps([t['name'] for t in task.get('tags', [])]),
                'dependencies': json.dumps(self._extract_dependencies(task)),
                'blockers': json.dumps(self._extract_blockers(task)),
                'context': json.dumps(task),
                'updated_at': datetime.now().isoformat()
            })
        return transformed
    
    def _compute_priority(self, task: Dict) -> int:
        """Compute priority score 0-100."""
        score = 50  # Base score
        
        # Due date urgency
        if task.get('due_on'):
            due = datetime.fromisoformat(task['due_on'])
            days_until = (due - datetime.now()).days
            if days_until < 0:
                score += 40  # Overdue
            elif days_until == 0:
                score += 30  # Due today
            elif days_until <= 3:
                score += 20  # Due soon
            elif days_until <= 7:
                score += 10
        
        # Explicit priority field
        for field in task.get('custom_fields', []):
            if field.get('name', '').lower() == 'priority':
                mapping = self.config.get('priority_rules', [{}])[0].get('mapping', {})
                value = field.get('display_value', '')
                score += mapping.get(value, 0)
        
        return min(100, max(0, score))


# lib/collectors/gmail.py
class GmailCollector(BaseCollector):
    """Collects emails from Gmail."""
    
    source_name = 'gmail'
    target_table = 'communications'
    
    async def collect(self) -> Dict[str, Any]:
        """Fetch emails from configured labels."""
        messages = []
        for label in self.config['labels_to_sync']:
            label_messages = await self._fetch_label_messages(label)
            messages.extend(label_messages)
        return {'messages': messages}
    
    def transform(self, raw_data: Dict) -> List[Dict]:
        """Transform Gmail messages to canonical format."""
        transformed = []
        for msg in raw_data['messages']:
            priority = self._compute_priority(msg)
            transformed.append({
                'id': f"gmail_{msg['id']}",
                'source': 'email',
                'source_id': msg['id'],
                'thread_id': msg.get('threadId'),
                'from_address': self._extract_from(msg),
                'to_addresses': json.dumps(self._extract_to(msg)),
                'subject': self._extract_subject(msg),
                'snippet': msg.get('snippet', '')[:500],
                'priority': priority,
                'requires_response': self._needs_response(msg),
                'sentiment': self._analyze_sentiment(msg),
                'labels': json.dumps(msg.get('labelIds', [])),
                'created_at': self._extract_date(msg)
            })
        return transformed
    
    def _compute_priority(self, msg: Dict) -> int:
        """Compute email priority 0-100."""
        score = 50
        
        # Sender importance
        from_addr = self._extract_from(msg)
        for rule in self.config.get('priority_senders', []):
            if rule['pattern'] in from_addr:
                score += rule['boost']
        
        # Labels
        labels = msg.get('labelIds', [])
        if 'IMPORTANT' in labels:
            score += 15
        if 'STARRED' in labels:
            score += 10
        if 'CATEGORY_UPDATES' in labels:
            score -= 20
        if 'CATEGORY_PROMOTIONS' in labels:
            score -= 30
            
        return min(100, max(0, score))


# lib/collectors/calendar.py
class CalendarCollector(BaseCollector):
    """Collects events from Google Calendar."""
    
    source_name = 'calendar'
    target_table = 'events'
    
    async def collect(self) -> Dict[str, Any]:
        """Fetch events from configured calendars."""
        events = []
        time_min = datetime.now().isoformat() + 'Z'
        time_max = (datetime.now() + timedelta(days=14)).isoformat() + 'Z'
        
        for cal in self.config['calendars']:
            cal_events = await self._fetch_calendar_events(
                cal['id'], time_min, time_max
            )
            for event in cal_events:
                event['_calendar_importance'] = cal['importance']
            events.extend(cal_events)
        
        return {'events': events}
    
    def transform(self, raw_data: Dict) -> List[Dict]:
        """Transform calendar events to canonical format."""
        transformed = []
        for event in raw_data['events']:
            transformed.append({
                'id': f"calendar_{event['id']}",
                'source': 'calendar',
                'source_id': event['id'],
                'title': event.get('summary', 'No Title'),
                'start_time': self._parse_event_time(event.get('start', {})),
                'end_time': self._parse_event_time(event.get('end', {})),
                'location': event.get('location'),
                'attendees': json.dumps([
                    a.get('email') for a in event.get('attendees', [])
                ]),
                'status': event.get('status', 'confirmed'),
                'prep_required': json.dumps(self._infer_prep(event)),
                'context': json.dumps(event),
                'updated_at': datetime.now().isoformat()
            })
        return transformed


# lib/collectors/orchestrator.py
class CollectorOrchestrator:
    """Manages all collectors and sync scheduling."""
    
    def __init__(self, config_path: str, state_store: 'StateStore'):
        self.config = self._load_config(config_path)
        self.state = state_store
        self.collectors: Dict[str, BaseCollector] = {}
        self._init_collectors()
        
    def _init_collectors(self):
        """Initialize enabled collectors."""
        collector_classes = {
            'asana': AsanaCollector,
            'gmail': GmailCollector,
            'calendar': CalendarCollector,
            'apollo': ApolloCollector,
        }
        
        for source, cfg in self.config['sources'].items():
            if cfg.get('enabled', False):
                cls = collector_classes.get(source)
                if cls:
                    self.collectors[source] = cls(cfg, self.state)
    
    async def run_sync_cycle(self) -> Dict[str, Any]:
        """Run sync for all collectors that need it."""
        results = {}
        for name, collector in self.collectors.items():
            if self._should_sync(collector):
                try:
                    result = await collector.sync()
                    results[name] = result
                except Exception as e:
                    results[name] = {'error': str(e)}
        return results
    
    def _should_sync(self, collector: BaseCollector) -> bool:
        """Check if collector is due for sync."""
        if not collector.last_sync:
            return True
        elapsed = (datetime.now() - collector.last_sync).total_seconds()
        return elapsed >= collector.sync_interval
    
    async def run_forever(self):
        """Main loop: continuously sync all sources."""
        while True:
            await self.run_sync_cycle()
            await asyncio.sleep(60)  # Check every minute
```

---

### 3. INTELLIGENCE LAYER — Analysis & Reasoning

#### 3.1 Analyzers

**Location:** `lib/analyzers/`

```python
# lib/analyzers/priority.py
class PriorityAnalyzer:
    """Computes and maintains priority rankings across all items."""
    
    def __init__(self, config: Dict, state: 'StateStore'):
        self.config = config
        self.state = state
        self.weights = config['priority_weights']
    
    async def analyze(self) -> List[Dict]:
        """Compute priority queue across all actionable items."""
        items = []
        
        # Gather all actionable items
        tasks = await self.state.query(
            "SELECT * FROM tasks WHERE status != 'done'"
        )
        emails = await self.state.query(
            "SELECT * FROM communications WHERE requires_response = 1 AND processed = 0"
        )
        
        # Score and rank
        for task in tasks:
            score = self._compute_score(task, 'task')
            items.append({
                'type': 'task',
                'id': task['id'],
                'title': task['title'],
                'score': score,
                'due': task['due_date'],
                'source': task['source'],
                'reason': self._explain_score(task, score)
            })
        
        for email in emails:
            score = self._compute_score(email, 'email')
            items.append({
                'type': 'email',
                'id': email['id'],
                'title': email['subject'],
                'score': score,
                'due': email.get('response_deadline'),
                'source': 'email',
                'reason': self._explain_score(email, score)
            })
        
        # Sort by score descending
        items.sort(key=lambda x: x['score'], reverse=True)
        
        # Store computed queue
        await self.state.set_cache('priority_queue', items)
        
        return items
    
    def _compute_score(self, item: Dict, item_type: str) -> float:
        """Compute weighted priority score."""
        score = 0.0
        
        # Due date component
        if item.get('due_date') or item.get('response_deadline'):
            due = item.get('due_date') or item.get('response_deadline')
            days_until = self._days_until(due)
            if days_until < 0:
                score += self.weights['due_date'] * 100 * (1 + abs(days_until) * 0.1)
            elif days_until == 0:
                score += self.weights['due_date'] * 90
            elif days_until <= 3:
                score += self.weights['due_date'] * 70
            elif days_until <= 7:
                score += self.weights['due_date'] * 50
        
        # Explicit priority
        if item.get('priority'):
            score += self.weights['explicit_priority'] * item['priority']
        
        # Add other weight components...
        
        return score
    
    def _explain_score(self, item: Dict, score: float) -> str:
        """Generate human-readable score explanation."""
        reasons = []
        if item.get('due_date'):
            days = self._days_until(item['due_date'])
            if days < 0:
                reasons.append(f"Overdue by {abs(days)} days")
            elif days == 0:
                reasons.append("Due today")
            elif days <= 3:
                reasons.append(f"Due in {days} days")
        if item.get('priority', 0) >= 80:
            reasons.append("High priority")
        return "; ".join(reasons) if reasons else "Normal priority"


# lib/analyzers/time.py
class TimeAnalyzer:
    """Analyzes time usage, patterns, and availability."""
    
    async def analyze_day(self, date: datetime = None) -> Dict:
        """Analyze a specific day's time allocation."""
        date = date or datetime.now()
        
        events = await self.state.query(
            """SELECT * FROM events 
               WHERE date(start_time) = date(?)
               ORDER BY start_time""",
            [date.isoformat()]
        )
        
        # Compute blocks
        blocks = self._compute_time_blocks(events, date)
        
        # Identify available slots
        available = self._find_available_slots(blocks, date)
        
        # Categorize time
        categories = self._categorize_time(events)
        
        return {
            'date': date.date().isoformat(),
            'events': len(events),
            'blocks': blocks,
            'available_slots': available,
            'categories': categories,
            'deep_work_available': self._deep_work_slots(available),
            'overbooked': self._check_overbooked(events)
        }
    
    def _compute_time_blocks(self, events: List[Dict], date: datetime) -> List[Dict]:
        """Compute time blocks including buffers."""
        blocks = []
        work_start = self.config['time_analysis']['work_hours']['start']
        work_end = self.config['time_analysis']['work_hours']['end']
        buffer = self.config['time_analysis']['meeting_buffer']
        
        for event in events:
            start = datetime.fromisoformat(event['start_time'])
            end = datetime.fromisoformat(event['end_time']) if event['end_time'] else start + timedelta(hours=1)
            
            blocks.append({
                'type': 'event',
                'id': event['id'],
                'title': event['title'],
                'start': start.isoformat(),
                'end': end.isoformat(),
                'duration_minutes': (end - start).total_seconds() / 60
            })
            
            # Add buffer after meetings
            if 'meeting' in event['title'].lower() or event.get('attendees'):
                blocks.append({
                    'type': 'buffer',
                    'start': end.isoformat(),
                    'end': (end + timedelta(minutes=buffer)).isoformat(),
                    'duration_minutes': buffer
                })
        
        return sorted(blocks, key=lambda x: x['start'])


# lib/analyzers/patterns.py
class PatternAnalyzer:
    """Detects and learns patterns from historical data."""
    
    async def analyze(self) -> List[Dict]:
        """Run pattern detection across all domains."""
        patterns = []
        
        # Task completion patterns
        patterns.extend(await self._analyze_task_patterns())
        
        # Communication patterns
        patterns.extend(await self._analyze_communication_patterns())
        
        # Time usage patterns
        patterns.extend(await self._analyze_time_patterns())
        
        # Store patterns
        for pattern in patterns:
            await self._store_pattern(pattern)
        
        return patterns
    
    async def _analyze_task_patterns(self) -> List[Dict]:
        """Detect patterns in task completion."""
        patterns = []
        
        # Completion time by day of week
        completion_by_day = await self.state.query("""
            SELECT strftime('%w', updated_at) as day,
                   COUNT(*) as completed
            FROM tasks
            WHERE status = 'done'
            GROUP BY day
        """)
        
        if completion_by_day:
            peak_day = max(completion_by_day, key=lambda x: x['completed'])
            patterns.append({
                'type': 'productivity_peak',
                'domain': 'tasks',
                'description': f"Most tasks completed on {self._day_name(peak_day['day'])}",
                'data': {'by_day': completion_by_day},
                'confidence': 0.7
            })
        
        # Overdue patterns
        frequently_late = await self.state.query("""
            SELECT project, COUNT(*) as late_count
            FROM tasks
            WHERE due_date < date('now') AND status != 'done'
            GROUP BY project
            HAVING late_count > 3
        """)
        
        for project in frequently_late:
            patterns.append({
                'type': 'chronic_delay',
                'domain': 'tasks',
                'description': f"Project '{project['project']}' has {project['late_count']} overdue tasks",
                'data': project,
                'confidence': 0.9,
                'actionable': True
            })
        
        return patterns


# lib/analyzers/anomaly.py
class AnomalyDetector:
    """Detects anomalies and unusual situations."""
    
    async def detect(self) -> List[Dict]:
        """Scan for anomalies across all data."""
        anomalies = []
        
        # Sudden increase in high-priority items
        anomalies.extend(await self._detect_priority_spikes())
        
        # Unusual email patterns
        anomalies.extend(await self._detect_email_anomalies())
        
        # Schedule anomalies
        anomalies.extend(await self._detect_schedule_anomalies())
        
        return anomalies
    
    async def _detect_schedule_anomalies(self) -> List[Dict]:
        """Detect schedule issues."""
        anomalies = []
        
        # Double bookings
        events = await self.state.query("""
            SELECT * FROM events
            WHERE date(start_time) >= date('now')
            ORDER BY start_time
        """)
        
        for i, event in enumerate(events[:-1]):
            next_event = events[i + 1]
            if event['end_time'] and next_event['start_time']:
                if event['end_time'] > next_event['start_time']:
                    anomalies.append({
                        'type': 'double_booking',
                        'severity': 'high',
                        'description': f"Overlap: '{event['title']}' and '{next_event['title']}'",
                        'data': {
                            'event1': event,
                            'event2': next_event
                        }
                    })
        
        return anomalies
```

#### 3.2 Reasoner (Decision Engine)

**Location:** `lib/reasoner/`

```python
# lib/reasoner/engine.py
class ReasonerEngine:
    """Makes decisions based on analyzed data and governance rules."""
    
    def __init__(self, config: Dict, state: 'StateStore'):
        self.config = config
        self.state = state
        self.governance = GovernanceEngine(config['governance'])
    
    async def process_cycle(self) -> List[Dict]:
        """Run one reasoning cycle: analyze, decide, propose actions."""
        decisions = []
        
        # Get current state
        priority_queue = await self.state.get_cache('priority_queue')
        time_analysis = await self.state.get_cache('time_analysis')
        anomalies = await self.state.get_cache('anomalies')
        
        # Process anomalies (high priority)
        for anomaly in anomalies:
            decision = await self._handle_anomaly(anomaly)
            if decision:
                decisions.append(decision)
        
        # Process priority queue
        for item in priority_queue[:10]:  # Top 10 items
            decision = await self._process_priority_item(item)
            if decision:
                decisions.append(decision)
        
        # Time optimization
        decisions.extend(await self._optimize_schedule(time_analysis))
        
        # Store decisions
        for decision in decisions:
            await self._store_decision(decision)
        
        return decisions
    
    async def _handle_anomaly(self, anomaly: Dict) -> Optional[Dict]:
        """Create decision for anomaly resolution."""
        if anomaly['type'] == 'double_booking':
            return {
                'domain': 'calendar',
                'decision_type': 'conflict_resolution',
                'input_data': anomaly,
                'options': [
                    {'action': 'reschedule', 'target': anomaly['data']['event2']['id']},
                    {'action': 'decline', 'target': anomaly['data']['event2']['id']},
                    {'action': 'notify_conflict', 'targets': [
                        anomaly['data']['event1']['id'],
                        anomaly['data']['event2']['id']
                    ]}
                ],
                'selected_option': 'notify_conflict',  # Safe default
                'rationale': 'Double booking detected, notifying user',
                'confidence': 0.95,
                'requires_approval': True
            }
        return None
    
    async def _process_priority_item(self, item: Dict) -> Optional[Dict]:
        """Process a priority queue item."""
        if item['score'] >= 90 and item['type'] == 'task':
            # Critical task - create reminder
            return {
                'domain': 'notifications',
                'decision_type': 'reminder',
                'input_data': item,
                'selected_option': 'create_notification',
                'rationale': f"Critical task: {item['reason']}",
                'confidence': 0.9,
                'requires_approval': self._check_approval_required('notifications', 'create')
            }
        return None
    
    def _check_approval_required(self, domain: str, action: str) -> bool:
        """Check governance rules for approval requirement."""
        return self.governance.requires_approval(domain, action)


# lib/reasoner/governance.py
class GovernanceEngine:
    """Enforces governance policies on all system actions."""
    
    def __init__(self, config: Dict):
        self.config = config
        self.domain_modes = config['domains']
        self.approval_rules = config['approval_required']
        self.rate_limits = config['rate_limits']
        self._action_counts = defaultdict(int)
        self._last_reset = datetime.now()
    
    def can_execute(self, domain: str, action: str, context: Dict) -> Tuple[bool, str]:
        """Check if action can be executed automatically."""
        mode = self.domain_modes.get(domain, {}).get('mode', 'observe')
        
        if mode == 'observe':
            return False, "Domain in observe mode"
        
        if mode == 'propose':
            return False, "Domain in propose mode - requires approval"
        
        # Check rate limits
        if not self._check_rate_limit(domain, action):
            return False, "Rate limit exceeded"
        
        # Check specific approval rules
        for rule in self.approval_rules:
            if rule['domain'] == domain and rule['action'] == action:
                if rule['condition'] == 'always':
                    return False, "Action always requires approval"
                if self._evaluate_condition(rule['condition'], context):
                    return False, f"Condition met: {rule['condition']}"
        
        if mode == 'auto_low':
            threshold = self.domain_modes[domain].get('auto_threshold', 0.8)
            if context.get('confidence', 0) < threshold:
                return False, f"Confidence {context.get('confidence')} below threshold {threshold}"
        
        return True, "Approved for automatic execution"
    
    def requires_approval(self, domain: str, action: str) -> bool:
        """Quick check if action type requires approval."""
        mode = self.domain_modes.get(domain, {}).get('mode', 'observe')
        if mode in ('observe', 'propose'):
            return True
        for rule in self.approval_rules:
            if rule['domain'] == domain and rule['action'] == action:
                return True
        return False
```

---

### 4. EXECUTION LAYER — Taking Action

#### 4.1 Action Executor

**Location:** `lib/executor/`

```python
# lib/executor/engine.py
class ExecutorEngine:
    """Executes approved actions across systems."""
    
    def __init__(self, config: Dict, state: 'StateStore', governance: 'GovernanceEngine'):
        self.config = config
        self.state = state
        self.governance = governance
        self.handlers = {
            'task_create': TaskCreateHandler(),
            'task_update': TaskUpdateHandler(),
            'email_send': EmailSendHandler(),
            'email_reply': EmailReplyHandler(),
            'calendar_create': CalendarCreateHandler(),
            'calendar_update': CalendarUpdateHandler(),
            'notification_send': NotificationSendHandler(),
        }
    
    async def process_pending_actions(self) -> List[Dict]:
        """Process all pending approved actions."""
        results = []
        
        actions = await self.state.query(
            "SELECT * FROM actions WHERE status = 'approved' ORDER BY created_at"
        )
        
        for action in actions:
            result = await self._execute_action(action)
            results.append(result)
        
        return results
    
    async def _execute_action(self, action: Dict) -> Dict:
        """Execute a single action."""
        handler = self.handlers.get(action['type'])
        if not handler:
            return {'id': action['id'], 'error': f"Unknown action type: {action['type']}"}
        
        try:
            # Update status to executing
            await self.state.update('actions', action['id'], {'status': 'executing'})
            
            # Execute
            result = await handler.execute(json.loads(action['payload']))
            
            # Update with result
            await self.state.update('actions', action['id'], {
                'status': 'done',
                'executed_at': datetime.now().isoformat(),
                'result': json.dumps(result)
            })
            
            return {'id': action['id'], 'status': 'done', 'result': result}
            
        except Exception as e:
            await self.state.update('actions', action['id'], {
                'status': 'failed',
                'error': str(e),
                'retry_count': action.get('retry_count', 0) + 1
            })
            return {'id': action['id'], 'status': 'failed', 'error': str(e)}


# lib/executor/handlers/notification.py
class NotificationSendHandler:
    """Sends notifications through configured channels."""
    
    async def execute(self, payload: Dict) -> Dict:
        """Send notification."""
        notification_id = payload['notification_id']
        channels = payload.get('channels', ['push'])
        
        # Get notification details
        notification = await self.state.get('notifications', notification_id)
        
        results = {}
        for channel in channels:
            if channel == 'push':
                results['push'] = await self._send_push(notification)
            elif channel == 'sms':
                results['sms'] = await self._send_sms(notification)
            elif channel == 'email':
                results['email'] = await self._send_email(notification)
        
        # Update notification
        await self.state.update('notifications', notification_id, {
            'sent_at': datetime.now().isoformat()
        })
        
        return results
    
    async def _send_push(self, notification: Dict) -> Dict:
        """Send push notification via Clawdbot nodes."""
        # Uses nodes notify
        cmd = [
            'nodes', 'notify',
            '--title', notification['title'],
            '--body', notification.get('body', ''),
            '--priority', notification['priority']
        ]
        if notification.get('action_url'):
            cmd.extend(['--url', notification['action_url']])
        
        result = await run_command(cmd)
        return {'sent': True, 'result': result}
```

---

### 5. USER INTERFACE LAYER — Direct Interaction

#### 5.1 Dashboard (Web UI)

**Location:** `ui/dashboard/`

```
ui/dashboard/
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx              # Main dashboard
│   │   ├── priorities/
│   │   │   └── page.tsx          # Priority queue view
│   │   ├── calendar/
│   │   │   └── page.tsx          # Time view
│   │   ├── inbox/
│   │   │   └── page.tsx          # Communications
│   │   ├── projects/
│   │   │   └── page.tsx          # Project health
│   │   ├── decisions/
│   │   │   └── page.tsx          # Pending approvals
│   │   ├── insights/
│   │   │   └── page.tsx          # Patterns & anomalies
│   │   └── settings/
│   │       └── page.tsx          # Configuration
│   ├── components/
│   │   ├── PriorityQueue.tsx
│   │   ├── TimelineView.tsx
│   │   ├── TaskCard.tsx
│   │   ├── EmailCard.tsx
│   │   ├── ApprovalCard.tsx
│   │   ├── InsightCard.tsx
│   │   └── ActionButton.tsx
│   └── lib/
│       ├── api.ts                # API client
│       └── websocket.ts          # Real-time updates
├── package.json
└── next.config.js
```

**Main Dashboard Page:**

```tsx
// ui/dashboard/src/app/page.tsx
import { PriorityQueue } from '@/components/PriorityQueue'
import { UpcomingEvents } from '@/components/UpcomingEvents'
import { PendingApprovals } from '@/components/PendingApprovals'
import { ActiveInsights } from '@/components/ActiveInsights'
import { QuickActions } from '@/components/QuickActions'

export default async function Dashboard() {
  const [priorities, events, approvals, insights] = await Promise.all([
    api.getPriorityQueue({ limit: 10 }),
    api.getUpcomingEvents({ hours: 24 }),
    api.getPendingApprovals(),
    api.getActiveInsights()
  ])
  
  return (
    <div className="grid grid-cols-12 gap-4 p-4">
      {/* Header with quick status */}
      <header className="col-span-12 flex justify-between items-center">
        <h1 className="text-2xl font-bold">MOH TIME OS</h1>
        <div className="flex gap-4">
          <SystemStatus />
          <QuickActions />
        </div>
      </header>
      
      {/* Main priority queue */}
      <section className="col-span-8">
        <h2 className="text-xl mb-4">Priority Queue</h2>
        <PriorityQueue items={priorities} />
      </section>
      
      {/* Sidebar */}
      <aside className="col-span-4 space-y-4">
        {/* Pending approvals (if any) */}
        {approvals.length > 0 && (
          <div className="bg-yellow-50 border border-yellow-200 rounded p-4">
            <h3 className="font-semibold text-yellow-800">Pending Approvals</h3>
            <PendingApprovals items={approvals} />
          </div>
        )}
        
        {/* Upcoming */}
        <div>
          <h3 className="font-semibold">Next 24 Hours</h3>
          <UpcomingEvents events={events} />
        </div>
        
        {/* Insights */}
        <div>
          <h3 className="font-semibold">Insights</h3>
          <ActiveInsights insights={insights} />
        </div>
      </aside>
    </div>
  )
}
```

**Priority Queue Component:**

```tsx
// ui/dashboard/src/components/PriorityQueue.tsx
'use client'

import { useState } from 'react'
import { TaskCard } from './TaskCard'
import { EmailCard } from './EmailCard'
import { api } from '@/lib/api'

interface PriorityItem {
  type: 'task' | 'email'
  id: string
  title: string
  score: number
  due?: string
  source: string
  reason: string
}

export function PriorityQueue({ items }: { items: PriorityItem[] }) {
  const [queue, setQueue] = useState(items)
  
  const handleComplete = async (item: PriorityItem) => {
    await api.completeItem(item.id, item.type)
    setQueue(queue.filter(i => i.id !== item.id))
  }
  
  const handleSnooze = async (item: PriorityItem, hours: number) => {
    await api.snoozeItem(item.id, item.type, hours)
    setQueue(queue.filter(i => i.id !== item.id))
  }
  
  const handleDelegate = async (item: PriorityItem, assignee: string) => {
    await api.delegateItem(item.id, item.type, assignee)
    setQueue(queue.filter(i => i.id !== item.id))
  }
  
  return (
    <div className="space-y-2">
      {queue.map((item, index) => (
        <div key={item.id} className="flex items-start gap-3">
          {/* Priority indicator */}
          <div className={`
            w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold
            ${item.score >= 90 ? 'bg-red-500 text-white' : 
              item.score >= 70 ? 'bg-orange-500 text-white' :
              item.score >= 50 ? 'bg-yellow-500' : 'bg-gray-200'}
          `}>
            {index + 1}
          </div>
          
          {/* Item card */}
          {item.type === 'task' ? (
            <TaskCard 
              item={item}
              onComplete={() => handleComplete(item)}
              onSnooze={(hours) => handleSnooze(item, hours)}
              onDelegate={(assignee) => handleDelegate(item, assignee)}
            />
          ) : (
            <EmailCard
              item={item}
              onComplete={() => handleComplete(item)}
              onSnooze={(hours) => handleSnooze(item, hours)}
            />
          )}
        </div>
      ))}
    </div>
  )
}
```

**Approval Component:**

```tsx
// ui/dashboard/src/components/PendingApprovals.tsx
'use client'

import { api } from '@/lib/api'

interface Approval {
  id: string
  domain: string
  decision_type: string
  description: string
  options: { action: string; label: string }[]
  selected_option: string
  rationale: string
  confidence: number
}

export function PendingApprovals({ items }: { items: Approval[] }) {
  const handleApprove = async (id: string) => {
    await api.approveDecision(id)
    // Refresh or update state
  }
  
  const handleReject = async (id: string) => {
    await api.rejectDecision(id)
  }
  
  const handleModify = async (id: string, newOption: string) => {
    await api.modifyDecision(id, newOption)
  }
  
  return (
    <div className="space-y-3 mt-2">
      {items.map(item => (
        <div key={item.id} className="bg-white p-3 rounded shadow-sm">
          <div className="flex justify-between items-start">
            <div>
              <span className="text-xs bg-gray-100 px-2 py-1 rounded">
                {item.domain}
              </span>
              <p className="mt-1 font-medium">{item.description}</p>
              <p className="text-sm text-gray-600 mt-1">{item.rationale}</p>
            </div>
            <span className="text-xs text-gray-500">
              {Math.round(item.confidence * 100)}% confident
            </span>
          </div>
          
          <div className="flex gap-2 mt-3">
            <button
              onClick={() => handleApprove(item.id)}
              className="px-3 py-1 bg-green-500 text-white rounded text-sm"
            >
              Approve
            </button>
            <button
              onClick={() => handleReject(item.id)}
              className="px-3 py-1 bg-red-500 text-white rounded text-sm"
            >
              Reject
            </button>
            <select
              onChange={(e) => handleModify(item.id, e.target.value)}
              className="px-2 py-1 border rounded text-sm"
              defaultValue=""
            >
              <option value="" disabled>Modify...</option>
              {item.options.map(opt => (
                <option key={opt.action} value={opt.action}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      ))}
    </div>
  )
}
```

#### 5.2 CLI Interface

**Location:** `cli/`

```python
# cli/main.py
import click
import json
from rich.console import Console
from rich.table import Table

console = Console()

@click.group()
def cli():
    """MOH TIME OS - Personal Operating System"""
    pass

@cli.command()
@click.option('--limit', default=10, help='Number of items to show')
def priorities(limit):
    """Show priority queue."""
    queue = api.get_priority_queue(limit=limit)
    
    table = Table(title="Priority Queue")
    table.add_column("#", style="bold")
    table.add_column("Score", justify="right")
    table.add_column("Type")
    table.add_column("Title")
    table.add_column("Due")
    table.add_column("Reason")
    
    for i, item in enumerate(queue, 1):
        score_color = "red" if item['score'] >= 90 else "yellow" if item['score'] >= 70 else "white"
        table.add_row(
            str(i),
            f"[{score_color}]{item['score']:.0f}[/{score_color}]",
            item['type'],
            item['title'][:40],
            item.get('due', '-'),
            item['reason'][:30]
        )
    
    console.print(table)

@cli.command()
def approvals():
    """Show pending approvals."""
    pending = api.get_pending_approvals()
    
    if not pending:
        console.print("[green]No pending approvals[/green]")
        return
    
    for item in pending:
        console.print(f"\n[bold]{item['domain']}[/bold]: {item['description']}")
        console.print(f"  Rationale: {item['rationale']}")
        console.print(f"  Confidence: {item['confidence']*100:.0f}%")
        console.print(f"  [dim]ID: {item['id']}[/dim]")

@cli.command()
@click.argument('decision_id')
def approve(decision_id):
    """Approve a pending decision."""
    result = api.approve_decision(decision_id)
    console.print(f"[green]Approved: {result['description']}[/green]")

@cli.command()
@click.argument('decision_id')
def reject(decision_id):
    """Reject a pending decision."""
    result = api.reject_decision(decision_id)
    console.print(f"[red]Rejected: {result['description']}[/red]")

@cli.command()
def today():
    """Show today's schedule and priorities."""
    schedule = api.get_day_analysis()
    priorities = api.get_priority_queue(limit=5)
    
    console.print("\n[bold]TODAY'S SCHEDULE[/bold]")
    for block in schedule['blocks']:
        time = block['start'][11:16]
        console.print(f"  {time} - {block['title']}")
    
    console.print(f"\n[dim]Available deep work: {schedule['deep_work_available']} hours[/dim]")
    
    console.print("\n[bold]TOP PRIORITIES[/bold]")
    for i, item in enumerate(priorities, 1):
        console.print(f"  {i}. [{item['score']:.0f}] {item['title'][:50]}")

@cli.command()
@click.option('--domain', help='Filter by domain')
def insights(domain):
    """Show current insights and patterns."""
    data = api.get_insights(domain=domain)
    
    for insight in data:
        icon = "⚠️" if insight['type'] == 'anomaly' else "💡"
        console.print(f"\n{icon} [{insight['domain']}] {insight['title']}")
        console.print(f"   {insight['description']}")

@cli.command()
def sync():
    """Force sync all data sources."""
    with console.status("Syncing..."):
        results = api.force_sync()
    
    for source, result in results.items():
        status = "✓" if 'error' not in result else "✗"
        console.print(f"  {status} {source}: {result.get('collected', result.get('error'))}")

@cli.group()
def config():
    """Configuration commands."""
    pass

@config.command()
@click.argument('domain')
@click.argument('mode', type=click.Choice(['observe', 'propose', 'auto_low', 'auto_high']))
def set_mode(domain, mode):
    """Set governance mode for a domain."""
    api.set_domain_mode(domain, mode)
    console.print(f"[green]{domain} mode set to {mode}[/green]")

if __name__ == '__main__':
    cli()
```

#### 5.3 API Server

**Location:** `api/`

```python
# api/server.py
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import asyncio

app = FastAPI(title="MOH TIME OS API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize system components
state = StateStore('data/state.db')
collectors = CollectorOrchestrator('config/sources.yaml', state)
analyzers = AnalyzerOrchestrator(config, state)
reasoner = ReasonerEngine(config, state)
executor = ExecutorEngine(config, state, reasoner.governance)

# WebSocket connections for real-time updates
connections: List[WebSocket] = []

@app.get("/api/priorities")
async def get_priorities(limit: int = 10):
    """Get current priority queue."""
    queue = await state.get_cache('priority_queue')
    return queue[:limit] if queue else []

@app.get("/api/events")
async def get_events(hours: int = 24):
    """Get upcoming events."""
    cutoff = (datetime.now() + timedelta(hours=hours)).isoformat()
    events = await state.query(
        "SELECT * FROM events WHERE start_time <= ? ORDER BY start_time",
        [cutoff]
    )
    return events

@app.get("/api/approvals")
async def get_approvals():
    """Get pending approval decisions."""
    decisions = await state.query(
        "SELECT * FROM decisions WHERE requires_approval = 1 AND approved IS NULL"
    )
    return decisions

@app.post("/api/approvals/{decision_id}/approve")
async def approve_decision(decision_id: str):
    """Approve a pending decision."""
    decision = await state.get('decisions', decision_id)
    if not decision:
        raise HTTPException(404, "Decision not found")
    
    await state.update('decisions', decision_id, {
        'approved': True,
        'approved_at': datetime.now().isoformat()
    })
    
    # Create action for execution
    await state.insert('actions', {
        'id': f"action_{uuid4()}",
        'type': decision['decision_type'],
        'payload': decision['selected_option'],
        'status': 'approved',
        'created_at': datetime.now().isoformat()
    })
    
    # Broadcast update
    await broadcast({'type': 'approval_processed', 'id': decision_id})
    
    return {'status': 'approved', 'decision_id': decision_id}

@app.post("/api/approvals/{decision_id}/reject")
async def reject_decision(decision_id: str):
    """Reject a pending decision."""
    await state.update('decisions', decision_id, {
        'approved': False,
        'approved_at': datetime.now().isoformat()
    })
    await broadcast({'type': 'approval_processed', 'id': decision_id})
    return {'status': 'rejected', 'decision_id': decision_id}

@app.get("/api/insights")
async def get_insights(domain: str = None):
    """Get current insights."""
    query = "SELECT * FROM insights WHERE expires_at > datetime('now')"
    params = []
    if domain:
        query += " AND domain = ?"
        params.append(domain)
    return await state.query(query, params)

@app.get("/api/day/{date}")
async def get_day_analysis(date: str = None):
    """Get analysis for a specific day."""
    target_date = datetime.fromisoformat(date) if date else datetime.now()
    return await analyzers.time.analyze_day(target_date)

@app.post("/api/sync")
async def force_sync():
    """Force sync all data sources."""
    return await collectors.run_sync_cycle()

@app.put("/api/config/governance/{domain}")
async def set_governance_mode(domain: str, mode: str):
    """Set governance mode for a domain."""
    valid_modes = ['observe', 'propose', 'auto_low', 'auto_high']
    if mode not in valid_modes:
        raise HTTPException(400, f"Invalid mode. Must be one of: {valid_modes}")
    
    await reasoner.governance.set_mode(domain, mode)
    return {'domain': domain, 'mode': mode}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates."""
    await websocket.accept()
    connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except:
        connections.remove(websocket)

async def broadcast(message: dict):
    """Broadcast message to all connected clients."""
    for ws in connections:
        try:
            await ws.send_json(message)
        except:
            pass
```

---

### 6. AUTONOMOUS LOOP — The Engine

**Location:** `lib/autonomous_loop.py`

```python
# lib/autonomous_loop.py
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class AutonomousLoop:
    """Main autonomous execution loop."""
    
    def __init__(self, config_path: str = 'config/'):
        self.config = self._load_config(config_path)
        self.state = StateStore('data/state.db')
        
        # Initialize all components
        self.collectors = CollectorOrchestrator(config_path, self.state)
        self.analyzers = AnalyzerOrchestrator(self.config, self.state)
        self.reasoner = ReasonerEngine(self.config, self.state)
        self.executor = ExecutorEngine(self.config, self.state, self.reasoner.governance)
        self.notifier = NotificationEngine(self.config, self.state)
        
        self.running = False
        self.cycle_count = 0
    
    async def run_cycle(self) -> Dict:
        """Run one complete autonomous cycle."""
        cycle_start = datetime.now()
        self.cycle_count += 1
        
        logger.info(f"Starting cycle {self.cycle_count}")
        
        results = {
            'cycle': self.cycle_count,
            'started_at': cycle_start.isoformat(),
            'phases': {}
        }
        
        try:
            # Phase 1: Collect
            logger.debug("Phase 1: Collecting data")
            results['phases']['collect'] = await self.collectors.run_sync_cycle()
            
            # Phase 2: Analyze
            logger.debug("Phase 2: Analyzing data")
            results['phases']['analyze'] = {
                'priority': await self.analyzers.priority.analyze(),
                'time': await self.analyzers.time.analyze_day(),
                'patterns': await self.analyzers.patterns.analyze(),
                'anomalies': await self.analyzers.anomaly.detect()
            }
            
            # Phase 3: Reason
            logger.debug("Phase 3: Making decisions")
            decisions = await self.reasoner.process_cycle()
            results['phases']['reason'] = {
                'decisions': len(decisions),
                'requires_approval': len([d for d in decisions if d.get('requires_approval')])
            }
            
            # Phase 4: Execute (approved actions only)
            logger.debug("Phase 4: Executing approved actions")
            execution_results = await self.executor.process_pending_actions()
            results['phases']['execute'] = {
                'executed': len(execution_results),
                'succeeded': len([r for r in execution_results if r.get('status') == 'done']),
                'failed': len([r for r in execution_results if r.get('status') == 'failed'])
            }
            
            # Phase 5: Notify
            logger.debug("Phase 5: Sending notifications")
            notifications = await self.notifier.process_pending()
            results['phases']['notify'] = {'sent': len(notifications)}
            
        except Exception as e:
            logger.error(f"Cycle failed: {e}")
            results['error'] = str(e)
        
        results['completed_at'] = datetime.now().isoformat()
        results['duration_ms'] = (datetime.now() - cycle_start).total_seconds() * 1000
        
        # Store cycle result
        await self.state.insert('cycle_logs', {
            'id': f"cycle_{self.cycle_count}",
            'data': json.dumps(results),
            'created_at': datetime.now().isoformat()
        })
        
        logger.info(f"Cycle {self.cycle_count} completed in {results['duration_ms']:.0f}ms")
        
        return results
    
    async def run_forever(self, interval_seconds: int = 300):
        """Run autonomous loop continuously."""
        self.running = True
        logger.info(f"Starting autonomous loop (interval: {interval_seconds}s)")
        
        while self.running:
            try:
                await self.run_cycle()
            except Exception as e:
                logger.error(f"Cycle error: {e}")
            
            await asyncio.sleep(interval_seconds)
    
    def stop(self):
        """Stop the autonomous loop."""
        self.running = False
        logger.info("Autonomous loop stopped")


# Entry point
async def main():
    loop = AutonomousLoop()
    await loop.run_forever()

if __name__ == '__main__':
    asyncio.run(main())
```

---

## PART III: WIRING DIAGRAM

### How Components Connect

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MOH TIME OS - WIRED SYSTEM                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  EXTERNAL SYSTEMS                                                           │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐                          │
│  │  Asana  │ │  Gmail  │ │Calendar │ │ Apollo  │                          │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘                          │
│       │           │           │           │                                 │
│       └───────────┴───────────┴───────────┘                                │
│                       │                                                     │
│                       ▼                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     COLLECTOR ORCHESTRATOR                          │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │   │
│  │  │  Asana   │ │  Gmail   │ │ Calendar │ │  Apollo  │              │   │
│  │  │Collector │ │Collector │ │Collector │ │Collector │              │   │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘              │   │
│  │       └────────────┴────────────┴────────────┘                     │   │
│  └───────────────────────────┬─────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         STATE STORE                                 │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐     │   │
│  │  │  tasks  │ │ events  │ │  comms  │ │insights │ │decisions│     │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘     │   │
│  └───────────────────────────┬─────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    ANALYZER ORCHESTRATOR                            │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │   │
│  │  │Priority  │ │  Time    │ │ Pattern  │ │ Anomaly  │              │   │
│  │  │Analyzer  │ │ Analyzer │ │ Analyzer │ │ Detector │              │   │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘              │   │
│  │       └────────────┴────────────┴────────────┘                     │   │
│  └───────────────────────────┬─────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      REASONER ENGINE                                │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │                   GOVERNANCE ENGINE                          │   │   │
│  │  │  Domain Modes │ Approval Rules │ Rate Limits │ Confidence   │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                              │                                      │   │
│  │                   ┌──────────┴──────────┐                          │   │
│  │                   ▼                      ▼                          │   │
│  │            Auto-Execute           Pending Approval                  │   │
│  └───────────────────────────┬─────────────┬───────────────────────────┘   │
│                              │             │                                │
│              ┌───────────────┘             └──────────────┐                 │
│              │                                            │                 │
│              ▼                                            ▼                 │
│  ┌─────────────────────┐                    ┌─────────────────────┐        │
│  │  EXECUTOR ENGINE    │                    │   USER INTERFACE    │        │
│  │  ┌───────────────┐  │                    │  ┌───────────────┐  │        │
│  │  │ Task Handler  │  │                    │  │   Dashboard   │──┼───┐    │
│  │  │ Email Handler │  │                    │  │      CLI      │──┼───┤    │
│  │  │Calendar Handler│ │                    │  │     API       │──┼───┤    │
│  │  │Notification H.│  │                    │  │  Mobile Push  │──┼───┘    │
│  │  └───────────────┘  │                    │  └───────────────┘  │        │
│  └──────────┬──────────┘                    └──────────┬──────────┘        │
│             │                                          │                    │
│             └──────────────────┬───────────────────────┘                   │
│                                │                                            │
│                                ▼                                            │
│                         ┌──────────────┐                                   │
│                         │     USER     │                                   │
│                         │   (Moh)      │                                   │
│                         └──────────────┘                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Collection → State**: Collectors pull from external systems, transform to canonical format, store in state
2. **State → Analysis**: Analyzers read state, compute insights, store back to state
3. **Analysis → Reasoning**: Reasoner reads insights/anomalies, makes decisions based on governance
4. **Reasoning → Execution**: Auto-approved decisions go to executor; others to UI for approval
5. **Execution → Systems**: Executor performs actions on external systems
6. **Everything → UI**: All state is readable via UI; user can act directly

### User Interaction Points

| Interaction | UI Component | Direct Action |
|-------------|--------------|---------------|
| View priorities | Dashboard / CLI | - |
| Complete task | Task card button | Marks done in Asana |
| Approve decision | Approval card | Triggers executor |
| Reject decision | Approval card | Cancels action |
| Modify decision | Approval card dropdown | Changes action, then executes |
| Snooze item | Task/Email card | Deprioritizes for N hours |
| Delegate | Task card | Reassigns in source system |
| View schedule | Calendar view | - |
| Check insights | Insights page | - |
| Force sync | CLI / Button | Triggers all collectors |
| Change mode | Settings / CLI | Updates governance config |

---

## PART IV: IMPLEMENTATION ROADMAP

### Phase 1: Foundation (Week 1)

**Goal:** Working data pipeline with basic UI

- [ ] State store implementation (SQLite)
- [ ] Asana collector (tasks)
- [ ] Calendar collector (events)
- [ ] Basic priority analyzer
- [ ] CLI: `priorities`, `today`, `sync`
- [ ] Dashboard: Priority queue view

**Deliverable:** Can see prioritized task list from Asana + Calendar

### Phase 2: Intelligence (Week 2)

**Goal:** Automated analysis and insights

- [ ] Gmail collector (communications)
- [ ] Time analyzer (day analysis)
- [ ] Pattern analyzer (basic patterns)
- [ ] Anomaly detector (double bookings, overdue)
- [ ] CLI: `insights`, `approvals`
- [ ] Dashboard: Insights view, Anomaly alerts

**Deliverable:** System detects and surfaces issues automatically

### Phase 3: Reasoning (Week 3)

**Goal:** Automated decision-making with governance

- [ ] Reasoner engine (decision logic)
- [ ] Governance engine (modes, approvals, limits)
- [ ] Notification engine (push via Clawdbot)
- [ ] CLI: `approve`, `reject`, `config set-mode`
- [ ] Dashboard: Approval workflow, Settings page

**Deliverable:** System proposes actions, user can approve/reject via UI

### Phase 4: Execution (Week 4)

**Goal:** Full autonomous operation

- [ ] Executor engine (all handlers)
- [ ] Action queue processing
- [ ] Feedback collection
- [ ] Learning from feedback
- [ ] Full autonomous loop
- [ ] Dashboard: Action history, Feedback UI

**Deliverable:** System runs autonomously, user monitors and approves

### Phase 5: Optimization (Week 5+)

**Goal:** Polish and enhance

- [ ] Apollo collector (leads)
- [ ] Advanced patterns (ML-based)
- [ ] Mobile-optimized dashboard
- [ ] Voice interface (via Clawdbot TTS)
- [ ] Proactive scheduling suggestions
- [ ] Email drafting assistance

---

## PART V: SUCCESS CRITERIA

### The System Works If:

1. **Autonomous Operation**: System runs 24/7 without prompting
2. **Zero AI Bottleneck**: User can interact with all data via UI without asking AI
3. **Complete Wiring**: Data flows automatically from source to insight to action
4. **Governance Control**: User can tune autonomy level per domain
5. **Learning**: System gets better through feedback loops
6. **User-Facilitated**: All common actions available through UI, not chat

### The System Fails If:

- User needs to ask "what should I do today?"
- AI is required to check email/calendar/tasks
- Components exist but don't connect
- Actions require manual execution in source systems
- User can't control autonomy level
- System doesn't improve over time

---

## APPENDIX: File Structure

```
moh_time_os/
├── SPEC.md                      # This document
├── config/
│   ├── sources.yaml             # Data source configuration
│   ├── intelligence.yaml        # Analysis configuration
│   └── governance.yaml          # Governance rules
├── data/
│   ├── state.db                 # SQLite state store
│   └── cache/                   # Computed data cache
├── lib/
│   ├── state_store.py           # Database abstraction
│   ├── collectors/
│   │   ├── base.py
│   │   ├── asana.py
│   │   ├── gmail.py
│   │   ├── calendar.py
│   │   └── orchestrator.py
│   ├── analyzers/
│   │   ├── priority.py
│   │   ├── time.py
│   │   ├── patterns.py
│   │   ├── anomaly.py
│   │   └── orchestrator.py
│   ├── reasoner/
│   │   ├── engine.py
│   │   └── governance.py
│   ├── executor/
│   │   ├── engine.py
│   │   └── handlers/
│   ├── notifier/
│   │   └── engine.py
│   └── autonomous_loop.py
├── api/
│   └── server.py                # FastAPI server
├── cli/
│   └── main.py                  # Click CLI
├── ui/
│   └── dashboard/               # Next.js dashboard
└── scripts/
    ├── setup.sh                 # Initial setup
    ├── start.sh                 # Start all services
    └── migrate.py               # Database migrations
```

---

**This is the complete specification. No exceptions. No disconnected components. One wired system.**
