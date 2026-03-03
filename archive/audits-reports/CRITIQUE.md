# TIME OS CRITIQUE

## The Actual Engineering Problem

This system ingests:
- Tasks (Google Tasks, Asana)
- Events (Calendar)
- Communications (Gmail)
- Clients (CRM)
- Finance (Xero AR)
- Team (capacity, assignments)
- Commitments (inferred from email)

That's not overengineering. That's operations reality.

The problem is not "too many signals."

The problem is: **no control theory for managing those signals.**

---

## I. SIGNAL HIERARCHY

### The Missing Definition

The system treats all signals equally. A stale task, an overdue invoice, and a missed commitment all create "notifications" with "priority" scores.

**What's needed: explicit signal hierarchy.**

```
TIER 0 — INTERRUPT (push immediately, any hour)
├── Client escalation (angry email, complaint)
├── Financial threshold breach (AR > threshold for tier)
├── Deadline < 2h on critical item
└── Commitment to external party due today, not done

TIER 1 — URGENT (push during work hours)
├── Task blocked on you > 24h
├── Team member overloaded > 150%
├── Client health transition to critical
└── Meeting in < 30min, no prep done

TIER 2 — IMPORTANT (include in morning brief)
├── Tasks due today
├── Commitments due this week
├── Client health at poor
├── AR 60+ days
└── Unassigned tasks on active projects

TIER 3 — ADVISORY (available in dashboard, no push)
├── Tasks due this week
├── Team workload changes
├── Project health updates
└── Pattern observations

TIER 4 — BACKGROUND (logged, not surfaced)
├── Routine syncs
├── Data refreshes
└── Non-actionable observations
```

### Implementation

```python
class SignalTier(Enum):
    INTERRUPT = 0
    URGENT = 1
    IMPORTANT = 2
    ADVISORY = 3
    BACKGROUND = 4

class Signal:
    def __init__(self, type: str, source: dict, tier: SignalTier):
        self.type = type
        self.source = source
        self.tier = tier
        self.timestamp = datetime.now()
        self.arbitration_key = self._compute_key()

    def _compute_key(self) -> str:
        """Key for deduplication and arbitration."""
        return f"{self.type}:{self.source.get('id', 'unknown')}"

def classify_signal(event: dict) -> Signal:
    """Classify incoming event into signal tier."""

    # TIER 0: Interrupt
    if event['type'] == 'email' and event.get('sentiment') == 'escalation':
        return Signal('client_escalation', event, SignalTier.INTERRUPT)

    if event['type'] == 'ar_update':
        client = get_client(event['client_id'])
        threshold = AR_THRESHOLDS[client.get('tier', 'C')]
        if event['days_overdue'] >= 90 and event['amount'] > threshold:
            return Signal('ar_critical', event, SignalTier.INTERRUPT)

    if event['type'] == 'task':
        hours_to_due = (parse(event['due_date']) - datetime.now()).total_seconds() / 3600
        if hours_to_due < 2 and event.get('is_critical'):
            return Signal('deadline_imminent', event, SignalTier.INTERRUPT)

    # TIER 1: Urgent
    if event['type'] == 'task' and event.get('waiting_for_moh'):
        hours_waiting = (datetime.now() - parse(event['blocked_since'])).total_seconds() / 3600
        if hours_waiting > 24:
            return Signal('blocked_on_you', event, SignalTier.URGENT)

    if event['type'] == 'team_load':
        if event['load_percentage'] > 150:
            return Signal('team_overload', event, SignalTier.URGENT)

    # TIER 2: Important
    if event['type'] == 'task' and event.get('due_date') == date.today().isoformat():
        return Signal('due_today', event, SignalTier.IMPORTANT)

    if event['type'] == 'commitment' and is_this_week(event.get('due_date')):
        return Signal('commitment_due', event, SignalTier.IMPORTANT)

    # TIER 3: Advisory (default for most updates)
    return Signal('update', event, SignalTier.ADVISORY)
```

---

## II. PRIORITY ARBITRATION

### The Problem

When multiple signals fire, which wins?

Current system: all become notifications, all get scored 0-100, user sees a pile.

**What's needed: arbitration rules.**

### Arbitration Principles

