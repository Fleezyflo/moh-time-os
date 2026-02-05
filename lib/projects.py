#!/usr/bin/env python3
"""
MOH Time OS — Project Registry

Enrolled project management per spec 4.2:
- name + aliases/recognizers
- involvement type
- default lane mapping
- routing rules
- scheduling eligibility + caps
- delegation policy
- reporting cadence + escalation thresholds
- approval gates / sensitivity profile
- archive policy + reactivation criteria
- proposal rate-limit policy
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field, asdict

PROJECTS_FILE = Path(__file__).parent.parent / "data" / "projects.json"
PROJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class Project:
    """Enrolled project per spec."""
    id: str
    name: str
    aliases: List[str] = field(default_factory=list)
    
    # Involvement type
    involvement: str = "active"  # active, supporting, monitoring, archived
    
    # Lane mapping
    default_lane: str = "client"
    
    # Routing rules
    task_list: str = None  # Google Tasks list to route to
    auto_create_threshold: float = 0.8  # Confidence threshold for auto-create
    propose_threshold: float = 0.5  # Confidence threshold for propose
    
    # Scheduling
    scheduling_eligible: bool = True
    weekly_cap_minutes: int = None  # Max minutes per week
    
    # Delegation
    default_delegatee: str = None  # Default person to delegate to
    delegation_allowed: bool = True
    
    # Reporting
    reporting_cadence: str = "weekly"  # daily, weekly, monthly, on-demand
    escalation_threshold_days: int = 3  # Escalate if no progress
    
    # Sensitivity
    sensitivity_profile: List[str] = field(default_factory=list)  # e.g., ["financial", "clientVIP"]
    approval_required: bool = False  # Require approval for actions
    
    # Archive policy
    archive_after_days: int = 30  # Archive if no activity
    reactivation_keywords: List[str] = field(default_factory=list)
    
    # Rate limits
    max_proposals_per_day: int = 5
    max_proposals_per_week: int = 20
    
    # Metadata
    client_id: str = None
    created_at: str = None
    updated_at: str = None
    archived_at: str = None
    
    def matches(self, text: str) -> bool:
        """Check if text matches this project (name or aliases)."""
        text_lower = text.lower()
        if self.name.lower() in text_lower:
            return True
        for alias in self.aliases:
            if alias.lower() in text_lower:
                return True
        return False
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Project':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def load_projects() -> Dict[str, Project]:
    """Load all projects from disk."""
    if not PROJECTS_FILE.exists():
        return {}
    
    try:
        data = json.loads(PROJECTS_FILE.read_text())
        return {pid: Project.from_dict(p) for pid, p in data.items()}
    except (json.JSONDecodeError, TypeError):
        return {}


def save_projects(projects: Dict[str, Project]) -> None:
    """Save all projects to disk."""
    data = {pid: p.to_dict() for pid, p in projects.items()}
    PROJECTS_FILE.write_text(json.dumps(data, indent=2))


def get_project(project_id: str) -> Optional[Project]:
    """Get a project by ID."""
    projects = load_projects()
    return projects.get(project_id)


def find_project(name: str = None, text: str = None) -> Optional[Project]:
    """Find a project by name or by matching text."""
    projects = load_projects()
    
    if name:
        for p in projects.values():
            if p.name.lower() == name.lower():
                return p
            if name.lower() in [a.lower() for a in p.aliases]:
                return p
    
    if text:
        for p in projects.values():
            if p.matches(text):
                return p
    
    return None


def create_project(
    name: str,
    aliases: List[str] = None,
    default_lane: str = "client",
    client_id: str = None,
    **kwargs
) -> Project:
    """Create and save a new project."""
    import uuid
    
    projects = load_projects()
    
    project_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()
    
    project = Project(
        id=project_id,
        name=name,
        aliases=aliases or [],
        default_lane=default_lane,
        client_id=client_id,
        created_at=now,
        updated_at=now,
        **kwargs
    )
    
    projects[project_id] = project
    save_projects(projects)
    
    return project


def update_project(project_id: str, **updates) -> Optional[Project]:
    """Update a project."""
    projects = load_projects()
    
    if project_id not in projects:
        return None
    
    project = projects[project_id]
    
    for key, value in updates.items():
        if hasattr(project, key):
            setattr(project, key, value)
    
    project.updated_at = datetime.now(timezone.utc).isoformat()
    
    save_projects(projects)
    return project


def archive_project(project_id: str) -> Optional[Project]:
    """Archive a project."""
    return update_project(
        project_id,
        involvement="archived",
        archived_at=datetime.now(timezone.utc).isoformat()
    )


def reactivate_project(project_id: str) -> Optional[Project]:
    """Reactivate an archived project."""
    return update_project(
        project_id,
        involvement="active",
        archived_at=None
    )


def list_projects(
    involvement: str = None,
    lane: str = None,
    client_id: str = None,
) -> List[Project]:
    """List projects with optional filters."""
    projects = load_projects()
    result = list(projects.values())
    
    if involvement:
        result = [p for p in result if p.involvement == involvement]
    if lane:
        result = [p for p in result if p.default_lane == lane]
    if client_id:
        result = [p for p in result if p.client_id == client_id]
    
    return result


def list_active_projects() -> List[Project]:
    """List all active (non-archived) projects."""
    return list_projects(involvement="active")


# CLI interface
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: projects.py <command> [args]")
        print("Commands: list, get <id>, create <name>, find <text>, archive <id>")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "list":
        for p in list_active_projects():
            print(f"{p.id}: {p.name} ({p.default_lane}) [{p.involvement}]")
    
    elif cmd == "get" and len(sys.argv) >= 3:
        p = get_project(sys.argv[2])
        if p:
            print(json.dumps(p.to_dict(), indent=2))
        else:
            print("Not found")
    
    elif cmd == "create" and len(sys.argv) >= 3:
        p = create_project(sys.argv[2])
        print(f"Created: {p.id}")
    
    elif cmd == "find" and len(sys.argv) >= 3:
        p = find_project(text=sys.argv[2])
        if p:
            print(f"Found: {p.id} - {p.name}")
        else:
            print("Not found")
    
    elif cmd == "archive" and len(sys.argv) >= 3:
        p = archive_project(sys.argv[2])
        if p:
            print(f"Archived: {p.name}")
        else:
            print("Not found")
    
    else:
        print(f"Unknown command: {cmd}")
