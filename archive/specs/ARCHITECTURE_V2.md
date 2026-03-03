# MOH Time OS — Architecture V2: Signal-Based Intelligence

## Core Insight

**Stop fixing weak data. Cross-reference strong signals.**

| Source | Strength | What It Tells Us |
|--------|----------|------------------|
| Xero Invoices | STRONG | Money reality (who owes, who pays, how fast) |
| Calendar Events | STRONG | Relationship reality (who you meet, how often) |
| Gmail | STRONG | Communication reality (response patterns, threads) |
| Asana | WEAK | Work structure (projects exist, tasks exist, but sparse metadata) |

The old architecture tried to make Asana data complete. The new architecture uses Asana as a structural backbone but derives intelligence from cross-source signals.

---

## Entity Resolution: The Foundation

Everything starts with mapping entities across sources.

### Domain → Client Resolution

```python
# lib/intelligence/entity_resolver.py

class EntityResolver:
    """
    Resolves entities across data sources.

    Core mappings:
    - email domain → company → client
    - person email → person (internal/external)
    - invoice client_name → client
    - project name → client (weak)
    """

    def __init__(self, db_path: Path):
        self.db = db_path
        self._build_domain_map()
        self._build_person_map()

    def _build_domain_map(self):
        """Build domain → client mapping from multiple sources."""
        self.domain_to_client = {}

        # Source 1: Existing client_identities
        for row in self._query("SELECT domain, client_id FROM client_identities"):
            self.domain_to_client[row['domain'].lower()] = row['client_id']

        # Source 2: Invoice client names → infer domain
        for row in self._query("""
            SELECT DISTINCT client_name FROM invoices WHERE client_name IS NOT NULL
        """):
            # Normalize to domain-like format
            domain = self._name_to_domain(row['client_name'])
            if domain and domain not in self.domain_to_client:
                # Find or create client
                client = self._find_or_create_client(row['client_name'])
                self.domain_to_client[domain] = client['id']

        # Source 3: Calendar attendees (external domains we meet with)
        for row in self._query("""
            SELECT DISTINCT
                LOWER(SUBSTR(value, INSTR(value, '@')+1)) as domain
            FROM events, json_each(events.attendees)
            WHERE events.source = 'calendar'
              AND value NOT LIKE '%hrmny.co%'
              AND value LIKE '%@%.%'
        """):
            domain = row['domain']
            if domain and domain not in self.domain_to_client:
                # Mark as known external domain (may not be a client yet)
                self.domain_to_client[domain] = None  # Known but not linked

    def _name_to_domain(self, name: str) -> Optional[str]:
        """Convert company name to likely domain."""
        # "GMG Consumer LLC" → "gmg.com"
        # "Al Khayyat Investments LLC" → "alkhayyat.com" or "aki.com"
        normalized = re.sub(r'\s+(LLC|Inc|Ltd|FZE|FZCO|L\.?L\.?C\.?|FZ)\.?$', '', name, flags=re.I)
        normalized = re.sub(r'[^a-zA-Z0-9]', '', normalized).lower()
        return f"{normalized}.com" if normalized else None

    def resolve_email(self, email: str) -> Dict:
        """
        Resolve an email address to entity info.
        Returns {
            'type': 'internal'|'external'|'unknown',
            'person_name': str|None,
            'client_id': str|None,
            'company_domain': str
        }
        """
        domain = email.split('@')[-1].lower()

        # Internal?
        if domain == 'hrmny.co':
            person = self._query_one(
                "SELECT name FROM team_members WHERE email = ?", (email,)
            )
            return {
                'type': 'internal',
                'person_name': person['name'] if person else email.split('@')[0],
                'client_id': None,
                'company_domain': domain,
            }

        # Known client domain?
        client_id = self.domain_to_client.get(domain)
        return {
            'type': 'external' if client_id else 'unknown',
            'person_name': None,
            'client_id': client_id,
            'company_domain': domain,
        }
```

---

## Signal Extractors

Each source produces signals that feed into intelligence.

### Financial Signal (from Invoices)

