"""
Task classification - distinguish work from tracking.

Tracking items (0 effort):
- CRM entries, leads, contacts
- Invoices, receivables
- Candidates, applicants
- Equipment, assets
- Pipeline stages

Actual work (needs effort):
- Deliverables
- Reviews/approvals that require action
- Creation tasks
- Client work
"""

# Projects that are tracking/pipeline (tasks = records, not work)
TRACKING_PROJECTS = {
    # CRM & Sales
    'crm',
    'leads',
    'pipeline',
    'sales pipeline',
    
    # Finance tracking
    'outgoing invoice tracker',
    'receivables',
    'invoices',
    
    # HR tracking
    'candidates',
    'applicants',
    'recruitment tracker',
    
    # Asset tracking
    'equipment monitoring',
    'office equipment',
    'inventory',
    
    # System/meta
    'templates',
    'workflows',
}

# Task title patterns that indicate tracking (not work)
TRACKING_PATTERNS = [
    r'^[A-Z]{2,5}\s*[-:]\s*\d',  # "INV-001", "RFP: 123"
    r'\b(invoice|inv)\s*#?\d',
    r'\b(candidate|applicant)\s*[-:]\s',
    r'\b(lead|contact)\s*[-:]\s',
    r'\b(asset|equipment)\s*#?\d',
]

import re


def is_tracking_item(task: dict) -> bool:
    """
    Determine if a task is a tracking record (not actual work).
    
    Args:
        task: Dict with 'title', 'project', 'lane', etc.
        
    Returns:
        True if this is a tracking item (0 effort)
    """
    project = (task.get('project') or '').lower().strip()
    title = (task.get('title') or '').lower().strip()
    
    # Check if project is a tracking project
    for tracking_proj in TRACKING_PROJECTS:
        if tracking_proj in project:
            return True
    
    # Check title patterns
    for pattern in TRACKING_PATTERNS:
        if re.search(pattern, title, re.IGNORECASE):
            return True
    
    return False


def classify_tasks(tasks: list) -> tuple:
    """
    Split tasks into work vs tracking.
    
    Returns:
        (work_tasks, tracking_tasks)
    """
    work = []
    tracking = []
    
    for task in tasks:
        if is_tracking_item(task):
            tracking.append(task)
        else:
            work.append(task)
    
    return work, tracking


if __name__ == "__main__":
    # Test
    test_tasks = [
        {"title": "Review contract", "project": "Client Work"},
        {"title": "INV-2024-001", "project": "Outgoing Invoice Tracker"},
        {"title": "John Smith - Marketing Lead", "project": "CRM"},
        {"title": "Create campaign assets", "project": "Traffic: Creative Team"},
        {"title": "Asset #1234 - Laptop", "project": "Equipment Monitoring"},
        {"title": "Prepare monthly report", "project": "ret-monoprix"},
    ]
    
    work, tracking = classify_tasks(test_tasks)
    
    print("WORK tasks:")
    for t in work:
        print(f"  ✓ {t['title'][:40]} ({t['project']})")
    
    print("\nTRACKING items (0 effort):")
    for t in tracking:
        print(f"  ○ {t['title'][:40]} ({t['project']})")
