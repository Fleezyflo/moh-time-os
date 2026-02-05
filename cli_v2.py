#!/usr/bin/env python3
"""MOH Time OS v2 CLI."""

import argparse
import sys
from datetime import date

# Add lib to path
sys.path.insert(0, str(__file__).rsplit('/', 1)[0])

from lib import (
    init_db, startup_check, status_report, summary_stats,
    open_items, overdue, due_today, due_this_week, waiting,
    generate_brief, needs_attention,
    list_clients, find_client, client_summary_by_name,
    create_backup, backup_status,
)


def cmd_status(args):
    """Show system status."""
    print(status_report())


def cmd_stats(args):
    """Show summary statistics."""
    stats = summary_stats()
    print(f"Items: {stats['open']} open, {stats['waiting']} waiting, {stats['overdue']} overdue")
    print(f"Entities: {stats['clients']} clients, {stats['projects']} projects, {stats['people']} people")
    print(f"Total items: {stats['total_items']} ({stats['done']} done)")


def cmd_overdue(args):
    """Show overdue items."""
    items = overdue()
    if not items:
        print("No overdue items 🎉")
        return
    
    print(f"⚠️ {len(items)} overdue items:\n")
    for item in items[:args.limit]:
        print(f"• {item.short_display()}")
        if args.verbose:
            print(f"  {item.context.summary() if item.context else ''}")
            print()


def cmd_today(args):
    """Show items due today."""
    items = due_today()
    if not items:
        print(f"Nothing due today ({date.today().isoformat()})")
        return
    
    print(f"📅 {len(items)} items due today:\n")
    for item in items[:args.limit]:
        print(f"• {item.what}")
        if item.counterparty:
            print(f"  ({item.counterparty})")


def cmd_week(args):
    """Show items due this week."""
    items = due_this_week()
    if not items:
        print("Nothing due this week")
        return
    
    print(f"📅 {len(items)} items due this week:\n")
    for item in items[:args.limit]:
        print(f"• {item.short_display()}")


def cmd_open(args):
    """Show all open items."""
    items = open_items()
    if not items:
        print("No open items")
        return
    
    print(f"📋 {len(items)} open items:\n")
    for item in items[:args.limit]:
        print(f"• {item.short_display()}")


def cmd_brief(args):
    """Generate daily brief."""
    print(generate_brief())


def cmd_attention(args):
    """Show what needs attention."""
    result = needs_attention()
    
    if not result['needs_attention']:
        print("✅ All clear. Nothing urgent needs attention.")
        return
    
    counts = result['counts']
    print(f"🔔 Needs attention: {counts['overdue']} overdue, {counts['due_today']} due today, "
          f"{counts['waiting_too_long']} waiting too long, {counts['clients_at_risk']} clients at risk\n")
    
    if result['overdue']:
        print("⚠️ Overdue:")
        for item in result['overdue'][:5]:
            print(f"  • {item.short_display()}")
        print()
    
    if result['due_today']:
        print("📅 Due today:")
        for item in result['due_today'][:5]:
            print(f"  • {item.what}")
        print()


def cmd_clients(args):
    """List clients."""
    clients = list_clients(tier=args.tier, limit=args.limit)
    if not clients:
        print("No clients found")
        return
    
    for client in clients:
        print(f"• [{client.tier}] {client.name} — {client.health}")
        if args.verbose:
            print(f"    AR: {client.ar_outstanding:,.0f} AED ({client.ar_aging})")


def cmd_client(args):
    """Show client details."""
    result = client_summary_by_name(args.name)
    if 'error' in result:
        print(result['error'])
        return
    
    print(result['client'])
    print(f"\nOpen items: {result['open_items']} ({result['overdue_items']} overdue)")
    
    if result['items']:
        print("\nItems:")
        for item in result['items'][:10]:
            print(f"  • {item.short_display()}")


def cmd_backup(args):
    """Create a backup."""
    path = create_backup()
    if path:
        print(f"✅ Backup created: {path.name}")
    else:
        print("❌ Backup failed")


def cmd_backups(args):
    """Show backup status."""
    print(backup_status())


