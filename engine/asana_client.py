"""Asana API client using Personal Access Token."""

import json
import os
from typing import Any

import requests

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", ".credentials.json")
ASANA_API_BASE = "https://app.asana.com/api/1.0"


def load_pat() -> str:
    with open(CONFIG_PATH) as f:
        data = json.load(f)
    return data["asana"]["pat"]


def asana_get(endpoint: str, params: dict | None = None) -> dict[str, Any]:
    """Make authenticated GET request to Asana API."""
    pat = load_pat()

    url = f"{ASANA_API_BASE}/{endpoint}"
    resp = requests.get(
        url,
        params=params,
        headers={
            "Authorization": f"Bearer {pat}",
            "Accept": "application/json",
        },
        timeout=30,
    )

    if resp.status_code != 200:
        raise RuntimeError(f"Asana API error: {resp.status_code} {resp.text}")

    return resp.json()


def list_workspaces() -> list[dict]:
    """List all workspaces."""
    data = asana_get("workspaces")
    return data.get("data", [])


def list_projects(
    workspace_gid: str, *, archived: bool = False, opt_fields: str = None
) -> list[dict]:
    """List projects in a workspace."""
    params = {"workspace": workspace_gid, "archived": str(archived).lower()}
    if opt_fields:
        params["opt_fields"] = opt_fields
    data = asana_get("projects", params=params)
    return data.get("data", [])


def get_project(project_gid: str) -> dict:
    """Get project details."""
    data = asana_get(f"projects/{project_gid}")
    return data.get("data", {})


def list_tasks_in_project(
    project_gid: str, *, completed: bool | None = None, opt_fields: str = None
) -> list[dict]:
    """List tasks in a project."""
    params = {}
    if opt_fields:
        params["opt_fields"] = opt_fields
    else:
        params["opt_fields"] = (
            "name,completed,completed_at,due_on,due_at,assignee,assignee.name,tags,tags.name,notes,created_at,modified_at"
        )
    if completed is not None:
        params["completed_since"] = "now" if not completed else None

    data = asana_get(f"projects/{project_gid}/tasks", params=params)
    return data.get("data", [])


def list_sections(project_gid: str) -> list[dict]:
    """List sections in a project (for board/pipeline stages)."""
    data = asana_get(f"projects/{project_gid}/sections")
    return data.get("data", [])


def list_tasks_in_section(section_gid: str) -> list[dict]:
    """List tasks in a section."""
    params = {"opt_fields": "name,completed,due_on,assignee,assignee.name"}
    data = asana_get(f"sections/{section_gid}/tasks", params=params)
    return data.get("data", [])


def search_tasks(workspace_gid: str, query: str) -> list[dict]:
    """Search tasks by text."""
    data = asana_get(
        f"workspaces/{workspace_gid}/tasks/search",
        params={"text": query, "opt_fields": "name,completed,projects,projects.name"},
    )
    return data.get("data", [])


def get_user_task_list(user_gid: str, workspace_gid: str) -> list[dict]:
    """Get user's task list (My Tasks)."""
    # First get the user task list gid
    data = asana_get(f"users/{user_gid}/user_task_list", params={"workspace": workspace_gid})
    task_list_gid = data.get("data", {}).get("gid")

    if not task_list_gid:
        return []

    # Get tasks from the list
    tasks_data = asana_get(
        f"user_task_lists/{task_list_gid}/tasks",
        params={"opt_fields": "name,completed,due_on,projects,projects.name"},
    )
    return tasks_data.get("data", [])


def get_task_detail(task_gid: str, opt_fields: str = None) -> dict:
    """Get full task details with expanded fields."""
    params = {}
    if opt_fields:
        params["opt_fields"] = opt_fields
    else:
        params["opt_fields"] = (
            "name,completed,completed_at,due_on,due_at,assignee,assignee.name,assignee.gid,"
            "tags,tags.name,notes,created_at,modified_at,custom_fields,custom_fields.name,"
            "custom_fields.type,custom_fields.display_value,memberships,memberships.section,"
            "memberships.section.name,num_subtasks,dependencies,attachments"
        )
    data = asana_get(f"tasks/{task_gid}", params=params)
    return data.get("data", {})


def list_subtasks(task_gid: str, opt_fields: str = None) -> list[dict]:
    """List subtasks for a task."""
    params = {}
    if opt_fields:
        params["opt_fields"] = opt_fields
    else:
        params["opt_fields"] = "name,completed,due_on,assignee,assignee.name,assignee.gid"
    data = asana_get(f"tasks/{task_gid}/subtasks", params=params)
    return data.get("data", [])


def list_stories(task_gid: str, opt_fields: str = None) -> list[dict]:
    """List stories (comments + system events) for a task."""
    params = {}
    if opt_fields:
        params["opt_fields"] = opt_fields
    else:
        params["opt_fields"] = "type,text,created_by,created_by.name,created_at"
    data = asana_get(f"tasks/{task_gid}/stories", params=params)
    return data.get("data", [])


def list_task_dependencies(task_gid: str) -> list[dict]:
    """List task dependencies (what this task depends on)."""
    data = asana_get(f"tasks/{task_gid}/dependencies", params={"opt_fields": "gid,name,completed"})
    return data.get("data", [])


def list_task_attachments(task_gid: str) -> list[dict]:
    """List attachments for a task."""
    params = {"opt_fields": "gid,name,download_url,host,size,created_at"}
    data = asana_get(f"tasks/{task_gid}/attachments", params=params)
    return data.get("data", [])


def list_portfolios(workspace_gid: str, owner_gid: str = None) -> list[dict]:
    """List portfolios in a workspace."""
    params = {"workspace": workspace_gid}
    if owner_gid:
        params["owner"] = owner_gid
    data = asana_get("portfolios", params=params)
    return data.get("data", [])


def list_goals(workspace_gid: str, owner_gid: str = None) -> list[dict]:
    """List goals in a workspace."""
    params = {"workspace": workspace_gid}
    if owner_gid:
        params["owner"] = owner_gid
    data = asana_get("goals", params=params)
    return data.get("data", [])


if __name__ == "__main__":
    # Test connection
    print("Testing Asana connection...")
    try:
        workspaces = list_workspaces()
        print(f"✓ Connected! Found {len(workspaces)} workspaces")
        for ws in workspaces:
            print(f"  - {ws.get('name')} (gid: {ws.get('gid')})")

            # List first few projects
            projects = list_projects(ws["gid"])[:5]
            for p in projects:
                print(f"    • {p.get('name')}")
    except Exception as e:
        print(f"✗ Error: {e}")
