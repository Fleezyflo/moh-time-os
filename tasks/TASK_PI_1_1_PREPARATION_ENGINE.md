# PI-1.1: Preparation Engine & Action Registry

## Objective
Build the core engine that watches triggers (signals raised, predictions generated, schedule events, on-demand requests) and prepares actions in a staging area. Every prepared action has type, context, content, priority, and expiry. Actions sit in staging until you approve, modify, or dismiss them. Dismissals feed back into the decision journal (Brief 22).

## Implementation

### New Tables
```sql
CREATE TABLE prepared_actions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    action_type TEXT NOT NULL,
    -- 'email_draft' | 'asana_task' | 'asana_update' | 'calendar_event' | 'chat_message'
    trigger_type TEXT NOT NULL,
    -- 'signal' | 'prediction' | 'schedule' | 'on_demand' | 'time_based'
    trigger_id TEXT,                    -- FK to signal/prediction/etc.
    entity_type TEXT,                   -- 'client' | 'project' | 'engagement' | 'invoice'
    entity_id TEXT,
    priority TEXT NOT NULL DEFAULT 'normal',
    -- 'urgent' | 'high' | 'normal' | 'low'
    status TEXT NOT NULL DEFAULT 'staged',
    -- 'staged' | 'approved' | 'modified' | 'dismissed' | 'dispatched' | 'expired'
    content TEXT NOT NULL,              -- JSON: the actual draft (subject, body, recipients, etc.)
    context TEXT NOT NULL,              -- JSON: why prepared (signals, predictions, history)
    modified_content TEXT,              -- JSON: if you edited the draft before approving
    dispatched_at TEXT,
    dispatch_result TEXT,               -- JSON: success/failure details from writer
    dismissed_at TEXT,
    approved_at TEXT,
    modified_at TEXT
);

CREATE INDEX idx_prepared_actions_status ON prepared_actions(status, priority, created_at DESC);
CREATE INDEX idx_prepared_actions_entity ON prepared_actions(entity_type, entity_id, status);
CREATE INDEX idx_prepared_actions_type ON prepared_actions(action_type, status);
CREATE INDEX idx_prepared_actions_expiry ON prepared_actions(expires_at) WHERE status = 'staged';

CREATE TABLE preparation_rules (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    trigger_type TEXT NOT NULL,         -- 'signal' | 'prediction' | 'schedule' | 'time_based'
    trigger_condition TEXT NOT NULL,    -- JSON: conditions that activate this rule
    action_type TEXT NOT NULL,          -- what kind of action to prepare
    template TEXT NOT NULL,             -- JSON: action template with placeholders
    priority TEXT NOT NULL DEFAULT 'normal',
    enabled INTEGER NOT NULL DEFAULT 1,
    cooldown_hours INTEGER DEFAULT 24,  -- don't re-fire for same entity within this window
    last_fired_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT
);

CREATE INDEX idx_preparation_rules_trigger ON preparation_rules(trigger_type, enabled);
```

### PreparationEngine (`lib/intelligence/preparation_engine.py`)
```python
class PreparationEngine:
    """Core engine that watches triggers and prepares actions."""

    def evaluate_signal(self, signal: dict) -> List[PreparedAction]:
        """
        Signal raised → check preparation rules → create staged actions.
        e.g., client health < 50 → prepare follow-up email draft.
        Returns list of any actions staged.
        """

    def evaluate_prediction(self, prediction: dict) -> List[PreparedAction]:
        """
        Prediction generated → check preparation rules → create staged actions.
        e.g., deadline predicted to slip → prepare Asana task update.
        """

    def evaluate_schedule(self, calendar_event: dict) -> List[PreparedAction]:
        """
        Calendar event approaching → prepare pre-meeting brief + post-meeting follow-up.
        Triggered 2 hours before a meeting.
        """

    def prepare_on_demand(self, action_type: str, entity_type: str,
                          entity_id: str, instructions: str = None) -> PreparedAction:
        """
        You explicitly request a preparation.
        e.g., "Draft a follow-up email to Client X about the overdue invoice."
        """

    def run_periodic_check(self) -> List[PreparedAction]:
        """
        Time-based trigger: check for stale items needing follow-up.
        e.g., client not contacted in 30 days with declining health → prepare outreach.
        """

    def get_staged_actions(self, entity_type: str = None, entity_id: str = None,
                           action_type: str = None, priority: str = None) -> List[PreparedAction]:
        """Get all staged actions, optionally filtered."""

    def approve_action(self, action_id: str) -> DispatchResult:
        """
        Approve a staged action → dispatch via appropriate writer.
        Records decision in journal. Returns dispatch result.
        """

    def modify_action(self, action_id: str, modified_content: dict) -> PreparedAction:
        """
        Edit a staged action's content before approving.
        Stores modified version, status → 'modified' (still needs approve to dispatch).
        """

    def dismiss_action(self, action_id: str, reason: str = None) -> None:
        """
        Dismiss a staged action. Records in decision journal.
        Feeds into behavioral patterns (Brief 22).
        """

    def expire_stale_actions(self) -> int:
        """Mark staged actions past their expires_at as expired. Returns count."""
```