```python
# lib/intelligence/signals/financial.py

class FinancialSignal:
    """
    Extracts financial health signals from invoice data.
    """

    def compute(self, client_id: str) -> Dict:
        """
        Returns:
        {
            'total_ar': float,
            'overdue_ar': float,
            'overdue_pct': float,
            'severe_ar': float,  # 60+ days
            'payment_velocity': float,  # avg days to pay
            'payment_trend': 'improving'|'stable'|'worsening',
            'last_payment_date': str|None,
            'risk_level': 'low'|'medium'|'high'|'critical',
            'confidence': float,
        }
        """
        client_name = self._get_client_name(client_id)

        # Get all invoices for client
        invoices = self._query("""
            SELECT
                amount,
                due_date,
                paid_date,
                created_at,
                julianday(COALESCE(paid_date, date('now'))) - julianday(due_date) as days_overdue
            FROM invoices
            WHERE client_name = ?
            ORDER BY created_at DESC
        """, (client_name,))

        if not invoices:
            return {'confidence': 0, 'risk_level': 'unknown'}

        total_ar = sum(i['amount'] for i in invoices if not i['paid_date'])
        overdue = [i for i in invoices if not i['paid_date'] and i['days_overdue'] > 0]
        overdue_ar = sum(i['amount'] for i in overdue)
        severe_ar = sum(i['amount'] for i in overdue if i['days_overdue'] > 60)

        # Payment velocity (for paid invoices)
        paid = [i for i in invoices if i['paid_date']]
        if paid:
            velocities = [i['days_overdue'] for i in paid]
            avg_velocity = sum(velocities) / len(velocities)

            # Trend: compare recent vs older
            recent = velocities[:len(velocities)//2] if len(velocities) > 2 else velocities
            older = velocities[len(velocities)//2:] if len(velocities) > 2 else []
            if older:
                recent_avg = sum(recent) / len(recent)
                older_avg = sum(older) / len(older)
                trend = 'improving' if recent_avg < older_avg - 5 else \
                        'worsening' if recent_avg > older_avg + 5 else 'stable'
            else:
                trend = 'stable'
        else:
            avg_velocity = None
            trend = 'unknown'

        # Risk level
        if severe_ar > 50000 or (overdue_ar > 0 and overdue_ar / total_ar > 0.5):
            risk = 'critical'
        elif overdue_ar > 20000 or (overdue_ar > 0 and overdue_ar / total_ar > 0.3):
            risk = 'high'
        elif overdue_ar > 0:
            risk = 'medium'
        else:
            risk = 'low'

        return {
            'total_ar': total_ar,
            'overdue_ar': overdue_ar,
            'overdue_pct': overdue_ar / total_ar if total_ar > 0 else 0,
            'severe_ar': severe_ar,
            'payment_velocity': avg_velocity,
            'payment_trend': trend,
            'last_payment_date': max((i['paid_date'] for i in paid), default=None),
            'risk_level': risk,
            'confidence': 1.0,  # Invoice data is authoritative
        }
```

### Relationship Signal (from Calendar)

```python
# lib/intelligence/signals/relationship.py

class RelationshipSignal:
    """
    Extracts relationship health signals from calendar data.
    """

    def compute(self, client_id: str) -> Dict:
        """
        Returns:
        {
            'meeting_count_30d': int,
            'meeting_count_90d': int,
            'last_meeting_date': str|None,
            'days_since_last_meeting': int|None,
            'meeting_trend': 'increasing'|'stable'|'decreasing'|'cold',
            'key_contacts': [{'email': str, 'meeting_count': int}],
            'engagement_level': 'high'|'medium'|'low'|'cold',
            'confidence': float,
        }
        """
        # Get domains for this client
        domains = self._get_client_domains(client_id)
        if not domains:
            return {'confidence': 0, 'engagement_level': 'unknown'}

        domain_pattern = '|'.join(domains)

        # Find meetings with this client
        meetings = self._query(f"""
            SELECT
                events.id,
                events.start_time,
                events.title,
                events.attendees
            FROM events
            WHERE events.source = 'calendar'
              AND events.attendees LIKE '%{domain_pattern}%'
            ORDER BY events.start_time DESC
        """)

        now = datetime.now()
        meetings_30d = [m for m in meetings if self._within_days(m['start_time'], 30)]
        meetings_90d = [m for m in meetings if self._within_days(m['start_time'], 90)]

        # Extract key contacts
        contact_counts = {}
        for m in meetings:
            for email in json.loads(m['attendees'] or '[]'):
                if any(d in email for d in domains):
                    contact_counts[email] = contact_counts.get(email, 0) + 1

        key_contacts = [
            {'email': e, 'meeting_count': c}
            for e, c in sorted(contact_counts.items(), key=lambda x: -x[1])[:5]
        ]

        # Last meeting
        last_meeting = meetings[0] if meetings else None
        days_since = None
        if last_meeting:
            last_dt = datetime.fromisoformat(last_meeting['start_time'].replace('Z', '+00:00'))
            days_since = (now - last_dt).days

        # Trend
        if len(meetings_30d) >= 3:
            trend = 'increasing' if len(meetings_30d) > len(meetings_90d) / 3 else 'stable'
        elif len(meetings_30d) >= 1:
            trend = 'stable'
        elif len(meetings_90d) >= 1:
            trend = 'decreasing'
        else:
            trend = 'cold'

        # Engagement level
        if len(meetings_30d) >= 3 or (days_since and days_since < 14):
            engagement = 'high'
        elif len(meetings_30d) >= 1 or (days_since and days_since < 30):
            engagement = 'medium'
        elif len(meetings_90d) >= 1:
            engagement = 'low'
        else:
            engagement = 'cold'

        return {
            'meeting_count_30d': len(meetings_30d),
            'meeting_count_90d': len(meetings_90d),
            'last_meeting_date': last_meeting['start_time'] if last_meeting else None,
            'days_since_last_meeting': days_since,
            'meeting_trend': trend,
            'key_contacts': key_contacts,
            'engagement_level': engagement,
            'confidence': 0.9 if meetings else 0.3,
        }
```

