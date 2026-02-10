# MOH Time OS — Architecture Fixes

## Problem Summary

| Issue | Current State | Target State |
|-------|---------------|--------------|
| Task duration | 100% = 60min default | Lane-based + Asana custom fields |
| Task assignees | 93.7% missing | Accept reality + infer from project |
| Task due dates | 85.4% missing | Inherit from project/section |
| Project owners | 100% missing | Infer from task assignees + manual |
| Client tiers | 100% = "C" default | Auto-compute from revenue |
| Project→Client | 11% linked | Fuzzy match + manual mapping |
| Comms→Client | 15% linked | Domain expansion + thread inference |
| Health scores | 4 weak factors | 8 weighted factors |
| Commitments | 3 extracted | LLM extraction |

---

## Architecture: Three Layers

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        LAYER 1: DATA ENRICHMENT                              │
│                     (Runs during collection/normalization)                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1.1 Asana Field Expansion                                                   │
│  1.2 Duration Inference Engine                                               │
│  1.3 Project Owner Inference                                                 │
│  1.4 Client-Project Linker                                                   │
│  1.5 Client Tier Calculator                                                  │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                        LAYER 2: RELATIONSHIP INFERENCE                       │
│                     (Runs after normalization)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  2.1 Task→Project Inheritance (due dates, assignees)                         │
│  2.2 Comms→Client Thread Propagation                                         │
│  2.3 Project→Client Fuzzy Matching                                           │
│  2.4 Commitment Extraction (LLM)                                             │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                        LAYER 3: SCORING & WEIGHTING                          │
│                     (Runs before snapshot generation)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  3.1 Health Score v2 (8 factors, weighted)                                   │
│  3.2 Capacity Reality Engine (calendar + lane baselines)                     │
│  3.3 Priority Weighting (tier × urgency × impact)                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Layer 1: Data Enrichment

### 1.1 Asana Field Expansion

**Problem:** Asana API returns minimal fields. Need custom fields.

**Solution:**
```python
# lib/collectors/asana.py - expand opt_fields

TASK_FIELDS = [
    'gid', 'name', 'notes', 'completed', 'due_on', 'due_at',
    'assignee', 'assignee.name',
    'projects', 'projects.name',
    'memberships.section', 'memberships.section.name',
    'custom_fields',  # <-- ADD THIS
    'tags', 'tags.name',
    'created_at', 'modified_at',
    'start_on',  # <-- ADD: for duration inference
    'num_subtasks',  # <-- ADD: complexity signal
]
```

**Custom field mapping:**
```python
# config/asana_custom_fields.yaml
custom_field_gids:
  time_estimate: "1234567890"  # Your Asana custom field GID
  effort_level: "1234567891"   # Low/Medium/High
  client_name: "1234567892"    # If you tag tasks with client
```

**Location:** `lib/collectors/asana.py`

---

### 1.2 Duration Inference Engine

**Problem:** 3,748 tasks × 60min default = meaningless capacity.

**Solution:** Cascading inference with confidence tracking.