### Preparation Rules Engine
```python
DEFAULT_RULES = [
    {
        'name': 'health_decline_followup',
        'trigger_type': 'signal',
        'trigger_condition': {'signal_type': 'health_declining', 'severity': ['high', 'critical']},
        'action_type': 'email_draft',
        'template': {
            'subject': 'Checking in — {client_name}',
            'intent': 'warm_followup',
            'context_keys': ['health_score', 'last_contact_days', 'active_projects']
        },
        'priority': 'high',
        'cooldown_hours': 72
    },
    {
        'name': 'overdue_invoice_reminder',
        'trigger_type': 'signal',
        'trigger_condition': {'signal_type': 'invoice_overdue', 'days_overdue_gt': 14},
        'action_type': 'email_draft',
        'template': {
            'subject': 'Invoice #{invoice_number} — friendly reminder',
            'intent': 'payment_reminder',
            'context_keys': ['invoice_amount', 'days_overdue', 'payment_history']
        },
        'priority': 'normal',
        'cooldown_hours': 168  # weekly
    },
    {
        'name': 'deadline_slip_task_update',
        'trigger_type': 'prediction',
        'trigger_condition': {'prediction_type': 'deadline_risk', 'risk_level': ['high', 'critical']},
        'action_type': 'asana_update',
        'template': {
            'update_type': 'status_comment',
            'intent': 'flag_risk',
            'context_keys': ['predicted_date', 'confidence', 'blockers']
        },
        'priority': 'high',
        'cooldown_hours': 48
    },
    {
        'name': 'pre_meeting_brief',
        'trigger_type': 'schedule',
        'trigger_condition': {'event_type': 'meeting', 'hours_before': 2},
        'action_type': 'chat_message',
        'template': {
            'intent': 'pre_meeting_summary',
            'context_keys': ['attendee_entities', 'recent_signals', 'open_items']
        },
        'priority': 'normal',
        'cooldown_hours': 0  # always prepare for meetings
    },
    {
        'name': 'stale_client_outreach',
        'trigger_type': 'time_based',
        'trigger_condition': {'no_contact_days_gt': 21, 'has_active_engagement': True},
        'action_type': 'email_draft',
        'template': {
            'subject': 'Quick update — {client_name}',
            'intent': 'relationship_maintenance',
            'context_keys': ['last_contact_date', 'active_projects', 'health_score']
        },
        'priority': 'low',
        'cooldown_hours': 336  # every 2 weeks
    }
]
```

### Data Schemas
```python
@dataclass
class PreparedAction:
    id: str
    created_at: str
    expires_at: str | None
    action_type: str
    trigger_type: str
    trigger_id: str | None
    entity_type: str | None
    entity_id: str | None
    priority: str
    status: str
    content: dict          # the draft
    context: dict          # why it was prepared
    modified_content: dict | None

@dataclass
class DispatchResult:
    action_id: str
    success: bool
    writer_used: str       # 'GmailWriter' | 'AsanaWriter' | etc.
    external_id: str | None  # ID returned from external system
    error: str | None
    dispatched_at: str
```

### API Endpoints
```
GET    /api/v2/prepared-actions?status=staged&entity_type=...&entity_id=...&action_type=...
GET    /api/v2/prepared-actions/:id
POST   /api/v2/prepared-actions/prepare          (on-demand preparation)
PATCH  /api/v2/prepared-actions/:id/approve
PATCH  /api/v2/prepared-actions/:id/modify       (body: modified_content)
PATCH  /api/v2/prepared-actions/:id/dismiss      (body: reason)
GET    /api/v2/preparation-rules
PATCH  /api/v2/preparation-rules/:id             (enable/disable, adjust cooldown)
POST   /api/v2/prepared-actions/expire-stale     (maintenance endpoint)
```

## Validation
- [ ] Signal triggers correctly matched to preparation rules
- [ ] Prediction triggers correctly matched to preparation rules
- [ ] Cooldown prevents duplicate preparations for same entity
- [ ] On-demand preparation creates correctly-structured staged action
- [ ] Approve → dispatches via correct writer and records in decision journal
- [ ] Modify → stores changes, doesn't dispatch until explicitly approved
- [ ] Dismiss → records in decision journal, feeds behavioral patterns
- [ ] Stale expiry runs without affecting non-expired actions
- [ ] All action types (email, asana, calendar, chat) representable in content schema
- [ ] Preparation rules can be enabled/disabled without code changes

## Files Created
- `lib/intelligence/preparation_engine.py`
- `lib/intelligence/preparation_rules.py`
- `api/prepared_actions_router.py`
- `tests/test_preparation_engine.py`

## Estimated Effort
Large — ~900 lines (engine + rules + dispatch routing + API)
