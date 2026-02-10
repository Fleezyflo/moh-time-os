#!/usr/bin/env python3
"""
Time OS V4 CLI - Executive Operating System

Usage:
    python cli_v4.py status           # Full system status
    python cli_v4.py cycle            # Run full pipeline cycle
    python cli_v4.py brief            # Executive brief

    # M1: Truth & Proof
    python cli_v4.py artifacts [N]    # List recent artifacts
    python cli_v4.py identities       # List identity profiles
    python cli_v4.py links            # Show entity links
    python cli_v4.py fix-queue        # Show Fix Data queue

    # M2: Signals & Proposals
    python cli_v4.py signals [type]   # List active signals
    python cli_v4.py detect           # Run detectors only
    python cli_v4.py proposals        # List proposals

    # M3: Issues
    python cli_v4.py issues           # List open issues
    python cli_v4.py tag <prop_id>    # Tag a proposal to create issue

    # M4: Intersections, Reports, Policy
    python cli_v4.py couplings        # Show entity couplings
    python cli_v4.py report-exec      # Generate exec pack report
    python cli_v4.py report-client <id> # Generate client report
    python cli_v4.py reports          # List report snapshots
    python cli_v4.py policy           # Show policy stats
    python cli_v4.py violations       # Show protocol violations

    python cli_v4.py backfill [N]     # Backfill N events
"""

import sys

# Ensure lib is importable
sys.path.insert(0, ".")

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


def cmd_status():
    """Show comprehensive system status."""
    orch = get_orchestrator()
    status = orch.get_system_status()

    print("=" * 70)
    print("TIME OS V4 - EXECUTIVE OPERATING SYSTEM STATUS")
    print("=" * 70)

    # Artifacts
    a = status["artifacts"]
    print(
        f"\n📦 ARTIFACTS: {a['total_artifacts']} total, {a['total_excerpts']} excerpts"
    )
    if a["by_source"]:
        sources = ", ".join(f"{k}:{v}" for k, v in list(a["by_source"].items())[:5])
        print(f"   Sources: {sources}")

    # Identities
    i = status["identities"]
    print(
        f"\n👤 IDENTITIES: {i['active_profiles']} profiles, {i['active_claims']} claims"
    )
    if i["by_type"]:
        types = ", ".join(f"{k}:{v}" for k, v in i["by_type"].items())
        print(f"   Types: {types}")

    # Links
    l = status["links"]
    total_links = sum(l.get("links_by_status", {}).values())
    print(f"\n🔗 ENTITY LINKS: {total_links} total")
    if l.get("links_by_status"):
        statuses = ", ".join(f"{k}:{v}" for k, v in l["links_by_status"].items())
        print(f"   Status: {statuses}")

    # Signals
    s = status["signals"]
    print(f"\n⚡ SIGNALS: {s.get('registered_signal_types', 0)} types registered")
    if s.get("active_by_severity"):
        sev = ", ".join(f"{k}:{v}" for k, v in s["active_by_severity"].items())
        print(f"   Active by severity: {sev}")
    if s.get("active_by_type"):
        top_types = list(s["active_by_type"].items())[:5]
        types = ", ".join(f"{k}:{v}" for k, v in top_types)
        print(f"   Top types: {types}")

    # Proposals
    p = status["proposals"]
    print("\n📋 PROPOSALS")
    if p.get("by_status"):
        statuses = ", ".join(f"{k}:{v}" for k, v in p["by_status"].items())
        print(f"   By status: {statuses}")
    if p.get("open_by_exposure"):
        exp = ", ".join(f"{k}:{v}" for k, v in p["open_by_exposure"].items())
        print(f"   Open by exposure: {exp}")

    # Issues
    iss = status["issues"]
    print("\n🎯 ISSUES")
    if iss.get("by_state"):
        states = ", ".join(f"{k}:{v}" for k, v in iss["by_state"].items())
        print(f"   By state: {states}")
    print(f"   Active watchers: {iss.get('active_watchers', 0)}")
    print(f"   Pending handoffs: {iss.get('pending_handoffs', 0)}")

    # Couplings
    c = status.get("couplings", {})
    print(f"\n🔀 COUPLINGS: {c.get('total_couplings', 0)} total")
    if c.get("by_type"):
        types = ", ".join(f"{k}:{v}" for k, v in c["by_type"].items())
        print(f"   By type: {types}")

    # Reports
    r = status.get("reports", {})
    print(
        f"\n📊 REPORTS: {r.get('templates', 0)} templates, {r.get('snapshots', 0)} snapshots"
    )

    # Policy
    pol = status.get("policy", {})
    print("\n🔐 POLICY")
    print(f"   Roles: {pol.get('roles', 0)}, ACL entries: {pol.get('acl_entries', 0)}")
    print(
        f"   Retention rules: {pol.get('retention_rules', 0)}, Redactions: {pol.get('redactions', 0)}"
    )
    if pol.get("violations"):
        viol = ", ".join(f"{k}:{v}" for k, v in pol["violations"].items())
        print(f"   Violations: {viol}")

    # Detectors
    print(f"\n🔍 DETECTORS: {len(status['detectors'])} registered")
    for d in status["detectors"]:
        print(f"   • {d['id']} v{d['version']}")

    print("\n" + "=" * 70)


