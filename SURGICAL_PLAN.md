# Time OS Surgical Repair Plan

**Date:** 2026-02-02  
**Status:** DRAFT  
**Author:** A (for Moh)

---

## Executive Summary

The system has correct architecture but broken data flow. This plan addresses 9 critical issues in priority order, with exact file changes, SQL migrations, and test criteria.

**Estimated effort:** 4-6 hours focused work  
**Risk:** Low (all changes are additive or fix existing code)

---

## Issue Map

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA FLOW PROBLEMS                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Google Calendar ──✗──► events table ──?──► time_blocks            │
│                         (events exist)      (only 1 block)          │
│                                                                     │
│  Gmail ──✗──► communications ──✗──► commitments                     │
│               (empty)                (7 from test only)             │
│                                                                     │
│  Asana ──✓──► tasks ──✗──► scheduled_block_id                       │
│               (229)        (only 1 scheduled)                       │
│                                                                     │
│  Asana ──✓──► projects ──✗──► client_projects ──✗──► clients        │
│               (15)             (only 3 links)        (170)          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Fix #1: Block Generation (CRITICAL)

### Problem
`create_blocks_from_calendar()` creates 1 default block when no events exist. Should create blocks for full workday.

### Current Code (broken)
```python
# lib/time_truth/block_manager.py line ~160
if not events:
    # No events - create one default block
    return [self.create_block(date, "10:00", "11:00", lane)]
```

### Fix
```python
# lib/time_truth/block_manager.py

def create_blocks_from_calendar(self, date: str, events: List[dict] = None, 
                                 lane: str = 'ops',
                                 work_start: str = "09:00",
                                 work_end: str = "18:00",
                                 block_duration_min: int = 60) -> List[TimeBlock]:
    """
    Generate time blocks for a workday, carving around calendar events.
    
    1. Define work window (default 09:00-18:00)
    2. Mark protected blocks for each calendar event
    3. Fill gaps with available blocks of block_duration_min
    """
    created = []
    
    # Get existing blocks to avoid duplicates
    existing = self.get_all_blocks(date)
    if existing:
        return existing  # Already generated
    
    # Parse events into time ranges
    busy_ranges = []
    for event in (events or []):
        start = self._parse_time(event.get('start_time', ''))
        end = self._parse_time(event.get('end_time', ''))
        if start and end:
            busy_ranges.append((start, end, event.get('title', 'Meeting')))
            # Create protected block for event
            block, _ = self.create_block(date, start, end, lane, is_protected=True)
            if block:
                created.append(block)
    
    # Sort busy ranges
    busy_ranges.sort(key=lambda x: x[0])
    
    # Generate available blocks in gaps
    current_time = work_start
    
    for busy_start, busy_end, _ in busy_ranges:
        # Create available blocks from current_time to busy_start
        while self._time_diff_min(current_time, busy_start) >= block_duration_min:
            block_end = self._add_minutes(current_time, block_duration_min)
            if self._time_to_min(block_end) > self._time_to_min(busy_start):
                block_end = busy_start
            
            if self._time_diff_min(current_time, block_end) >= 30:  # Min 30min blocks
                block, _ = self.create_block(date, current_time, block_end, lane)
                if block:
                    created.append(block)
            
            current_time = block_end
        
        # Skip past the busy period
        current_time = busy_end
    
    # Fill remaining time until work_end
    while self._time_diff_min(current_time, work_end) >= block_duration_min:
        block_end = self._add_minutes(current_time, block_duration_min)
        if self._time_to_min(block_end) > self._time_to_min(work_end):
            block_end = work_end
        
        if self._time_diff_min(current_time, block_end) >= 30:
            block, _ = self.create_block(date, current_time, block_end, lane)
            if block:
                created.append(block)
        
        current_time = block_end
    
    return created

def _time_to_min(self, time_str: str) -> int:
    """Convert HH:MM to minutes since midnight."""
    h, m = map(int, time_str.split(':'))
    return h * 60 + m

def _time_diff_min(self, start: str, end: str) -> int:
    """Minutes between two HH:MM times."""
    return self._time_to_min(end) - self._time_to_min(start)

def _add_minutes(self, time_str: str, minutes: int) -> str:
    """Add minutes to HH:MM time."""
    total = self._time_to_min(time_str) + minutes
    return f"{total // 60:02d}:{total % 60:02d}"

def _parse_time(self, dt_str: str) -> Optional[str]:
    """Extract HH:MM from datetime string."""
    if not dt_str:
        return None
    if 'T' in dt_str:
        return dt_str.split('T')[1][:5]
    return dt_str[:5] if ':' in dt_str else None
```

