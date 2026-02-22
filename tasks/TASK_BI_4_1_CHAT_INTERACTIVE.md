# BI-4.1: Google Chat Interactive Mode

## Objective
Transform Google Chat from one-way notifications into a bidirectional interface — slash commands for querying system data, interactive cards with action buttons, and message-based commands.

## Context
Brief 8 (UR-4.1) builds one-way webhook notifications. This task builds the reverse: Chat → MOH Time OS. Uses Google Chat API's incoming webhook for outbound, and Cloud Functions / HTTP endpoint for inbound.

## Implementation

### Inbound Message Handler
```python
# api/chat_handler.py
@app.post("/api/v1/chat/webhook")
async def handle_chat_event(request: Request):
    """Receive events from Google Chat (messages, card clicks, slash commands)."""
    event = await request.json()
    event_type = event.get("type")

    if event_type == "MESSAGE":
        return handle_message(event)
    elif event_type == "CARD_CLICKED":
        return handle_card_click(event)
    elif event_type == "ADDED_TO_SPACE":
        return handle_added_to_space(event)
```

### Slash Commands
| Command | Description | Response |
|---------|-------------|----------|
| `/status` | System health summary | Card with cycle status, pattern counts, queue size |
| `/client {name}` | Client health snapshot | Card with health score, risk signals, cost-to-serve |
| `/capacity` | Team utilization overview | Card with utilization bars per team member |
| `/queue` | Pending resolution items | Card with top 5 items + approve/dismiss buttons |
| `/scenario add-client {name}` | Quick scenario | Card with capacity impact projection |

### Interactive Cards
```python
def build_resolution_card(item: ResolutionItem) -> dict:
    return {
        "cards": [{
            "header": {"title": f"🔔 {item.issue_type}", "subtitle": item.entity_name},
            "sections": [{
                "widgets": [
                    {"textParagraph": {"text": item.description}},
                    {"textParagraph": {"text": f"Severity: {item.severity} | Age: {item.age_hours}h"}},
                    {"buttonList": {"buttons": [
                        {"text": "✅ Approve", "onClick": {"action": {
                            "function": "approve_action",
                            "parameters": [{"key": "action_id", "value": str(item.action_id)}]
                        }}},
                        {"text": "❌ Dismiss", "onClick": {"action": {
                            "function": "dismiss_action",
                            "parameters": [{"key": "action_id", "value": str(item.action_id)}]
                        }}},
                    ]}}
                ]
            }]
        }]
    }
```

### Card Click Handling
```python
def handle_card_click(event: dict) -> dict:
    action = event["action"]
    function_name = action["actionMethodName"]
    params = {p["key"]: p["value"] for p in action.get("parameters", [])}

    if function_name == "approve_action":
        result = action_executor.approve_and_execute(params["action_id"], approved_by="chat")
        return {"text": f"✅ Action approved and executed: {result.summary}"}
    elif function_name == "dismiss_action":
        action_executor.reject(params["action_id"], reason="Dismissed via Chat")
        return {"text": "❌ Action dismissed."}
```

### Setup Requirements
- Google Chat API enabled in Google Cloud project
- Chat bot created with HTTP endpoint configured
- Webhook URL for outbound (already in Brief 8)
- Inbound endpoint registered as Chat app's URL

## Validation
- [ ] /status returns live system health card
- [ ] /client {name} returns client health card
- [ ] /queue shows pending items with action buttons
- [ ] Approve button triggers action execution
- [ ] Dismiss button rejects action
- [ ] Card click responses are timely (<3 seconds)
- [ ] Invalid commands return helpful error messages

## Files Created
- `api/chat_handler.py` — inbound event handler
- `lib/chat/commands.py` — slash command implementations
- `lib/chat/cards.py` — card builder functions

## Estimated Effort
Large — ~400 lines, Chat API integration + card builders + command handlers