```python
# lib/enrichment/duration_inference.py

class DurationInferenceEngine:
    """
    Infers task duration using cascading rules.
    Returns (minutes, confidence, source).
    """

    # Lane-based defaults (from hrmny patterns)
    LANE_DEFAULTS = {
        'ops': 30,       # Ops tasks are typically quick
        'finance': 45,   # Finance tasks moderate
        'people': 60,    # HR tasks vary
        'growth': 90,    # Growth initiatives longer
        'client': 60,    # Client work moderate
        'admin': 20,     # Admin quick
        'music': 120,    # Creative work longer
        'creative': 120,
    }

    # Keyword signals in task title
    DURATION_SIGNALS = {
        'quick': 15,
        'review': 30,
        'check': 15,
        'send': 10,
        'draft': 60,
        'write': 90,
        'create': 120,
        'build': 180,
        'strategy': 240,
        'workshop': 180,
        'meeting': 60,
        'call': 30,
    }

    def infer(self, task: Dict) -> Tuple[int, str, str]:
        """
        Returns (duration_min, confidence, source).
        Confidence: HIGH, MED, LOW
        """
        # 1. Asana custom field (if present)
        custom = task.get('custom_fields', {})
        if custom.get('time_estimate'):
            return (custom['time_estimate'], 'HIGH', 'asana_custom_field')

        # 2. Start date → due date span (if both present)
        if task.get('start_on') and task.get('due_on'):
            days = (parse_date(task['due_on']) - parse_date(task['start_on'])).days
            if days > 0:
                # Assume 4 productive hours per day
                return (days * 240, 'MED', 'date_span')

        # 3. Keyword signals in title
        title = (task.get('title') or '').lower()
        for keyword, minutes in self.DURATION_SIGNALS.items():
            if keyword in title:
                return (minutes, 'MED', f'keyword:{keyword}')

        # 4. Subtask count (complexity signal)
        subtasks = task.get('num_subtasks', 0)
        if subtasks >= 5:
            return (180, 'LOW', 'subtask_complexity')
        elif subtasks >= 2:
            return (90, 'LOW', 'subtask_complexity')

        # 5. Lane-based default
        lane = (task.get('lane') or 'ops').lower()
        default = self.LANE_DEFAULTS.get(lane, 60)
        return (default, 'LOW', f'lane_default:{lane}')
```

**Integration point:** Called in `lib/normalizer.py` after lane assignment.

---

### 1.3 Project Owner Inference

**Problem:** 100% projects have no owner.

**Solution:** Infer from most frequent task assignee.

```python
# lib/enrichment/project_owner_inference.py

class ProjectOwnerInference:
    """
    Infers project owner from task assignees.
    Uses: most frequent assignee with recent activity.
    """

    def infer_owner(self, project_id: str) -> Optional[str]:
        """Returns inferred owner name or None."""

        # Query: most common assignee on project tasks
        result = self._query_one("""
            SELECT assignee, COUNT(*) as cnt,
                   MAX(updated_at) as last_activity
            FROM tasks
            WHERE project_id = ?
              AND assignee IS NOT NULL
              AND assignee != ''
              AND status NOT IN ('done', 'completed')
            GROUP BY assignee
            ORDER BY cnt DESC, last_activity DESC
            LIMIT 1
        """, (project_id,))

        if result and result['cnt'] >= 2:  # At least 2 tasks
            return result['assignee']

        return None

    def run_batch(self):
        """Update all projects with inferred owners."""
        projects = self._query_all("SELECT id FROM projects WHERE owner IS NULL")

        updated = 0
        for proj in projects:
            owner = self.infer_owner(proj['id'])
            if owner:
                self._execute(
                    "UPDATE projects SET owner = ?, owner_source = 'inferred' WHERE id = ?",
                    (owner, proj['id'])
                )
                updated += 1

        return {'updated': updated, 'total': len(projects)}
```

**Schema change:** Add `owner_source` column to track provenance.

---

### 1.4 Client-Project Linker (Fuzzy Match)

**Problem:** Only 11% projects linked to clients.

**Solution:** Multi-pass fuzzy matching.