### Test Criteria
```python
# After fix:
blocks = manager.create_blocks_from_calendar("2026-02-03", events=[], lane='ops')
assert len(blocks) >= 8  # 9 hours / 60 min = 9 blocks minimum
```

### Files Changed
- `lib/time_truth/block_manager.py`

---

## Fix #2: Gmail → State Store Pipeline (CRITICAL)

### Problem
Gmail collector runs but communications table is empty. Emails aren't being stored.

### Root Cause
`GmailCollector.collect()` returns data but `store()` method may not be called, or the gog CLI isn't returning data.

### Diagnostic
```bash
# Test gog CLI directly
gog gmail search "is:unread" --json | head -20

# Check if collector stores anything
python3 -c "
from lib.collectors import GmailCollector
from lib.state_store import get_store
gc = GmailCollector(get_store())
result = gc.sync()
print(result)
"
```

### Fix Architecture
```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   gog CLI    │────►│ GmailCollector│────►│communications│
│ (gmail search)│     │  .transform() │     │    table     │
└──────────────┘     └──────────────┘     └──────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │ commitment   │
                     │ extraction   │
                     │ (Phase 1c)   │
                     └──────────────┘
```

### Code Fix
```python
# lib/collectors/gmail.py - ensure transform outputs correct schema

def transform(self, raw_data: Dict) -> List[Dict]:
    """Transform Gmail threads to communications table schema."""
    now = datetime.now().isoformat()
    transformed = []
    
    for thread in raw_data.get('threads', []):
        thread_id = thread.get('id')
        if not thread_id:
            continue
        
        # Get full message content if available
        body = thread.get('body', '') or thread.get('snippet', '') or ''
        
        transformed.append({
            'id': f"gmail_{thread_id}",
            'source': 'gmail',  # NOT 'email' - must match query in autonomous_loop
            'source_id': thread_id,
            'thread_id': thread_id,
            'from_address': self._extract_from(thread),
            'to_addresses': '[]',
            'subject': thread.get('subject', '(no subject)'),
            'snippet': body[:500],  # Store more content for commitment extraction
            'body': body,  # Full body if available
            'priority': self._compute_priority(thread),
            'requires_response': 1 if self._needs_response(thread) else 0,
            'processed': 0,  # CRITICAL: must be 0 for commitment extraction
            'created_at': self._parse_date(thread.get('date', '')),
            'updated_at': now
        })
    
    return transformed
```

### Also Fix: Autonomous Loop Query
```python
# lib/autonomous_loop.py - _process_commitment_truth()
# Current query uses source = 'email', but collector stores source = 'gmail'

emails = self.store.query("""
    SELECT * FROM communications 
    WHERE source IN ('gmail', 'email')  # Accept both
    AND processed = 0
    AND created_at >= datetime('now', '-1 day')
    LIMIT 50
""")
```

### Test Criteria
```python
# After fix:
from lib.state_store import get_store
store = get_store()
count = store.query("SELECT COUNT(*) as c FROM communications WHERE source = 'gmail'")[0]['c']
assert count > 0, "Gmail emails should be in communications table"
```

### Files Changed
- `lib/collectors/gmail.py`
- `lib/autonomous_loop.py`

---

## Fix #3: Commitment Deduplication (HIGH)

### Problem
Detector extracts duplicates and partial matches like ". Can you please..."

### Current Deduplication (weak)
```python
def _deduplicate(items):
    # Uses substring matching - catches overlapping extractions
    for seen in seen_texts:
        if normalized in seen or seen in normalized:
            is_duplicate = True
```