1. **Higher tier always wins** — Tier 0 interrupts even if Tier 2 is "higher score"
2. **Within tier, client tier wins** — Tier A client issue > Tier C client issue
3. **Recency breaks ties** — Newer signal wins if same tier and client
4. **Consolidation over repetition** — Multiple signals about same entity merge

### Implementation

```python
class Arbitrator:
    def __init__(self):
        self.active_signals: Dict[str, Signal] = {}
        self.cooldowns: Dict[str, datetime] = {}

    def ingest(self, signal: Signal) -> Optional[Signal]:
        """Process signal, return if it should surface."""

        key = signal.arbitration_key

        # Check cooldown
        if key in self.cooldowns:
            if datetime.now() < self.cooldowns[key]:
                return None  # Suppressed

        # Check for existing signal on same entity
        if key in self.active_signals:
            existing = self.active_signals[key]
            winner = self._arbitrate(existing, signal)
            if winner == existing:
                return None  # Existing wins, no new notification
            # New wins, replace
            self.active_signals[key] = signal
            return signal

        # New signal
        self.active_signals[key] = signal
        return signal

    def _arbitrate(self, a: Signal, b: Signal) -> Signal:
        """Determine winner between two signals."""

        # Tier comparison
        if a.tier.value < b.tier.value:
            return a
        if b.tier.value < a.tier.value:
            return b

        # Same tier: client tier comparison
        a_client_tier = get_client_tier(a.source.get('client_id'))
        b_client_tier = get_client_tier(b.source.get('client_id'))

        tier_order = {'A': 0, 'B': 1, 'C': 2, None: 3}
        if tier_order.get(a_client_tier, 3) < tier_order.get(b_client_tier, 3):
            return a
        if tier_order.get(b_client_tier, 3) < tier_order.get(a_client_tier, 3):
            return b

        # Same client tier: recency
        return b if b.timestamp > a.timestamp else a

    def set_cooldown(self, key: str, minutes: int):
        """Prevent re-alerting on same issue."""
        self.cooldowns[key] = datetime.now() + timedelta(minutes=minutes)
```

---

## III. GATING RULES

### The Problem

When can the system act? When must it wait?

Current system: governance set to "observe" — nothing acts.

**What's needed: explicit gating rules per action type.**

### Gate Definitions

```yaml
gates:
  # NOTIFICATIONS
  notification_interrupt:
    requires: signal.tier == INTERRUPT
    conditions:
      - not in_quiet_hours()  # Unless INTERRUPT tier
      - cooldown_clear(signal.key, 60)  # 60min between same alert
      - daily_interrupt_count < 5
    allows: immediate push to WhatsApp

  notification_urgent:
    requires: signal.tier == URGENT
    conditions:
      - is_work_hours()  # 9am-9pm
      - cooldown_clear(signal.key, 120)
      - daily_urgent_count < 10
    allows: push to WhatsApp

  notification_important:
    requires: signal.tier == IMPORTANT
    conditions:
      - none  # Always allowed
    allows: include in next brief (morning/evening)

  # DATA UPDATES (internal, no approval)
  update_priority_score:
    requires: recalculation_triggered
    conditions:
      - last_recalc > 15min ago
    allows: update task.priority in database

  update_client_health:
    requires: health_signal_changed
    conditions:
      - change is computable (AR, activity, overdue count)
    allows: update client.relationship_health

  update_team_load:
    requires: task_assignment_changed
    conditions:
      - none
    allows: recalculate person.load_percentage

  # EXTERNAL ACTIONS (require approval or high confidence)
  send_email:
    requires: action.type == email
    conditions:
      - NEVER auto-execute
    allows: queue for human approval

  create_calendar_event:
    requires: action.type == calendar
    conditions:
      - NEVER auto-execute
    allows: queue for human approval

  create_task:
    requires: action.type == task_create
    conditions:
      - confidence > 0.9
      - source is commitment extraction
    allows: create as draft, flag for review
```

### Implementation

