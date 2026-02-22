# BI-3.1: Gmail Drafts + Calendar Automation

## Objective
Compose Gmail drafts for invoice follow-ups and client communications, and create Calendar events for review meetings — all through the action framework.

## Context
Gmail scope is currently readonly. Calendar scope is readonly. Both need upgrading to read-write. Draft mode (not sending) is the safe default — Molham reviews before sending.

## Implementation

### Gmail OAuth Scope Upgrade
```python
# From:
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
# To:
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",  # create drafts
]
```

### Gmail Draft Handler
```python
class GmailDraftCreator(ActionHandler):
    def execute(self, payload: dict) -> dict:
        # payload: {to, subject, body_html, cc, reply_to_message_id}
        message = MIMEMultipart()
        message["to"] = payload["to"]
        message["subject"] = payload["subject"]
        if payload.get("cc"):
            message["cc"] = payload["cc"]
        message.attach(MIMEText(payload["body_html"], "html"))

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        draft = gmail_service.users().drafts().create(
            userId="me",
            body={"message": {"raw": raw, "threadId": payload.get("reply_to_thread_id")}}
        ).execute()
        return {"draft_id": draft["id"], "message_id": draft["message"]["id"]}
```

### Calendar Event Handler
```python
class CalendarEventCreator(ActionHandler):
    def execute(self, payload: dict) -> dict:
        # payload: {summary, start, end, attendees, description, calendar_id}
        event = {
            "summary": payload["summary"],
            "start": {"dateTime": payload["start"], "timeZone": "Asia/Dubai"},
            "end": {"dateTime": payload["end"], "timeZone": "Asia/Dubai"},
            "attendees": [{"email": e} for e in payload.get("attendees", [])],
            "description": payload.get("description", ""),
        }
        result = calendar_service.events().insert(
            calendarId=payload.get("calendar_id", "primary"),
            body=event
        ).execute()
        return {"event_id": result["id"], "html_link": result["htmlLink"]}
```

### Use Cases Wired
1. **Invoice follow-up** → Gmail draft to client: "Invoice #{number} is {days} days overdue..."
2. **Client risk alert** → Gmail draft to account manager with context summary
3. **Quarterly review** → Calendar event: "Q1 Review: {client_name}" with team attendees
4. **Capacity meeting** → Calendar event: "Capacity Planning" when utilization >85%
5. **Focus time blocking** → Calendar event: "Deep Work Block" for team members with meeting overload

## Validation
- [ ] Gmail draft created (visible in Drafts folder, NOT sent)
- [ ] Draft contains correct to/cc/subject/body
- [ ] Thread reply drafts linked to correct thread
- [ ] Calendar events created with correct time, attendees, description
- [ ] All writes go through approval workflow
- [ ] Audit log captures draft ID and event ID

## Files Created
- `lib/actions/handlers/gmail.py` — GmailDraftCreator
- `lib/actions/handlers/calendar.py` — CalendarEventCreator

## Estimated Effort
Medium — ~200 lines across both handlers
