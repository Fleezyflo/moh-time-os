#!/usr/bin/env python3
"""
MOH TIME OS CLI - Direct user interface.
No AI required. Direct control.
"""

import sys
from datetime import datetime, timezone

from lib.analyzers import AnalyzerOrchestrator
from lib.autonomous_loop import AutonomousLoop
from lib.collectors import CollectorOrchestrator
from lib.executor import ExecutorEngine
from lib.governance import DomainMode, get_governance
from lib.state_store import get_store
from lib.v4 import (
    get_artifact_service,
    get_coupling_service,
    get_entity_link_service,
    get_identity_service,
    get_issue_service,
    get_policy_service,
    get_proposal_service,
    get_report_service,
    get_signal_service,
)
from lib.v4.ingest_pipeline import get_ingest_pipeline
from lib.v4.orchestrator import get_brief, get_orchestrator, run_cycle


def print_header(text: str):
    """Print a section header."""
    print(f"\n{'═' * 50}")
    print(f"  {text}")
    print(f"{'═' * 50}")


def print_table(headers: list, rows: list, widths: list = None):
    """Print a simple table."""
    if not widths:
        widths = [max(len(str(row[i])) for row in [headers] + rows) for i in range(len(headers))]

    # Header
    header_str = " │ ".join(str(h).ljust(w) for h, w in zip(headers, widths, strict=False))
    print(header_str)
    print("─" * len(header_str))

    # Rows
    for row in rows:
        print(" │ ".join(str(c)[:w].ljust(w) for c, w in zip(row, widths, strict=False)))


def score_color(score: float) -> str:
    """Return ANSI color code for score."""
    if score >= 85:
        return "\033[91m"  # Red
    if score >= 70:
        return "\033[93m"  # Yellow
    return "\033[0m"  # Default


def _format_staleness(ts) -> str:
    """Format a cache timestamp into a human-readable staleness label."""
    if ts is None:
        return "unknown age"
    age = (datetime.now(timezone.utc) - ts).total_seconds()
    if age < 60:
        return "just now"
    if age < 3600:
        return f"{int(age / 60)}m ago"
    if age < 86400:
        return f"{int(age / 3600)}h ago"
    return f"{int(age / 86400)}d ago"


def cmd_priorities(args):
    """Show priority queue."""
    store = get_store()
    queue = store.get_cache("priority_queue")
    cache_ts = store.get_cache_timestamp("priority_queue")

    from_cache = queue is not None
    if not queue:
        print("Priority queue not computed. Running analysis...")
        analyzers = AnalyzerOrchestrator(store=store)
        queue = analyzers.priority_analyzer.analyze()

    limit = int(args[0]) if args else 10

    print_header("PRIORITY QUEUE")

    # Show data freshness
    if from_cache:
        staleness = _format_staleness(cache_ts)
        print(f"  (cached data -- last computed {staleness})")
    else:
        print("  (freshly computed)")

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

    print_table(["#", "Score", "Type", "Title", "Due", "Reason"], rows, [3, 5, 4, 35, 10, 40])


def cmd_today(args):
    """Show today's schedule and priorities."""
    store = get_store()
    analyzers = AnalyzerOrchestrator(store=store)

    # Get day analysis
    day = analyzers.time_analyzer.analyze_day()

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
    queue = store.get_cache("priority_queue")
    cache_ts = store.get_cache_timestamp("priority_queue")
    if queue:
        staleness = _format_staleness(cache_ts)
        print(f"  (cached -- last computed {staleness})")
        for i, item in enumerate(queue[:5], 1):
            score = item.get("score", 0)
            print(f"  {i}. [{score:.0f}] {item.get('title', '')[:45]}")
    else:
        print("  No priority data available (cache empty or expired).")


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
        print(f"\n📋 [{item['domain']}] {item.get('description', item['decision_type'])}")
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
        {"approved": 1, "approved_at": datetime.now(timezone.utc).isoformat()},
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
        {"approved": 0, "approved_at": datetime.now(timezone.utc).isoformat()},
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
            {"status": "done", "updated_at": datetime.now(timezone.utc).isoformat()},
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

