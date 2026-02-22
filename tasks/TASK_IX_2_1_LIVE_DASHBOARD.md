# IX-2.1: Live Intelligence Dashboard

## Objective
Build the primary intelligence dashboard — a web application serving live data from all API endpoints, displaying agency health, client status, capacity, and financial intelligence.

## Context
The API endpoints exist (`api/server.py`), the intelligence modules produce real data (Briefs 9-11), and the design system is established (IX-1.1). This task builds the frontend that connects them all.

## Implementation

### Technology Stack
- **Frontend**: Single-page application (HTML/CSS/JS or lightweight framework)
- **Charts**: Chart.js or D3.js for data visualization
- **API**: Fetch from existing FastAPI/Flask endpoints
- **State**: Client-side state management for navigation and caching
- **Build**: Minimal build tooling — must run without complex build pipeline

### Dashboard Pages

1. **Command Center** (home):
   - Agency health score (from unified signals)
   - Pattern alerts (from pattern engine)
   - Capacity utilization (from capacity_truth)
   - Revenue summary (from cost-to-serve)
   - Cycle status (from /health endpoint)

2. **Client Intelligence**:
   - Client list with health scores
   - Click → client detail: cost-to-serve, communication patterns, task status, trajectories
   - Sortable/filterable by health score, revenue, risk level

3. **Team Capacity**:
   - Team member cards with utilization gauges
   - Meeting density visualization
   - Task distribution chart
   - Overload warnings from pattern engine

4. **Financial Overview**:
   - Revenue by client (bar chart)
   - Cost-to-serve comparison (client profitability)
   - Invoice aging (overdue heatmap)
   - Monthly trends (line chart)

5. **Agency Snapshot** (existing 13 pages):
   - Render all snapshot pages with live data
   - Replace hardcoded Feb 9 data with current cycle data

### API Integration
```javascript
// All data fetched from existing API endpoints
const apiBase = "/api/v1";

async function loadDashboard() {
    const [health, snapshot, signals, patterns] = await Promise.all([
        fetch(`${apiBase}/health`).then(r => r.json()),
        fetch(`${apiBase}/snapshot`).then(r => r.json()),
        fetch(`${apiBase}/signals`).then(r => r.json()),
        fetch(`${apiBase}/patterns`).then(r => r.json()),
    ]);
    renderCommandCenter(health, snapshot, signals, patterns);
}
```

## Validation
- [ ] Dashboard loads in <2 seconds
- [ ] All 5 primary views render with live data
- [ ] Charts display correctly on desktop and tablet
- [ ] Navigation works without full page reloads
- [ ] Data refreshes on configured interval
- [ ] Zero hardcoded data — everything from API

## Files Created
- `frontend/index.html` — SPA entry point
- `frontend/app.js` — application logic
- `frontend/styles.css` — design system implementation
- `frontend/components/` — reusable UI components
- `api/server.py` — add any missing endpoints

## Estimated Effort
Large — ~1000+ lines of frontend code, full dashboard implementation
