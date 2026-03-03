# MOH Time OS — Architecture V3: Full Organizational Intelligence

## The Unlock

**Moh is workspace superadmin.** Can pull every team member's calendar via Google Workspace Admin API.

This transforms capacity from "my availability" to **organizational capacity truth**.

---

## Data Sources (Expanded)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              DATA SOURCES                                        │
└─────────────────────────────────────────────────────────────────────────────────┘

  XERO                  GOOGLE WORKSPACE (Admin)           ASANA              GMAIL
  ────                  ────────────────────────           ─────              ─────
  • Invoices            • ALL team calendars               • Projects         • Threads
  • Contacts            • ALL team emails (opt-in)         • Tasks            • Responses
  • Payments            • Directory (org chart)            • Sections         • Contacts
  • AR aging            • Groups/Teams                     • Assignees        • Sentiment
                        • Drive activity (opt)             • Due dates
                        • Meet recordings (opt)            • Comments

                              ▼ ▼ ▼ ▼ ▼
                    ┌─────────────────────────────────────────────────────────────┐
                    │                    UNIFIED DATA LAYER                        │
                    └─────────────────────────────────────────────────────────────┘
```

---

## Team Calendar Intelligence

### What We Get Per Person

```python
# lib/intelligence/team_calendar.py

class TeamCalendarIntelligence:
    """
    Pulls and analyzes calendars for all team members.
    Requires: Google Workspace Admin API with calendar read scope.
    """

    def __init__(self, workspace_domain: str = 'hrmny.co'):
        self.domain = workspace_domain
        self.admin_service = self._get_admin_service()
        self.calendar_service = self._get_calendar_service()

    def get_team_members(self) -> List[Dict]:
        """Get all users in workspace."""
        users = self.admin_service.users().list(
            domain=self.domain,
            maxResults=100,
            orderBy='email'
        ).execute()

        return [
            {
                'email': u['primaryEmail'],
                'name': u.get('name', {}).get('fullName', u['primaryEmail']),
                'department': u.get('organizations', [{}])[0].get('department'),
                'title': u.get('organizations', [{}])[0].get('title'),
                'is_suspended': u.get('suspended', False),
            }
            for u in users.get('users', [])
            if not u.get('suspended')
        ]

    def get_calendar_for_user(self, email: str, days_ahead: int = 7) -> Dict:
        """
        Get calendar events for a specific user.
        Uses domain-wide delegation (superadmin).
        """
        now = datetime.utcnow()
        end = now + timedelta(days=days_ahead)

        # Impersonate user via domain-wide delegation
        delegated_creds = self._get_delegated_creds(email)
        service = build('calendar', 'v3', credentials=delegated_creds)

        events = service.events().list(
            calendarId='primary',
            timeMin=now.isoformat() + 'Z',
            timeMax=end.isoformat() + 'Z',
            singleEvents=True,
            orderBy='startTime',
        ).execute()

        return self._parse_events(events.get('items', []), email)

    def compute_team_capacity(self, horizon: str = 'THIS_WEEK') -> Dict:
        """
        Compute capacity for entire team.

        Returns:
        {
            'total_available_hours': float,
            'total_meeting_hours': float,
            'utilization_pct': float,
            'by_person': [
                {
                    'email': str,
                    'name': str,
                    'meeting_hours': float,
                    'available_hours': float,
                    'utilization_pct': float,
                    'status': 'overloaded'|'optimal'|'underutilized',
                    'meetings': [...]
                }
            ],
            'overloaded': [...],  # >80% utilization
            'available': [...],   # <50% utilization
        }
        """
        team = self.get_team_members()
        days = 7 if horizon == 'THIS_WEEK' else 1 if horizon == 'TODAY' else 1
        base_hours = 40 if horizon == 'THIS_WEEK' else 8

        results = []
        for member in team:
            cal = self.get_calendar_for_user(member['email'], days)

            meeting_hours = cal['total_meeting_hours']
            available = max(0, base_hours - meeting_hours)
            utilization = meeting_hours / base_hours if base_hours > 0 else 0

            status = 'overloaded' if utilization > 0.8 else \
                     'underutilized' if utilization < 0.5 else 'optimal'

            results.append({
                'email': member['email'],
                'name': member['name'],
                'department': member.get('department'),
                'meeting_hours': round(meeting_hours, 1),
                'available_hours': round(available, 1),
                'utilization_pct': round(utilization * 100, 1),
                'status': status,
                'meetings': cal['meetings'][:10],  # Top 10 for display
                'external_meeting_hours': cal['external_hours'],
                'internal_meeting_hours': cal['internal_hours'],
            })

        total_available = sum(r['available_hours'] for r in results)
        total_meeting = sum(r['meeting_hours'] for r in results)

        return {
            'horizon': horizon,
            'team_size': len(results),
            'total_available_hours': round(total_available, 1),
            'total_meeting_hours': round(total_meeting, 1),
            'utilization_pct': round(total_meeting / (len(results) * base_hours) * 100, 1),
            'by_person': sorted(results, key=lambda x: -x['utilization_pct']),
            'overloaded': [r for r in results if r['status'] == 'overloaded'],
            'available': [r for r in results if r['status'] == 'underutilized'],
        }