def cmd_query(args):
    """Handle natural language query."""
    from lib.protocol import handle_query
    query = ' '.join(args.query)
    print(handle_query(query))


def cmd_track(args):
    """Track a new item."""
    from lib.capture import capture_item
    item_id, msg = capture_item(
        what=args.what,
        due=args.due,
        client=args.client,
        person=args.person,
        stakes=args.stakes,
    )
    print(msg)
    print(f"\nItem ID: {item_id[:8]}...")


def cmd_add_contact(args):
    """Add an external contact."""
    from lib.contacts import create_external_contact
    
    person_id = create_external_contact(
        name=args.name,
        client_name=args.client,
        role=args.role,
        email=args.email,
        notes=args.notes,
    )
    
    if person_id:
        print(f"✅ Created contact: {args.name} at {args.client}")
        if args.role:
            print(f"   Role: {args.role}")
        print(f"   ID: {person_id[:8]}...")
    else:
        print(f"❌ Client '{args.client}' not found")


def cmd_contacts(args):
    """List contacts for a client."""
    from lib.contacts import list_client_contacts_by_name, contact_summary
    from lib import find_client
    
    if args.client:
        contacts = list_client_contacts_by_name(args.client)
        client = find_client(name=args.client)
        if not client:
            print(f"Client '{args.client}' not found")
            return
        
        if not contacts:
            print(f"No contacts for {client.name}")
            return
        
        print(f"Contacts at {client.name}:")
        for c in contacts:
            role = f" ({c.role})" if c.role else ""
            email = f" - {c.email}" if c.email else ""
            print(f"  • {c.name}{role}{email}")
    else:
        summary = contact_summary()
        print(f"Contact Summary:")
        print(f"  Internal team: {summary['internal_count']}")
        print(f"  External contacts: {summary['external_count']}")
        
        if summary['by_client']:
            print(f"\n  By client:")
            for client, count in sorted(summary['by_client'].items()):
                print(f"    {client}: {count}")


def cmd_init(args):
    """Initialize database."""
    init_db()
    status, msg = startup_check()
    print(msg)


def cmd_daemon(args):
    """Manage the background daemon."""
    from lib.daemon import TimeOSDaemon
    
    if args.action == 'start':
        running, pid = TimeOSDaemon.is_running()
        if running:
            print(f"Daemon already running (PID {pid})")
            return
        
        if args.bg:
            import os
            pid = os.fork()
            if pid > 0:
                print(f"Daemon started in background (PID {pid})")
                return
            os.setsid()
        
        daemon = TimeOSDaemon()
        daemon.run()
        
    elif args.action == 'stop':
        TimeOSDaemon.stop()
        
    elif args.action == 'status':
        status = TimeOSDaemon.status()
        print(f"Running: {'✓ Yes' if status['running'] else '✗ No'}")
        if status['pid']:
            print(f"PID: {status['pid']}")
        if status.get('state_updated'):
            print(f"State updated: {status['state_updated']}")
        print(f"\nJobs:")
        for name, job in status.get('jobs', {}).items():
            last_run = job.get('last_run', 'never')[:19] if job.get('last_run') else 'never'
            failures = job.get('consecutive_failures', 0)
            status_str = '✓' if failures == 0 else f'✗ ({failures} failures)'
            print(f"  {name}: last run {last_run} {status_str}")
            
    elif args.action == 'run-once':
        daemon = TimeOSDaemon()
        daemon.run_once()


def cmd_attendance(args):
    """Run meeting attendance analysis."""
    from lib.state_store import StateStore
    from lib.analyzers.attendance import AttendanceAnalyzer
    import json as json_mod
    
    store = StateStore()
    analyzer = AttendanceAnalyzer(store)
    
    analysis = analyzer.analyze_all(days_back=args.days)
    
    if getattr(args, 'json', False):
        # JSON output - exclude full meeting details for brevity
        output = {
            'team_summary': analysis['team_summary'],
            'person_stats': analysis['person_stats'],
            'flags': analysis['flags'],
            'period_days': analysis['period_days'],
        }
        print(json_mod.dumps(output, indent=2, default=str))
    else:
        analyzer.print_report(analysis)


