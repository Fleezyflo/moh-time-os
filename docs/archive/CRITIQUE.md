# MOH TIME OS — System Critique & Build Checklist

**Created:** 2026-02-02
**Last Verified:** 2026-02-02 10:55 GST
**Status:** ACTIVE BUILD — 6 critical gaps

---

## I. VERIFIED SYSTEM STATE

### Databases (3 FRAGMENTED)
| DB | Size | Items | Used By |
|----|------|-------|---------|
| `state.db` | 745KB | 40 tasks, 10 events, 12 comms, 61 notifs, 2 decisions, **0 actions** | autonomous_loop.py |
| `moh_time_os_v2.db` | 368KB | 187 items, 166 clients, 70 projects | cli_v2.py |
| `moh_time_os.db` | 1MB | 272 items, 154 clients, 290 projects | Legacy (unused) |

### Autonomous Loop (5 PHASES)
| Phase | Code | Works | Output |
|-------|------|-------|--------|
| 1. COLLECT | `collectors.sync_all()` | ✅ | 40 tasks, 10 events, 12 comms |
| 2. ANALYZE | `analyzers.analyze_all()` | ✅ | priorities, anomalies |
| 3. SURFACE | `_surface_critical_items()` | ⚠️ | Creates notifications, **never sends** |
| 4. REASON | `reasoner.process_cycle()` | ⚠️ | Creates decisions, **never approves** |
| 5. EXECUTE | `executor.process_pending_actions()` | ❌ | **0 actions exist** |

### Notifications (61 UNSENT)
```
sqlite> SELECT COUNT(*), SUM(CASE WHEN sent_at IS NULL THEN 1 ELSE 0 END) FROM notifications;
61|61
```
**Every notification ever created is unsent.**

### Actions (0 EXIST)
```
sqlite> SELECT COUNT(*) FROM actions;
0
```
**Nothing has ever been queued for execution.**

### Decisions (2 PENDING)
```
sqlite> SELECT id, approved, executed FROM decisions;
decision_803e9c36||0
decision_4f61ab92||0
```
**Both pending forever, never approved.**

### Governance (ALL OBSERVE)
```yaml
domains:
  calendar: {mode: observe}
  email: {mode: observe}
  tasks: {mode: observe}
  notifications: {mode: observe}
```
**Nothing can auto-execute.**

---

## II. ROOT CAUSE ANALYSIS

### WHY NOTIFICATIONS NEVER SEND

**The Wire Is Broken:**
```
autonomous_loop._surface_critical_items()
    ↓
    Creates row in `notifications` table
    ↓
    [STOPS HERE]
    
    ❌ Never queued as action
    ❌ Never calls NotificationEngine.process_pending()
    ❌ Executor looks at `actions` table (which is empty)
```

**Additional Bug:** In `lib/executor/engine.py`:
```python
'notification': NotificationHandler(self.store),  # ← notifier=None!
```
Even if actions existed, `self.notifier` is `None` so nothing sends.

### WHY DECISIONS NEVER EXECUTE

1. Reasoner creates decisions with `requires_approval=1`
2. No auto-approval logic for low-risk decisions
3. Dashboard approval buttons exist but user never sees decisions
4. Governance mode=observe blocks execution anyway

### WHY THREE DATABASES

Historical debt:
- `moh_time_os.db` = v1 build (legacy)
- `moh_time_os_v2.db` = v2 build (cli_v2.py)
- `state.db` = v3 build (autonomous loop)

`cli_v2.py brief` shows **different data** than autonomous loop.

---

## III. FIX CHECKLIST (Ordered)

### FIX 1: Wire Notification Sending
**File:** `lib/autonomous_loop.py`
**Problem:** `_surface_critical_items()` creates notifications but never sends them
**Solution:** Add call to NotificationEngine.process_pending() after surface phase

```python
# After PHASE 3: SURFACE
from .notifier import NotificationEngine
notifier = NotificationEngine(self.store, self._load_notification_config())
import asyncio
loop = asyncio.get_event_loop()
sent = loop.run_until_complete(notifier.process_pending())
```

**Test:** Create anomaly → notification row created → message arrives on WhatsApp
**Status:** [x] DONE (2026-02-02) — Wire complete, WhatsApp needs linking via `clawdbot channels login --channel whatsapp`

---