```

---

## What This Enables

### 1. Real Capacity Dashboard

```
TEAM CAPACITY — THIS WEEK
═══════════════════════════════════════════════════════════════════════════

  TOTAL: 320h available across 10 people (avg 32h/person)

  🔴 OVERLOADED (>80%)          🟡 OPTIMAL (50-80%)         🟢 AVAILABLE (<50%)
  ─────────────────────         ──────────────────          ──────────────────
  Molham      8h avail (80%)    Ramy       16h (60%)        Mark      32h (20%)
  Jessica    10h avail (75%)    Youssef    18h (55%)        Maher     34h (15%)
                                Imad       20h (50%)        Elnaz     30h (25%)
```

### 2. Work Routing Intelligence

```python
def suggest_assignee(self, task: Dict) -> Dict:
    """
    Suggest best assignee based on:
    - Lane/skill match
    - Current capacity
    - Client relationship
    """
    lane = task.get('lane', 'ops')
    client_id = task.get('client_id')

    # Get team capacity
    capacity = self.team_calendar.compute_team_capacity('THIS_WEEK')

    # Filter by lane/skill (from team_members table)
    candidates = [
        p for p in capacity['by_person']
        if self._matches_lane(p['email'], lane)
    ]

    # Prefer people with client relationship
    if client_id:
        client_contacts = self._get_client_meeting_history(client_id)
        for c in candidates:
            if c['email'] in client_contacts:
                c['relationship_bonus'] = 10

    # Score: available_hours + relationship_bonus - current_load
    for c in candidates:
        c['score'] = (
            c['available_hours'] * 2 +
            c.get('relationship_bonus', 0) -
            c['utilization_pct'] / 10
        )

    best = max(candidates, key=lambda x: x['score'])

    return {
        'recommended': best['email'],
        'reason': f"{best['available_hours']}h available, {best['utilization_pct']}% utilized",
        'alternatives': sorted(candidates, key=lambda x: -x['score'])[1:3],
    }
```

### 3. Client Coverage Map

```python
def get_client_coverage(self, client_id: str) -> Dict:
    """
    Who from our team is meeting with this client?
    Who SHOULD be meeting with them?
    """
    client_domains = self._get_client_domains(client_id)

    # Find all meetings with this client across ALL team calendars
    coverage = {}
    for member in self.get_team_members():
        cal = self.get_calendar_for_user(member['email'], days_ahead=30)
        client_meetings = [
            m for m in cal['meetings']
            if any(d in str(m.get('attendees', [])) for d in client_domains)
        ]
        if client_meetings:
            coverage[member['email']] = {
                'meeting_count': len(client_meetings),
                'last_meeting': max(m['start'] for m in client_meetings),
                'next_meeting': min(
                    (m['start'] for m in client_meetings if m['start'] > datetime.now().isoformat()),
                    default=None
                ),
            }

    # Determine primary owner (most meetings)
    primary = max(coverage.items(), key=lambda x: x[1]['meeting_count'])[0] if coverage else None

    # Check for gaps
    days_since_last = None
    if coverage:
        last_meeting = max(c['last_meeting'] for c in coverage.values())
        days_since_last = (datetime.now() - datetime.fromisoformat(last_meeting)).days

    return {
        'client_id': client_id,
        'primary_owner': primary,
        'team_coverage': coverage,
        'days_since_last_meeting': days_since_last,
        'coverage_gap': days_since_last > 21 if days_since_last else True,
        'next_scheduled': min(
            (c['next_meeting'] for c in coverage.values() if c.get('next_meeting')),
            default=None
        ),
    }
```

### 4. Meeting Load Balancing

```python
def analyze_meeting_distribution(self) -> Dict:
    """
    Is meeting load distributed fairly?
    Who's drowning in meetings? Who's isolated?
    """
    capacity = self.compute_team_capacity('THIS_WEEK')

    meeting_hours = [p['meeting_hours'] for p in capacity['by_person']]
    avg = sum(meeting_hours) / len(meeting_hours)
    std_dev = (sum((h - avg) ** 2 for h in meeting_hours) / len(meeting_hours)) ** 0.5

    # Flag extremes
    drowning = [p for p in capacity['by_person'] if p['meeting_hours'] > avg + std_dev]
    isolated = [p for p in capacity['by_person'] if p['meeting_hours'] < avg - std_dev]

    return {
        'average_meeting_hours': round(avg, 1),
        'std_deviation': round(std_dev, 1),
        'distribution_health': 'unbalanced' if std_dev > avg * 0.5 else 'balanced',
        'drowning_in_meetings': [
            {'name': p['name'], 'hours': p['meeting_hours'], 'vs_avg': f"+{p['meeting_hours'] - avg:.0f}h"}
            for p in drowning
        ],
        'isolated': [
            {'name': p['name'], 'hours': p['meeting_hours'], 'vs_avg': f"{p['meeting_hours'] - avg:.0f}h"}
            for p in isolated
        ],
    }