### Communication Signal (from Email)

```python
# lib/intelligence/signals/communication.py

class CommunicationSignal:
    """
    Extracts communication health signals from email data.
    """

    def compute(self, client_id: str) -> Dict:
        """
        Returns:
        {
            'email_count_30d': int,
            'inbound_count': int,
            'outbound_count': int,
            'avg_response_time_hours': float|None,
            'threads_open': int,
            'threads_awaiting_reply': int,  # They're waiting on us
            'last_inbound_date': str|None,
            'last_outbound_date': str|None,
            'days_since_contact': int,
            'communication_health': 'active'|'responsive'|'lagging'|'silent',
            'confidence': float,
        }
        """
        domains = self._get_client_domains(client_id)
        if not domains:
            return {'confidence': 0, 'communication_health': 'unknown'}

        # Get communications with this client
        comms = self._query("""
            SELECT
                id, thread_id, from_email, to_emails,
                received_at, created_at, subject,
                CASE WHEN from_domain IN ({domains}) THEN 'inbound' ELSE 'outbound' END as direction
            FROM communications
            WHERE client_id = ? OR from_domain IN ({domains})
            ORDER BY COALESCE(received_at, created_at) DESC
        """.format(domains=','.join(f"'{d}'" for d in domains)), (client_id,))

        if not comms:
            return {'confidence': 0.3, 'communication_health': 'silent'}

        # Counts
        now = datetime.now()
        recent = [c for c in comms if self._within_days(c['received_at'] or c['created_at'], 30)]
        inbound = [c for c in recent if c['direction'] == 'inbound']
        outbound = [c for c in recent if c['direction'] == 'outbound']

        # Thread analysis
        threads = {}
        for c in comms:
            tid = c['thread_id'] or c['id']
            if tid not in threads:
                threads[tid] = {'messages': [], 'last_direction': None}
            threads[tid]['messages'].append(c)
            threads[tid]['last_direction'] = c['direction']

        # Open threads where we need to respond
        awaiting_us = sum(1 for t in threads.values() if t['last_direction'] == 'inbound')

        # Last contact
        last_inbound = inbound[0] if inbound else None
        last_outbound = outbound[0] if outbound else None
        last_contact = comms[0]
        days_since = (now - self._parse_date(last_contact['received_at'] or last_contact['created_at'])).days

        # Health assessment
        if days_since < 7 and len(recent) >= 3:
            health = 'active'
        elif days_since < 14 and awaiting_us == 0:
            health = 'responsive'
        elif awaiting_us > 0 or days_since > 14:
            health = 'lagging'
        else:
            health = 'silent'

        return {
            'email_count_30d': len(recent),
            'inbound_count': len(inbound),
            'outbound_count': len(outbound),
            'avg_response_time_hours': None,  # TODO: compute from thread pairs
            'threads_open': len([t for t in threads.values() if len(t['messages']) > 0]),
            'threads_awaiting_reply': awaiting_us,
            'last_inbound_date': last_inbound['received_at'] if last_inbound else None,
            'last_outbound_date': last_outbound['created_at'] if last_outbound else None,
            'days_since_contact': days_since,
            'communication_health': health,
            'confidence': 0.8,
        }
```