```python
class Gate:
    def __init__(self, name: str, config: dict):
        self.name = name
        self.requires = config.get('requires')
        self.conditions = config.get('conditions', [])
        self.allows = config.get('allows')

    def check(self, context: dict) -> Tuple[bool, str]:
        """Check if gate allows passage."""

        for condition in self.conditions:
            result, reason = self._eval_condition(condition, context)
            if not result:
                return False, reason

        return True, self.allows

    def _eval_condition(self, condition: str, context: dict) -> Tuple[bool, str]:
        if condition == 'not in_quiet_hours()':
            if is_quiet_hours() and context.get('tier') != SignalTier.INTERRUPT:
                return False, "quiet hours active"
            return True, ""

        if condition == 'is_work_hours()':
            if not is_work_hours():
                return False, "outside work hours"
            return True, ""

        if condition.startswith('cooldown_clear'):
            key = context.get('signal_key')
            minutes = int(condition.split(',')[1].strip(' )'))
            if not cooldown_clear(key, minutes):
                return False, f"cooldown active ({minutes}min)"
            return True, ""

        if condition.startswith('daily_') and '_count' in condition:
            limit_name = condition.split('<')[0].strip()
            limit_value = int(condition.split('<')[1].strip())
            current = get_daily_count(limit_name)
            if current >= limit_value:
                return False, f"{limit_name} limit reached ({current}/{limit_value})"
            return True, ""

        # Unknown condition, fail safe
        return False, f"unknown condition: {condition}"

class GateKeeper:
    def __init__(self, config_path: str):
        self.gates = self._load_gates(config_path)

    def may_proceed(self, action_type: str, context: dict) -> Tuple[bool, str]:
        """Check if action may proceed through its gate."""
        gate = self.gates.get(action_type)
        if not gate:
            return False, f"no gate defined for {action_type}"
        return gate.check(context)
```

---

## IV. ESCALATION PATHS

### The Problem

When something isn't handled, what happens?

Current system: items sit in tables indefinitely.

**What's needed: explicit escalation paths with time bounds.**

### Escalation Definitions

```yaml
escalation_paths:

  unassigned_task:
    initial_state: created without owner
    escalation:
      - after: 24h
        action: include in morning brief as "needs owner"
      - after: 48h
        action: push notification "X tasks unassigned >48h"
      - after: 72h
        action: auto-assign to project owner or escalate to you

  blocked_task:
    initial_state: marked blocked or waiting_for set
    escalation:
      - after: 24h
        action: include in brief under "blocked items"
      - after: 48h
        action: push notification if blocker is you
      - after: 72h
        action: escalate to project owner

  overdue_task:
    initial_state: due_date passed, status != done
    escalation:
      - after: 0h
        action: mark overdue, include in brief
      - after: 24h
        action: push if client tier A or B
      - after: 72h
        action: mark stale, flag for review/archive

  ar_overdue:
    initial_state: invoice past due
    escalation:
      - after: 30d
        action: update client health to "watch"
      - after: 60d
        action: update client health to "poor", include in brief
      - after: 90d
        action: update client health to "critical", push notification
      - after: 120d
        action: daily reminder until resolved

  commitment_due:
    initial_state: commitment with due_date
    escalation:
      - before: 24h
        action: include in morning brief
      - before: 2h
        action: push reminder
      - after: 0h (missed)
        action: push alert "commitment to X missed"
      - after: 24h
        action: flag for follow-up/apology

  client_no_contact:
    initial_state: no meaningful interaction
    escalation:
      - after: 14d (tier A)
        action: include in brief "no contact with X"
      - after: 21d (tier A)
        action: push reminder
      - after: 30d (tier B)
        action: include in brief
      - after: 60d (tier C)
        action: include in brief
```

### Implementation