```

---

## Cross-Source Intelligence (Enhanced)

Now with team calendars, the intelligence layer gets much richer:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     ORGANIZATIONAL INTELLIGENCE LAYER                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  CLIENT HEALTH = f(                                                              │
│    financial_signal,           // AR aging, payment velocity (Xero)              │
│    relationship_signal,        // meeting frequency across TEAM (Calendars)      │
│    communication_signal,       // email patterns (Gmail)                         │
│    delivery_signal,            // task completion (Asana)                        │
│    coverage_signal             // who owns this client? gaps? (Calendars)        │
│  )                                                                               │
│                                                                                  │
│  TEAM CAPACITY = f(                                                              │
│    individual_calendars[],     // each person's meeting load                     │
│    focus_blocks[],             // protected time                                 │
│    pto_events[],               // vacation, sick days                            │
│    external_vs_internal        // client-facing vs internal meetings             │
│  )                                                                               │
│                                                                                  │
│  WORK ROUTING = f(                                                               │
│    task_requirements,          // lane, skills, client                           │
│    team_capacity,              // who has time?                                  │
│    relationship_history,       // who knows this client?                         │
│    current_workload            // fair distribution                              │
│  )                                                                               │
│                                                                                  │
│  RISK DETECTION = f(                                                             │
│    client_coverage_gaps,       // no meetings scheduled with key client          │
│    capacity_crunch,            // team is overloaded, work incoming              │
│    relationship_cooling,       // dropping meeting frequency                     │
│    ar_correlation              // high AR + cooling relationship = churn risk    │
│  )                                                                               │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation: Google Workspace Admin API

### Setup Required

1. **Google Cloud Project** with:
   - Admin SDK API enabled
   - Calendar API enabled
   - Domain-wide delegation configured

2. **Service Account** with:
   - Domain-wide delegation enabled
   - Scopes:
     ```
     https://www.googleapis.com/auth/admin.directory.user.readonly
     https://www.googleapis.com/auth/calendar.readonly
     ```

3. **Credentials File**:
   ```
   config/google_service_account.json
   ```

### Collector Implementation

```python
# lib/collectors/google_workspace.py

from google.oauth2 import service_account
from googleapiclient.discovery import build

class GoogleWorkspaceCollector:
    """
    Collects data from Google Workspace Admin API.
    Requires superadmin privileges and domain-wide delegation.
    """

    SCOPES = [
        'https://www.googleapis.com/auth/admin.directory.user.readonly',
        'https://www.googleapis.com/auth/calendar.readonly',
    ]

    def __init__(self, config_path: str, store: StateStore):
        self.config_path = Path(config_path)
        self.store = store
        self.domain = 'hrmny.co'

        # Load service account credentials
        creds_file = self.config_path / 'google_service_account.json'
        self.credentials = service_account.Credentials.from_service_account_file(
            creds_file,
            scopes=self.SCOPES,
            subject='molham@hrmny.co'  # Superadmin to impersonate
        )

    def sync_team_calendars(self) -> Dict:
        """
        Sync calendars for all team members.
        """
        # Get team members
        admin_service = build('admin', 'directory_v1', credentials=self.credentials)
        users = admin_service.users().list(
            domain=self.domain,
            maxResults=100
        ).execute().get('users', [])

        results = {'synced': 0, 'errors': []}

        for user in users:
            if user.get('suspended'):
                continue

            email = user['primaryEmail']

            try:
                # Get delegated credentials for this user
                user_creds = self.credentials.with_subject(email)
                calendar_service = build('calendar', 'v3', credentials=user_creds)

                # Fetch events
                now = datetime.utcnow()
                events = calendar_service.events().list(
                    calendarId='primary',
                    timeMin=now.isoformat() + 'Z',
                    timeMax=(now + timedelta(days=14)).isoformat() + 'Z',
                    singleEvents=True,
                    orderBy='startTime',
                    maxResults=100,
                ).execute()

                # Store events
                for event in events.get('items', []):
                    self._store_event(event, email)

                results['synced'] += 1

            except Exception as e:
                results['errors'].append({'email': email, 'error': str(e)})

        return results

    def _store_event(self, event: Dict, owner_email: str):
        """Store calendar event with owner attribution."""
        event_id = f"calendar_{owner_email}_{event['id']}"

        self.store.upsert('events', {
            'id': event_id,
            'source': 'calendar',
            'source_id': event['id'],
            'owner_email': owner_email,
            'title': event.get('summary', ''),
            'start_time': event.get('start', {}).get('dateTime') or event.get('start', {}).get('date'),
            'end_time': event.get('end', {}).get('dateTime') or event.get('end', {}).get('date'),
            'attendees': json.dumps([a.get('email') for a in event.get('attendees', [])]),
            'status': event.get('status'),
            'raw': json.dumps(event),
            'updated_at': datetime.now().isoformat(),
        })