def cmd_cycle():
    """Run full pipeline cycle."""
    print("Running V4 pipeline cycle...")
    print("-" * 50)

    stats = run_cycle()

    print(f"\n✅ Cycle completed in {stats['total_duration_ms']}ms")
    print()

    for stage, data in stats.get("stages", {}).items():
        status = data.get("status", "unknown")
        duration = data.get("duration_ms", 0)
        icon = "✓" if status == "completed" else "✗"
        print(f"{icon} {stage.upper()}: {status} ({duration}ms)")

        if stage == "detect" and "detectors" in data:
            for d in data["detectors"]:
                sig_count = d.get("signals_created", 0)
                if "error" in d:
                    print(f"    {d['detector_id']}: ERROR - {d['error']}")
                else:
                    print(f"    {d['detector_id']}: {sig_count} signals")

        if stage == "proposals":
            print(
                f"    Created: {data.get('created', 0)}, Updated: {data.get('updated', 0)}"
            )


def cmd_brief():
    """Show executive brief."""
    brief = get_brief()

    print("=" * 70)
    print("EXECUTIVE BRIEF")
    print(f"Generated: {brief['generated_at']}")
    print("=" * 70)

    s = brief["summary"]
    print("\n📊 SUMMARY")
    print(
        f"   Active Signals: {s['active_signals']} ({s['critical_signals']} critical, {s['high_signals']} high)"
    )
    print(
        f"   Open Proposals: {s['open_proposals']} ({s['surfaceable_proposals']} surfaceable)"
    )
    print(f"   Open Issues: {s['open_issues']} (watchers: {s['active_watchers']})")

    if brief["proposals"]:
        print(f"\n📋 TOP PROPOSALS ({len(brief['proposals'])})")
        print("-" * 70)
        for p in brief["proposals"][:5]:
            trend_icon = (
                "↑"
                if p["trend"] == "worsening"
                else "↓"
                if p["trend"] == "improving"
                else "→"
            )
            print(f"  [{p['proposal_id'][:12]}] {p['headline'][:50]}")
            print(
                f"     Score: {p['score']:.1f} | Count: {p['occurrence_count']} | Trend: {trend_icon}"
            )

    if brief["issues"]:
        print(f"\n🎯 OPEN ISSUES ({len(brief['issues'])})")
        print("-" * 70)
        for i in brief["issues"][:5]:
            print(f"  [{i['issue_id'][:12]}] {i['headline'][:50]}")
            print(
                f"     State: {i['state']} | Priority: {i['priority']} | Type: {i['issue_type']}"
            )

    if brief["critical_signals"]:
        print("\n🚨 CRITICAL SIGNALS")
        print("-" * 70)
        for sig in brief["critical_signals"]:
            print(
                f"  {sig['signal_type']}: {sig['entity_ref_type']}/{sig['entity_ref_id'][:12]}"
            )

    print("\n" + "=" * 70)


def cmd_artifacts(limit: int = 20):
    """List recent artifacts."""
    art = get_artifact_service()
    artifacts = art.find_artifacts(limit=limit)

    print(f"\n📦 RECENT ARTIFACTS ({len(artifacts)})")
    print("-" * 80)

    for a in artifacts:
        print(
            f"  {a['artifact_id'][:16]}  {a['source']:10}  {a['type']:15}  {a['occurred_at'][:19]}"
        )


def cmd_identities():
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


def cmd_links():
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


def cmd_fix_queue():
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


def cmd_signals(signal_type: str = None):
    """List active signals."""
    sig_svc = get_signal_service()
    signals = sig_svc.find_signals(signal_type=signal_type, status="active", limit=30)

    print(f"\n⚡ ACTIVE SIGNALS ({len(signals)})")
    print("-" * 80)

    for s in signals:
        sev = s["severity"].upper()[:4]
        print(
            f"  [{sev}] {s['signal_type']:25} {s['entity_ref_type']}/{s['entity_ref_id'][:12]}"
        )


def cmd_detect():
    """Run detectors only."""
    orch = get_orchestrator()
    result = orch.run_detectors_only()

    print("\n🔍 DETECTOR RUN")
    print("-" * 50)

    for d in result["detectors"]:
        if "error" in d:
            print(f"  ✗ {d['detector_id']}: {d['error']}")
        else:
            print(
                f"  ✓ {d['detector_id']}: {d['signals_created']} signals ({d['duration_ms']}ms)"
            )


def cmd_proposals():
    """List proposals."""
    prop_svc = get_proposal_service()
    proposals = prop_svc.get_all_open_proposals(limit=20)

    print(f"\n📋 OPEN PROPOSALS ({len(proposals)})")
    print("-" * 80)

    for p in proposals:
        exp = p["ui_exposure_level"][:4]
        trend = (
            "↑"
            if p["trend"] == "worsening"
            else "↓"
            if p["trend"] == "improving"
            else "→"
        )
        print(f"  [{p['proposal_id'][:12]}] score={p['score']:.1f} {trend} [{exp}]")
        print(f"      {p['headline'][:65]}")