```python
class EscalationEngine:
    def __init__(self, store, config: dict):
        self.store = store
        self.paths = config.get('escalation_paths', {})

    def check_escalations(self) -> List[Signal]:
        """Check all items against escalation paths, return signals."""
        signals = []

        # Unassigned tasks
        unassigned = self.store.query("""
            SELECT *,
                   (julianday('now') - julianday(created_at)) * 24 as hours_unassigned
            FROM tasks
            WHERE status = 'pending'
            AND (assignee IS NULL OR assignee = '')
        """)

        for task in unassigned:
            hours = task['hours_unassigned']
            path = self.paths['unassigned_task']['escalation']

            for step in path:
                threshold = self._parse_time(step['after'])
                if hours >= threshold:
                    signal = self._create_escalation_signal(
                        'unassigned_task', task, step, hours
                    )
                    signals.append(signal)
                    break  # Only highest applicable escalation

        # Blocked tasks
        blocked = self.store.query("""
            SELECT *,
                   (julianday('now') - julianday(COALESCE(blocked_since, updated_at))) * 24 as hours_blocked
            FROM tasks
            WHERE status = 'pending'
            AND (is_blocked = 1 OR waiting_for IS NOT NULL)
        """)

        for task in blocked:
            hours = task['hours_blocked']
            # ... similar pattern

        # AR overdue
        ar_overdue = self.store.query("""
            SELECT c.*,
                   MAX(CAST(REPLACE(c.financial_ar_aging, '+', '') AS INTEGER)) as days_overdue
            FROM clients c
            WHERE c.financial_ar_outstanding > 0
            AND c.financial_ar_aging IS NOT NULL
        """)

        for client in ar_overdue:
            days = client['days_overdue']
            path = self.paths['ar_overdue']['escalation']

            for step in path:
                threshold = self._parse_time(step['after'])
                if days >= threshold:
                    # Check if health update needed
                    if 'update client health' in step['action']:
                        new_health = self._extract_health(step['action'])
                        if client['relationship_health'] != new_health:
                            self.store.update('clients', client['id'], {
                                'relationship_health': new_health
                            })

                    signal = self._create_escalation_signal(
                        'ar_overdue', client, step, days
                    )
                    signals.append(signal)
                    break

        return signals

    def _parse_time(self, time_str: str) -> float:
        """Parse '24h', '30d', etc into hours."""
        if time_str.endswith('h'):
            return float(time_str[:-1])
        if time_str.endswith('d'):
            return float(time_str[:-1]) * 24
        return 0
```

---

## V. DRIFT BOUNDARIES

### The Problem

Systems drift. Priority scores inflate. Stale data accumulates. Noise increases.

Current system: no bounds checking.

**What's needed: explicit boundaries that trigger correction.**

### Boundary Definitions

```yaml
drift_boundaries:

  priority_inflation:
    measure: count of tasks with priority >= 90
    healthy: <= 5
    warning: 6-10
    critical: > 10
    correction: force_rank_top_priorities()

  stale_accumulation:
    measure: count of tasks overdue > 7 days
    healthy: <= 5
    warning: 6-15
    critical: > 15
    correction: flag_for_archive_review()

  unassigned_accumulation:
    measure: count of tasks with no owner
    healthy: <= 10
    warning: 11-25
    critical: > 25
    correction: surface_in_brief(), block_new_task_creation()

  notification_spam:
    measure: notifications sent in last 24h
    healthy: <= 10
    warning: 11-20
    critical: > 20
    correction: increase_cooldowns(), raise_thresholds()

  data_freshness:
    measure: hours since last successful sync per source
    healthy: <= 1h
    warning: 1-4h
    critical: > 4h
    correction: alert_sync_failure(), retry_sync()

  client_health_skew:
    measure: percentage of clients at critical or poor
    healthy: <= 10%
    warning: 11-25%
    critical: > 25%
    correction: review_health_calculation(), surface_systemic_issue()
```

### Implementation

