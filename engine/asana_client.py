"""Asana API client using Personal Access Token."""

import json
import os
import requests
from dataclasses import dataclass
from typing import Any

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", ".credentials.json")
ASANA_API_BASE = "https://app.asana.com/api/1.0"


def load_pat() -> str:
    with open(CONFIG_PATH, "r") as f:
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
    )
    
    if resp.status_code != 200:
        raise RuntimeError(f"Asana API error: {resp.status_code} {resp.text}")
    
    return resp.json()


def list_workspaces() -> list[dict]:
    """List all workspaces."""
    data = asana_get("workspaces")
    return data.get("data", [])


def list_projects(workspace_gid: str, *, archived: bool = False, opt_fields: str = None) -> list[dict]:
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


def list_tasks_in_project(project_gid: str, *, completed: bool | None = None) -> list[dict]:
    """List tasks in a project."""
    params = {"opt_fields": "name,completed,due_on,assignee,assignee.name,tags,tags.name"}
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
