# IX-1.1: UI/UX Design System & Wireframes

## Objective
Establish the visual design system (colors, typography, spacing, components) and create wireframes for every dashboard view before writing any frontend code.

## Context
MOH Time OS currently has no designed interface — data is served via JSON API endpoints. Before building, we design. This prevents throwaway code and ensures the interface serves Molham's actual workflow.

## Deliverables

### 1. Design System
- **Color palette**: Primary, secondary, accent, semantic (success/warning/danger/info), background tones
- **Typography**: Font family, size scale, weight scale, line heights
- **Spacing system**: 4px base unit grid
- **Component library**: Buttons, cards, tables, charts, badges, alerts, navigation
- **Data visualization palette**: Chart colors that work for colorblind users

### 2. Wireframes

**Dashboard Home** — The "command center" view:
- Agency health score (large, prominent)
- Active patterns (critical/warning counts)
- Capacity utilization heat map
- Revenue/cost summary
- Quick links to deep-dive views

**Client Detail View**:
- Client health score + trajectory
- Cost-to-serve breakdown
- Communication timeline
- Task status overview
- Invoice status

**Team Member View**:
- Capacity utilization gauge
- Task load distribution
- Meeting density
- Communication volume
- Trajectory indicators

**Resolution Queue View**:
- Pending items sorted by severity
- Action buttons (approve, dismiss, escalate)
- History of resolved items
- Automation log

**Scenario Modeling View**:
- Input form (scenario type, parameters)
- Impact visualization (before/after)
- Affected entities list
- Confidence indicator

### 3. Interaction Patterns
- Navigation: sidebar + breadcrumb
- Data density: progressive disclosure (summary → detail on click)
- Refresh: auto-refresh indicator with manual override
- Notifications: toast for real-time events, badge counts

## Approach
- Design in HTML/CSS mockups (not image files — interactive and iterative)
- Review with Molham before proceeding to IX-2.1
- Design must accommodate all data from Briefs 9-11 intelligence outputs

## Validation
- [ ] Design system documented with all tokens (colors, fonts, spacing)
- [ ] Wireframes for all 5 primary views
- [ ] Mobile-responsive layouts included
- [ ] Molham reviews and approves before implementation

## Files Created
- `frontend/design-system.html` — interactive design system reference
- `frontend/wireframes/` — HTML wireframes for each view

## Estimated Effort
Medium — ~2-3 days of design work, Molham review required
