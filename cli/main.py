#!/usr/bin/env python3
"""
MOH TIME OS CLI - Direct user interface.
No AI required. Direct control.
"""

from datetime import datetime

from lib.analyzers import AnalyzerOrchestrator
from lib.autonomous_loop import AutonomousLoop
from lib.collectors import CollectorOrchestrator
from lib.executor import ExecutorEngine
from lib.governance import DomainMode, get_governance
from lib.state_store import get_store


def print_header(text: str):
    """Print a section header."""
    print(f"\n{'═' * 50}")
    print(f"  {text}")
    print(f"{'═' * 50}")


def print_table(headers: list, rows: list, widths: list = None):
    """Print a simple table."""
    if not widths:
        widths = [
            max(len(str(row[i])) for row in [headers] + rows)
            for i in range(len(headers))
        ]

    # Header
    header_str = " │ ".join(str(h).ljust(w) for h, w in zip(headers, widths))
    print(header_str)
    print("─" * len(header_str))

    # Rows
    for row in rows:
        print(" │ ".join(str(c)[:w].ljust(w) for c, w in zip(row, widths)))


def score_color(score: float) -> str:
    """Return ANSI color code for score."""
    if score >= 85:
        return "\033[91m"  # Red
    if score >= 70:
        return "\033[93m"  # Yellow
    return "\033[0m"  # Default


def cmd_priorities(args):
    """Show priority queue."""
    store = get_store()
    queue = store.get_cache("priority_queue")

    if not queue:
        print("Priority queue not computed. Running analysis...")
        analyzers = AnalyzerOrchestrator(store=store)
        queue = analyzers.priority.analyze()

    limit = int(args[0]) if args else 10

    print_header("PRIORITY QUEUE")

    if not queue:
        print("No items in queue.")
        return

    rows = []
    for i, item in enumerate(queue[:limit], 1):
        score = item.get("score", 0)
        reasons = ", ".join(item.get("reasons", []))[:40]
        rows.append(
            [
                i,
                f"{score:.0f}",
                item.get("type", "?")[:4],
                item.get("title", "")[:35],
                item.get("due", "-")[:10] if item.get("due") else "-",
                reasons,
            ]
        )

    print_table(
        ["#", "Score", "Type", "Title", "Due", "Reason"], rows, [3, 5, 4, 35, 10, 40]
    )


def cmd_today(args):
    """Show today's schedule and priorities."""
    store = get_store()
    analyzers = AnalyzerOrchestrator(store=store)

    # Get day analysis
    day = analyzers.time.analyze_day()

    print_header(f"TODAY: {day['date']}")

    # Events
    print(f"\n📅 EVENTS ({day['events_count']})")
    events = store.get_upcoming_events(24)
    if events:
        for event in events[:10]:
            start = event.get("start_time", "")[:16].replace("T", " ")
            print(f"  {start}  {event.get('title', '')[:40]}")
    else:
        print("  No events")

    # Available time
    print("\n⏰ AVAILABLE TIME")
    print(f"  Total: {day['total_available_hours']:.1f} hours")
    print(f"  Deep work: {day['deep_work_hours']:.1f} hours")

    # Issues
    issues = day.get("issues", {})
    if issues.get("overbooked") or issues.get("back_to_back"):
        print("\n⚠️  ISSUES")
        for overlap in issues.get("overbooked", []):
            print(f"  Conflict: {overlap['event1'][:20]} & {overlap['event2'][:20]}")
        for b2b in issues.get("back_to_back", []):
            print(f"  No buffer: {b2b['event1'][:20]} → {b2b['event2'][:20]}")

    # Top priorities
    print("\n🎯 TOP PRIORITIES")
    queue = store.get_cache("priority_queue") or []
    for i, item in enumerate(queue[:5], 1):
        score = item.get("score", 0)
        print(f"  {i}. [{score:.0f}] {item.get('title', '')[:45]}")


def cmd_insights(args):
    """Show current insights and anomalies."""
    store = get_store()
    insights = store.get_active_insights()

    print_header("ACTIVE INSIGHTS")

    if not insights:
        print("No active insights.")
        return

    for insight in insights:
        icon = "🔴" if "critical" in insight.get("title", "").lower() else "🟡"
        print(f"\n{icon} [{insight['domain']}] {insight['title']}")
        if insight.get("description"):
            print(f"   {insight['description']}")


def cmd_approvals(args):
    """Show pending approvals."""
    store = get_store()
    pending = store.get_pending_decisions()

    print_header("PENDING APPROVALS")

    if not pending:
        print("No pending approvals.")
        return

    for item in pending:
        print(
            f"\n📋 [{item['domain']}] {item.get('description', item['decision_type'])}"
        )
        print(f"   Rationale: {item.get('rationale', 'N/A')}")
        print(f"   Confidence: {float(item.get('confidence', 0)) * 100:.0f}%")
        print(f"   ID: {item['id']}")


def cmd_approve(args):
    """Approve a pending decision."""
    if not args:
        print("Usage: approve <decision_id>")
        return

    decision_id = args[0]
    store = get_store()

    decision = store.get("decisions", decision_id)
    if not decision:
        print(f"Decision not found: {decision_id}")
        return

    store.update(
        "decisions",
        decision_id,
        {"approved": 1, "approved_at": datetime.now().isoformat()},
    )

    print(f"✅ Approved: {decision.get('description', decision_id)}")


def cmd_reject(args):
    """Reject a pending decision."""
    if not args:
        print("Usage: reject <decision_id>")
        return

    decision_id = args[0]
    store = get_store()

    decision = store.get("decisions", decision_id)
    if not decision:
        print(f"Decision not found: {decision_id}")
        return

    store.update(
        "decisions",
        decision_id,
        {"approved": 0, "approved_at": datetime.now().isoformat()},
    )

    print(f"❌ Rejected: {decision.get('description', decision_id)}")


