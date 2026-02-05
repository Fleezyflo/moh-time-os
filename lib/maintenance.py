"""
Maintenance utilities for MOH Time OS.

- Clean up ancient/stale items
- Archive old data
- Recalculate priorities
- Data quality fixes
"""

from datetime import date, timedelta
from typing import List, Dict, Tuple

from .store import get_connection, now_iso
from .items import get_item, mark_cancelled, recalculate_all_priorities
from .backup import create_backup


def get_ancient_items(days_overdue: int = 180) -> List[Dict]:
    """
    Get items that are extremely overdue (likely stale/abandoned).
    
    Args:
        days_overdue: Minimum days overdue to consider "ancient"
    
    Returns list of {id, what, due, days_overdue, source_type}
    """
    cutoff = (date.today() - timedelta(days=days_overdue)).isoformat()
    
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, what, due, source_type
            FROM items
            WHERE status = 'open' AND due IS NOT NULL AND due < ?
            ORDER BY due ASC
        """, (cutoff,)).fetchall()
    
    result = []
    today = date.today()
    for r in rows:
        due_date = date.fromisoformat(r['due'])
        days = (today - due_date).days
        result.append({
            'id': r['id'],
            'what': r['what'],
            'due': r['due'],
            'days_overdue': days,
            'source_type': r['source_type']
        })
    
    return result


def archive_ancient_items(days_overdue: int = 365, dry_run: bool = True) -> Tuple[int, List[str]]:
    """
    Archive (cancel) items that are extremely old.
    
    Args:
        days_overdue: Items older than this are archived
        dry_run: If True, just report what would be archived
    
    Returns (count, list of archived item descriptions)
    """
    ancient = get_ancient_items(days_overdue)
    archived = []
    
    if dry_run:
        for item in ancient:
            archived.append(f"{item['what']} ({item['days_overdue']}d overdue)")
        return len(archived), archived
    
    # Create backup first
    create_backup(tag='pre-archive')
    
    for item in ancient:
        mark_cancelled(
            item['id'],
            notes=f"Auto-archived: {item['days_overdue']} days overdue",
            by='maintenance'
        )
        archived.append(f"{item['what']} ({item['days_overdue']}d overdue)")
    
    return len(archived), archived


def cleanup_asana_cruft(dry_run: bool = True) -> Dict:
    """
    Clean up old Asana imports that are likely stale.
    
    Targets:
    - Asana tasks > 1 year overdue
    - Items with no client context from Asana
    """
    results = {
        'ancient_tasks': [],
        'no_context_tasks': [],
        'dry_run': dry_run
    }
    
    cutoff_ancient = (date.today() - timedelta(days=365)).isoformat()
    cutoff_stale = (date.today() - timedelta(days=180)).isoformat()
    
    with get_connection() as conn:
        # Ancient Asana tasks (>1 year)
        ancient = conn.execute("""
            SELECT id, what, due
            FROM items
            WHERE source_type = 'asana' 
            AND status = 'open'
            AND due IS NOT NULL 
            AND due < ?
        """, (cutoff_ancient,)).fetchall()
        
        results['ancient_tasks'] = [{'id': r[0], 'what': r[1], 'due': r[2]} for r in ancient]
        
        # Stale tasks with no client (>6 months, no context)
        stale = conn.execute("""
            SELECT id, what, due
            FROM items
            WHERE source_type = 'asana'
            AND status = 'open'
            AND client_id IS NULL
            AND context_client_name IS NULL
            AND due IS NOT NULL
            AND due < ?
        """, (cutoff_stale,)).fetchall()
        
        results['no_context_tasks'] = [{'id': r[0], 'what': r[1], 'due': r[2]} for r in stale]
    
    if not dry_run:
        create_backup(tag='pre-cleanup')
        
        # Archive ancient
        for item in results['ancient_tasks']:
            mark_cancelled(item['id'], notes='Auto-archived: >1 year overdue Asana task', by='maintenance')
        
        # Archive stale no-context
        for item in results['no_context_tasks']:
            mark_cancelled(item['id'], notes='Auto-archived: Stale Asana task with no context', by='maintenance')
    
    return results


def fix_item_priorities() -> int:
    """Recalculate all item priorities."""
    recalculate_all_priorities()
    
    with get_connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM items WHERE status IN ('open', 'waiting')"
        ).fetchone()[0]
    
    return count


def get_maintenance_report() -> Dict:
    """Get maintenance status report."""
    ancient = get_ancient_items(180)
    very_ancient = [i for i in ancient if i['days_overdue'] > 365]
    
    with get_connection() as conn:
        # Items by source
        by_source = conn.execute("""
            SELECT source_type, COUNT(*) 
            FROM items 
            WHERE status = 'open'
            GROUP BY source_type
        """).fetchall()
        
        # Items without due date
        no_due = conn.execute("""
            SELECT COUNT(*) FROM items 
            WHERE status = 'open' AND due IS NULL
        """).fetchone()[0]
        
        # Items without client
        no_client = conn.execute("""
            SELECT COUNT(*) FROM items
            WHERE status = 'open' AND client_id IS NULL AND context_client_name IS NULL
        """).fetchone()[0]
    
    return {
        'ancient_items': len(ancient),
        'very_ancient_items': len(very_ancient),
        'items_by_source': {r[0]: r[1] for r in by_source},
        'items_without_due': no_due,
        'items_without_client': no_client,
        'recommendation': 'Run cleanup_asana_cruft() to archive old stale tasks' if very_ancient else 'System is clean'
    }


if __name__ == "__main__":
    print("=== Maintenance Report ===\n")
    
    report = get_maintenance_report()
    
    print(f"Ancient items (>180d): {report['ancient_items']}")
    print(f"Very ancient (>1yr): {report['very_ancient_items']}")
    print(f"Items by source: {report['items_by_source']}")
    print(f"Without due date: {report['items_without_due']}")
    print(f"Without client context: {report['items_without_client']}")
    print(f"\nRecommendation: {report['recommendation']}")
    
    if report['very_ancient_items'] > 0:
        print("\n=== Cleanup Preview (dry run) ===")
        results = cleanup_asana_cruft(dry_run=True)
        print(f"Would archive {len(results['ancient_tasks'])} ancient Asana tasks")
        print(f"Would archive {len(results['no_context_tasks'])} stale no-context tasks")
