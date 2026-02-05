# MOH TIME OS

Personal Operating System for executive productivity. Runs autonomously without AI in the critical path.

## Quick Start

```bash
# Start API server
cd ~/clawd/moh_time_os
source .venv/bin/activate
python3 -m api.server

# Dashboard available at http://localhost:8420
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AUTONOMOUS LOOP                           │
│  (runs via system cron every 15 min, no AI required)        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐                 │
│  │ COLLECT │ → │ ANALYZE │ → │ SURFACE │                   │
│  │ Gmail   │    │Priority │    │Anomalies│                  │
│  │Calendar │    │ Queue   │    │ Alerts  │                  │
│  │ Tasks   │    │         │    │         │                  │
│  └─────────┘    └─────────┘    └─────────┘                 │
│       ↓              ↓              ↓                       │
│  ┌─────────┐    ┌─────────┐                                │
│  │ REASON  │ → │ EXECUTE │                                 │
│  │Decisions│    │ Actions │                                │
│  │Proposals│    │ Bundles │                                │
│  └─────────┘    └─────────┘                                │
│                                                              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    GOVERNANCE LAYER                          │
│  • Domain modes: observe → propose → auto_low → auto_high   │
│  • All writes create change bundles (rollback enabled)      │
│  • Emergency brake available                                 │
└─────────────────────────────────────────────────────────────┘
```

## API Endpoints (40+)

### Core
- `GET /api/health` - System health
- `GET /api/overview` - Dashboard home data
- `GET /api/summary` - Quick summary

### Priorities
- `GET /api/priorities` - Priority queue
- `POST /api/priorities/:id/complete` - Mark complete
- `POST /api/priorities/:id/snooze` - Defer due date
- `POST /api/priorities/:id/delegate` - Delegate to team

### Data
- `GET /api/tasks` - All tasks
- `GET /api/calendar` - Calendar with analysis
- `GET /api/inbox` - Pending communications
- `GET /api/team` - Team members
- `GET /api/projects` - Projects with health
- `GET /api/insights` - System insights
- `GET /api/decisions` - Pending decisions
- `POST /api/decisions/:id` - Approve/reject

### Governance
- `GET /api/governance` - Current settings
- `PUT /api/governance/:domain` - Set domain mode
- `POST /api/governance/emergency-brake` - Activate brake
- `DELETE /api/governance/emergency-brake` - Release brake

### Bundles (Rollback)
- `GET /api/bundles` - List change bundles
- `GET /api/bundles/:id` - Get bundle details
- `POST /api/bundles/:id/rollback` - Rollback change

### System
- `POST /api/sync` - Trigger data sync
- `POST /api/cycle` - Run autonomous cycle
- `GET /api/calibration` - Last calibration report
- `POST /api/calibration/run` - Run calibration
- `POST /api/feedback` - Submit feedback

## Governance Modes

| Mode | Description |
|------|-------------|
| `observe` | Only watch and analyze, never act |
| `propose` | Propose actions, require approval for all |
| `auto_low` | Auto low-risk (confidence > threshold), propose high-risk |
| `auto_high` | Auto most things, only critical needs approval |

## Directory Structure

```
moh_time_os/
├── api/
│   └── server.py         # FastAPI server (40+ endpoints)
├── config/
│   ├── governance.yaml   # Domain modes, rate limits
│   └── intelligence.yaml # Scoring weights
├── data/
│   ├── state.db         # SQLite database
│   └── bundles/         # Change bundles for rollback
├── lib/
│   ├── autonomous_loop.py
│   ├── collectors/      # Gmail, Calendar, Tasks
│   ├── analyzers/       # Priority, Anomaly, Time
│   ├── governance.py    # Governance engine
│   ├── change_bundles.py
│   ├── calibration.py   # Weekly calibration
│   └── notifier/        # Notification engine
├── ui/
│   └── index.html       # Dashboard (Tailwind)
└── README.md
```

## Cron Schedule

| Interval | Job |
|----------|-----|
| Every 5 min | Data sync from Gmail, Calendar, Tasks |
| Every 15 min | Full autonomous loop cycle |
| 09:00 Dubai | Daily morning brief |
| 13:00 Dubai | Midday pulse |
| 19:30 Dubai | End of day summary |
| Sunday midnight | Weekly calibration |

## Key Invariants

1. **NO AI IN CRITICAL PATH** - System operates independently
2. **GOVERNANCE GATES ALL WRITES** - Every write checked against mode
3. **ATTRIBUTION REQUIRED** - All outputs trace to sources
4. **REVERSIBLE BY DEFAULT** - All changes produce rollback bundles
5. **USER CONTROLS AUTONOMY** - Per-domain mode switching

## Development

```bash
# Install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run tests
python3 -m pytest tests/

# Run single cycle
python3 -m lib.autonomous_loop run

# Check status
python3 -m lib.autonomous_loop status
```

## Dashboard

Access at `http://localhost:8420` when API server is running.

Features:
- Priority queue with complete/snooze/delegate actions
- Today's calendar and events
- Pending approvals panel
- Anomaly alerts
- Governance controls (domain modes, emergency brake)
- Recent changes with rollback
- Feedback mechanism