def main():
    parser = argparse.ArgumentParser(
        description="MOH Time OS v2 — Entity-centric tracking with full context"
    )
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Status
    subparsers.add_parser('status', help='Show system status')
    subparsers.add_parser('stats', help='Show summary statistics')
    subparsers.add_parser('init', help='Initialize database')
    
    # Items
    p = subparsers.add_parser('overdue', help='Show overdue items')
    p.add_argument('--limit', '-l', type=int, default=20)
    p.add_argument('--verbose', '-v', action='store_true')
    
    p = subparsers.add_parser('today', help='Show items due today')
    p.add_argument('--limit', '-l', type=int, default=20)
    
    p = subparsers.add_parser('week', help='Show items due this week')
    p.add_argument('--limit', '-l', type=int, default=20)
    
    p = subparsers.add_parser('open', help='Show all open items')
    p.add_argument('--limit', '-l', type=int, default=50)
    
    # Brief
    subparsers.add_parser('brief', help='Generate daily brief')
    subparsers.add_parser('attention', help='Show what needs attention')
    
    # Clients
    p = subparsers.add_parser('clients', help='List clients')
    p.add_argument('--tier', '-t', choices=['A', 'B', 'C'])
    p.add_argument('--limit', '-l', type=int, default=50)
    p.add_argument('--verbose', '-v', action='store_true')
    
    p = subparsers.add_parser('client', help='Show client details')
    p.add_argument('name', help='Client name (partial match)')
    
    # Backup
    subparsers.add_parser('backup', help='Create a backup')
    subparsers.add_parser('backups', help='Show backup status')
    
    # Daemon
    p = subparsers.add_parser('daemon', help='Manage background daemon')
    p.add_argument('action', choices=['start', 'stop', 'status', 'run-once'],
                   help='Daemon action')
    p.add_argument('--bg', action='store_true',
                   help='Run in background (start only)')
    
    # Query
    p = subparsers.add_parser('query', help='Natural language query')
    p.add_argument('query', nargs='+', help='Query text')
    
    # Track
    p = subparsers.add_parser('track', help='Track a new item')
    p.add_argument('what', help='What needs to happen')
    p.add_argument('--due', '-d', help='Due date (natural language)')
    p.add_argument('--client', '-c', help='Client name/hint')
    p.add_argument('--person', '-p', help='Person name/hint')
    p.add_argument('--stakes', '-s', help='Why this matters')
    
    # Contacts
    p = subparsers.add_parser('add-contact', help='Add external contact')
    p.add_argument('name', help='Contact name')
    p.add_argument('--client', '-c', required=True, help='Client company name')
    p.add_argument('--role', '-r', help='Role at the company')
    p.add_argument('--email', '-e', help='Email address')
    p.add_argument('--notes', '-n', help='Relationship notes')
    
    p = subparsers.add_parser('contacts', help='List contacts')
    p.add_argument('--client', '-c', help='Client name (optional)')
    
    # Attendance analysis
    p = subparsers.add_parser('attendance', help='Meeting attendance analysis')
    p.add_argument('--days', '-d', type=int, default=30, help='Days to analyze (default: 30)')
    p.add_argument('--person', '-p', help='Filter to specific person')
    p.add_argument('--json', action='store_true', help='Output JSON')
    
    args = parser.parse_args()
    
    if not args.command:
        # Default: show attention
        status, msg = startup_check()
        print(msg)
        print()
        cmd_attention(args)
        return
    
    # Dispatch
    commands = {
        'status': cmd_status,
        'stats': cmd_stats,
        'init': cmd_init,
        'overdue': cmd_overdue,
        'today': cmd_today,
        'week': cmd_week,
        'open': cmd_open,
        'brief': cmd_brief,
        'attention': cmd_attention,
        'clients': cmd_clients,
        'client': cmd_client,
        'backup': cmd_backup,
        'backups': cmd_backups,
        'query': cmd_query,
        'track': cmd_track,
        'add-contact': cmd_add_contact,
        'contacts': cmd_contacts,
        'daemon': cmd_daemon,
        'attendance': cmd_attendance,
    }
    
    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
