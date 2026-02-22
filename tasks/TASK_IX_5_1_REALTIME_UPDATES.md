# IX-5.1: Real-Time Updates & Notification Center

## Objective
Add WebSocket or Server-Sent Events for live data push to the dashboard, plus an in-app notification center showing recent alerts and automation actions.

## Context
Dashboard currently requires manual refresh or polling. With the autonomous loop running every N minutes, the dashboard should update automatically when new data is available. Critical patterns should surface immediately as in-app notifications.

## Implementation

### Real-Time Data Push

**Option A: Server-Sent Events (SSE)** (preferred — simpler, one-directional):
```python
# api/server.py
@app.get("/api/v1/stream")
async def event_stream():
    async def generate():
        while True:
            event = await get_next_event()
            yield f"data: {json.dumps(event)}\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")
```

**Option B: WebSocket** (if bidirectional needed later):
```python
@app.websocket("/api/v1/ws")
async def websocket_endpoint(websocket):
    await websocket.accept()
    while True:
        event = await get_next_event()
        await websocket.send_json(event)
```

### Event Types
- `cycle_complete` — new data available, refresh dashboard
- `pattern_detected` — new pattern found, show notification
- `resolution_created` — new item in queue, update badge count
- `automation_executed` — automation ran, show result
- `health_change` — system health changed (healthy → degraded)

### Notification Center

**In-App Panel** (slide-out from top-right bell icon):
- Chronological list of recent notifications
- Each shows: icon, title, time, severity badge
- Click → navigate to relevant dashboard view
- Mark as read / dismiss
- Filter by type

**Badge Count**:
- Bell icon in header with unread count
- Count reflects unread critical + warning notifications

### Auto-Refresh Logic
```javascript
// On cycle_complete event:
eventSource.addEventListener("cycle_complete", () => {
    // Refresh active dashboard view with new data
    refreshCurrentView();
    // Update last-refresh timestamp
    updateRefreshIndicator();
});

// On pattern_detected event:
eventSource.addEventListener("pattern_detected", (e) => {
    const pattern = JSON.parse(e.data);
    addNotification(pattern);
    incrementBadgeCount();
    if (pattern.severity === "critical") {
        showToast(pattern.description);
    }
});
```

## Validation
- [ ] Dashboard updates automatically after cycle completes (no manual refresh)
- [ ] Critical pattern notifications appear within 5 seconds of detection
- [ ] Notification center shows history of recent events
- [ ] Badge count is accurate
- [ ] SSE/WebSocket reconnects after connection drop
- [ ] No excessive re-rendering (only update changed data)

## Files Created/Modified
- `api/server.py` — add SSE/WebSocket endpoint
- `frontend/realtime.js` — event handling and notification center
- `frontend/notifications.js` — notification UI component

## Estimated Effort
Medium — ~200 lines backend + ~250 lines frontend
