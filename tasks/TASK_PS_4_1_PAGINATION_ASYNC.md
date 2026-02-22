# PS-4.1: Pagination Enforcement + Async Operations

## Objective
Ensure every list endpoint has enforced pagination, and move long-running operations (collectors, analyzers) to background tasks with status tracking.

## Context
Some endpoints have pagination (spec_router.py lines 205, 745), others don't. Unbounded queries on 80+ table DB with 556MB data are dangerous. Collector runs take minutes — they should not block API responses.

## Implementation

### Pagination Enforcement
```python
# Shared pagination dependency
class PaginationParams:
    def __init__(
        self,
        page: int = Query(1, ge=1),
        per_page: int = Query(50, ge=1, le=100),
    ):
        self.page = page
        self.per_page = per_page
        self.offset = (page - 1) * per_page

class PaginatedResponse(BaseModel):
    data: list[Any]
    page: int
    per_page: int
    total: int
    total_pages: int
    has_next: bool

# Usage on every list endpoint:
@app.get("/api/v1/clients")
def list_clients(pagination: PaginationParams = Depends()):
    total = db.count("clients")
    data = db.fetchall("SELECT * FROM clients LIMIT ? OFFSET ?",
                       (pagination.per_page, pagination.offset))
    return PaginatedResponse(
        data=data, page=pagination.page, per_page=pagination.per_page,
        total=total, total_pages=math.ceil(total / pagination.per_page),
        has_next=pagination.page * pagination.per_page < total,
    )
```

### Async Background Tasks
```python
# lib/background.py
import threading
import uuid

class BackgroundTaskManager:
    def __init__(self):
        self._tasks: dict[str, TaskStatus] = {}

    def submit(self, name: str, func, *args, **kwargs) -> str:
        task_id = str(uuid.uuid4())[:8]
        self._tasks[task_id] = TaskStatus(name=name, status="running", started_at=now())
        thread = threading.Thread(target=self._run, args=(task_id, func, args, kwargs))
        thread.daemon = True
        thread.start()
        return task_id

    def _run(self, task_id, func, args, kwargs):
        try:
            result = func(*args, **kwargs)
            self._tasks[task_id].status = "completed"
            self._tasks[task_id].result = result
        except Exception as e:
            self._tasks[task_id].status = "failed"
            self._tasks[task_id].error = str(e)

    def get_status(self, task_id: str) -> TaskStatus | None:
        return self._tasks.get(task_id)

# API endpoints
@app.post("/api/v1/collect/trigger")  # admin only
def trigger_collection():
    task_id = bg_manager.submit("collect", collector_orchestrator.run)
    return {"task_id": task_id, "status": "running"}

@app.get("/api/v1/tasks/{task_id}/status")
def get_task_status(task_id: str):
    return bg_manager.get_status(task_id)
```

### Endpoints to Audit
Every endpoint returning a list must be paginated:
- `/api/v1/clients` → paginated
- `/api/v1/projects` → paginated
- `/api/v1/tasks` → paginated
- `/api/v1/signals` → paginated
- `/api/v1/patterns` → paginated
- `/api/v1/resolution/pending` → paginated
- `/api/v1/resolution/history` → paginated
- All `spec_router` list endpoints → verify pagination present

## Validation
- [ ] Every list endpoint returns PaginatedResponse format
- [ ] Default page size = 50, max = 100 enforced
- [ ] No endpoint returns unbounded result sets
- [ ] Collector trigger returns immediately with task_id
- [ ] Background task status trackable via API
- [ ] Long operations don't block API responses

## Files Created/Modified
- New: `lib/background.py`
- `api/server.py` — add pagination dependency, background task endpoints
- `api/spec_router.py` — enforce pagination on all list endpoints
- `api/intelligence_router.py` — enforce pagination

## Estimated Effort
Medium — ~200 lines background task manager + pagination audit across endpoints
