# PI-3.1: Email & Communication Drafting

## Objective
Build context-aware email drafting, calendar event proposals, and Google Chat message drafting. Every draft draws on everything the system knows: client health, payment status, communication history, project status, and relationship tone. All drafts staged for review — never auto-sent. Support both trigger-based (system detects a need) and on-demand (you ask for a draft) creation.

## Implementation

### CommunicationDrafter (`lib/intelligence/communication_drafter.py`)
```python
class CommunicationDrafter:
    """Context-aware drafting for emails, calendar events, and chat messages."""

    def draft_email(self, entity_type: str, entity_id: str,
                    intent: str, instructions: str = None) -> PreparedAction:
        """
        Draft an email using full entity context.

        Intents:
          'warm_followup' — client gone quiet, gentle check-in
          'payment_reminder' — overdue invoice, tone based on payment history
          'project_update' — status update on deliverables
          'meeting_followup' — post-meeting summary and next steps
          'relationship_maintenance' — periodic touch-base
          'escalation' — serious concern requiring attention
          'custom' — use instructions for freeform drafting

        Context automatically gathered:
          - Client name, company, primary contact email
          - Health score and trend
          - Outstanding invoices (amounts, days overdue)
          - Active project names and status
          - Last communication date and channel
          - Communication frequency pattern
          - Recent signals and predictions
          - Decision history (from Brief 22)
        """

    def draft_calendar_event(self, entity_type: str, entity_id: str,
                              intent: str, instructions: str = None) -> PreparedAction:
        """
        Propose a calendar event.

        Intents:
          'review_meeting' — schedule a review session
          'followup_call' — schedule a follow-up
          'deadline_review' — schedule before a predicted deadline
          'custom' — freeform

        Auto-populated:
          - Attendee email from entity contacts
          - Duration based on meeting type (30min call, 1hr review)
          - Suggested time slots from availability patterns
          - Description with context and agenda items
        """

    def draft_chat_message(self, entity_type: str, entity_id: str,
                            intent: str, instructions: str = None) -> PreparedAction:
        """
        Draft a Google Chat message.

        Intents:
          'quick_update' — brief status ping
          'heads_up' — alert about an issue
          'request_input' — ask for information or decision
          'custom' — freeform
        """

    def gather_context(self, entity_type: str, entity_id: str) -> DraftContext:
        """
        Collect all relevant context for drafting.
        Pulls from: client table, health engine, invoice data,
        engagement data, communication history, decision journal,
        active signals, predictions.
        """
```

### Draft Templates
```python
DRAFT_TEMPLATES = {
    'warm_followup': {
        'subject_pattern': 'Quick check-in — {client_name}',
        'tone': 'warm_professional',
        'max_length': 150,  # words
        'structure': ['greeting', 'context_reference', 'soft_ask', 'sign_off'],
        'context_required': ['client_name', 'last_contact_days', 'active_projects'],
    },
    'payment_reminder': {
        'subject_pattern': 'Invoice #{invoice_number} — reminder',
        'tone': 'polite_firm',
        'max_length': 120,
        'structure': ['greeting', 'invoice_reference', 'amount_due', 'payment_request', 'sign_off'],
        'context_required': ['client_name', 'invoice_number', 'invoice_amount', 'days_overdue'],
        'tone_escalation': {
            'days_overdue_lt_14': 'gentle',
            'days_overdue_lt_30': 'firm',
            'days_overdue_gte_30': 'direct'
        }
    },
    'meeting_followup': {
        'subject_pattern': 'Following up — {meeting_subject}',
        'tone': 'professional',
        'max_length': 200,
        'structure': ['greeting', 'meeting_reference', 'key_points', 'next_steps', 'sign_off'],
        'context_required': ['meeting_subject', 'attendees', 'meeting_date'],
    },
    'relationship_maintenance': {
        'subject_pattern': 'Touching base — {client_name}',
        'tone': 'casual_professional',
        'max_length': 100,
        'structure': ['greeting', 'recent_achievement', 'open_question', 'sign_off'],
        'context_required': ['client_name', 'recent_positive_data_point'],
    }
}
```

### Draft Content Builder
```python
class DraftContentBuilder:
    """Build draft content from templates and context."""

    def build_email_content(self, template: dict, context: DraftContext) -> dict:
        """
        Returns: {
            'to': ['email@example.com'],
            'cc': [],
            'subject': 'Resolved subject line',
            'body': 'Full email body text',
            'body_html': '<p>...</p>',
            'intent': 'warm_followup',
            'tone_used': 'warm_professional',
            'context_summary': 'Client health at 58, no contact 12 days, 2 active projects'
        }
        """

    def build_calendar_content(self, intent: str, context: DraftContext) -> dict:
        """
        Returns: {
            'summary': 'Review meeting — Client X',
            'description': 'Agenda items...',
            'attendees': ['email@example.com'],
            'duration_minutes': 60,
            'suggested_slots': [{'start': '...', 'end': '...'}],
            'context_summary': '...'
        }
        """

    def build_chat_content(self, intent: str, context: DraftContext) -> dict:
        """
        Returns: {
            'space': 'spaces/xxx',
            'text': 'Message content',
            'context_summary': '...'
        }
        """
```

### API Endpoints
```
POST /api/v2/draft/email         (body: entity_type, entity_id, intent, instructions)
POST /api/v2/draft/calendar      (body: entity_type, entity_id, intent, instructions)
POST /api/v2/draft/chat          (body: entity_type, entity_id, intent, instructions)
GET  /api/v2/draft/templates     (list available templates and intents)
GET  /api/v2/draft/context/:entity_type/:entity_id  (preview what context would be gathered)
```

## Validation
- [ ] Email drafts include correct recipient from entity contacts
- [ ] Email tone adjusts based on intent and context (payment reminder escalation)
- [ ] Calendar proposals include valid attendee emails and reasonable time slots
- [ ] Chat messages are concise and contextually appropriate
- [ ] Context gathering pulls from all relevant data sources (health, invoices, projects, history)
- [ ] On-demand drafting works with custom instructions
- [ ] Trigger-based drafting fires correctly from preparation engine rules
- [ ] Draft content doesn't include stale or incorrect data
- [ ] All drafts create PreparedAction entries (staged, not dispatched)
- [ ] Templates are extensible without code changes

## Files Created
- `lib/intelligence/communication_drafter.py`
- `lib/intelligence/draft_templates.py`
- `api/drafting_router.py`
- `tests/test_communication_drafter.py`

## Estimated Effort
Large — ~800 lines (drafting engine + templates + context gathering + 3 action types)