### Fix
```python
# lib/commitment_truth/detector.py

import re

def _clean_text(text: str) -> str:
    """Clean extracted text before storing."""
    # Remove leading punctuation and whitespace
    text = re.sub(r'^[\s\.\,\;\:\!\?\-]+', '', text)
    # Remove trailing incomplete sentences
    text = re.sub(r'\s+\w{1,3}$', '', text)  # Remove trailing short words
    # Normalize whitespace
    text = ' '.join(text.split())
    return text.strip()

def _deduplicate(items: List[DetectedCommitment]) -> List[DetectedCommitment]:
    """Remove duplicate/overlapping detections."""
    if not items:
        return items
    
    # Sort by confidence descending, then by length descending
    items.sort(key=lambda x: (x.confidence, len(x.text)), reverse=True)
    
    unique = []
    seen_normalized = set()
    
    for item in items:
        # Clean the text
        cleaned = _clean_text(item.text)
        
        # Skip too short
        if len(cleaned) < 15:
            continue
        
        # Normalize for comparison
        normalized = cleaned.lower().strip()
        
        # Skip if we've seen very similar text
        is_dup = False
        for seen in seen_normalized:
            # Use ratio instead of substring
            similarity = _similarity_ratio(normalized, seen)
            if similarity > 0.8:
                is_dup = True
                break
        
        if not is_dup:
            item.text = cleaned  # Store cleaned version
            unique.append(item)
            seen_normalized.add(normalized)
    
    return unique

def _similarity_ratio(a: str, b: str) -> float:
    """Simple similarity ratio based on common words."""
    words_a = set(a.split())
    words_b = set(b.split())
    if not words_a or not words_b:
        return 0
    intersection = len(words_a & words_b)
    union = len(words_a | words_b)
    return intersection / union if union > 0 else 0
```

### Test Criteria
```python
# After fix:
from lib.commitment_truth.detector import extract_all
result = extract_all("""
I'll send the report by Friday.
Can you please review this by tomorrow?
""")
# Should extract exactly 2 commitments, not 4-5 with fragments
assert result['total'] == 2
```

### Files Changed
- `lib/commitment_truth/detector.py`

---

## Fix #4: Client-Project Linking (HIGH)

### Problem
Auto-linking matched only 3/15 projects because naming conventions differ.

### Current Approach (too strict)
```python
# Only matches "ClientName:" or "ClientName -" prefixes
if project_lower.startswith(client_name + ':')
```

### Fix: Multi-Strategy Matching
```python
# lib/client_truth/linker.py

def auto_link_by_name(self) -> Dict:
    """
    Auto-link projects to clients using multiple strategies:
    1. Exact prefix match (ClientName:)
    2. Word boundary match (ClientName appears as whole word)
    3. Fuzzy match (>80% similarity on first 2 words)
    """
    results = {'linked': 0, 'already_linked': 0, 'no_match': 0, 'details': []}
    
    projects = self.store.query("SELECT id, name FROM projects")
    clients = self.store.query("SELECT id, name FROM clients")
    
    # Build client lookup with normalized names
    client_lookup = {}
    for c in clients:
        name = c['name'].lower().strip()
        # Store multiple variations
        client_lookup[name] = c['id']
        # Also store first word (often company name)
        first_word = name.split()[0] if name.split() else name
        if len(first_word) >= 4:
            client_lookup[first_word] = c['id']
    
    for project in projects:
        # Skip if already linked
        existing = self.store.query(
            "SELECT * FROM client_projects WHERE project_id = ?",
            [project['id']]
        )
        if existing:
            results['already_linked'] += 1
            continue
        
        project_name = project['name'].lower().strip()
        matched_client = None
        match_method = None
        
        # Strategy 1: Prefix match
        for client_name, client_id in client_lookup.items():
            if project_name.startswith(client_name + ':') or \
               project_name.startswith(client_name + ' -') or \
               project_name.startswith(client_name + ' |') or \
               project_name.startswith(client_name + ' '):
                matched_client = client_id
                match_method = 'prefix'
                break
        
        # Strategy 2: Word boundary match
        if not matched_client:
            project_words = set(re.findall(r'\b\w+\b', project_name))
            for client_name, client_id in client_lookup.items():
                client_words = set(re.findall(r'\b\w+\b', client_name))
                # If all client words appear in project name
                if client_words and client_words.issubset(project_words):
                    matched_client = client_id
                    match_method = 'word_boundary'
                    break
        
        # Strategy 3: First word match (common for "Sixt: Campaign" -> "Sixt")
        if not matched_client:
            first_project_word = project_name.split(':')[0].split('-')[0].strip()
            if first_project_word in client_lookup:
                matched_client = client_lookup[first_project_word]
                match_method = 'first_word'
        
        if matched_client:
            success, msg = self.link_project_to_client(project['id'], matched_client)
            if success:
                results['linked'] += 1
                results['details'].append({
                    'project': project['name'],
                    'client_id': matched_client,
                    'method': match_method
                })
        else:
            results['no_match'] += 1
    
    return results
```

