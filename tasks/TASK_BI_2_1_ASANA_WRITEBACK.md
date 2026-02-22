# BI-2.1: Asana Write-Back

## Objective
Implement Asana write operations: create tasks from resolution items, update task status, and add comments — all through the action framework (BI-1.1).

## Context
Current Asana integration is read-only (collectors/asana.py). Asana API supports full CRUD. Use cases: resolution queue says "reassign overloaded tasks" → system creates follow-up tasks in Asana. Pattern engine detects scope creep → system comments on the project.

## Implementation

### OAuth Scope Upgrade
Current: read-only. Need to upgrade to include write scopes in Asana PAT or OAuth configuration.

### Write Operations

**Create Task**:
```python
class AsanaTaskCreator(ActionHandler):
    def execute(self, payload: dict) -> dict:
        # payload: {project_id, name, assignee, due_on, notes, section_id}
        response = asana_client.tasks.create_task({
            "data": {
                "projects": [payload["project_id"]],
                "name": payload["name"],
                "assignee": payload.get("assignee"),
                "due_on": payload.get("due_on"),
                "notes": payload.get("notes", ""),
            }
        })
        return {"task_gid": response["gid"], "url": response["permalink_url"]}
```

**Update Task Status**:
```python
class AsanaTaskUpdater(ActionHandler):
    def execute(self, payload: dict) -> dict:
        # payload: {task_id, completed, assignee, due_on}
        response = asana_client.tasks.update_task(payload["task_id"], {
            "data": {k: v for k, v in payload.items() if k != "task_id"}
        })
        return {"updated": True, "task_gid": payload["task_id"]}
```

**Add Comment**:
```python
class AsanaCommentCreator(ActionHandler):
    def execute(self, payload: dict) -> dict:
        # payload: {task_id, text}
        response = asana_client.tasks.add_comment(payload["task_id"], {
            "data": {"text": payload["text"]}
        })
        return {"story_gid": response["gid"]}
```

### Use Cases Wired
1. **Overdue escalation** → Create follow-up task assigned to project lead
2. **Scope creep detection** → Comment on project with analysis
3. **Capacity rebalancing** → Create reassignment proposal tasks
4. **Client risk alert** → Create "Client Review" task in internal project

## Validation
- [ ] Task creation in Asana from action framework
- [ ] Task update (complete, reassign) works
- [ ] Comments posted with correct attribution
- [ ] All writes go through approval workflow
- [ ] Audit log captures Asana task GID for traceability
- [ ] Rate limiting respected (Asana: 1500 req/min)

## Files Created
- `lib/actions/handlers/asana.py` — AsanaTaskCreator, AsanaTaskUpdater, AsanaCommentCreator

## Estimated Effort
Medium — ~200 lines, straightforward Asana API wrapping
