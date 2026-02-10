# MOH TIME OS

Personal Operating System for executive productivity. Runs autonomously without AI in the critical path.

## Pristine Bootstrap

**Toolchain:** uv (Python package manager)
**API Framework:** FastAPI/Uvicorn
**Database:** SQLite (auto-created on first run)

### Fresh Clone → Running

```bash
# 1. Clone the repo
git clone <repo-url> moh_time_os
cd moh_time_os

# 2. Install dependencies (requires uv: https://docs.astral.sh/uv/)
make setup
# OR: uv sync

# 3. Run verification (optional but recommended)
make verify
# OR: ./scripts/verify_pristine.sh

# 4. Start API server
make run-api
# OR: uv run python -m api.server

# Dashboard available at http://localhost:8420
# API docs at http://localhost:8420/docs
```

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Node.js 18+ (for frontend, optional)

### Development

```bash
# Start both backend and frontend
make dev

# Backend only
make api

# Frontend only
make ui

# Run tests
make test

# Run linter
make lint

# Format code
make format

# Full verification
make verify
```

---

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
└──────────────────────────────────────────────────────────────┘
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

### Health Check
- `GET /api/health` - System health (use for pristine verification)

### Core
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
├── data/                 # Runtime data (gitignored)
│   ├── moh_time_os.db   # SQLite database
│   └── bundles/         # Change bundles for rollback
├── lib/
│   ├── autonomous_loop.py
│   ├── collectors/      # Gmail, Calendar, Tasks
│   ├── analyzers/       # Priority, Anomaly, Time
│   ├── governance.py    # Governance engine
│   ├── change_bundles.py
│   ├── calibration.py   # Weekly calibration
│   └── notifier/        # Notification engine
├── scripts/
│   ├── verify_pristine.sh     # Pristine verification
│   ├── check_no_derived_tracked.sh
│   └── ...
├── tests/
│   ├── contract/        # Contract tests
│   └── negative/        # Negative tests
├── time-os-ui/          # Frontend (Vite + React)
├── pyproject.toml       # Python project config
├── Makefile             # Build targets
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