### Also: Link Tasks to Clients via Projects
```python
# New method in linker.py

def propagate_client_to_tasks(self) -> Dict:
    """
    For tasks that have a project, inherit the client from client_projects.
    """
    updated = 0
    
    # Get tasks with projects but no client
    tasks = self.store.query("""
        SELECT t.id, t.project FROM tasks t
        WHERE t.project IS NOT NULL 
        AND t.project != ''
        AND (t.client_id IS NULL OR t.client_id = '')
    """)
    
    for task in tasks:
        # Find project by name
        project = self.store.query(
            "SELECT id FROM projects WHERE name LIKE ?",
            [f"%{task['project']}%"]
        )
        if not project:
            continue
        
        # Get client for project
        link = self.store.query(
            "SELECT client_id FROM client_projects WHERE project_id = ?",
            [project[0]['id']]
        )
        if link:
            self.store.query(
                "UPDATE tasks SET client_id = ? WHERE id = ?",
                [link[0]['client_id'], task['id']]
            )
            updated += 1
    
    return {'tasks_updated': updated}
```

### Test Criteria
```python
# After fix:
linker = ClientLinker()
result = linker.auto_link_by_name()
assert result['linked'] >= 10  # Should match most of the 15 projects
```

### Files Changed
- `lib/client_truth/linker.py`

---

## Fix #5: Notifications Schema (MEDIUM)

### Problem
Query for `status` column fails - schema mismatch.

### Current Schema (check)
```sql
PRAGMA table_info(notifications);
```

### Fix: Add Missing Column
```python
# lib/state_store.py - in _init_schema()

CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    body TEXT,
    priority TEXT DEFAULT 'normal',
    category TEXT,
    status TEXT DEFAULT 'pending',  -- ENSURE THIS EXISTS
    channel TEXT,
    delivered_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

### Migration (if table exists without column)
```python
# Add to state_store.py after CREATE TABLE statements

# Migration: add status column if missing
try:
    conn.execute("ALTER TABLE notifications ADD COLUMN status TEXT DEFAULT 'pending'")
except:
    pass  # Column already exists
```

### Files Changed
- `lib/state_store.py`

---

## Fix #6: Calendar Events → Blocks Sync (MEDIUM)

### Problem
Events exist in `events` table but aren't being used to generate blocks.

### Current Flow (broken)
```
calendar_collector.py → events table → ??? → time_blocks
```

### Fix: Wire CalendarSync into Autonomous Loop
```python
# lib/autonomous_loop.py - in _process_time_truth()

def _process_time_truth(self) -> Dict:
    from datetime import date, timedelta
    from lib.time_truth import CalendarSync, Scheduler
    
    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    
    results = {
        'date': today,
        'blocks_created': 0,
        'blocks_total': 0,
        'tasks_scheduled': 0
    }
    
    try:
        calendar_sync = CalendarSync(self.store)
        
        # Generate blocks for today AND tomorrow
        for target_date in [today, tomorrow]:
            # Get events from events table
            events = self.store.query("""
                SELECT * FROM events 
                WHERE date(start_time) = ?
            """, [target_date])
            
            # Generate blocks (this now creates full workday)
            blocks = calendar_sync.generate_available_blocks(
                target_date, 
                events=events,
                lane='ops'
            )
            results['blocks_created'] += len(blocks)
        
        # Run scheduler
        scheduler = Scheduler(self.store)
        schedule_results = scheduler.schedule_unscheduled(today)
        results['tasks_scheduled'] = len([r for r in schedule_results if r.success])
        results['blocks_total'] = len(scheduler.block_manager.get_all_blocks(today))
        
        # Validate
        validation = scheduler.validate_schedule(today)
        results['valid'] = validation.valid
        
    except Exception as e:
        logger.error(f"Time Truth error: {e}")
        results['error'] = str(e)
    
    return results
```

### Test Criteria
```python
# After fix, for a day with 3 meetings:
# Expected: (9 work hours - 3 meeting hours) / 1 hour = 6 available blocks
blocks = manager.get_all_blocks("2026-02-03")
assert len(blocks) >= 6
```

### Files Changed
- `lib/autonomous_loop.py`
- `lib/time_truth/calendar_sync.py`

---

## Fix #7: Manual UI Controls (MEDIUM)

### Problem
No way to manually schedule tasks or link clients in dashboard.

### Solution: Add Action Buttons

```html
<!-- ui/index.html - in task row template -->