---

## Composite Intelligence

Combine signals into actionable intelligence.

```python
# lib/intelligence/composite.py

class ClientIntelligence:
    """
    Combines signals into composite client intelligence.
    """

    def __init__(self, db_path: Path):
        self.financial = FinancialSignal(db_path)
        self.relationship = RelationshipSignal(db_path)
        self.communication = CommunicationSignal(db_path)

    def analyze(self, client_id: str) -> Dict:
        """
        Returns comprehensive client intelligence.
        """
        fin = self.financial.compute(client_id)
        rel = self.relationship.compute(client_id)
        comm = self.communication.compute(client_id)

        # Composite health score (weighted)
        weights = {
            'financial': 0.40,    # Money talks
            'relationship': 0.35, # Meetings matter
            'communication': 0.25 # Email rounds it out
        }

        health_scores = {
            'financial': self._score_financial(fin),
            'relationship': self._score_relationship(rel),
            'communication': self._score_communication(comm),
        }

        composite_score = sum(
            health_scores[k] * weights[k]
            for k in weights
        )

        # Determine tier from financial value
        tier = self._compute_tier(fin)

        # Generate attention flags
        attention_flags = []

        if fin['risk_level'] == 'critical':
            attention_flags.append({
                'type': 'ar_critical',
                'severity': 'high',
                'message': f"${fin['severe_ar']:,.0f} severely overdue (60+ days)",
            })

        if rel['engagement_level'] == 'cold' and fin['total_ar'] > 0:
            attention_flags.append({
                'type': 'relationship_cold',
                'severity': 'medium',
                'message': f"No meetings in {rel.get('days_since_last_meeting', '90+')} days, AR outstanding",
            })

        if comm['threads_awaiting_reply'] > 0:
            attention_flags.append({
                'type': 'response_needed',
                'severity': 'medium',
                'message': f"{comm['threads_awaiting_reply']} threads awaiting your reply",
            })

        # Generate recommended actions
        actions = self._generate_actions(fin, rel, comm, attention_flags)

        return {
            'client_id': client_id,
            'composite_score': round(composite_score),
            'tier': tier,
            'signals': {
                'financial': fin,
                'relationship': rel,
                'communication': comm,
            },
            'health_scores': health_scores,
            'attention_flags': attention_flags,
            'recommended_actions': actions,
            'confidence': min(fin['confidence'], rel['confidence'], comm['confidence']),
        }

    def _generate_actions(self, fin, rel, comm, flags) -> List[Dict]:
        """Generate prioritized action recommendations."""
        actions = []

        # Critical AR + upcoming meeting = discuss payment
        if fin['risk_level'] in ('critical', 'high') and rel.get('days_since_last_meeting', 999) < 14:
            actions.append({
                'action': 'discuss_payment',
                'priority': 'high',
                'message': "Upcoming meeting opportunity - address AR situation",
                'context': f"${fin['overdue_ar']:,.0f} overdue",
            })

        # Cold relationship + AR = re-engage
        if rel['engagement_level'] == 'cold' and fin['total_ar'] > 10000:
            actions.append({
                'action': 'reactivate_relationship',
                'priority': 'high',
                'message': "Schedule call to discuss account status",
                'context': f"No meetings in {rel.get('days_since_last_meeting', '90+')} days",
            })

        # Awaiting reply threads
        if comm['threads_awaiting_reply'] > 0:
            actions.append({
                'action': 'respond_to_threads',
                'priority': 'medium',
                'message': f"Respond to {comm['threads_awaiting_reply']} pending email(s)",
            })

        # Good relationship + no recent invoice = upsell opportunity
        if rel['engagement_level'] == 'high' and fin['total_ar'] < 5000:
            actions.append({
                'action': 'explore_upsell',
                'priority': 'low',
                'message': "Active engagement with low revenue - explore expansion",
            })

        return sorted(actions, key=lambda a: {'high': 0, 'medium': 1, 'low': 2}[a['priority']])
```

---

## Capacity Intelligence (from Calendar)

Real capacity based on actual calendar, not fake task hours.