def cmd_issues():
    """List open issues."""
    iss_svc = get_issue_service()
    issues = iss_svc.get_open_issues(limit=20)

    print(f"\n🎯 OPEN ISSUES ({len(issues)})")
    print("-" * 80)

    if not issues:
        print("  No open issues")
        return

    for i in issues:
        print(f"  [{i['issue_id'][:12]}] pri={i['priority']} state={i['state']}")
        print(f"      {i['headline'][:65]}")


def cmd_tag(proposal_id: str):
    """Tag a proposal to create an issue."""
    iss_svc = get_issue_service()
    result = iss_svc.tag_proposal(proposal_id, actor="cli")

    if result["status"] == "created":
        print(f"\n✅ Issue created: {result['issue_id']}")
        print(f"   Signals attached: {result['signals_attached']}")
        print(f"   Evidence attached: {result['evidence_attached']}")
        print(f"   Watchers created: {result['watchers_created']}")
    else:
        print(f"\n❌ Failed: {result.get('error', 'Unknown error')}")


def cmd_backfill(limit: int = 500):
    """Backfill artifacts from events_raw."""
    print(f"Backfilling up to {limit} events...")

    pipe = get_ingest_pipeline()
    result = pipe.backfill_from_events_raw(limit=limit)

    print("\n✅ Backfill Complete")
    print(f"   Processed: {result['processed']}")
    print(f"   Created: {result['created']}")
    print(f"   Unchanged: {result['unchanged']}")
    print(f"   Errors: {result['errors']}")


def cmd_couplings():
    """Show entity couplings."""
    coupling_svc = get_coupling_service()
    couplings = coupling_svc.get_strongest_couplings(limit=20)

    print(f"\n🔀 ENTITY COUPLINGS ({len(couplings)})")
    print("-" * 70)

    if not couplings:
        print("  No couplings discovered yet. Run 'cycle' to discover.")
        return

    for c in couplings:
        entities = c["entity_refs"]
        entity_str = " <-> ".join(f"{e['type']}/{e['id'][:8]}" for e in entities[:3])
        print(f"  [{c['coupling_type']}] strength={c['strength']:.2f}")
        print(f"      {entity_str}")


def cmd_report_exec():
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
                f"   AR Total: ${ar.get('total_ar', 0):,.0f}, Overdue: ${ar.get('total_overdue', 0):,.0f}"
            )
        if "workload" in content["sections"]:
            wl = content["sections"]["workload"]
            print(
                f"   Open Proposals: {wl.get('open_proposals', 0)}, Issues: {wl.get('open_issues', 0)}"
            )
    else:
        print(f"\n❌ Failed: {result.get('error')}")


def cmd_report_client(client_id: str):
    """Generate client report."""
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


def cmd_reports():
    """List report snapshots."""
    report_svc = get_report_service()
    snapshots = report_svc.list_snapshots(limit=20)

    print(f"\n📊 REPORT SNAPSHOTS ({len(snapshots)})")
    print("-" * 70)

    if not snapshots:
        print("  No reports generated yet.")
        return

    for s in snapshots:
        print(
            f"  [{s['snapshot_id'][:12]}] {s['scope_ref_type']}/{s['scope_ref_id'][:12]}"
        )
        print(f"      Period: {s['period_start'][:10]} to {s['period_end'][:10]}")


def cmd_policy():
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
        for status, count in stats["violations"].items():
            print(f"      {status}: {count}")

    # Show retention rules
    rules = policy_svc.get_retention_rules()
    if rules:
        print("\n   Retention Rules:")
        for r in rules[:5]:
            print(f"      {r['source']}: {r['retention_days']} days")


def cmd_violations():
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


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]

    if cmd == "status":
        cmd_status()
    elif cmd == "cycle":
        cmd_cycle()
    elif cmd == "brief":
        cmd_brief()
    elif cmd == "artifacts":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        cmd_artifacts(limit)
    elif cmd == "identities":
        cmd_identities()
    elif cmd == "links":
        cmd_links()
    elif cmd == "fix-queue":
        cmd_fix_queue()
    elif cmd == "signals":
        sig_type = sys.argv[2] if len(sys.argv) > 2 else None
        cmd_signals(sig_type)
    elif cmd == "detect":
        cmd_detect()
    elif cmd == "proposals":
        cmd_proposals()
    elif cmd == "issues":
        cmd_issues()
    elif cmd == "tag":
        if len(sys.argv) < 3:
            print("Usage: cli_v4.py tag <proposal_id>")
            return
        cmd_tag(sys.argv[2])
    elif cmd == "couplings":
        cmd_couplings()
    elif cmd == "report-exec":
        cmd_report_exec()
    elif cmd == "report-client":
        if len(sys.argv) < 3:
            print("Usage: cli_v4.py report-client <client_id>")
            return
        cmd_report_client(sys.argv[2])
    elif cmd == "reports":
        cmd_reports()
    elif cmd == "policy":
        cmd_policy()
    elif cmd == "violations":
        cmd_violations()
    elif cmd == "backfill":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 500
        cmd_backfill(limit)
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    main()