<button onclick="scheduleTask('${task.id}')" 
        class="text-xs text-blue-600 hover:underline"
        title="Schedule into next available block">
    📅 Schedule
</button>

<button onclick="linkTaskToClient('${task.id}')" 
        class="text-xs text-green-600 hover:underline"
        title="Link to client">
    🔗 Link
</button>
```

```javascript
// ui/index.html - add functions

async function scheduleTask(taskId) {
    const today = new Date().toISOString().split('T')[0];
    const response = await fetch(`${API_BASE}/time/schedule?task_id=${taskId}&date=${today}`, {
        method: 'POST'
    });
    const result = await response.json();
    if (result.success) {
        showToast(`Scheduled into block ${result.block_id}`);
        fetchTasks();
    } else {
        showToast(`Failed: ${result.message}`, 'error');
    }
}

async function linkTaskToClient(taskId) {
    // Show client picker modal
    const clients = await fetch(`${API_BASE}/clients?limit=50`).then(r => r.json());
    const clientId = await showClientPicker(clients.items);
    if (!clientId) return;
    
    const response = await fetch(`${API_BASE}/tasks/${taskId}/client`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({client_id: clientId})
    });
    const result = await response.json();
    if (result.success) {
        showToast('Task linked to client');
        fetchTasks();
    }
}
```

### New API Endpoint Needed
```python
# api/server.py

@app.post("/api/tasks/{task_id}/client")
async def set_task_client(task_id: str, client_id: str):
    """Set the client for a task."""
    task = store.get('tasks', task_id)
    if not task:
        return {'success': False, 'message': 'Task not found'}
    
    store.query(
        "UPDATE tasks SET client_id = ?, updated_at = ? WHERE id = ?",
        [client_id, datetime.now().isoformat(), task_id]
    )
    
    return {'success': True, 'message': f'Task linked to client {client_id}'}
```

### Files Changed
- `ui/index.html`
- `api/server.py`

---

## Fix #8: Stability Tracking (LOW)

### Problem
No table tracking tier stability for unlock criteria.

### Solution
```sql
-- Add to state_store.py