```python
# lib/intelligence/capacity.py

class CapacityIntelligence:
    """
    Computes actual capacity from calendar data.

    This is REAL capacity:
    - Base hours in workday (8h)
    - Minus actual meetings scheduled
    - Minus focus blocks reserved
    - = Actual available time
    """

    def compute(self, horizon: str = 'TODAY') -> Dict:
        """
        Returns:
        {
            'base_hours': float,
            'meeting_hours': float,
            'focus_hours': float,
            'available_hours': float,
            'meetings': [{'title': str, 'start': str, 'duration_min': int}],
            'utilization_pct': float,
            'largest_free_block_hours': float,
            'confidence': float,
        }
        """
        if horizon == 'TODAY':
            start = datetime.combine(date.today(), time.min)
            end = datetime.combine(date.today(), time.max)
            base_hours = 8
        elif horizon == 'THIS_WEEK':
            start = datetime.combine(date.today(), time.min)
            end = start + timedelta(days=7)
            base_hours = 40
        else:  # NOW (4h window)
            start = datetime.now()
            end = start + timedelta(hours=4)
            base_hours = 4

        events = self._query("""
            SELECT id, title, start_time, end_time, attendees
            FROM events
            WHERE source = 'calendar'
              AND start_time >= ?
              AND start_time <= ?
            ORDER BY start_time
        """, (start.isoformat(), end.isoformat()))

        meeting_hours = 0
        focus_hours = 0
        meetings = []

        for e in events:
            try:
                e_start = datetime.fromisoformat(e['start_time'].replace('Z', '+00:00'))
                e_end = datetime.fromisoformat(e['end_time'].replace('Z', '+00:00'))
                duration = (e_end - e_start).total_seconds() / 3600

                is_focus = 'focus' in e['title'].lower() or 'block' in e['title'].lower()

                if is_focus:
                    focus_hours += duration
                else:
                    meeting_hours += duration
                    meetings.append({
                        'title': e['title'],
                        'start': e['start_time'],
                        'duration_min': int(duration * 60),
                        'attendees': len(json.loads(e['attendees'] or '[]')),
                    })
            except:
                pass

        available = max(0, base_hours - meeting_hours - focus_hours)
        utilization = (meeting_hours + focus_hours) / base_hours if base_hours > 0 else 0

        # Find largest free block
        largest_free = self._find_largest_free_block(events, start, end)

        return {
            'base_hours': base_hours,
            'meeting_hours': round(meeting_hours, 1),
            'focus_hours': round(focus_hours, 1),
            'available_hours': round(available, 1),
            'meetings': meetings,
            'utilization_pct': round(utilization * 100, 1),
            'largest_free_block_hours': round(largest_free, 1),
            'confidence': 1.0 if events else 0.5,
        }
```

---

## Attention Queue

The ultimate output: what should you pay attention to NOW?