```python
class DriftMonitor:
    def __init__(self, store, config: dict):
        self.store = store
        self.boundaries = config.get('drift_boundaries', {})

    def check_boundaries(self) -> List[dict]:
        """Check all boundaries, return violations."""
        violations = []

        # Priority inflation
        high_priority_count = self.store.query(
            "SELECT COUNT(*) FROM tasks WHERE status='pending' AND priority >= 90"
        )[0][0]

        boundary = self.boundaries['priority_inflation']
        status = self._check_threshold(high_priority_count, boundary)
        if status != 'healthy':
            violations.append({
                'boundary': 'priority_inflation',
                'status': status,
                'value': high_priority_count,
                'correction': boundary['correction']
            })
            if status == 'critical':
                self._execute_correction(boundary['correction'])

        # Stale accumulation
        stale_count = self.store.query("""
            SELECT COUNT(*) FROM tasks
            WHERE status='pending' AND due_date < date('now', '-7 days')
        """)[0][0]

        boundary = self.boundaries['stale_accumulation']
        status = self._check_threshold(stale_count, boundary)
        if status != 'healthy':
            violations.append({
                'boundary': 'stale_accumulation',
                'status': status,
                'value': stale_count,
                'correction': boundary['correction']
            })

        # ... etc for each boundary

        return violations

    def _check_threshold(self, value: int, boundary: dict) -> str:
        healthy = boundary.get('healthy', '<= 0')
        warning = boundary.get('warning', '0')

        healthy_max = self._parse_threshold(healthy)
        warning_max = self._parse_threshold(warning)

        if value <= healthy_max:
            return 'healthy'
        if value <= warning_max:
            return 'warning'
        return 'critical'

    def _execute_correction(self, correction: str):
        """Execute automatic correction."""
        if correction == 'force_rank_top_priorities()':
            self._force_rank_priorities()
        elif correction == 'flag_for_archive_review()':
            self._flag_stale_for_review()
        # ... etc

    def _force_rank_priorities(self):
        """Enforce max 5 at priority 90+."""
        tasks = self.store.query("""
            SELECT id FROM tasks
            WHERE status='pending'
            ORDER BY priority DESC, due_date ASC
        """)

        for i, task in enumerate(tasks):
            if i < 5:
                new_priority = 95 - i
            elif i < 20:
                new_priority = 84 - (i - 5)
            else:
                new_priority = max(30, 69 - (i - 20))

            self.store.update('tasks', task['id'], {'priority': new_priority})
```

---

## VI. TRUTH LAYERS (SEQUENCED)

### The Problem

The system tries to do everything at once. No stable foundation.

**What's needed: sequential truth establishment.**

### Layer Sequence

```
LAYER 1: DATA TRUTH
├── All sources sync successfully
├── Deduplication complete
├── Entity IDs stable
├── Timestamps consistent
└── GATE: Layer 2 blocked until Layer 1 healthy

LAYER 2: TASK TRUTH
├── Every task has: title, status, source
├── Every task has: due_date OR explicitly marked "no date"
├── Every task has: owner OR explicitly marked "unassigned"
├── Priority scores computed
└── GATE: Layer 3 blocked until Layer 2 healthy

LAYER 3: COMMITMENT TRUTH
├── Commitments extracted from sent emails
├── Commitments have: description, to_whom, due_date
├── Commitments linked to tasks where applicable
└── GATE: Layer 4 blocked until Layer 3 healthy

LAYER 4: CALENDAR TRUTH
├── Events synced with correct times
├── Conflicts detected
├── Prep time requirements known
└── GATE: Layer 5 blocked until Layer 4 healthy

LAYER 5: ASSIGNMENT TRUTH (Lane/Team)
├── Every person has: capacity, current_load
├── Load calculated from assigned tasks
├── Overload detected
└── GATE: Layer 6 blocked until Layer 5 healthy

LAYER 6: CLIENT TRUTH
├── Clients have: tier, health
├── Health calculated from signals (AR, activity, overdue)
├── Client linked to projects and tasks
└── GATE: Layer 7 blocked until Layer 6 healthy

LAYER 7: FINANCE TRUTH
├── AR synced from Xero
├── AR aging calculated
├── AR linked to clients
└── GATE: Layer 8 blocked until Layer 7 healthy

LAYER 8: ALERT TRUTH
├── Signals classified by tier
├── Arbitration complete
├── Escalations checked
├── Notifications queued
└── System ready for briefing/alerting
```

### Implementation

