"""Improve project-client linking."""

import re
from typing import Dict, List, Tuple, Optional

from .entities import list_clients, list_projects, find_client, update_project, get_client
from .store import get_connection


# Known project prefixes/patterns to client names
PROJECT_CLIENT_MAP = {
    # GMG brands
    'gmg:': 'GMG Consumer LLC',
    'gmg ': 'GMG Consumer LLC',
    'aswaaq': 'GMG Consumer LLC',
    'geant': 'GMG Consumer LLC',
    'monoprix': 'GMG Consumer LLC',
    
    # SSS
    'sss |': 'Sun & Sand Sports',
    'sss:': 'Sun & Sand Sports',
    'sss ': 'Sun & Sand Sports',
    'sun sand': 'Sun & Sand Sports',
    'sun & sand': 'Sun & Sand Sports',
    
    # Gargash brands
    'gargash': 'Gargash Enterprises L.L.C',
    'mercedes': 'Gargash Enterprises L.L.C',
    'mercedes-benz': 'Gargash Enterprises L.L.C',
    'alfa romeo': 'Gargash Enterprises L.L.C',
    'daimler': 'Gargash Enterprises L.L.C',
    
    # Other known mappings
    'sixt': 'SIXT Rent a Car LLC',
    'five guys': 'Five Guys',
    'binsina': 'BinSina Pharmacy L.L.C',
    'bin sina': 'BinSina Pharmacy L.L.C',
    'super care': 'Super Care Pharmacy L.L.C',
    'supercare': 'Super Care Pharmacy L.L.C',
    'asics': 'ASICS ARABIA FZE',
    'chalhoub': 'Chalhoub Inc. FZE',
    'deliveroo': 'Deliveroo',
    'red bull': 'Red Bull',
    'redbull': 'Red Bull',
}

# Internal project keywords (don't need client)
INTERNAL_KEYWORDS = [
    'system', 'internal', 'board', 'pipeline', 'crm', 'hr', 'hrmny', 
    'previously assigned', 'offboarding', 'on-boarding', 'candidates',
    'payroll', 'timesheet', 'procurement', 'equipment monitoring', 'docs', 
    'tracker', 'hiring', 'creative hires', 'social', 'admin', 'feedback',
    'workflows', 'talents', 'performance review', 'receivables', 'focus points',
    'incoming projects', 'feb', 'all clients', 'tasks', 'ramy | ayham',
    '[creative] projects', 'master production', 'post production', 
    'active production', 'production deliveries'
]


def is_internal_project(name: str) -> bool:
    """Check if project is internal (no client needed)."""
    name_lower = name.lower()
    return any(kw in name_lower for kw in INTERNAL_KEYWORDS)


def find_client_for_project(project_name: str) -> Optional[str]:
    """
    Try to find a matching client for a project name.
    Returns client_id if found, None otherwise.
    """
    name_lower = project_name.lower()
    
    # Check known mappings first (order matters - check specific patterns first)
    for pattern, client_name in PROJECT_CLIENT_MAP.items():
        if pattern in name_lower:
            client = find_client(name=client_name)
            if client:
                return client.id
    
    # Try extracting first word/segment before colon or pipe
    segments = re.split(r'[:|]', project_name)
    if segments:
        first_segment = segments[0].strip()
        # Only use if it's a meaningful segment (not just an acronym)
        if len(first_segment) > 4:
            client = find_client(name=first_segment)
            if client:
                return client.id
    
    # Don't try random word matching - too many false positives
    return None


def analyze_project_linking() -> Dict:
    """Analyze current state of project-client linking."""
    projects = list_projects(limit=500)
    
    result = {
        'total': len(projects),
        'linked': 0,
        'internal': 0,
        'unlinked_client': 0,
        'suggestions': [],
    }
    
    for p in projects:
        if p.client_id:
            result['linked'] += 1
        elif is_internal_project(p.name):
            result['internal'] += 1
        else:
            # Try to find a match
            suggested_client_id = find_client_for_project(p.name)
            if suggested_client_id:
                client = get_client(suggested_client_id)
                result['suggestions'].append({
                    'project': p.name,
                    'project_id': p.id,
                    'suggested_client': client.name if client else '?',
                    'client_id': suggested_client_id,
                })
            else:
                result['unlinked_client'] += 1
    
    return result


def link_projects(dry_run: bool = True) -> Dict:
    """
    Link projects to clients based on name matching.
    
    Args:
        dry_run: If True, don't actually update, just report
    
    Returns:
        Summary of changes
    """
    projects = list_projects(limit=500)
    
    result = {
        'linked': 0,
        'skipped_internal': 0,
        'skipped_already_linked': 0,
        'no_match': 0,
        'changes': [],
    }
    
    for p in projects:
        if p.client_id:
            result['skipped_already_linked'] += 1
            continue
        
        if is_internal_project(p.name):
            result['skipped_internal'] += 1
            continue
        
        client_id = find_client_for_project(p.name)
        if client_id:
            client = get_client(client_id)
            result['changes'].append({
                'project': p.name,
                'client': client.name if client else '?',
            })
            
            if not dry_run:
                update_project(p.id, client_id=client_id)
            
            result['linked'] += 1
        else:
            result['no_match'] += 1
    
    return result


def print_analysis():
    """Print analysis of project linking."""
    result = analyze_project_linking()
    
    print(f"Project-Client Linking Analysis")
    print(f"=" * 50)
    print(f"Total projects: {result['total']}")
    print(f"Already linked: {result['linked']}")
    print(f"Internal (no client): {result['internal']}")
    print(f"Unlinked (no match): {result['unlinked_client']}")
    print(f"Suggestions found: {len(result['suggestions'])}")
    
    if result['suggestions']:
        print(f"\nSuggested links:")
        for s in result['suggestions'][:20]:
            print(f"  {s['project'][:40]} → {s['suggested_client']}")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--link':
        print("Linking projects to clients...")
        result = link_projects(dry_run=False)
        print(f"Linked: {result['linked']}")
        print(f"Skipped (internal): {result['skipped_internal']}")
        print(f"Skipped (already linked): {result['skipped_already_linked']}")
        print(f"No match: {result['no_match']}")
        
        if result['changes']:
            print("\nChanges made:")
            for c in result['changes'][:20]:
                print(f"  {c['project'][:40]} → {c['client']}")
    else:
        print_analysis()