```

---

## New Dashboard Views

### Capacity Command (Real)

```
CAPACITY COMMAND — THIS WEEK
═══════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────┐
│  TEAM CAPACITY                                                          │
│  ───────────────────────────────────────────────────────────────────────│
│  Available: 287h | Meeting Load: 153h | Utilization: 35%                │
│  [████████░░░░░░░░░░░░] 35% utilized                                    │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  BY PERSON                                                              │
│  ───────────────────────────────────────────────────────────────────────│
│  🔴 Molham      [████████████████████] 80%    8h available              │
│  🔴 Jessica     [███████████████████░] 75%   10h available              │
│  🟡 Ramy        [████████████░░░░░░░░] 60%   16h available              │
│  🟡 Youssef     [███████████░░░░░░░░░] 55%   18h available              │
│  🟡 Imad        [██████████░░░░░░░░░░] 50%   20h available              │
│  🟢 Dana        [████████░░░░░░░░░░░░] 40%   24h available              │
│  🟢 Elnaz       [█████░░░░░░░░░░░░░░░] 25%   30h available              │
│  🟢 Mark        [████░░░░░░░░░░░░░░░░] 20%   32h available              │
│  🟢 Maher       [███░░░░░░░░░░░░░░░░░] 15%   34h available              │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  REBALANCING OPPORTUNITIES                                              │
│  ───────────────────────────────────────────────────────────────────────│
│  • Molham has 12 meetings with GMG → delegate 3 to Ramy (GMG contact)   │
│  • Jessica owns 8 tasks due this week, 10h available → reassign 2       │
│  • Mark has 32h available, 0 client meetings → increase exposure        │
└─────────────────────────────────────────────────────────────────────────┘
```

### Client Coverage Map

```
CLIENT COVERAGE — TOP 10 BY AR
═══════════════════════════════════════════════════════════════════════════

CLIENT              AR OUTSTANDING    PRIMARY OWNER    LAST MEETING    NEXT MEETING
────────────────────────────────────────────────────────────────────────────────────
GMG Consumer        $308,058 🔴       Molham           3 days ago      Tomorrow 2pm
Gargash             $84,772 🟡        Ramy             12 days ago     —
Super Care          $105,344 🔴       Jessica          8 days ago      Thursday
Al Khayyat          $42,851 🟡        —                45 days ago     — ⚠️ NO OWNER
FGE International   $22,400 🟡        Imad             5 days ago      Monday
Chalhoub            $38,588 🔴        Dana             21 days ago     — ⚠️ STALE
...

⚠️ COVERAGE GAPS:
• Al Khayyat ($42k AR) — no team member has met with them in 45 days
• Chalhoub ($38k AR) — last meeting 21 days ago, nothing scheduled
```

---

## Summary: V3 vs V2

| Dimension | V2 (Single Calendar) | V3 (Team Calendars) |
|-----------|----------------------|---------------------|
| Capacity source | Moh's calendar only | All 20 team calendars |
| Capacity accuracy | 1 person | Organizational truth |
| Client coverage | Inferred from meetings | Mapped per team member |
| Work routing | Generic | Capacity + relationship aware |
| Overload detection | Only for Moh | Entire team |
| Relationship ownership | Unknown | Explicit from meeting patterns |

---

## Setup Steps

1. **Google Cloud Console**
   - Create project or use existing
   - Enable Admin SDK API + Calendar API
   - Create service account with domain-wide delegation

2. **Google Workspace Admin**
   - Grant service account domain-wide delegation
   - Add required OAuth scopes

3. **Config**
   ```
   config/google_service_account.json  # Service account key
   config/workspace.yaml               # Domain, admin email
   ```

4. **Collector**
   ```
   lib/collectors/google_workspace.py  # Sync all calendars
   ```

5. **Intelligence**
   ```
   lib/intelligence/team_calendar.py   # Capacity analysis
   lib/intelligence/client_coverage.py # Coverage mapping
   lib/intelligence/work_routing.py    # Assignment recommendations
   ```