```python
class TruthLayer:
    def __init__(self, name: str, checks: List[callable], dependencies: List[str] = None):
        self.name = name
        self.checks = checks
        self.dependencies = dependencies or []
        self.healthy = False
        self.last_check = None
        self.issues = []

    def verify(self, layer_states: Dict[str, bool]) -> bool:
        """Verify this layer is healthy."""

        # Check dependencies first
        for dep in self.dependencies:
            if not layer_states.get(dep, False):
                self.healthy = False
                self.issues = [f"dependency {dep} not healthy"]
                return False

        # Run checks
        self.issues = []
        for check in self.checks:
            result, issue = check()
            if not result:
                self.issues.append(issue)

        self.healthy = len(self.issues) == 0
        self.last_check = datetime.now()
        return self.healthy

class TruthEngine:
    def __init__(self, store):
        self.store = store
        self.layers = self._define_layers()

    def _define_layers(self) -> Dict[str, TruthLayer]:
        return {
            'data': TruthLayer('data', [
                self._check_sync_freshness,
                self._check_no_duplicates,
            ]),
            'task': TruthLayer('task', [
                self._check_tasks_have_required_fields,
                self._check_priorities_computed,
            ], dependencies=['data']),
            'commitment': TruthLayer('commitment', [
                self._check_commitments_extracted,
            ], dependencies=['task']),
            'calendar': TruthLayer('calendar', [
                self._check_events_synced,
                self._check_conflicts_detected,
            ], dependencies=['task']),
            'assignment': TruthLayer('assignment', [
                self._check_capacity_defined,
                self._check_load_calculated,
            ], dependencies=['task']),
            'client': TruthLayer('client', [
                self._check_clients_tiered,
                self._check_health_calculated,
            ], dependencies=['task', 'assignment']),
            'finance': TruthLayer('finance', [
                self._check_ar_synced,
                self._check_ar_linked_to_clients,
            ], dependencies=['client']),
            'alert': TruthLayer('alert', [
                self._check_signals_classified,
                self._check_escalations_current,
            ], dependencies=['client', 'finance', 'commitment']),
        }

    def verify_all(self) -> Dict[str, dict]:
        """Verify all layers in sequence."""
        states = {}
        results = {}

        for name in ['data', 'task', 'commitment', 'calendar', 'assignment', 'client', 'finance', 'alert']:
            layer = self.layers[name]
            healthy = layer.verify(states)
            states[name] = healthy
            results[name] = {
                'healthy': healthy,
                'issues': layer.issues,
                'last_check': layer.last_check.isoformat() if layer.last_check else None
            }

            if not healthy:
                # Don't proceed to dependent layers
                break

        return results

    def _check_sync_freshness(self) -> Tuple[bool, str]:
        """Check all sources synced within threshold."""
        sources = ['tasks', 'calendar', 'gmail']
        for source in sources:
            last_sync = self.store.query(f"""
                SELECT MAX(synced_at) FROM {source}
                WHERE synced_at IS NOT NULL
            """)[0][0]

            if not last_sync:
                return False, f"{source} never synced"

            hours_ago = (datetime.now() - datetime.fromisoformat(last_sync)).total_seconds() / 3600
            if hours_ago > 4:
                return False, f"{source} last synced {hours_ago:.1f}h ago"

        return True, ""

    def _check_tasks_have_required_fields(self) -> Tuple[bool, str]:
        """Check all tasks have required fields."""
        missing = self.store.query("""
            SELECT COUNT(*) FROM tasks
            WHERE status = 'pending'
            AND (title IS NULL OR title = '')
        """)[0][0]

        if missing > 0:
            return False, f"{missing} tasks missing title"
        return True, ""

    # ... etc for each check
```

---

## VII. BOUNDED COMPLETENESS

### The Fixed Objects

```yaml
objects:
  task:
    required: [id, title, status, source]
    optional: [due_date, assignee, project, client_id, priority, notes]
    computed: [priority_score, is_overdue, is_blocked, days_stale]

  commitment:
    required: [id, description, due_date, source]
    optional: [promised_to, linked_task_id]
    computed: [is_overdue, hours_until_due]

  client:
    required: [id, name]
    optional: [tier, health, ar_outstanding, ar_aging]
    computed: [health_score, days_since_contact, overdue_task_count]

  person:
    required: [id, name]
    optional: [capacity_hours, is_internal]
    computed: [current_load, load_percentage, overdue_count]

  event:
    required: [id, title, start_time]
    optional: [end_time, attendees, location]
    computed: [duration_hours, has_conflict, needs_prep]

  project:
    required: [id, name]
    optional: [client_id, deadline, owner]
    computed: [health, completion_pct, days_to_deadline]
```

### Allowable Transformations

```yaml
transformations:
  # Internal (no approval)
  task.priority_score: recompute from signals
  task.is_overdue: compute from due_date
  task.is_blocked: compute from waiting_for, blockers
  client.health: compute from AR + activity + overdue
  person.load_percentage: compute from assigned tasks

  # Gated (requires conditions)
  notification.send: requires gate check
  task.status -> done: requires user action or API call
  task.assignee: requires user action or delegation rules

  # Forbidden (never auto)
  email.send: never
  calendar.create: never
  external.any: never
```

