#!/usr/bin/env python3
"""
Delegation suggestions for Time OS.

Analyzes work items and suggests who might handle them based on:
- Lane categorization
- Team member roles
- Historical patterns
"""

from typing import Optional

# Team roster (can be expanded)
TEAM = {
    "Ayham": {
        "email": "ay@hrmny.co",
        "lanes": ["Operations", "Finance", "People"],
        "projects": ["hrmny mgmt", "BinSina"],
        "capacity": "high",
    },
    "Dana": {
        "email": "dana@hrmny.co",
        "lanes": ["Creative", "Sales"],
        "projects": ["SSS", "Ramadan"],
        "capacity": "medium",
    },
    "Krystie": {
        "email": "krystie@hrmny.co",
        "lanes": ["People", "Operations"],
        "projects": ["CS", "hrmny"],
        "capacity": "high",
    },
    "Youssef": {
        "email": "youssef@hrmny.co",
        "lanes": ["Creative", "Operations"],
        "projects": ["GMG", "Five Guys"],
        "capacity": "medium",
    },
    "John": {
        "email": "john@hrmny.co",
        "lanes": ["Finance", "Operations"],
        "projects": [],
        "capacity": "low",  # shared services
    },
}

# Keywords that suggest delegation
DELEGATION_KEYWORDS = [
    "follow up", "remind", "check", "update", "send", "schedule",
    "coordinate", "prepare", "draft", "review", "organize",
]

# Keywords that suggest owner-only work
OWNER_ONLY_KEYWORDS = [
    "authorize", "sign", "approve", "strategic", "confidential",
    "personal", "budget approval", "hiring decision", "contract",
]


def can_delegate(task_title: str) -> bool:
    """Check if a task is a candidate for delegation."""
    task_lower = task_title.lower()
    
    # Check for owner-only keywords
    if any(kw in task_lower for kw in OWNER_ONLY_KEYWORDS):
        return False
    
    # Check for delegation keywords
    if any(kw in task_lower for kw in DELEGATION_KEYWORDS):
        return True
    
    # Default: potentially delegatable
    return True


def suggest_delegate(task_title: str, lane: str = None, project: str = None) -> list:
    """
    Suggest team members who could handle a task.
    
    Returns list of: {"name": str, "email": str, "score": float, "reason": str}
    """
    if not can_delegate(task_title):
        return []
    
    task_lower = task_title.lower()
    suggestions = []
    
    for name, info in TEAM.items():
        score = 0.0
        reasons = []
        
        # Check lane match
        if lane and lane in info["lanes"]:
            score += 2.0
            reasons.append(f"{lane} specialist")
        
        # Check project match
        if project:
            for p in info["projects"]:
                if p.lower() in task_lower or project.lower() in p.lower():
                    score += 3.0
                    reasons.append(f"works on {p}")
                    break
        
        # Check keyword matches in task
        for p in info["projects"]:
            if p.lower() in task_lower:
                score += 1.5
                if f"works on {p}" not in reasons:
                    reasons.append(f"familiar with {p}")
        
        # Capacity modifier
        capacity_mod = {"high": 1.2, "medium": 1.0, "low": 0.5}
        score *= capacity_mod.get(info["capacity"], 1.0)
        
        if score > 0:
            suggestions.append({
                "name": name,
                "email": info["email"],
                "score": round(score, 2),
                "reason": ", ".join(reasons) if reasons else "Available",
            })
    
    # Sort by score descending
    suggestions.sort(key=lambda x: -x["score"])
    return suggestions[:3]


def format_delegation_suggestion(task: str, lane: str = None, project: str = None) -> Optional[str]:
    """Format a delegation suggestion as a string."""
    suggestions = suggest_delegate(task, lane, project)
    
    if not suggestions:
        if not can_delegate(task):
            return "⚠️ Owner-only task (cannot delegate)"
        return None
    
    top = suggestions[0]
    return f"💡 Delegate to {top['name']} ({top['reason']})"


if __name__ == "__main__":
    print("Delegation Suggestions Test")
    print("=" * 50)
    
    test_tasks = [
        ("Follow up with GMG re: invoice", "Finance", "GMG"),
        ("Send Ramadan campaign proposal", "Creative", "SSS"),
        ("Authorize payment for supplier", "Finance", None),
        ("Schedule team meeting", "People", None),
        ("Review BinSina deliverables", "Creative", "BinSina"),
        ("Update project status in Asana", "Operations", None),
    ]
    
    for task, lane, project in test_tasks:
        print(f"\nTask: {task}")
        print(f"Lane: {lane}, Project: {project}")
        suggestion = format_delegation_suggestion(task, lane, project)
        if suggestion:
            print(f"  → {suggestion}")
        else:
            print("  → No delegation suggestion")
