#!/usr/bin/env python3
"""
MOH Time OS CLI

Quick command-line access to the system for A integration.

Usage:
    python cli.py status          # System status + summary
    python cli.py brief           # Morning brief
    python cli.py overdue         # Overdue items
    python cli.py open            # All open items
    python cli.py client <name>   # Client status
    python cli.py search <query>  # Search items
    python cli.py add "<what>" [--due DATE] [--client NAME]
    python cli.py done <id>       # Mark item done
    python cli.py sync            # Run Xero + Asana sync
    python cli.py health          # Health check
"""

import sys
import argparse
from datetime import date

# Ensure lib is importable
sys.path.insert(0, str(__file__).rsplit('/', 1)[0])

from lib import (
    # Health
    health_check, ensure_initialized,
    
    # Queries
    summary_stats, overdue, due_today, open_items, waiting, search, high_priority,
    for_client_name,
    
    # Entities
    find_client, find_project,
    
    # Items
    create_item, get_item, mark_done, mark_waiting, mark_cancelled,
    
    # Brief
    generate_morning_brief, generate_status_summary, generate_client_status,
    
    # Sync
    sync_xero_clients, sync_asana_projects, sync_overdue_tasks,
    
    # Backup
    create_backup
)


def cmd_status(args):
    """System status."""
    ok, msg = ensure_initialized()
    if not ok:
        print(f"❌ {msg}")
        return 1
    
    print(generate_status_summary())
    return 0


def cmd_brief(args):
    """Morning brief."""
    print(generate_morning_brief())
    return 0


def cmd_overdue(args):
    """List overdue items."""
    items = overdue(limit=args.limit or 20)
    
    # Filter to recent if requested
    if not args.all:
        items = [i for i in items if i.days_overdue() <= 30]
    
    if not items:
        print("No overdue items 🎉")
        return 0
    
    print(f"## Overdue Items ({len(items)})\n")
    for item in items:
        print(f"- {item.brief_display()}")
        if item.context_stakes:
            print(f"  Stakes: {item.context_stakes}")
    
    return 0


def cmd_open(args):
    """List open items."""
    items = open_items(limit=args.limit or 50)
    
    if not items:
        print("No open items")
        return 0
    
    print(f"## Open Items ({len(items)})\n")
    for item in items[:20]:
        print(f"- {item.brief_display()}")
    
    if len(items) > 20:
        print(f"\n*+ {len(items) - 20} more*")
    
    return 0


def cmd_waiting(args):
    """List waiting items."""
    items = waiting(limit=args.limit or 20)
    
    if not items:
        print("No waiting items")
        return 0
    
    print(f"## Waiting ({len(items)})\n")
    for item in items:
        print(f"- {item.brief_display()}")
    
    return 0


def cmd_client(args):
    """Client status."""
    print(generate_client_status(args.name))
    return 0


def cmd_search(args):
    """Search items."""
    items = search(args.query, limit=20)
    
    if not items:
        print(f"No items matching '{args.query}'")
        return 0
    
    print(f"## Search: {args.query} ({len(items)} results)\n")
    for item in items:
        print(f"- {item.brief_display()}")
    
    return 0


def cmd_add(args):
    """Add a new item."""
    client_id = None
    client_name = args.client
    project_id = None
    project_name = args.project
    
    # Try to find client
    if args.client:
        client = find_client(args.client)
        if client:
            client_id = client.id
            client_name = client.name
    
    # Try to find project
    if args.project:
        project = find_project(args.project)
        if project:
            project_id = project.id
            project_name = project.name
            if not client_id and project.client_id:
                client_id = project.client_id
    
    item_id = create_item(
        what=args.what,
        owner='me',
        due=args.due,
        client_id=client_id,
        client_name=client_name,
        project_id=project_id,
        project_name=project_name,
        stakes=args.stakes or '',
        captured_by='A'
    )
    
    item = get_item(item_id)
    print(f"✓ Tracked: **{item.what}**")
    if item.due:
        print(f"  Due: {item.due}")
    if item.context_client_name:
        print(f"  Client: {item.context_client_name}")
    
    return 0


def cmd_done(args):
    """Mark item done."""
    item = get_item(args.id)
    if not item:
        print(f"Item not found: {args.id}")
        return 1
    
    mark_done(args.id, notes=args.notes)
    print(f"✓ Done: {item.what}")
    return 0


def cmd_sync(args):
    """Run sync."""
    print("Syncing Xero...")
    created, updated, skipped, errors = sync_xero_clients()
    print(f"  Clients: {created} created, {updated} updated")
    
    print("Syncing Asana projects...")
    created, updated, matched, skipped, errors = sync_asana_projects()
    print(f"  Projects: {created} created, {updated} updated, {matched} matched")
    
    if args.tasks:
        print("Syncing Asana overdue tasks...")
        created, skipped, errors = sync_overdue_tasks()
        print(f"  Tasks: {created} imported, {skipped} skipped")
    
    print("\n✅ Sync complete")
    return 0


def cmd_health(args):
    """Health check."""
    report = health_check()
    print(report.full_report())
    return 0 if report.overall == "HEALTHY" else 1


def cmd_backup(args):
    """Create backup."""
    success, result = create_backup(tag=args.tag)
    if success:
        print(f"✅ Backup created: {result}")
    else:
        print(f"❌ Backup failed: {result}")
    return 0 if success else 1