CREATE TABLE IF NOT EXISTS tier_stability (
    id TEXT PRIMARY KEY,
    tier INTEGER NOT NULL,
    date TEXT NOT NULL,
    stable BOOLEAN DEFAULT 1,
    issues TEXT,
    metrics TEXT,
    created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_tier_stability_date 
ON tier_stability(tier, date);
```

```python
# lib/stability_tracker.py (new file)

class StabilityTracker:
    def record_day(self, tier: int, stable: bool, issues: List[str], metrics: Dict):
        """Record stability for a tier on a day."""
        today = date.today().isoformat()
        self.store.insert('tier_stability', {
            'id': f"stability_{tier}_{today}",
            'tier': tier,
            'date': today,
            'stable': 1 if stable else 0,
            'issues': json.dumps(issues),
            'metrics': json.dumps(metrics),
            'created_at': datetime.now().isoformat()
        })
    
    def get_stable_days(self, tier: int) -> int:
        """Count consecutive stable days for a tier."""
        rows = self.store.query("""
            SELECT date, stable FROM tier_stability
            WHERE tier = ?
            ORDER BY date DESC
            LIMIT 30
        """, [tier])
        
        count = 0
        for row in rows:
            if row['stable']:
                count += 1
            else:
                break
        return count
    
    def can_unlock_tier(self, tier: int, required_days: int = 7) -> bool:
        """Check if a tier can be unlocked."""
        previous_tier = tier - 1
        if previous_tier < 0:
            return True
        return self.get_stable_days(previous_tier) >= required_days
```

### Files Changed
- `lib/state_store.py`
- `lib/stability_tracker.py` (new)

---

## Fix #9: Nightly Cron for Rollover (LOW)

### Problem
Rollover logic exists but isn't scheduled.

### Solution: Add Cron Job via Clawdbot
```yaml
# Add to clawdbot config or HEARTBEAT.md instruction

cron:
  - id: time_os_rollover
    schedule: "0 6 * * *"  # 6 AM daily
    text: |
      Run Time OS nightly rollover:
      cd ~/clawd/moh_time_os && source .venv/bin/activate && \
      python3 -c "from lib.time_truth import Rollover; r=Rollover(); print(r.run_nightly())"
```

### Alternative: Add to Autonomous Loop
```python
# lib/autonomous_loop.py - at start of run_cycle()

def run_cycle(self):
    # Check if we should run rollover (once per day, before 9 AM)
    now = datetime.now()
    if now.hour < 9:
        last_rollover = self._get_last_rollover_date()
        if last_rollover != date.today().isoformat():
            self._run_rollover()
```

### Files Changed
- `lib/autonomous_loop.py` or Clawdbot cron config

---

## Execution Order

| Priority | Fix | Effort | Impact |
|----------|-----|--------|--------|
| 1 | Block Generation | 30 min | Unlocks scheduling |
| 2 | Gmail Pipeline | 30 min | Unlocks commitments |
| 3 | Commitment Dedup | 20 min | Cleans data |
| 4 | Client-Project Linking | 30 min | Enables health calc |
| 5 | Notifications Schema | 10 min | Fixes errors |
| 6 | Calendar → Blocks | 20 min | Full day coverage |
| 7 | Manual UI | 45 min | User control |
| 8 | Stability Tracking | 30 min | Unlock criteria |
| 9 | Nightly Cron | 15 min | Automation |

**Total: ~4 hours**

---

## Validation Checklist

After all fixes:

```python
# Run this to validate
from lib.state_store import get_store
store = get_store()

# 1. Blocks
blocks = store.query("SELECT COUNT(*) as c FROM time_blocks WHERE date = date('now')")[0]['c']
assert blocks >= 6, f"Expected 6+ blocks, got {blocks}"

# 2. Scheduled tasks
scheduled = store.query("SELECT COUNT(*) as c FROM tasks WHERE scheduled_block_id IS NOT NULL")[0]['c']
assert scheduled >= 10, f"Expected 10+ scheduled, got {scheduled}"

# 3. Communications
comms = store.query("SELECT COUNT(*) as c FROM communications WHERE source = 'gmail'")[0]['c']
assert comms > 0, f"Expected gmail data, got {comms}"

# 4. Clean commitments
commits = store.query("SELECT * FROM commitments")
for c in commits:
    assert len(c['text']) >= 15, f"Commitment too short: {c['text']}"
    assert not c['text'].startswith('.'), f"Commitment starts with punctuation: {c['text']}"

# 5. Client links
links = store.query("SELECT COUNT(*) as c FROM client_projects")[0]['c']
assert links >= 10, f"Expected 10+ project-client links, got {links}"

# 6. Task-client coverage
coverage = store.query("""
    SELECT COUNT(*) * 100.0 / (SELECT COUNT(*) FROM tasks) as pct 
    FROM tasks WHERE client_id IS NOT NULL
""")[0]['pct']
assert coverage >= 80, f"Expected 80%+ task-client coverage, got {coverage}%"

print("✓ All validations passed")
```

---

## Architecture After Fixes

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           AUTONOMOUS LOOP                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  COLLECT ──► TIME TRUTH ──► COMMITMENT ──► CAPACITY ──► CLIENT          │
│     │            │              │             │            │            │
│     ▼            ▼              ▼             ▼            ▼            │
│  ┌──────┐   ┌─────────┐   ┌──────────┐  ┌─────────┐  ┌─────────┐       │
│  │events│   │ blocks  │   │commitments│  │capacity │  │ health  │       │
│  │comms │   │(full day│   │(cleaned)  │  │  lanes  │  │ scores  │       │
│  │tasks │   │ 6-9/day)│   │           │  │         │  │         │       │
│  └──────┘   └─────────┘   └──────────┘  └─────────┘  └─────────┘       │
│                 │                                          │            │
│                 ▼                                          ▼            │
│           ┌──────────┐                              ┌───────────┐       │
│           │scheduled │◄─────────────────────────────│ client_   │       │
│           │  tasks   │                              │ projects  │       │
│           │ (10+/day)│                              │ (15 links)│       │
│           └──────────┘                              └───────────┘       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Next: Tier 4 (Financial Truth)

After these fixes are validated, Tier 4 can be built:

1. **Xero sync** - AR aging, invoices, payments
2. **Financial health** - integrate into client health score
3. **Alerts** - overdue invoices, payment patterns
4. **Dashboard** - AR overview, aging buckets

But first: **fix the pipes so data flows**.
