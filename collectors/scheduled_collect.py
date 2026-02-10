#!/usr/bin/env python3
"""
Scheduled Collector — Runs periodically to refresh cached data.

This should be triggered by cron every 15-30 minutes.
It collects data from all sources and caches it for heartbeat use.
"""

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from lib import paths
from lib.state_tracker import mark_collected

OUT_DIR = paths.out_dir()


def run_cmd(cmd: list, timeout: int = 60) -> dict:
    """Run command and return JSON output."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            return json.loads(result.stdout)
        print(f"  Command failed: {' '.join(cmd)}")
        print(f"  stderr: {result.stderr[:200]}")
        return {}
    except subprocess.TimeoutExpired:
        print(f"  Timeout: {' '.join(cmd)}")
        return {}
    except json.JSONDecodeError as e:
        print(f"  JSON decode error: {e}")
        return {}
    except Exception as e:
        print(f"  Error: {e}")
        return {}


GOG_ACCOUNT = "molham@hrmny.co"


def collect_calendar():
    """Collect calendar events: 3 days back + 7 days ahead."""
    print("📅 Collecting calendar...")
    from datetime import timedelta

    now = datetime.now(UTC)
    start = now - timedelta(days=3)  # 3 days back for context
    end = now + timedelta(days=7)  # 7 days ahead

    cmd = [
        "gog",
        "calendar",
        "events",
        "primary",
        "--account",
        GOG_ACCOUNT,
        "--from",
        start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "--to",
        end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "--json",
    ]
    data = run_cmd(cmd, timeout=90)

    if data:
        (OUT_DIR / "calendar-next.json").write_text(json.dumps(data, indent=2))
        mark_collected("calendar")
        print(f"   → {len(data.get('events', []))} events")
    return data


def collect_gmail():
    """Collect Gmail incrementally using multi-user collector."""
    print("📧 Collecting gmail...")
    try:
        import importlib.util

        collector_path = Path(__file__).parent / "gmail_multi_user.py"
        spec = importlib.util.spec_from_file_location(
            "gmail_multi_user", collector_path
        )
        gmail_collector = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gmail_collector)

        # Run one cycle (processes next user in queue)
        gmail_collector.run_collection_cycle()

        # Get status
        status = gmail_collector.get_status()
        print(
            f"   → {status.get('total_messages', 0)} messages from {status.get('users_collected', 0)} users"
        )

        return status
    except Exception as e:
        import traceback

        print(f"   → Gmail error: {e}")
        traceback.print_exc()
        return {}

        data = {
            "collected_at": datetime.now(UTC).isoformat(),
            "messages": all_messages,
            "threads_count": len(seen_ids),
        }
        gmail_direct.save(data)
        gmail_direct.save(data)
        mark_collected("gmail")
        print(
            f"   → {len(data.get('messages', []))} messages from {data.get('threads_count', 0)} threads"
        )
        return data
    except Exception as e:
        import traceback

        print(f"   → Gmail error: {e}")
        traceback.print_exc()
        return {}


def collect_tasks():
    """Collect all tasks from all lists."""
    print("📋 Collecting tasks...")
    try:
        from tasks import collect_tasks as _collect
        from tasks import save as save_tasks

        data = _collect()
        save_tasks(data)
        mark_collected("tasks")
        print(f"   → {len(data.get('tasks', []))} tasks")
        return data
    except Exception as e:
        print(f"   → Error: {e}")
        return {}


def collect_chat():
    """Collect chat messages with mentions using direct API (bypasses gog)."""
    print("💬 Collecting chat...")
    try:
        import importlib.util

        chat_path = Path(__file__).parent / "chat_direct.py"
        spec = importlib.util.spec_from_file_location("chat_direct", chat_path)
        chat_direct = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(chat_direct)

        data = chat_direct.collect_chat_full(max_spaces=30, max_messages_per_space=20)
        chat_direct.save(data)
        mark_collected("chat")
        print(
            f"   → {len(data.get('messages', []))} messages, {len(data.get('mentions', []))} mentions"
        )
        return data
    except Exception as e:
        import traceback

        print(f"   → Chat error: {e}")
        traceback.print_exc()
        return {}


def collect_asana():
    """Collect Asana hygiene data."""
    print("📊 Collecting asana...")
    try:
        from asana_ops import generate_asana_report

        report = generate_asana_report()
        if report:
            (OUT_DIR / "asana-ops.json").write_text(json.dumps(report, indent=2))
            mark_collected("asana")
            print(
                f"   → {report.get('overdue_count', 0)} overdue, {report.get('stale_count', 0)} stale"
            )
        return report
    except Exception as e:
        print(f"   → Error: {e}")
        return {}


def collect_xero():
    """Collect Xero AR/invoice data and sync to invoices table."""
    print("💰 Collecting xero...")
    try:
        import importlib.util

        xero_path = Path(__file__).parent / "xero_ops.py"
        spec = importlib.util.spec_from_file_location("xero_ops", xero_path)
        xero_ops = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(xero_ops)

        # Get outstanding invoices and summary
        outstanding = xero_ops.get_outstanding_invoices()
        summary = xero_ops.get_ar_summary()

        data = {
            "collected_at": datetime.now(UTC).isoformat(),
            "outstanding": outstanding,
            "summary": summary,
        }

        # Save output (JSON for V5 detectors)
        out_path = OUT_DIR / "xero-ar.json"
        out_path.write_text(json.dumps(data, indent=2, default=str))
        mark_collected("xero")

        overdue = len([i for i in outstanding if i.get("is_overdue")])
        print(f"   → {len(outstanding)} invoices, {overdue} overdue")

        # Also sync to invoices table (used by API endpoints)
        # This ensures the API has fresh invoice data
        try:
            from lib.collectors.xero import XeroCollector
            from lib.state_store import get_store

            xero_collector = XeroCollector({}, store=get_store())
            sync_result = xero_collector.sync()
            if sync_result.get("success"):
                print(f"   → DB sync: {sync_result.get('stored', 0)} invoices")
            else:
                print(f"   → DB sync warning: {sync_result.get('error', 'unknown')}")
        except Exception as db_err:
            # Don't fail the whole collection if DB sync fails
            print(f"   → DB sync skipped: {db_err}")

        return data
    except Exception as e:
        import traceback

        print(f"   → Xero error: {e}")
        traceback.print_exc()
        return {}


def collect_drive():
    """Collect Google Drive files."""
    print("📁 Collecting drive...")
    try:
        import importlib.util

        drive_path = Path(__file__).parent / "drive_direct.py"
        spec = importlib.util.spec_from_file_location("drive_direct", drive_path)
        drive_direct = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(drive_direct)

        data = drive_direct.collect_drive_full(days=60)
        drive_direct.save(data)
        mark_collected("drive")
        print(f"   → {len(data.get('files', []))} files")
        return data
    except Exception as e:
        import traceback

        print(f"   → Drive error: {e}")
        traceback.print_exc()
        return {}


def collect_contacts():
    """Collect Google Contacts."""
    print("👥 Collecting contacts...")
    try:
        import importlib.util

        contacts_path = Path(__file__).parent / "contacts_direct.py"
        spec = importlib.util.spec_from_file_location("contacts_direct", contacts_path)
        contacts_direct = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(contacts_direct)

        data = contacts_direct.collect_contacts_full()
        contacts_direct.save(data)
        mark_collected("contacts")
        print(f"   → {len(data.get('people', []))} people")
        return data
    except Exception as e:
        import traceback

        print(f"   → Contacts error: {e}")
        traceback.print_exc()
        return {}


def collect_all(sources: list = None, v4_ingest: bool = True):
    """Collect from all sources in parallel, then ingest to V4."""

    from lib.collector_registry import CollectorLock

    # Acquire lock to prevent concurrent runs
    with CollectorLock() as lock:
        if not lock.acquired:
            print("❌ Another collector is already running. Exiting.")
            return {"error": "locked", "message": "Another collector is running"}

        return _collect_all_impl(sources, v4_ingest)


def _collect_all_impl(sources: list = None, v4_ingest: bool = True):
    """Internal implementation of collect_all (runs under lock)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from lib.collector_registry import get_all_sources

    all_sources = get_all_sources()
    sources = sources or all_sources

    print(f"\n{'=' * 50}")
    print(f"📡 Scheduled Collection — {datetime.now(UTC).isoformat()}")
    print(f"{'=' * 50}\n")

    # Collector map — references functions defined in THIS module
    collectors = {
        "calendar": collect_calendar,
        "gmail": collect_gmail,
        "tasks": collect_tasks,
        "chat": collect_chat,
        "asana": collect_asana,
        "xero": collect_xero,
        "drive": collect_drive,
        "contacts": collect_contacts,
    }

    results = {}

    # Run all collectors in parallel
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(collectors[src]): src
            for src in sources
            if src in collectors
        }

        for future in as_completed(futures):
            src = futures[future]
            try:
                results[src] = future.result()
            except Exception as e:
                print(f"  {src} failed: {e}")
                results[src] = {}

    print(f"\n{'=' * 50}")
    print("✅ Collection complete")
    print(f"{'=' * 50}\n")

    # V4 Integration: Ingest collected data into artifact system
    if v4_ingest:
        try:
            from v4_integration import ingest_from_collectors

            print(f"\n{'=' * 50}")
            print("📥 V4 Artifact Ingest")
            print(f"{'=' * 50}\n")
            v4_results = ingest_from_collectors()
            results["v4_ingest"] = v4_results
        except Exception as e:
            print(f"  V4 ingest failed: {e}")
            results["v4_ingest"] = {"error": str(e)}

    # Entity Linking: Keep client/brand/project relationships updated
    try:
        from lib.entity_linker import run_linking

        print(f"\n{'=' * 50}")
        print("🔗 Entity Linking")
        print(f"{'=' * 50}\n")
        linking_results = run_linking(dry_run=False)
        results["entity_linking"] = linking_results["stats"]
    except Exception as e:
        print(f"  Entity linking failed: {e}")
        results["entity_linking"] = {"error": str(e)}

    # V5 Detection Pipeline: Generate signals and issues
    try:
        from lib.v5 import TimeOSOrchestrator, get_db

        print(f"\n{'=' * 50}")
        print("🔍 V5 Signal Detection")
        print(f"{'=' * 50}\n")
        db = get_db()
        orch = TimeOSOrchestrator(db, auto_migrate=False)
        v5_result = orch.run_full_pipeline()
        print(f"  Signals: {v5_result['detection']['signals_detected']}")
        print(f"  Issues: {v5_result['issue_formation']['created']}")
        results["v5_pipeline"] = v5_result
    except Exception as e:
        import traceback

        print(f"  V5 pipeline failed: {e}")
        traceback.print_exc()
        results["v5_pipeline"] = {"error": str(e)}

    # Inbox Enrichment: Populate drill-down context for inbox items
    try:
        from lib.ui_spec_v21.inbox_enricher import run_enrichment_batch

        print(f"\n{'=' * 50}")
        print("🔮 Inbox Drill-Down Enrichment")
        print(f"{'=' * 50}\n")
        enrichment_stats = run_enrichment_batch(use_llm=True, limit=20)
        print(f"  Enriched: {enrichment_stats.get('enriched', 0)}")
        print(f"  Skipped: {enrichment_stats.get('skipped', 0)}")
        results["inbox_enrichment"] = enrichment_stats
    except Exception as e:
        import traceback

        print(f"  Inbox enrichment failed: {e}")
        traceback.print_exc()
        results["inbox_enrichment"] = {"error": str(e)}

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", nargs="*", help="Specific sources to collect")
    args = parser.parse_args()

    collect_all(args.sources)