```python
# lib/enrichment/client_project_linker.py

class ClientProjectLinker:
    """
    Links projects to clients using fuzzy matching.

    Pass 1: Exact substring match (project name contains client name)
    Pass 2: Fuzzy match (>85% similarity)
    Pass 3: Invoice-based (project name matches invoice client)
    Pass 4: Manual override table
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._load_clients()
        self._load_manual_overrides()

    def _load_clients(self):
        """Load client names for matching."""
        rows = self._query_all("SELECT id, name FROM clients")
        self.clients = {r['id']: r['name'] for r in rows}

        # Build normalized lookup
        self.client_lookup = {}
        for cid, name in self.clients.items():
            normalized = self._normalize(name)
            self.client_lookup[normalized] = cid

            # Also index significant words
            for word in name.split():
                if len(word) >= 4:  # Skip short words
                    self.client_lookup[self._normalize(word)] = cid

    def _normalize(self, text: str) -> str:
        """Normalize for matching."""
        return re.sub(r'[^a-z0-9]', '', text.lower())

    def match_project(self, project_name: str) -> Optional[Tuple[str, str, float]]:
        """
        Returns (client_id, match_type, confidence) or None.
        """
        normalized = self._normalize(project_name)

        # Pass 1: Manual override
        override = self.overrides.get(project_name)
        if override:
            return (override, 'manual', 1.0)

        # Pass 2: Exact substring
        for cid, cname in self.clients.items():
            if self._normalize(cname) in normalized:
                return (cid, 'substring', 0.9)

        # Pass 3: Fuzzy match (using rapidfuzz if available)
        try:
            from rapidfuzz import fuzz
            best_match = None
            best_score = 0

            for cid, cname in self.clients.items():
                score = fuzz.token_set_ratio(project_name, cname)
                if score > best_score and score >= 85:
                    best_score = score
                    best_match = cid

            if best_match:
                return (best_match, 'fuzzy', best_score / 100)
        except ImportError:
            pass

        # Pass 4: Invoice client name match
        invoice_clients = self._query_all(
            "SELECT DISTINCT client_name FROM invoices WHERE client_name IS NOT NULL"
        )
        for ic in invoice_clients:
            if self._normalize(ic['client_name']) in normalized:
                # Find matching client
                client = self._query_one(
                    "SELECT id FROM clients WHERE name LIKE ?",
                    (f"%{ic['client_name']}%",)
                )
                if client:
                    return (client['id'], 'invoice', 0.85)

        return None

    def run_batch(self) -> Dict:
        """Link all unlinked projects."""
        projects = self._query_all(
            "SELECT id, name FROM projects WHERE client_id IS NULL"
        )

        linked = 0
        for proj in projects:
            match = self.match_project(proj['name'])
            if match:
                client_id, match_type, confidence = match
                self._execute("""
                    UPDATE projects
                    SET client_id = ?,
                        client_link_source = ?,
                        client_link_confidence = ?
                    WHERE id = ?
                """, (client_id, match_type, confidence, proj['id']))
                linked += 1

        return {'linked': linked, 'total': len(projects)}
```

**Manual override table:**
```sql
CREATE TABLE IF NOT EXISTS project_client_overrides (
    project_id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    created_by TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (client_id) REFERENCES clients(id)
);
```

---

### 1.5 Client Tier Calculator

**Problem:** All clients = Tier C (default).

**Solution:** Auto-compute from revenue + project count.

```python
# lib/enrichment/client_tier_calculator.py

class ClientTierCalculator:
    """
    Computes client tier from financial and engagement signals.

    Tier 1 (VIP): AR > $100k OR >5 active projects
    Tier 2 (Key): AR > $25k OR >2 active projects
    Tier 3 (Standard): AR > $5k OR >0 active projects
    Tier C (Inactive): No AR, no active projects
    """

    TIER_THRESHOLDS = {
        '1': {'ar': 100000, 'projects': 5},
        '2': {'ar': 25000, 'projects': 2},
        '3': {'ar': 5000, 'projects': 0},
    }

    def compute_tier(self, client_id: str) -> Tuple[str, Dict]:
        """Returns (tier, factors)."""

        # Get AR outstanding
        ar = self._query_one("""
            SELECT COALESCE(SUM(amount), 0) as total_ar
            FROM invoices
            WHERE client_name = (SELECT name FROM clients WHERE id = ?)
              AND paid_date IS NULL
        """, (client_id,))
        total_ar = ar['total_ar'] if ar else 0

        # Get active project count
        projects = self._query_one("""
            SELECT COUNT(*) as cnt
            FROM projects
            WHERE client_id = ?
              AND status NOT IN ('completed', 'archived', 'cancelled')
        """, (client_id,))
        project_count = projects['cnt'] if projects else 0

        # Get historical revenue (last 12 months)
        revenue = self._query_one("""
            SELECT COALESCE(SUM(amount), 0) as total
            FROM invoices
            WHERE client_name = (SELECT name FROM clients WHERE id = ?)
              AND created_at >= date('now', '-12 months')
        """, (client_id,))
        annual_revenue = revenue['total'] if revenue else 0

        factors = {
            'ar_outstanding': total_ar,
            'active_projects': project_count,
            'annual_revenue': annual_revenue,
        }

        # Determine tier
        for tier, thresholds in self.TIER_THRESHOLDS.items():
            if total_ar >= thresholds['ar'] or project_count >= thresholds['projects']:
                return (tier, factors)

        return ('C', factors)

    def run_batch(self) -> Dict:
        """Update all client tiers."""
        clients = self._query_all("SELECT id FROM clients")

        tier_counts = {'1': 0, '2': 0, '3': 0, 'C': 0}
        for client in clients:
            tier, factors = self.compute_tier(client['id'])
            self._execute("""
                UPDATE clients
                SET tier = ?,
                    tier_factors = ?,
                    tier_updated_at = datetime('now')
                WHERE id = ?
            """, (tier, json.dumps(factors), client['id']))
            tier_counts[tier] += 1

        return tier_counts
```