def cmd_sync(args):
    """Force sync data sources."""
    source = args[0] if args else None
    collectors = CollectorOrchestrator()

    print(f"Syncing {'all sources' if not source else source}...")
    results = collectors.force_sync(source)

    for name, result in results.items():
        if result.get("success"):
            print(f"  ✓ {name}: {result.get('stored', 0)} items")
        else:
            print(f"  ✗ {name}: {result.get('error', 'Unknown error')}")


def cmd_run(args):
    """Run one autonomous cycle."""
    loop = AutonomousLoop()
    result = loop.run_cycle()

    if result.get("success"):
        print(f"\n✅ Cycle completed in {result['duration_ms']:.0f}ms")
    else:
        print(f"\n❌ Cycle failed: {result.get('error')}")


def cmd_status(args):
    """Show system status."""
    loop = AutonomousLoop()
    status = loop.get_status()

    print_header("SYSTEM STATUS")

    print("\n📊 COUNTS")
    counts = status.get("counts", {})
    print(f"  Pending tasks: {counts.get('pending_tasks', 0)}")
    print(f"  Pending emails: {counts.get('pending_emails', 0)}")
    print(f"  Events (24h): {counts.get('events_today', 0)}")
    print(f"  Pending decisions: {counts.get('pending_decisions', 0)}")

    print("\n🔄 COLLECTORS")
    for name, col in status.get("collectors", {}).items():
        status_icon = "✓" if col.get("healthy") else "✗"
        last = col.get("last_sync", "Never")[:19] if col.get("last_sync") else "Never"
        print(f"  {status_icon} {name}: Last sync {last}")

    print("\n🔒 GOVERNANCE")
    gov = status.get("governance", {})
    print(f"  Emergency brake: {'ACTIVE' if gov.get('emergency_brake') else 'Off'}")
    for domain, cfg in gov.get("domains", {}).items():
        print(f"  {domain}: {cfg.get('mode', 'observe')}")


def cmd_mode(args):
    """Set governance mode for a domain."""
    if len(args) < 2:
        print("Usage: mode <domain> <observe|propose|auto_low|auto_high>")
        return

    domain = args[0]
    mode_str = args[1]

    try:
        mode = DomainMode(mode_str)
    except ValueError:
        print(f"Invalid mode: {mode_str}")
        print("Valid modes: observe, propose, auto_low, auto_high")
        return

    governance = get_governance()
    governance.set_mode(domain, mode)
    print(f"✅ {domain} mode set to {mode.value}")


def cmd_actions(args):
    """Show pending actions."""
    executor = ExecutorEngine()
    pending = executor.get_pending_actions()

    print_header("PENDING ACTIONS")

    if not pending:
        print("No pending actions.")
        return

    for action in pending:
        print(f"\n⚡ [{action['type']}] {action.get('target_system', 'unknown')}")
        print(f"   ID: {action['id']}")
        print(f"   Created: {action['created_at'][:16]}")


def cmd_execute(args):
    """Execute all approved actions."""
    executor = ExecutorEngine()
    results = executor.process_pending_actions()

    if not results:
        print("No approved actions to execute.")
        return

    for result in results:
        status = "✓" if result.get("status") == "done" else "✗"
        print(f"  {status} {result['id']}: {result.get('status')}")


def cmd_complete(args):
    """Mark a priority item as complete."""
    if not args:
        print("Usage: complete <item_id>")
        return

    item_id = args[0]
    store = get_store()

    # Check if task or communication
    if item_id.startswith("gtask_"):
        store.update(
            "tasks",
            item_id,
            {"status": "done", "updated_at": datetime.now().isoformat()},
        )
        print(f"✓ Completed: {item_id}")
    elif item_id.startswith("gmail_"):
        store.update("communications", item_id, {"processed": 1})
        print(f"✓ Processed: {item_id}")
    else:
        print(f"Unknown item type: {item_id}")


def cmd_help(args):
    """Show help."""
    print_header("MOH TIME OS CLI")
    print("""
COMMANDS:

  priorities [n]     Show top n priority items (default 10)
  today              Show today's schedule and priorities
  insights           Show active insights and anomalies
  approvals          Show pending approval decisions
  approve <id>       Approve a decision
  reject <id>        Reject a decision
  complete <id>      Mark item as complete
  actions            Show pending actions
  execute            Execute approved actions
  sync [source]      Force sync data sources
  run                Run one autonomous cycle
  status             Show system status
  mode <d> <m>       Set governance mode for domain
  help               Show this help

GOVERNANCE MODES:
  observe            Only watch, never act automatically
  propose            Propose actions, require approval
  auto_low           Auto low-risk, propose high-risk
  auto_high          Auto most, only critical needs approval
""")


COMMANDS = {
    "priorities": cmd_priorities,
    "p": cmd_priorities,
    "today": cmd_today,
    "t": cmd_today,
    "insights": cmd_insights,
    "i": cmd_insights,
    "approvals": cmd_approvals,
    "a": cmd_approvals,
    "approve": cmd_approve,
    "reject": cmd_reject,
    "complete": cmd_complete,
    "c": cmd_complete,
    "actions": cmd_actions,
    "execute": cmd_execute,
    "x": cmd_execute,
    "sync": cmd_sync,
    "s": cmd_sync,
    "run": cmd_run,
    "r": cmd_run,
    "status": cmd_status,
    "mode": cmd_mode,
    "help": cmd_help,
    "h": cmd_help,
}


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        cmd_help([])
        return

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd in COMMANDS:
        COMMANDS[cmd](args)
    else:
        print(f"Unknown command: {cmd}")
        print("Run 'help' for available commands.")


if __name__ == "__main__":
    main()