V4 OPERATIONS (ops: prefix):

  ops:status         V4 pipeline status (all modules)
  ops:cycle          Run full V4 pipeline cycle
  ops:brief          Executive brief

  # M1: Truth & Proof
  ops:artifacts [n]  List recent artifacts
  ops:identities     List identity profiles
  ops:links          Show entity links
  ops:fix-queue      Show Fix Data queue

  # M2: Signals & Proposals
  ops:signals [type] List active signals
  ops:detect         Run detectors only
  ops:proposals      List proposals

  # M3: Issues
  ops:issues         List open issues
  ops:tag <prop_id>  Tag a proposal to create issue

  # M4: Intersections, Reports, Policy
  ops:couplings      Show entity couplings
  ops:report-exec    Generate exec pack report
  ops:report-client <id>  Generate client report
  ops:reports        List report snapshots
  ops:policy         Show policy stats
  ops:violations     Show protocol violations
  ops:backfill [n]   Backfill N events (default 500)

GOVERNANCE MODES:
  observe            Only watch, never act automatically
  propose            Propose actions, require approval
  auto_low           Auto low-risk, propose high-risk
  auto_high          Auto most, only critical needs approval
""")


# ══════════════════════════════════════════════════
#  V4 Operations Commands (ops: prefix)
# ══════════════════════════════════════════════════


def cmd_ops_status(args):
    """Show comprehensive V4 system status."""
    orch = get_orchestrator()
    status = orch.get_system_status()

    print("=" * 70)
    print("TIME OS V4 - EXECUTIVE OPERATING SYSTEM STATUS")
    print("=" * 70)

    a = status["artifacts"]
    print(f"\n📦 ARTIFACTS: {a['total_artifacts']} total, {a['total_excerpts']} excerpts")
    if a["by_source"]:
        sources = ", ".join(f"{k}:{v}" for k, v in list(a["by_source"].items())[:5])
        print(f"   Sources: {sources}")

    i = status["identities"]
    print(f"\n👤 IDENTITIES: {i['active_profiles']} profiles, {i['active_claims']} claims")
    if i["by_type"]:
        types = ", ".join(f"{k}:{v}" for k, v in i["by_type"].items())
        print(f"   Types: {types}")

    link_data = status["links"]
    total_links = sum(link_data.get("links_by_status", {}).values())
    print(f"\n🔗 ENTITY LINKS: {total_links} total")
    if link_data.get("links_by_status"):
        statuses = ", ".join(f"{k}:{v}" for k, v in link_data["links_by_status"].items())
        print(f"   Status: {statuses}")

    s = status["signals"]
    print(f"\n⚡ SIGNALS: {s.get('registered_signal_types', 0)} types registered")
    if s.get("active_by_severity"):
        sev = ", ".join(f"{k}:{v}" for k, v in s["active_by_severity"].items())
        print(f"   Active by severity: {sev}")
    if s.get("active_by_type"):
        top_types = list(s["active_by_type"].items())[:5]
        types = ", ".join(f"{k}:{v}" for k, v in top_types)
        print(f"   Top types: {types}")

    p = status["proposals"]
    print("\n📋 PROPOSALS")
    if p.get("by_status"):
        statuses = ", ".join(f"{k}:{v}" for k, v in p["by_status"].items())
        print(f"   By status: {statuses}")
    if p.get("open_by_exposure"):
        exp = ", ".join(f"{k}:{v}" for k, v in p["open_by_exposure"].items())
        print(f"   Open by exposure: {exp}")

    iss = status["issues"]
    print("\n🎯 ISSUES")
    if iss.get("by_state"):
        states = ", ".join(f"{k}:{v}" for k, v in iss["by_state"].items())
        print(f"   By state: {states}")
    print(f"   Active watchers: {iss.get('active_watchers', 0)}")
    print(f"   Pending handoffs: {iss.get('pending_handoffs', 0)}")

    c = status.get("couplings", {})
    print(f"\n🔀 COUPLINGS: {c.get('total_couplings', 0)} total")
    if c.get("by_type"):
        types = ", ".join(f"{k}:{v}" for k, v in c["by_type"].items())
        print(f"   By type: {types}")

    r = status.get("reports", {})
    print(f"\n📊 REPORTS: {r.get('templates', 0)} templates, {r.get('snapshots', 0)} snapshots")

    pol = status.get("policy", {})
    print("\n🔐 POLICY")
    print(f"   Roles: {pol.get('roles', 0)}, ACL entries: {pol.get('acl_entries', 0)}")
    print(
        f"   Retention rules: {pol.get('retention_rules', 0)}, "
        f"Redactions: {pol.get('redactions', 0)}"
    )
    if pol.get("violations"):
        viol = ", ".join(f"{k}:{v}" for k, v in pol["violations"].items())
        print(f"   Violations: {viol}")

    print(f"\n🔍 DETECTORS: {len(status['detectors'])} registered")
    for d in status["detectors"]:
        print(f"   • {d['id']} v{d['version']}")

    print("\n" + "=" * 70)


def cmd_ops_cycle(args):
    """Run full V4 pipeline cycle."""
    print("Running V4 pipeline cycle...")
    print("-" * 50)

    stats = run_cycle()

    print(f"\n✅ Cycle completed in {stats['total_duration_ms']}ms")
    print()

    for stage, data in stats.get("stages", {}).items():
        stage_status = data.get("status", "unknown")
        duration = data.get("duration_ms", 0)
        icon = "✓" if stage_status == "completed" else "✗"
        print(f"{icon} {stage.upper()}: {stage_status} ({duration}ms)")

        if stage == "detect" and "detectors" in data:
            for d in data["detectors"]:
                sig_count = d.get("signals_created", 0)
                if "error" in d:
                    print(f"    {d['detector_id']}: ERROR - {d['error']}")
                else:
                    print(f"    {d['detector_id']}: {sig_count} signals")

        if stage == "proposals":
            print(f"    Created: {data.get('created', 0)}, Updated: {data.get('updated', 0)}")


def cmd_ops_brief(args):
    """Show executive brief."""
    brief = get_brief()

    print("=" * 70)
    print("EXECUTIVE BRIEF")
    print(f"Generated: {brief.get('generated_at', 'unknown')}")
    print("=" * 70)

    s = brief.get("summary", {})
    print("\n📊 SUMMARY")
    print(
        f"   Active Signals: {s.get('active_signals', '?')} "
        f"({s.get('critical_signals', '?')} critical, {s.get('high_signals', '?')} high)"
    )
    print(
        f"   Open Proposals: {s.get('open_proposals', '?')} "
        f"({s.get('surfaceable_proposals', '?')} surfaceable)"
    )
    print(
        f"   Open Issues: {s.get('open_issues', '?')} (watchers: {s.get('active_watchers', '?')})"
    )

    if brief["proposals"]:
        print(f"\n📋 TOP PROPOSALS ({len(brief['proposals'])})")
        print("-" * 70)
        for p in brief["proposals"][:5]:
            trend_icon = (
                "↑" if p["trend"] == "worsening" else "↓" if p["trend"] == "improving" else "→"
            )
            print(f"  [{p['proposal_id'][:12]}] {p['headline'][:50]}")
            print(
                f"     Score: {p['score']:.1f} | Count: {p['occurrence_count']} "
                f"| Trend: {trend_icon}"
            )

    if brief["issues"]:
        print(f"\n🎯 OPEN ISSUES ({len(brief['issues'])})")
        print("-" * 70)
        for bi in brief["issues"][:5]:
            print(f"  [{bi['issue_id'][:12]}] {bi['headline'][:50]}")
            print(
                f"     State: {bi['state']} | Priority: {bi['priority']} | Type: {bi['issue_type']}"
            )

    if brief["critical_signals"]:
        print("\n🚨 CRITICAL SIGNALS")
        print("-" * 70)
        for sig in brief["critical_signals"]:
            print(f"  {sig['signal_type']}: {sig['entity_ref_type']}/{sig['entity_ref_id'][:12]}")

    print("\n" + "=" * 70)


def cmd_ops_artifacts(args):
    """List recent artifacts."""
    limit = int(args[0]) if args else 20
    art = get_artifact_service()
    artifacts = art.find_artifacts(limit=limit)

    print(f"\n📦 RECENT ARTIFACTS ({len(artifacts)})")
    print("-" * 80)

    for a in artifacts:
        print(
            f"  {a['artifact_id'][:16]}  {a['source']:10}  {a['type']:15}  {a['occurred_at'][:19]}"
        )


def cmd_ops_identities(args):
    """List identity profiles."""
    ident = get_identity_service()

    persons = ident.find_profiles(profile_type="person", limit=20)
    print(f"\n👤 PERSON PROFILES ({len(persons)})")
    print("-" * 70)
    for p in persons:
        email = p.get("canonical_email", "-") or "-"
        print(f"  {p['profile_id'][:16]}  {p['canonical_name'][:30]:30}  {email[:25]}")

    orgs = ident.find_profiles(profile_type="org", limit=20)
    print(f"\n🏢 ORG PROFILES ({len(orgs)})")
    print("-" * 70)
    for o in orgs[:10]:
        print(f"  {o['profile_id'][:16]}  {o['canonical_name'][:40]}")


def cmd_ops_links(args):
    """Show entity link statistics."""
    link = get_entity_link_service()
    stats = link.get_stats()

    print("\n🔗 ENTITY LINKS")
    print("-" * 50)

    if stats.get("links_by_status"):
        print("By Status:")
        for s, c in stats["links_by_status"].items():
            print(f"  {s}: {c}")

    if stats.get("links_by_entity_type"):
        print("\nBy Entity Type:")
        for t, c in stats["links_by_entity_type"].items():
            print(f"  {t}: {c}")

    if stats.get("links_by_confidence_band"):
        print("\nBy Confidence:")
        for b, c in stats["links_by_confidence_band"].items():
            print(f"  {b}: {c}")


def cmd_ops_fix_queue(args):
    """Show Fix Data queue."""
    link = get_entity_link_service()
    items = link.get_fix_data_queue(limit=30)

    print("\n🔧 FIX DATA QUEUE")
    print("-" * 70)

    if not items:
        print("  ✅ Queue empty")
        return

    for item in items:
        sev = item["severity"].upper()
        print(f"  [{sev:8}] {item['fix_type']}")
        print(f"            {item['description'][:60]}")


def cmd_ops_signals(args):
    """List active signals."""
    signal_type = args[0] if args else None
    sig_svc = get_signal_service()
    signals = sig_svc.find_signals(signal_type=signal_type, status="active", limit=30)

    print(f"\n⚡ ACTIVE SIGNALS ({len(signals)})")
    print("-" * 80)

    for s in signals:
        sev = s["severity"].upper()[:4]
        print(f"  [{sev}] {s['signal_type']:25} {s['entity_ref_type']}/{s['entity_ref_id'][:12]}")


def cmd_ops_detect(args):
    """Run detectors only."""
    orch = get_orchestrator()
    result = orch.run_detectors_only()

    print("\n🔍 DETECTOR RUN")
    print("-" * 50)

    for d in result["detectors"]:
        if "error" in d:
            print(f"  ✗ {d['detector_id']}: {d['error']}")
        else:
            print(f"  ✓ {d['detector_id']}: {d['signals_created']} signals ({d['duration_ms']}ms)")


def cmd_ops_proposals(args):
    """List proposals."""
    prop_svc = get_proposal_service()
    proposals = prop_svc.get_all_open_proposals(limit=20)

    print(f"\n📋 OPEN PROPOSALS ({len(proposals)})")
    print("-" * 80)

    for p in proposals:
        exp = p["ui_exposure_level"][:4]
        trend = "↑" if p["trend"] == "worsening" else "↓" if p["trend"] == "improving" else "→"
        print(f"  [{p['proposal_id'][:12]}] score={p['score']:.1f} {trend} [{exp}]")
        print(f"      {p['headline'][:65]}")


def cmd_ops_issues(args):
    """List open issues."""
    iss_svc = get_issue_service()
    issues = iss_svc.get_open_issues(limit=20)

    print(f"\n🎯 OPEN ISSUES ({len(issues)})")
    print("-" * 80)

    if not issues:
        print("  No open issues")
        return

    for oi in issues:
        print(f"  [{oi['issue_id'][:12]}] pri={oi['priority']} state={oi['state']}")
        print(f"      {oi['headline'][:65]}")


def cmd_ops_tag(args):
    """Tag a proposal to create an issue."""
    if not args:
        print("Usage: ops:tag <proposal_id>")
        return

    proposal_id = args[0]
    iss_svc = get_issue_service()
    result = iss_svc.tag_proposal(proposal_id, actor="cli")

    if result["status"] == "created":
        print(f"\n✅ Issue created: {result['issue_id']}")
        print(f"   Signals attached: {result['signals_attached']}")
        print(f"   Evidence attached: {result['evidence_attached']}")
        print(f"   Watchers created: {result['watchers_created']}")
    else:
        print(f"\n❌ Failed: {result.get('error', 'Unknown error')}")


def cmd_ops_backfill(args):
    """Backfill artifacts from events_raw."""
    limit = int(args[0]) if args else 500
    print(f"Backfilling up to {limit} events...")

    pipe = get_ingest_pipeline()
    result = pipe.backfill_from_events_raw(limit=limit)

    print("\n✅ Backfill Complete")
    print(f"   Processed: {result['processed']}")
    print(f"   Created: {result['created']}")
    print(f"   Unchanged: {result['unchanged']}")
    print(f"   Errors: {result['errors']}")


def cmd_ops_couplings(args):
    """Show entity couplings."""
    coupling_svc = get_coupling_service()
    couplings = coupling_svc.get_strongest_couplings(limit=20)

    print(f"\n🔀 ENTITY COUPLINGS ({len(couplings)})")
    print("-" * 70)

    if not couplings:
        print("  No couplings discovered yet. Run 'ops:cycle' to discover.")
        return

    for c in couplings:
        entities = c["entity_refs"]
        entity_str = " <-> ".join(f"{e['type']}/{e['id'][:8]}" for e in entities[:3])
        print(f"  [{c['coupling_type']}] strength={c['strength']:.2f}")
        print(f"      {entity_str}")


def cmd_ops_report_exec(args):
    """Generate executive pack report."""
    report_svc = get_report_service()
    result = report_svc.generate_exec_pack()

    if result["status"] == "generated":
        print("\n✅ Executive Pack Generated")
        print(f"   Snapshot ID: {result['snapshot_id']}")
        print(f"   Hash: {result['hash']}")

        content = result["content"]
        print("\n📊 SUMMARY")
        if "portfolio_health" in content["sections"]:
            ph = content["sections"]["portfolio_health"]
            print(f"   Portfolio Health: {ph.get('by_health', {})}")
        if "critical_risks" in content["sections"]:
            cr = content["sections"]["critical_risks"]
            print(f"   Critical Risks: {cr.get('count', 0)}")
        if "ar_summary" in content["sections"]:
            ar = content["sections"]["ar_summary"]
            print(
                f"   AR Total: ${ar.get('total_ar', 0):,.0f}, "
                f"Overdue: ${ar.get('total_overdue', 0):,.0f}"
            )
        if "workload" in content["sections"]:
            wl = content["sections"]["workload"]
            print(
                f"   Open Proposals: {wl.get('open_proposals', 0)}, "
                f"Issues: {wl.get('open_issues', 0)}"
            )
    else:
        print(f"\n❌ Failed: {result.get('error')}")


def cmd_ops_report_client(args):
    """Generate client report."""
    if not args:
        print("Usage: ops:report-client <client_id>")
        return

    client_id = args[0]
    report_svc = get_report_service()
    result = report_svc.generate_client_report(client_id)

    if result["status"] == "generated":
        print("\n✅ Client Report Generated")
        print(f"   Client: {result['client_name']}")
        print(f"   Snapshot ID: {result['snapshot_id']}")
        print(f"   Period: {result['period_days']} days")
        print(f"   Sections: {', '.join(result['sections'])}")
    else:
        print(f"\n❌ Failed: {result.get('error')}")


def cmd_ops_reports(args):
    """List report snapshots."""
    report_svc = get_report_service()
    snapshots = report_svc.list_snapshots(limit=20)

    print(f"\n📊 REPORT SNAPSHOTS ({len(snapshots)})")
    print("-" * 70)

    if not snapshots:
        print("  No reports generated yet.")
        return

    for s in snapshots:
        print(f"  [{s['snapshot_id'][:12]}] {s['scope_ref_type']}/{s['scope_ref_id'][:12]}")
        print(f"      Period: {s['period_start'][:10]} to {s['period_end'][:10]}")


def cmd_ops_policy(args):
    """Show policy stats."""
    policy_svc = get_policy_service()
    stats = policy_svc.get_stats()

    print("\n🔐 POLICY STATUS")
    print("-" * 50)
    print(f"   Access Roles: {stats['roles']}")
    print(f"   ACL Entries: {stats['acl_entries']}")
    print(f"   Retention Rules: {stats['retention_rules']}")
    print(f"   Redaction Markers: {stats['redactions']}")

    if stats["violations"]:
        print("   Protocol Violations:")
        for violation_status, count in stats["violations"].items():
            print(f"      {violation_status}: {count}")

    rules = policy_svc.get_retention_rules()
    if rules:
        print("\n   Retention Rules:")
        for r in rules[:5]:
            print(f"      {r['source']}: {r['retention_days']} days")


def cmd_ops_violations(args):
    """Show protocol violations."""
    policy_svc = get_policy_service()
    violations = policy_svc.get_open_violations(limit=20)

    print(f"\n⚠️ PROTOCOL VIOLATIONS ({len(violations)})")
    print("-" * 70)

    if not violations:
        print("  No open violations")
        return

    for v in violations:
        print(f"  [{v['severity'].upper():8}] {v['violation_type']}")
        print(f"      Detected: {v['detected_at'][:19]}")


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
    # V4 Operations commands
    "ops:status": cmd_ops_status,
    "ops:cycle": cmd_ops_cycle,
    "ops:brief": cmd_ops_brief,
    "ops:artifacts": cmd_ops_artifacts,
    "ops:identities": cmd_ops_identities,
    "ops:links": cmd_ops_links,
    "ops:fix-queue": cmd_ops_fix_queue,
    "ops:signals": cmd_ops_signals,
    "ops:detect": cmd_ops_detect,
    "ops:proposals": cmd_ops_proposals,
    "ops:issues": cmd_ops_issues,
    "ops:tag": cmd_ops_tag,
    "ops:backfill": cmd_ops_backfill,
    "ops:couplings": cmd_ops_couplings,
    "ops:report-exec": cmd_ops_report_exec,
    "ops:report-client": cmd_ops_report_client,
    "ops:reports": cmd_ops_reports,
    "ops:policy": cmd_ops_policy,
    "ops:violations": cmd_ops_violations,
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