---

## Layer 2: Relationship Inference

### 2.1 Task→Project Inheritance

**Problem:** Tasks missing due dates and assignees that exist at project level.

```python
# lib/enrichment/task_inheritance.py

class TaskInheritanceEngine:
    """
    Inherits missing task fields from project/section.
    """

    def inherit_due_dates(self):
        """
        Tasks without due_date inherit from:
        1. Section due date (if exists)
        2. Project due date (if exists)
        """
        # From project
        self._execute("""
            UPDATE tasks
            SET due_date = (
                SELECT p.due_date
                FROM projects p
                WHERE p.id = tasks.project_id
                  AND p.due_date IS NOT NULL
            ),
            due_date_source = 'inherited:project'
            WHERE due_date IS NULL
              AND project_id IS NOT NULL
              AND EXISTS (
                SELECT 1 FROM projects p
                WHERE p.id = tasks.project_id
                  AND p.due_date IS NOT NULL
              )
        """)

    def inherit_assignees(self):
        """
        Tasks without assignee inherit from project owner.
        Only if project has clear owner.
        """
        self._execute("""
            UPDATE tasks
            SET assignee = (
                SELECT p.owner
                FROM projects p
                WHERE p.id = tasks.project_id
                  AND p.owner IS NOT NULL
            ),
            assignee_source = 'inherited:project_owner'
            WHERE assignee IS NULL
              AND project_id IS NOT NULL
              AND EXISTS (
                SELECT 1 FROM projects p
                WHERE p.id = tasks.project_id
                  AND p.owner IS NOT NULL
              )
        """)
```

---

### 2.2 Comms→Client Thread Propagation

**Problem:** Only 15% comms linked. Thread siblings are unlinked.

```python
# lib/enrichment/comm_thread_linker.py

class CommThreadLinker:
    """
    Propagates client_id through email threads.
    If one email in thread is linked, link all.
    """

    def propagate(self):
        """Propagate client links through threads."""

        # Find threads where some messages have client_id
        threads = self._query_all("""
            SELECT thread_id, client_id
            FROM communications
            WHERE thread_id IS NOT NULL
              AND client_id IS NOT NULL
            GROUP BY thread_id
        """)

        updated = 0
        for thread in threads:
            result = self._execute("""
                UPDATE communications
                SET client_id = ?,
                    client_link_source = 'thread_propagation'
                WHERE thread_id = ?
                  AND client_id IS NULL
            """, (thread['client_id'], thread['thread_id']))
            updated += result.rowcount

        return {'threads_processed': len(threads), 'messages_updated': updated}
```

---

### 2.3 Commitment Extraction (LLM)

**Problem:** Regex only found 3 commitments from 488 emails.