```python
# lib/intelligence/attention.py

class AttentionQueue:
    """
    Generates prioritized attention queue from all signals.

    This is what the dashboard shows first.
    """

    def generate(self) -> List[Dict]:
        """
        Returns prioritized list of attention items.
        """
        items = []

        # 1. Critical AR situations
        critical_ar = self._query("""
            SELECT client_name, SUM(amount) as overdue
            FROM invoices
            WHERE paid_date IS NULL
              AND due_date < date('now', '-60 days')
            GROUP BY client_name
            HAVING overdue > 20000
            ORDER BY overdue DESC
        """)

        for row in critical_ar:
            client = self._find_client(row['client_name'])
            rel = self.relationship.compute(client['id']) if client else {}

            items.append({
                'type': 'ar_critical',
                'priority': 100,  # Highest
                'entity_type': 'client',
                'entity_id': client['id'] if client else None,
                'entity_name': row['client_name'],
                'headline': f"${row['overdue']:,.0f} severely overdue",
                'context': f"Last meeting: {rel.get('days_since_last_meeting', '?')} days ago",
                'action': 'Review AR and schedule call',
            })

        # 2. Meetings in next 24h needing prep
        upcoming = self._query("""
            SELECT title, start_time, attendees
            FROM events
            WHERE source = 'calendar'
              AND start_time BETWEEN datetime('now') AND datetime('now', '+24 hours')
              AND attendees NOT LIKE '%hrmny.co%' ONLY  -- external meetings
            ORDER BY start_time
        """)

        for event in upcoming:
            external_domains = self._extract_external_domains(event['attendees'])
            client = self._find_client_by_domains(external_domains)

            if client:
                fin = self.financial.compute(client['id'])
                if fin['overdue_ar'] > 0:
                    items.append({
                        'type': 'meeting_prep',
                        'priority': 80,
                        'entity_type': 'event',
                        'entity_id': event['id'],
                        'entity_name': event['title'],
                        'headline': f"Meeting with {client['name']} - AR outstanding",
                        'context': f"${fin['overdue_ar']:,.0f} overdue. Opportunity to discuss.",
                        'action': 'Prepare payment discussion',
                    })

        # 3. Emails awaiting response (by client importance)
        awaiting = self._query("""
            SELECT c.client_id, COUNT(*) as thread_count
            FROM communications c
            WHERE c.from_domain NOT LIKE '%hrmny.co%'
              AND NOT EXISTS (
                SELECT 1 FROM communications c2
                WHERE c2.thread_id = c.thread_id
                  AND c2.from_domain LIKE '%hrmny.co%'
                  AND c2.created_at > c.received_at
              )
            GROUP BY c.client_id
            HAVING thread_count > 0
        """)

        for row in awaiting:
            if row['client_id']:
                client = self._get_client(row['client_id'])
                tier = self._get_tier(row['client_id'])
                priority = 70 if tier == '1' else 60 if tier == '2' else 50

                items.append({
                    'type': 'response_needed',
                    'priority': priority,
                    'entity_type': 'client',
                    'entity_id': row['client_id'],
                    'entity_name': client['name'],
                    'headline': f"{row['thread_count']} email(s) awaiting reply",
                    'action': 'Respond to threads',
                })

        # 4. Relationships going cold (with AR)
        cooling = self._query("""
            SELECT c.id, c.name, c.tier,
                   (SELECT MAX(start_time) FROM events e
                    WHERE e.attendees LIKE '%' ||
                          (SELECT domain FROM client_identities ci WHERE ci.client_id = c.id LIMIT 1)
                          || '%') as last_meeting
            FROM clients c
            WHERE EXISTS (
                SELECT 1 FROM invoices i
                WHERE i.client_name = c.name
                  AND i.paid_date IS NULL
                  AND i.amount > 5000
            )
        """)

        for row in cooling:
            if row['last_meeting']:
                days_ago = (datetime.now() - datetime.fromisoformat(row['last_meeting'])).days
                if days_ago > 30:
                    items.append({
                        'type': 'relationship_cooling',
                        'priority': 40,
                        'entity_type': 'client',
                        'entity_id': row['id'],
                        'entity_name': row['name'],
                        'headline': f"No meeting in {days_ago} days",
                        'context': 'Active AR on account',
                        'action': 'Schedule check-in',
                    })

        # Sort by priority descending
        return sorted(items, key=lambda x: -x['priority'])
```

---

## What This Replaces

| Old Component | New Component | Why Better |
|---------------|---------------|------------|
| Fake capacity (60min × tasks) | Calendar-based capacity | Real time available |
| Task-level health | Signal-based health | Multi-source truth |
| Missing assignee inference | Entity resolution | Works across sources |
| Fuzzy project→client | Domain→client mapping | Based on meetings + emails |
| 4-factor health score | Weighted signal composite | Financial + relationship + comms |
| Task-derived moves | Attention queue | Actionable, prioritized |

---

## Implementation Plan

### Phase 1: Entity Resolution (2 hours)
- `lib/intelligence/entity_resolver.py`
- Build domain → client mapping from invoices + calendar + existing identities
- Test: All invoice clients resolvable, top meeting domains mapped

### Phase 2: Signal Extractors (4 hours)
- `lib/intelligence/signals/financial.py` (1h)
- `lib/intelligence/signals/relationship.py` (1.5h)
- `lib/intelligence/signals/communication.py` (1.5h)

### Phase 3: Composite Intelligence (2 hours)
- `lib/intelligence/composite.py`
- Weighted health scoring
- Action generation

### Phase 4: Capacity Intelligence (1 hour)
- `lib/intelligence/capacity.py`
- Calendar-based real capacity

### Phase 5: Attention Queue (2 hours)
- `lib/intelligence/attention.py`
- Priority ranking
- Integration with snapshot

### Phase 6: Snapshot Integration (2 hours)
- Update generator to use new intelligence layer
- Replace old engines with signal-based outputs

**Total: ~13 hours**

---

## Files to Create

```
lib/intelligence/
├── __init__.py
├── entity_resolver.py      # Domain → client mapping
├── composite.py            # Combined intelligence
├── capacity.py             # Calendar-based capacity
├── attention.py            # Priority queue
└── signals/
    ├── __init__.py
    ├── financial.py        # Invoice-derived signals
    ├── relationship.py     # Calendar-derived signals
    └── communication.py    # Email-derived signals
```