def cmd_classify(args):
    """Run auto-classification."""
    from lib.classify import run_auto_classification, get_data_quality_report
    
    print("=== Data Quality Before ===")
    q = get_data_quality_report()
    print(f"  Clients tiered: {q['clients']['tiered_pct']}%")
    print(f"  Projects linked: {q['projects']['linked_pct']}%")
    
    print("\n=== Running Classification ===")
    results = run_auto_classification()
    
    t = results['tiers']
    print(f"  Tier suggestions: {t['suggestions']} ({t['high_confidence']} high confidence)")
    print(f"  Applied: {t['applied']}")
    
    p = results['project_links']
    print(f"  Project link suggestions: {p['suggestions']}")
    print(f"  Applied: {p['applied']}")
    
    print("\n=== Data Quality After ===")
    q = results['quality']
    print(f"  Clients tiered: {q['clients']['tiered_pct']}%")
    print(f"  Projects linked: {q['projects']['linked_pct']}%")
    
    return 0


def cmd_cleanup(args):
    """Run maintenance cleanup."""
    from lib.maintenance import get_maintenance_report, cleanup_asana_cruft
    
    report = get_maintenance_report()
    print("=== Maintenance Report ===")
    print(f"  Ancient items (>180d): {report['ancient_items']}")
    print(f"  Very ancient (>1yr): {report['very_ancient_items']}")
    print(f"  Items without client: {report['items_without_client']}")
    
    if report['very_ancient_items'] == 0:
        print("\n✅ System is clean")
        return 0
    
    if args.dry_run:
        print("\n=== Cleanup Preview (dry run) ===")
        results = cleanup_asana_cruft(dry_run=True)
        print(f"  Would archive {len(results['ancient_tasks'])} ancient tasks")
        print(f"  Would archive {len(results['no_context_tasks'])} no-context tasks")
        print("\nRun with --apply to execute")
    else:
        print("\n=== Running Cleanup ===")
        results = cleanup_asana_cruft(dry_run=False)
        print(f"  Archived {len(results['ancient_tasks'])} ancient tasks")
        print(f"  Archived {len(results['no_context_tasks'])} no-context tasks")
    
    return 0


def cmd_quality(args):
    """Show data quality report."""
    from lib.classify import get_data_quality_report
    
    q = get_data_quality_report()
    
    print("## Data Quality Report\n")
    
    print("### Clients")
    print(f"  Total: {q['clients']['total']}")
    print(f"  Tiered: {q['clients']['tiered']} ({q['clients']['tiered_pct']}%)")
    print(f"  With health set: {q['clients']['with_health']}")
    
    print("\n### Projects")
    print(f"  Total: {q['projects']['total']}")
    print(f"  Linked to client: {q['projects']['linked']} ({q['projects']['linked_pct']}%)")
    
    print("\n### Items")
    print(f"  Total: {q['items']['total']}")
    print(f"  Open: {q['items']['open']}")
    print(f"  With client: {q['items']['with_client']} ({q['items']['with_client_pct']}%)")
    print(f"  With due date: {q['items']['with_due_date']} ({q['items']['due_date_pct']}%)")
    
    return 0


def main():
    parser = argparse.ArgumentParser(description="MOH Time OS CLI")
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    # status
    subparsers.add_parser('status', help='System status')
    
    # brief
    subparsers.add_parser('brief', help='Morning brief')
    
    # overdue
    p = subparsers.add_parser('overdue', help='Overdue items')
    p.add_argument('--all', action='store_true', help='Include ancient items')
    p.add_argument('--limit', type=int, help='Max items')
    
    # open
    p = subparsers.add_parser('open', help='Open items')
    p.add_argument('--limit', type=int, help='Max items')
    
    # waiting
    p = subparsers.add_parser('waiting', help='Waiting items')
    p.add_argument('--limit', type=int, help='Max items')
    
    # client
    p = subparsers.add_parser('client', help='Client status')
    p.add_argument('name', help='Client name')
    
    # search
    p = subparsers.add_parser('search', help='Search items')
    p.add_argument('query', help='Search query')
    
    # add
    p = subparsers.add_parser('add', help='Add item')
    p.add_argument('what', help='What needs to happen')
    p.add_argument('--due', help='Due date (YYYY-MM-DD)')
    p.add_argument('--client', help='Client name')
    p.add_argument('--project', help='Project name')
    p.add_argument('--stakes', help='Why it matters')
    
    # done
    p = subparsers.add_parser('done', help='Mark done')
    p.add_argument('id', help='Item ID')
    p.add_argument('--notes', help='Resolution notes')
    
    # sync
    p = subparsers.add_parser('sync', help='Run sync')
    p.add_argument('--tasks', action='store_true', help='Also sync overdue tasks')
    
    # health
    subparsers.add_parser('health', help='Health check')
    
    # backup
    p = subparsers.add_parser('backup', help='Create backup')
    p.add_argument('--tag', help='Backup tag')
    
    # classify
    subparsers.add_parser('classify', help='Run auto-classification')
    
    # cleanup
    p = subparsers.add_parser('cleanup', help='Run maintenance cleanup')
    p.add_argument('--dry-run', action='store_true', default=True, help='Preview only (default)')
    p.add_argument('--apply', dest='dry_run', action='store_false', help='Actually run cleanup')
    
    # quality
    subparsers.add_parser('quality', help='Data quality report')
    
    args = parser.parse_args()
    
    # Dispatch
    commands = {
        'status': cmd_status,
        'brief': cmd_brief,
        'overdue': cmd_overdue,
        'open': cmd_open,
        'waiting': cmd_waiting,
        'client': cmd_client,
        'search': cmd_search,
        'add': cmd_add,
        'done': cmd_done,
        'sync': cmd_sync,
        'health': cmd_health,
        'backup': cmd_backup,
        'classify': cmd_classify,
        'cleanup': cmd_cleanup,
        'quality': cmd_quality,
    }
    
    return commands[args.command](args)


if __name__ == '__main__':
    sys.exit(main())
