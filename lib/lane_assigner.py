"""
Lane Assignment Logic

Assigns tasks to lanes based on project, keywords, and source.
Run after collection to categorize tasks.
"""

import logging
import re
import sqlite3

from lib import paths

logger = logging.getLogger(__name__)


DB_PATH = paths.db_path()

# Lane assignment rules (evaluated in order - first match wins)
LANE_RULES = [
    # ===== MUSIC & PERSONAL (non-working hours) =====
    {
        "lane": "music",
        "projects": ["sonic unit", "moh flow"],
        "keywords": [],
    },
    {
        "lane": "personal",
        "sources": ["google_tasks"],
        "keywords": ["personal", "self", "gym", "health", "doctor", "apartment"],
    },
    # ===== CREAM (ice cream brand) =====
    {
        "lane": "cream",
        "projects": ["cream"],
        "keywords": ["cream brand", "ice cream", "cream ops", "cream launch"],
    },
    # ===== FINANCE =====
    {
        "lane": "finance",
        "projects": ["invoice tracker", "receivables", "procurement", "payroll"],
        "keywords": [
            "invoice",
            "payment",
            "ar aging",
            "accounts receivable",
            "expense",
            "budget",
            "financial",
        ],
    },
    # ===== PEOPLE & CULTURE =====
    {
        "lane": "people",
        "projects": [
            "candidates",
            "hires",
            "on-boarding",
            "onboarding",
            "off-boarding",
            "offboarding",
            "performance review",
            "hr & internal",
            "recruitment",
            "payroll",
            "reimbursement",
        ],
        "keywords": [
            "candidate",
            "interview",
            "hiring",
            "onboard",
            "offboard",
            "performance review",
            "employee",
            "team member",
            "recruitment",
        ],
    },
    # ===== GROWTH / SALES =====
    {
        "lane": "growth",
        "projects": ["crm", "sales pipeline", "proposal pipeline"],
        "keywords": [
            "proposal",
            "pitch",
            "lead",
            "prospect",
            "new business",
            "rfp",
            "tender",
        ],
        "tags": ["campaign"],
    },
    # ===== GOVERNANCE =====
    {
        "lane": "governance",
        "projects": [],
        "keywords": [
            "compliance",
            "policy review",
            "legal review",
            "audit",
            "regulation",
            "contract review",
        ],
    },
    # ===== ADMIN =====
    {
        "lane": "admin",
        "projects": ["internal misc", "managerial task board", "templates"],
        "keywords": ["admin", "review meeting", "approval", "sign off", "weekly sync"],
    },
    # ===== CLIENT (non-internal project work) =====
    # This is handled specially - any non-internal project not matched above
    # ===== OPS (default) =====
    # Anything left: traffic, equipment, general ops
]


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def keyword_match(text: str, keywords: list) -> bool:
    """Match keywords with word boundaries to avoid substring false positives."""
    for kw in keywords:
        # Use word boundary regex for short keywords to avoid false matches
        if len(kw) <= 3:
            pattern = r"\b" + re.escape(kw) + r"\b"
            if re.search(pattern, text):
                return True
        else:
            # Longer keywords can use simple substring
            if kw in text:
                return True
    return False


def assign_lane(task: dict, project: dict = None) -> str:
    """Determine lane for a task based on rules."""

    title = (task.get("title") or "").lower()
    source = (task.get("source") or "").lower()
    tags = (task.get("tags") or "").lower()
    project_name = (project.get("name") or "").lower() if project else ""
    is_internal = project.get("is_internal", 1) if project else 1

    for rule in LANE_RULES:
        lane = rule["lane"]

        # Check source match
        if "sources" in rule and source in [s.lower() for s in rule["sources"]]:
            # If source matches, also need keyword match (for personal)
            if "keywords" in rule and rule["keywords"]:
                if keyword_match(title, rule["keywords"]):
                    return lane
            else:
                return lane

        # Check project match
        if "projects" in rule and any(p in project_name for p in rule["projects"]):
            return lane

        # Check keyword match in title
        if (
            "keywords" in rule
            and rule["keywords"]
            and keyword_match(title, rule["keywords"])
        ):
            return lane

        # Check tag match
        if "tags" in rule and any(t in tags for t in rule["tags"]):
            return lane

    # Special case: client lane for non-internal projects
    if project and not is_internal:
        return "client"

    # Default: ops
    return "ops"


def run_assignment():
    """Assign lanes to all tasks."""
    conn = get_conn()
    cursor = conn.cursor()

    # Get all tasks with their projects
    cursor.execute("""
        SELECT t.id, t.title, t.source, t.tags, t.lane,
               p.name as project_name, p.is_internal
        FROM tasks t
        LEFT JOIN projects p ON t.project_id = p.id
    """)

    tasks = cursor.fetchall()

    updates = {
        "ops": 0,
        "finance": 0,
        "people": 0,
        "client": 0,
        "cream": 0,
        "growth": 0,
        "admin": 0,
        "governance": 0,
        "music": 0,
        "personal": 0,
    }
    changed = 0

    for task in tasks:
        task_dict = dict(task)
        project_dict = (
            {"name": task["project_name"], "is_internal": task["is_internal"]}
            if task["project_name"]
            else None
        )

        new_lane = assign_lane(task_dict, project_dict)

        if new_lane != task["lane"]:
            cursor.execute(
                "UPDATE tasks SET lane = ?, updated_at = datetime('now') WHERE id = ?",
                [new_lane, task["id"]],
            )
            changed += 1

        updates[new_lane] = updates.get(new_lane, 0) + 1

    conn.commit()
    conn.close()

    return {"changed": changed, "distribution": updates}


if __name__ == "__main__":
    import json

    result = run_assignment()
    logger.info(json.dumps(result, indent=2))