### Signal-Action Mapping

```yaml
signal_actions:
  # Which signals can trigger which actions

  ar_critical:
    may_trigger:
      - update_client_health
      - create_notification(INTERRUPT)
    may_not_trigger:
      - send_email
      - create_task

  deadline_imminent:
    may_trigger:
      - create_notification(INTERRUPT if critical, else URGENT)
    may_not_trigger:
      - reschedule
      - reassign

  team_overload:
    may_trigger:
      - create_notification(URGENT)
      - flag_for_rebalance
    may_not_trigger:
      - auto_reassign

  commitment_due:
    may_trigger:
      - create_notification(IMPORTANT or URGENT based on time)
    may_not_trigger:
      - mark_complete
      - send_apology
```

---

## VIII. FORMAL THRESHOLDS

### Time Thresholds

```yaml
time:
  work_hours_start: "09:00"
  work_hours_end: "21:00"
  quiet_hours_start: "23:00"
  quiet_hours_end: "08:00"

  deadline_imminent_hours: 2
  deadline_soon_hours: 24
  blocked_escalate_hours: 24
  stale_threshold_days: 7
  ancient_threshold_days: 14
```

### Count Thresholds

```yaml
counts:
  max_critical_priority: 5
  max_high_priority: 15
  max_daily_interrupts: 5
  max_daily_urgent: 10
  max_unassigned_healthy: 10
  max_overdue_healthy: 5
```

### Financial Thresholds (by client tier)

```yaml
ar_thresholds:
  tier_a:
    warning_days: 30
    critical_days: 60
    amount_threshold: 50000
  tier_b:
    warning_days: 45
    critical_days: 90
    amount_threshold: 25000
  tier_c:
    warning_days: 60
    critical_days: 90
    amount_threshold: 10000
```

### Client Contact Thresholds

```yaml
contact_thresholds:
  tier_a:
    warning_days: 14
    critical_days: 21
  tier_b:
    warning_days: 30
    critical_days: 45
  tier_c:
    warning_days: 60
    critical_days: 90
```

### Load Thresholds

```yaml
load:
  healthy_max_pct: 100
  warning_pct: 120
  critical_pct: 150
```

---

## IX. WHAT THE SYSTEM BECOMES

With these controls in place:

1. **Signals are classified** — Not all notifications equal, tier determines handling
2. **Conflicts are arbitrated** — When multiple signals fire, rules determine winner
3. **Actions are gated** — Clear conditions for what may proceed
4. **Escalations are bounded** — Time-based paths with defined endpoints
5. **Drift is detected** — Boundaries trigger corrections before chaos
6. **Truth is sequenced** — Each layer stable before next builds on it
7. **Completeness is bounded** — Fixed objects, allowed transformations, explicit mappings
8. **Thresholds are formal** — "Matters" has numeric definition

**This is control theory applied to operations.**

The system doesn't get simpler. It gets governed.

---

## X. IMPLEMENTATION SEQUENCE

```
WEEK 1: Control Foundation
├── Implement SignalTier enum and classification
├── Implement Arbitrator with cooldowns
├── Implement GateKeeper with basic gates
├── Test: signals classified correctly, gates enforced

WEEK 2: Escalation & Drift
├── Implement EscalationEngine
├── Implement DriftMonitor
├── Define all thresholds in config
├── Test: escalations fire on time, drift detected

WEEK 3: Truth Layers
├── Implement TruthEngine
├── Define checks per layer
├── Wire into autonomous loop
├── Test: layers verify in sequence, issues surface

WEEK 4: Integration
├── Wire all components into autonomous loop
├── Enable notification sending
├── Enable morning brief
├── Test: end-to-end cycle produces correct signals/alerts

WEEK 5: Tuning
├── Adjust thresholds based on real usage
├── Tune cooldowns based on noise
├── Refine escalation timing
├── Stabilize
```

---

This is the critique: not "delete the complexity" but "govern the complexity."

The system has the right inputs. It needs control theory to produce the right outputs.