```python
# lib/enrichment/commitment_extractor_llm.py

class LLMCommitmentExtractor:
    """
    Extracts commitments using Claude API.
    Batches emails for efficiency.
    """

    EXTRACTION_PROMPT = """
    Analyze this email and extract any commitments (promises, deadlines, action items).

    Email:
    From: {from_email}
    To: {to_email}
    Subject: {subject}
    Body: {body}

    Extract commitments in this JSON format:
    {{
      "commitments": [
        {{
          "type": "promise|request|deadline",
          "text": "exact quote from email",
          "owner": "who made/received commitment",
          "due_date": "YYYY-MM-DD or null",
          "confidence": 0.0-1.0
        }}
      ]
    }}

    Only include clear commitments. Return empty array if none found.
    """

    def extract_batch(self, emails: List[Dict], batch_size: int = 10) -> List[Dict]:
        """Extract commitments from a batch of emails."""
        commitments = []

        for email in emails:
            # Skip if already processed
            if email.get('commitment_extracted'):
                continue

            prompt = self.EXTRACTION_PROMPT.format(
                from_email=email.get('from_email', ''),
                to_email=email.get('to_email', ''),
                subject=email.get('subject', ''),
                body=(email.get('body_text', '') or '')[:2000],  # Truncate
            )

            try:
                response = self._call_claude(prompt)
                extracted = json.loads(response)

                for c in extracted.get('commitments', []):
                    commitments.append({
                        'id': f"commit_{uuid4().hex[:16]}",
                        'source_type': 'communication',
                        'source_id': email['id'],
                        'type': c['type'],
                        'text': c['text'],
                        'owner': c.get('owner'),
                        'due_date': c.get('due_date'),
                        'confidence': c.get('confidence', 0.7),
                        'client_id': email.get('client_id'),
                        'status': 'open',
                        'extracted_at': datetime.now().isoformat(),
                    })

            except Exception as e:
                self.logger.warning(f"Extraction failed for {email['id']}: {e}")

        return commitments
```

---

## Layer 3: Scoring & Weighting

### 3.1 Health Score v2

**Current:** 4 factors, commitment_score hardcoded to 75.

**New:** 8 weighted factors.

```python
# lib/scoring/health_score_v2.py

class HealthScoreV2:
    """
    Client health score with 8 weighted factors.
    """

    WEIGHTS = {
        'delivery': 0.20,      # Task completion, overdue rate
        'finance': 0.25,       # AR aging, payment patterns
        'responsiveness': 0.15, # Email response time
        'commitment': 0.15,    # Promise fulfillment
        'engagement': 0.10,    # Activity recency
        'capacity': 0.05,      # Resource allocation
        'sentiment': 0.05,     # Communication tone (future)
        'growth': 0.05,        # Revenue trend
    }

    def compute(self, client_id: str) -> Tuple[int, Dict]:
        """Returns (score 0-100, factor_breakdown)."""

        factors = {}

        # 1. Delivery (20%)
        tasks = self._query_one("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'overdue' THEN 1 ELSE 0 END) as overdue
            FROM tasks t
            JOIN projects p ON t.project_id = p.id
            WHERE p.client_id = ?
        """, (client_id,))

        if tasks and tasks['total'] > 0:
            completion_rate = tasks['completed'] / tasks['total']
            overdue_penalty = min(tasks['overdue'] * 0.1, 0.5)
            factors['delivery'] = max(0, completion_rate - overdue_penalty)
        else:
            factors['delivery'] = 0.5  # Neutral if no tasks

        # 2. Finance (25%)
        ar = self._query_one("""
            SELECT
                COALESCE(SUM(amount), 0) as total_ar,
                COALESCE(SUM(CASE WHEN due_date < date('now') THEN amount ELSE 0 END), 0) as overdue_ar
            FROM invoices
            WHERE client_name = (SELECT name FROM clients WHERE id = ?)
              AND paid_date IS NULL
        """, (client_id,))

        if ar and ar['total_ar'] > 0:
            overdue_ratio = ar['overdue_ar'] / ar['total_ar']
            factors['finance'] = max(0, 1 - overdue_ratio)
        else:
            factors['finance'] = 1.0  # No AR = healthy

        # 3. Responsiveness (15%)
        comms = self._query_one("""
            SELECT AVG(
                CASE WHEN response_time_hours IS NOT NULL
                THEN MIN(response_time_hours / 48.0, 1.0)
                ELSE 0.5 END
            ) as avg_response
            FROM communications
            WHERE client_id = ?
              AND received_at >= date('now', '-30 days')
        """, (client_id,))
        factors['responsiveness'] = 1 - (comms['avg_response'] if comms else 0.5)

        # 4. Commitment (15%)
        commits = self._query_one("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'fulfilled' THEN 1 ELSE 0 END) as fulfilled
            FROM commitments
            WHERE client_id = ?
        """, (client_id,))

        if commits and commits['total'] > 0:
            factors['commitment'] = commits['fulfilled'] / commits['total']
        else:
            factors['commitment'] = 0.75  # Neutral

        # 5. Engagement (10%)
        recent = self._query_one("""
            SELECT MAX(received_at) as last_contact
            FROM communications
            WHERE client_id = ?
        """, (client_id,))

        if recent and recent['last_contact']:
            days_ago = (datetime.now() - parse_datetime(recent['last_contact'])).days
            factors['engagement'] = max(0, 1 - (days_ago / 60))  # Decay over 60 days
        else:
            factors['engagement'] = 0.3

        # 6. Capacity (5%)
        factors['capacity'] = 0.7  # Placeholder until real capacity data

        # 7. Sentiment (5%)
        factors['sentiment'] = 0.7  # Placeholder for NLP analysis

        # 8. Growth (5%)
        revenue = self._query_one("""
            SELECT
                COALESCE(SUM(CASE WHEN created_at >= date('now', '-6 months') THEN amount END), 0) as recent,
                COALESCE(SUM(CASE WHEN created_at < date('now', '-6 months') AND created_at >= date('now', '-12 months') THEN amount END), 0) as prior
            FROM invoices
            WHERE client_name = (SELECT name FROM clients WHERE id = ?)
        """, (client_id,))

        if revenue and revenue['prior'] > 0:
            growth_rate = (revenue['recent'] - revenue['prior']) / revenue['prior']
            factors['growth'] = min(max(0.5 + growth_rate, 0), 1)
        else:
            factors['growth'] = 0.5

        # Weighted sum
        score = sum(
            factors[f] * self.WEIGHTS[f]
            for f in self.WEIGHTS
        ) * 100

        return (int(score), factors)
```

