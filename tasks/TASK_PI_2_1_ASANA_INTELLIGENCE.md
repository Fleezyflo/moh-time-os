# PI-2.1: Asana Intelligence Layer

## Objective
Build a unified Asana interface within MOH Time OS — not a mirror of Asana, but an intelligent overlay. Surface tasks that are overdue, blocked, or stale. Show project velocity with trajectory data. Prepare task creation and status updates when the system detects a need. Allow on-demand task management with full context pre-filled.

## Implementation

### AsanaIntelligence (`lib/intelligence/asana_intelligence.py`)
```python
class AsanaIntelligence:
    """Intelligent Asana overlay — watch, analyze, prepare."""

    def get_attention_items(self) -> List[AsanaAttentionItem]:
        """
        Surface Asana items that need your attention:
        - Overdue tasks (assigned to anyone in your projects)
        - Blocked tasks (dependencies not met)
        - Stale tasks (no update in 7+ days on active projects)
        - Tasks with approaching deadlines (3 days or less)
        Returns sorted by priority.
        """

    def get_project_velocity(self, project_gid: str) -> ProjectVelocity:
        """
        Analyze task completion rate, scope changes, and trajectory.
        Uses Brief 11 trajectory data where available.
        Returns: tasks_completed_this_week, avg_completion_rate,
                 scope_added_this_week, projected_completion_date.
        """

    def prepare_task_creation(self, entity_type: str, entity_id: str,
                               intent: str, context: dict) -> PreparedAction:
        """
        System detects a need → prepare a task draft.
        e.g., prediction says milestone will be missed → draft task:
          "Address blocker: [milestone name] at risk"
          with pre-filled project, section, assignee, description.
        """

    def prepare_status_update(self, task_gid: str, new_status: str,
                               reason: str) -> PreparedAction:
        """
        Prepare a task status comment or field update.
        e.g., task has been stale 14 days → prepare comment:
          "Status check: this task hasn't been updated since [date].
           Current blocker appears to be [inferred from context]."
        """

    def search_tasks(self, query: str, project_gid: str = None,
                     status: str = None) -> List[AsanaTaskSummary]:
        """
        Search Asana tasks with intelligent matching.
        Enriches results with MOH Time OS context (entity links, health data).
        """

    def get_project_dashboard(self, project_gid: str) -> AsanaProjectDashboard:
        """
        Unified view: task breakdown by status, velocity chart data,
        attention items, team workload, and any prepared actions for this project.
        """

    def sync_and_analyze(self) -> SyncResult:
        """
        Pull latest Asana data, compare with stored state,
        detect changes worth surfacing (new assignments, status changes,
        overdue transitions). Run on schedule (every 30 min).
        """
```

### Data Schemas
```python
@dataclass
class AsanaAttentionItem:
    task_gid: str
    task_name: str
    project_name: str
    attention_reason: str    # 'overdue' | 'blocked' | 'stale' | 'deadline_approaching'
    severity: str            # 'critical' | 'high' | 'normal'
    days_overdue: int | None
    days_stale: int | None
    deadline: str | None
    assignee: str | None
    entity_link: dict | None  # link to MOH Time OS entity if matched

@dataclass
class ProjectVelocity:
    project_gid: str
    project_name: str
    tasks_total: int
    tasks_completed: int
    tasks_completed_this_week: int
    avg_weekly_completion_rate: float
    scope_added_this_week: int
    projected_completion_date: str | None
    trajectory_direction: str  # 'on_track' | 'slipping' | 'ahead' | 'stalled'

@dataclass
class AsanaProjectDashboard:
    project: ProjectVelocity
    attention_items: List[AsanaAttentionItem]
    task_breakdown: Dict[str, int]   # status → count
    recent_activity: List[dict]       # last 10 changes
    prepared_actions: List[PreparedAction]  # pending for this project
```

### Asana Data Cache Table
```sql
CREATE TABLE asana_task_cache (
    task_gid TEXT PRIMARY KEY,
    project_gid TEXT,
    name TEXT NOT NULL,
    status TEXT,               -- 'open' | 'completed'
    assignee_gid TEXT,
    assignee_name TEXT,
    due_date TEXT,
    completed_at TEXT,
    modified_at TEXT,
    section_name TEXT,
    tags TEXT,                 -- JSON array
    custom_fields TEXT,        -- JSON
    entity_type TEXT,          -- matched MOH entity type
    entity_id TEXT,            -- matched MOH entity id
    synced_at TEXT NOT NULL,
    stale_since TEXT           -- when task was first detected as stale
);

CREATE INDEX idx_asana_cache_project ON asana_task_cache(project_gid, status);
CREATE INDEX idx_asana_cache_due ON asana_task_cache(due_date) WHERE status = 'open';
CREATE INDEX idx_asana_cache_stale ON asana_task_cache(stale_since) WHERE stale_since IS NOT NULL;
```

### API Endpoints
```
GET  /api/v2/asana/attention-items?severity=...
GET  /api/v2/asana/projects/:gid/velocity
GET  /api/v2/asana/projects/:gid/dashboard
GET  /api/v2/asana/tasks/search?q=...&project=...&status=...
POST /api/v2/asana/sync                        (manual sync trigger)
POST /api/v2/asana/prepare-task                (on-demand task draft)
POST /api/v2/asana/prepare-status-update       (on-demand status update draft)
```

## Validation
- [ ] Attention items correctly identify overdue, blocked, stale, approaching-deadline tasks
- [ ] Project velocity computed from real task completion data
- [ ] Prepared task creation includes correct project, section, and context
- [ ] Prepared status update references actual task state and inferred blockers
- [ ] Search returns enriched results with MOH Time OS entity links
- [ ] Sync detects meaningful changes (new overdue, status transitions)
- [ ] Cache doesn't grow unbounded (completed tasks archived after 90 days)
- [ ] Entity matching links Asana projects/tasks to MOH clients/engagements

## Files Created
- `lib/intelligence/asana_intelligence.py`
- `api/asana_intelligence_router.py`
- `tests/test_asana_intelligence.py`

## Estimated Effort
Large — ~800 lines (intelligence layer + cache + sync + entity matching)