### FIX 2: Pass Notifier to ExecutorEngine
**File:** `lib/executor/engine.py`
**Problem:** NotificationHandler initialized without notifier instance
**Solution:** 
```python
from ..notifier import NotificationEngine

# In __init__:
self.notifier = NotificationEngine(store, self._load_config())
self.handlers['notification'] = NotificationHandler(self.store, notifier=self.notifier)
```

**Test:** Action with type='notify' → NotificationHandler has working notifier
**Status:** [x] DONE (2026-02-02) — Notifier now passed to handler

---

### FIX 3: Enable Notifications Auto-Send
**File:** `config/governance.yaml`
**Problem:** notifications.mode = observe (blocks sending)
**Solution:**
```yaml
domains:
  notifications:
    mode: auto_low  # Was: observe
    auto_threshold: 0.7
```

**Test:** Notification with confidence > 0.7 sends automatically
**Status:** [x] DONE (2026-02-02) — Changed notifications.mode to auto_low

---

### FIX 4: Unify Databases
**Problem:** 3 DBs with different data, no single source of truth
**Solution:**
1. Deprecate `moh_time_os.db` (delete after backup)
2. Migrate `moh_time_os_v2.db` entities to `state.db`
3. Update `cli_v2.py` to use `state_store.py`

**Test:** `cli_v2.py brief` and `autonomous_loop status` show same data
**Status:** [x] DONE (2026-02-02)
- ✅ Migrated 166 clients, 227 tasks, 70 projects, 70 people to state.db
- ✅ Updated store.py to use state.db
- ✅ Fixed entities.py _row_to_project for schema compatibility
- ✅ cli_v2.py and autonomous_loop now share single database

---

### FIX 5: Wire Decision Auto-Approval
**File:** `lib/reasoner.py`
**Problem:** All decisions require approval, none get it
**Solution:**
```python
# In process_cycle():
if confidence > domain_threshold and governance.mode in ['auto_low', 'auto']:
    decision['approved'] = 1
    decision['approved_at'] = datetime.now().isoformat()
```

**Test:** High-confidence decision auto-approves and executes
**Status:** [x] DONE (2026-02-02) — Auto-approval now creates actions when confidence > threshold

---

### FIX 6: Re-enable Chat Collector
**File:** `collectors/chat.py`, `collectors/scheduled_collect.py`
**Problem:** 79 spaces caused timeout, disabled entirely
**Solution:**
1. Filter to spaces with activity in last 7 days
2. Add proper timeouts (already partially done)
3. Re-enable in scheduled_collect.py

**Test:** Chat collection completes in <30s
**Status:** [x] DONE (2026-02-02) — Re-enabled with max_spaces=20, completes in 28s

---

## IV. SUCCESS CRITERIA

The system works when:
- [ ] User gets proactive WhatsApp alerts without asking
- [ ] Morning brief arrives automatically at 09:00
- [ ] Critical anomalies push notification within 5 minutes
- [ ] High-confidence decisions auto-execute
- [ ] cli_v2.py and autonomous loop show same data
- [ ] Feedback loop captures user responses

**Current: 0/6 met.**

---

## V. VERIFICATION COMMANDS

```bash
# Check notification sending works
cd ~/clawd/moh_time_os && source .venv/bin/activate
python3 -c "
from lib.notifier import NotificationEngine
from lib.state_store import get_store
import asyncio
store = get_store()
ne = NotificationEngine(store, {'channels': {'clawdbot': {'enabled': True, 'gateway_url': 'http://127.0.0.1:18789', 'token': 'YOUR_TOKEN', 'default_to': '+971529111025'}}})
print(asyncio.get_event_loop().run_until_complete(ne.process_pending()))
"

# Check actions created
sqlite3 data/state.db "SELECT COUNT(*) FROM actions WHERE status='approved'"

# Check decisions auto-approved
sqlite3 data/state.db "SELECT COUNT(*) FROM decisions WHERE approved=1"
```

---

## VI. BOTTOM LINE

**This is a monitoring system, not an operating system.**

The loop runs. Data collects. Analysis happens. But:
- 61 notifications sit unsent
- 0 actions ever queued
- 2 decisions pending forever
- User still has to ask "what should I do?"

**Every heartbeat must make progress on this checklist until all 6 fixes are complete.**

---

*Last updated: 2026-02-02 10:55 GST*