---

### 3.2 Capacity Reality Engine

**Problem:** No real capacity data.

**Solution:** Calendar-based available hours + realistic lane baselines.

```python
# lib/scoring/capacity_reality.py

class CapacityRealityEngine:
    """
    Computes realistic capacity from calendar + team data.
    """

    def compute_available_hours(self, horizon: str = 'TODAY') -> Dict:
        """
        Compute actual available hours from calendar.
        """
        if horizon == 'TODAY':
            start = datetime.combine(date.today(), time.min)
            end = datetime.combine(date.today(), time.max)
        elif horizon == 'THIS_WEEK':
            start = datetime.combine(date.today(), time.min)
            end = start + timedelta(days=7)
        else:  # NOW
            start = datetime.now()
            end = start + timedelta(hours=4)

        # Get calendar events (meetings)
        events = self._query_all("""
            SELECT start_time, end_time, is_focus_block
            FROM calendar_events
            WHERE start_time >= ? AND end_time <= ?
        """, (start.isoformat(), end.isoformat()))

        # Calculate meeting hours
        meeting_hours = sum(
            (parse_datetime(e['end_time']) - parse_datetime(e['start_time'])).total_seconds() / 3600
            for e in events
            if not e.get('is_focus_block')
        )

        # Base available hours (work hours in horizon)
        if horizon == 'TODAY':
            base_hours = 8  # 8-hour workday
        elif horizon == 'THIS_WEEK':
            base_hours = 40  # 5-day week
        else:
            base_hours = 4  # 4-hour window

        # Subtract meetings, apply buffer
        buffer_pct = 0.2
        available = (base_hours - meeting_hours) * (1 - buffer_pct)

        return {
            'base_hours': base_hours,
            'meeting_hours': meeting_hours,
            'buffer_pct': buffer_pct,
            'available_hours': max(0, available),
            'confidence': 'HIGH' if events else 'LOW',
            'why_low': [] if events else ['no calendar events found'],
        }

    def compute_hours_needed(self, horizon: str = 'TODAY') -> Dict:
        """
        Compute hours needed from tasks with duration inference.
        """
        if horizon == 'TODAY':
            date_filter = "due_date <= date('now')"
        elif horizon == 'THIS_WEEK':
            date_filter = "due_date <= date('now', '+7 days')"
        else:
            date_filter = "due_date <= datetime('now', '+4 hours')"

        tasks = self._query_all(f"""
            SELECT id, title, lane, duration_min, duration_confidence
            FROM tasks
            WHERE status NOT IN ('done', 'completed')
              AND ({date_filter} OR due_date IS NULL)
        """)

        # Sum by confidence
        hours_high = sum(t['duration_min'] / 60 for t in tasks if t.get('duration_confidence') == 'HIGH')
        hours_med = sum(t['duration_min'] / 60 for t in tasks if t.get('duration_confidence') == 'MED')
        hours_low = sum(t['duration_min'] / 60 for t in tasks if t.get('duration_confidence') in ('LOW', None))

        return {
            'total_hours': hours_high + hours_med + hours_low,
            'high_confidence_hours': hours_high,
            'med_confidence_hours': hours_med,
            'low_confidence_hours': hours_low,
            'task_count': len(tasks),
        }
```

