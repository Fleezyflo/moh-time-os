# IE-6.1: Resolution Queue Automation

## Objective
Move the resolution queue from framework-only to actual automated execution — at least 3 automation types running in production.

## Context
`resolution_queue` table exists (or will after Brief 7). The framework for tracking issues → resolutions exists. But no actual automation executes. Issues are logged but never acted on. This task wires real actions.

## Implementation

### Automation Types

1. **Escalation Notification**
   - Trigger: issue severity = critical AND age > 24 hours AND unresolved
   - Action: Send Google Chat notification to project owner + team lead
   - Template: "[ESCALATION] {issue_type} on {entity_name} — unresolved for {age_hours}h"

2. **Task Reassignment Recommendation**
   - Trigger: capacity_crisis pattern detected for team member
   - Action: Identify overloaded member's tasks, find team members with available capacity, generate reassignment recommendation
   - Output: structured recommendation stored in resolution_queue with suggested reassignments

3. **Client Health Alert**
   - Trigger: client_risk pattern severity ≥ warning
   - Action: Compile client health summary (overdue tasks, unanswered emails, upcoming deadlines), send via Google Chat
   - Template: Card with client name, risk signals, recommended actions

4. **Invoice Follow-Up**
   - Trigger: invoice overdue > 14 days AND no communication in last 7 days
   - Action: Generate follow-up recommendation with invoice details, send notification
   - Template: "[FOLLOW-UP] Invoice {number} for {client} — {days} days overdue, ${amount}"

### Resolution Queue Manager
```python
class ResolutionQueueManager:
    def __init__(self, db, notifier, pattern_engine):
        self.automations = [
            EscalationAutomation(notifier),
            ReassignmentAutomation(db),
            ClientHealthAutomation(notifier),
            InvoiceFollowUpAutomation(notifier),
        ]

    def process_queue(self):
        """Process all pending resolution items."""
        pending = self.db.get_pending_resolutions()
        for item in pending:
            for automation in self.automations:
                if automation.matches(item):
                    result = automation.execute(item)
                    self.db.update_resolution(item.id, result)
                    break

    def generate_new_items(self, patterns: list[Pattern], insights: list[Insight]):
        """Create resolution items from detected patterns and insights."""
        for pattern in patterns:
            if pattern.severity in ("critical", "warning"):
                self.db.create_resolution_item(
                    source_type="pattern",
                    source_id=pattern.id,
                    issue_type=pattern.pattern_type,
                    entity_id=pattern.entity_id,
                    severity=pattern.severity,
                    recommended_action=pattern.recommended_action,
                )
```

### Integration
- Runs after pattern engine in the autonomous loop cycle
- New patterns → new resolution items
- Existing items processed by matching automations
- Results logged in resolution_queue with status tracking

## Validation
- [ ] Escalation notifications fire for aged critical issues
- [ ] Reassignment recommendations generated for overloaded members
- [ ] Client health alerts sent for at-risk clients
- [ ] Invoice follow-ups triggered for overdue invoices
- [ ] All automations log results in resolution_queue
- [ ] No duplicate notifications (dedup by entity + issue type + window)

## Files Created/Modified
- `lib/intelligence/resolution_manager.py` — new
- `lib/intelligence/automations/` — new directory with automation implementations
- `lib/autonomous_loop.py` — wire resolution processing into cycle
- `tests/test_resolution_manager.py` — new

## Estimated Effort
Large — ~350 lines, 4 automation types + queue management
