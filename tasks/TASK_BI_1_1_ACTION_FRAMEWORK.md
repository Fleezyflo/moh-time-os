# BI-1.1: Action Execution Framework + Approval Workflow

## Objective
Build a typed action system that connects intelligence outputs (patterns, resolution items, scenario results) to external write operations, with mandatory human approval before execution.

## Context
Resolution queue (IE-6.1) identifies actions. This framework executes them. But blindly writing to Asana/Gmail/Calendar is dangerous. Every action must be: proposed → reviewed → approved → executed → logged.

## Implementation

### Action Types
```python
class ActionType(Enum):
    CREATE_ASANA_TASK = "create_asana_task"
    UPDATE_ASANA_TASK = "update_asana_task"
    COMMENT_ASANA_TASK = "comment_asana_task"
    DRAFT_EMAIL = "draft_email"
    CREATE_CALENDAR_EVENT = "create_calendar_event"
    SEND_CHAT_MESSAGE = "send_chat_message"
    SEND_CHAT_CARD = "send_chat_card"

class ActionStatus(Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"

@dataclass
class Action:
    id: str
    type: ActionType
    status: ActionStatus
    source: str  # "resolution_queue", "scenario", "manual"
    source_id: str  # resolution item ID, scenario ID
    payload: dict  # type-specific parameters
    proposed_at: str
    approved_by: str | None
    approved_at: str | None
    executed_at: str | None
    result: dict | None
    error: str | None
```

### Approval Workflow
```
Pattern/Resolution → Action PROPOSED → Notification to Chat
                                           ↓
                     User clicks APPROVE → Action APPROVED → Execute
                     User clicks REJECT  → Action REJECTED → Log
                                           ↓
                                    COMPLETED or FAILED → Audit log
```

### Execution Engine
```python
class ActionExecutor:
    def __init__(self):
        self.handlers: dict[ActionType, ActionHandler] = {
            ActionType.CREATE_ASANA_TASK: AsanaTaskCreator(),
            ActionType.DRAFT_EMAIL: GmailDraftCreator(),
            ActionType.CREATE_CALENDAR_EVENT: CalendarEventCreator(),
            ActionType.SEND_CHAT_MESSAGE: ChatMessageSender(),
        }

    def execute(self, action: Action) -> ActionResult:
        if action.status != ActionStatus.APPROVED:
            raise ValueError("Action must be approved before execution")
        handler = self.handlers[action.type]
        try:
            result = handler.execute(action.payload)
            action.status = ActionStatus.COMPLETED
            action.result = result
        except Exception as e:
            action.status = ActionStatus.FAILED
            action.error = str(e)
        self.audit_log(action)
        return result
```

### API Endpoints
```
GET  /api/v1/actions/pending     — list proposed actions awaiting approval
POST /api/v1/actions/{id}/approve — approve action for execution
POST /api/v1/actions/{id}/reject  — reject action
GET  /api/v1/actions/history     — executed action log
```

## Validation
- [ ] Actions created from resolution queue items
- [ ] Proposed actions visible via API and Chat notification
- [ ] Approval required before any execution
- [ ] Rejection logs reason and prevents execution
- [ ] Every executed action has audit trail entry
- [ ] Failed actions don't leave partial state

## Files Created
- `lib/actions/framework.py` — Action, ActionExecutor, ActionHandler protocol
- `lib/actions/handlers/` — per-integration handler directory
- `api/server.py` — action management endpoints

## Estimated Effort
Large — ~300 lines framework + API + approval flow