---

## Execution Plan

### Phase 1: Schema Updates (30 min)
```sql
-- Add tracking columns
ALTER TABLE tasks ADD COLUMN duration_confidence TEXT;
ALTER TABLE tasks ADD COLUMN duration_source TEXT;
ALTER TABLE tasks ADD COLUMN assignee_source TEXT;
ALTER TABLE tasks ADD COLUMN due_date_source TEXT;

ALTER TABLE projects ADD COLUMN owner_source TEXT;
ALTER TABLE projects ADD COLUMN client_link_source TEXT;
ALTER TABLE projects ADD COLUMN client_link_confidence REAL;

ALTER TABLE clients ADD COLUMN tier_factors TEXT;
ALTER TABLE clients ADD COLUMN tier_updated_at TEXT;

ALTER TABLE communications ADD COLUMN client_link_source TEXT;
ALTER TABLE communications ADD COLUMN commitment_extracted INTEGER DEFAULT 0;

-- Manual override table
CREATE TABLE IF NOT EXISTS project_client_overrides (
    project_id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    created_by TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
```

### Phase 2: Enrichment Engines (4 hours)
1. `lib/enrichment/duration_inference.py` - 1 hour
2. `lib/enrichment/project_owner_inference.py` - 30 min
3. `lib/enrichment/client_project_linker.py` - 1 hour
4. `lib/enrichment/client_tier_calculator.py` - 30 min
5. `lib/enrichment/task_inheritance.py` - 30 min
6. `lib/enrichment/comm_thread_linker.py` - 30 min

### Phase 3: Scoring Engines (2 hours)
1. `lib/scoring/health_score_v2.py` - 1 hour
2. `lib/scoring/capacity_reality.py` - 1 hour

### Phase 4: Integration (2 hours)
1. Wire into `autonomous_loop.py`
2. Update snapshot generators
3. Add confidence indicators to UI

### Phase 5: LLM Commitment Extraction (Optional - 2 hours)
1. `lib/enrichment/commitment_extractor_llm.py`
2. Backfill recent emails
3. Wire into collection loop

---

## Expected Outcomes

| Metric | Before | After (Projected) |
|--------|--------|-------------------|
| Task duration accuracy | 0% (all defaults) | 70-80% (inferred) |
| Task assignees | 6.3% | 15-20% (inherited) |
| Task due dates | 14.6% | 40-50% (inherited) |
| Project owners | 0% | 60-70% (inferred) |
| Client tiers | 0% real | 100% auto-computed |
| Project→Client | 11% | 50-60% (fuzzy match) |
| Comms→Client | 15% | 35-45% (thread propagation) |
| Health score accuracy | Low | Medium-High |
| Commitments | 3 | 50-100 (LLM) |

---

## Files to Create

```
lib/enrichment/
├── __init__.py
├── duration_inference.py
├── project_owner_inference.py
├── client_project_linker.py
├── client_tier_calculator.py
├── task_inheritance.py
├── comm_thread_linker.py
└── commitment_extractor_llm.py

lib/scoring/
├── __init__.py
├── health_score_v2.py
└── capacity_reality.py
```
