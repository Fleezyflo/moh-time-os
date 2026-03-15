"""Asana API client using Personal Access Token.

Credentials: reads ASANA_PAT env var first, falls back to config/.credentials.json.
"""

import json
import logging
import os
import threading
import time
from typing import Any

import httpx

from lib.collectors.resilience import RateLimiter
from lib.credential_paths import credentials_json

_CONFIG_PATH = str(credentials_json())
ASANA_API_BASE = "https://app.asana.com/api/1.0"

# Asana PAT rate limit: 150 requests/minute. Use 120 for safety margin.
_rate_limiter = RateLimiter(requests_per_minute=120)
_rate_lock = threading.Lock()

logger = logging.getLogger(__name__)

# Default retry-after seconds when header is missing
_DEFAULT_RETRY_AFTER = 60


def load_pat() -> str:
    """Load Asana PAT from ASANA_PAT env var, falling back to credentials file."""
    pat = os.environ.get("ASANA_PAT")
    if pat:
        return pat
    try:
        with open(_CONFIG_PATH) as f:
            data = json.load(f)
        return data["asana"]["pat"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
        raise RuntimeError(
            "Asana PAT not found. Set ASANA_PAT env var or populate config/.credentials.json"
        ) from e


def asana_get(endpoint: str, params: dict | None = None) -> dict[str, Any]:
    """Make authenticated GET request to Asana API with rate limiting and 429 retry."""
    pat = load_pat()

    url = f"{ASANA_API_BASE}/{endpoint}"
    if params is None:
        params = {}
    # Always set a limit to avoid "result is too large" errors
    if "limit" not in params:
        params["limit"] = "100"

    headers = {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/json",
    }

    # Pre-flight rate limit check
    with _rate_lock:
        if not _rate_limiter.allow_request():
            wait = _rate_limiter.get_wait_time()
            logger.debug(f"Rate limiter: waiting {wait:.1f}s before request")
            time.sleep(wait)
            _rate_limiter.allow_request()  # Consume token after wait

    max_retries = 3
    for attempt in range(max_retries + 1):
        resp = httpx.get(url, params=params, headers=headers, timeout=30)

        if resp.status_code == 429:
            if attempt >= max_retries:
                raise RuntimeError(
                    f"Asana API rate limited after {max_retries + 1} attempts: {endpoint}"
                )
            retry_after = int(resp.headers.get("Retry-After", _DEFAULT_RETRY_AFTER))
            logger.warning(
                f"Asana 429 on {endpoint} (attempt {attempt + 1}/{max_retries + 1}). "
                f"Waiting {retry_after}s"
            )
            time.sleep(retry_after)
            continue

        if resp.status_code != 200:
            raise RuntimeError(f"Asana API error: {resp.status_code} {resp.text}")

        return resp.json()

    # Should not reach here, but just in case
    raise RuntimeError(f"Asana API: exhausted retries for {endpoint}")


def asana_get_all(endpoint: str, params: dict | None = None) -> list[dict]:
    """Make paginated GET request to Asana API, returning all results."""
    all_data: list[dict] = []
    if params is None:
        params = {}

    while True:
        result = asana_get(endpoint, params=dict(params))
        all_data.extend(result.get("data", []))

        next_page = result.get("next_page")
        if not next_page or not next_page.get("offset"):
            break

        params["offset"] = next_page["offset"]

    return all_data


def list_workspaces() -> list[dict]:
    """List all workspaces."""
    data = asana_get("workspaces")
    return data.get("data", [])


def list_projects(
    workspace_gid: str, *, archived: bool = False, opt_fields: str = None
) -> list[dict]:
    """List projects in a workspace (paginated)."""
    params = {"workspace": workspace_gid, "archived": str(archived).lower()}
    if opt_fields:
        params["opt_fields"] = opt_fields
    return asana_get_all("projects", params=params)


def get_project(project_gid: str) -> dict:
    """Get project details."""
    data = asana_get(f"projects/{project_gid}")
    return data.get("data", {})


def list_tasks_in_project(
    project_gid: str, *, completed: bool | None = None, opt_fields: str = None
) -> list[dict]:
    """List tasks in a project (paginated)."""
    params = {}
    if opt_fields:
        params["opt_fields"] = opt_fields
    else:
        params["opt_fields"] = (
            "name,completed,completed_at,due_on,due_at,assignee,assignee.name,tags,tags.name,notes,created_at,modified_at"
        )
    if completed is not None:
        params["completed_since"] = "now" if not completed else None

    return asana_get_all(f"projects/{project_gid}/tasks", params=params)


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
