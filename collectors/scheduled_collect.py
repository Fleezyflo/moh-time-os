#!/usr/bin/env python3
"""
Scheduled Collector — Runs periodically to refresh cached data.

This should be triggered by cron every 15-30 minutes.
It collects data from all sources and caches it for heartbeat use.
"""

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path

from lib import paths
from lib.compat import UTC
from lib.state_tracker import mark_collected

logger = logging.getLogger(__name__)

OUT_DIR = paths.out_dir()

# Per-collector timeout in seconds (5 minutes)
COLLECTOR_TIMEOUT_SECONDS = 300


def run_cmd(cmd: list, timeout: int = 60) -> dict:
    """Run command and return JSON output."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            return json.loads(result.stdout)
        logger.warning("Command failed: %s — stderr: %s", " ".join(cmd), result.stderr[:200])
        return {}
    except subprocess.TimeoutExpired:
        logger.warning("Command timed out: %s", " ".join(cmd))
        return {}
    except json.JSONDecodeError as e:
        logger.warning("JSON decode error for %s: %s", " ".join(cmd), e)
        return {}
    except OSError as e:
        logger.warning("OS error running %s: %s", " ".join(cmd), e)
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
        spec = importlib.util.spec_from_file_location("gmail_multi_user", collector_path)
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
    except (OSError, ValueError, KeyError) as e:
        logger.warning("Gmail collection error: %s", e, exc_info=True)
        return {}


def collect_tasks():
    """Collect Google Tasks via TasksCollector (DB sync)."""
    print("📋 Collecting tasks...")
    try:
        from lib.collectors.tasks import TasksCollector
        from lib.state_store import get_store

        collector = TasksCollector({}, store=get_store())
        sync_result = collector.sync()

        if sync_result.get("success"):
            mark_collected("tasks")
            stored = sync_result.get("stored", 0)
            print(f"   → {stored} tasks to DB")
        else:
            print(f"   → Tasks sync failed: {sync_result.get('error', 'unknown')}")

        return sync_result
    except (OSError, ValueError, KeyError) as e:
        logger.warning("Tasks collection error: %s", e, exc_info=True)
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
    except (OSError, ValueError, KeyError) as e:
        logger.warning("Chat collection error: %s", e, exc_info=True)
        return {}


def collect_asana():
    """Collect Asana tasks and expanded data via AsanaCollector (DB + JSON)."""
    print("📊 Collecting asana...")
    try:
        from lib.collectors.asana import AsanaCollector
        from lib.state_store import get_store

        collector = AsanaCollector({}, store=get_store())
        sync_result = collector.sync()

        if sync_result.get("success"):
            mark_collected("asana")
            stored = sync_result.get("stored_tasks", 0)
            secondary = sync_result.get("secondary_tables", {})
            print(f"   → {stored} tasks to DB")
            for table, count in secondary.items():
                if count > 0:
                    print(f"   → {count} {table}")
        else:
            print(f"   → Asana sync failed: {sync_result.get('error', 'unknown')}")

        return sync_result
    except (OSError, ValueError, KeyError) as e:
        logger.warning("Asana collection error: %s", e, exc_info=True)
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
        except (OSError, ValueError, KeyError) as db_err:
            # Don't fail the whole collection if DB sync fails
            logger.debug("Xero DB sync skipped: %s", db_err)

        return data
    except (OSError, ValueError, KeyError) as e:
        logger.warning("Xero collection error: %s", e, exc_info=True)
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
    except (OSError, ValueError, KeyError) as e:
        logger.warning("Drive collection error: %s", e, exc_info=True)
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
    except (OSError, ValueError, KeyError) as e:
        logger.warning("Contacts collection error: %s", e, exc_info=True)
        return {}


def collect_all(sources: list[str] | None = None, v4_ingest: bool = True):
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
        futures = {executor.submit(collectors[src]): src for src in sources if src in collectors}

        for future in as_completed(futures):
            src = futures[future]
            try:
                results[src] = future.result(timeout=COLLECTOR_TIMEOUT_SECONDS)
            except TimeoutError:
                logger.error("Collector %s timed out after %ds", src, COLLECTOR_TIMEOUT_SECONDS)
                results[src] = {"error": f"timeout after {COLLECTOR_TIMEOUT_SECONDS}s"}
            except (OSError, ValueError, KeyError) as e:
                logger.warning("Collector %s failed: %s", src, e)
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
        except (OSError, ValueError, KeyError, ImportError) as e:
            logger.warning("V4 ingest failed: %s", e)
            results["v4_ingest"] = {"error": str(e)}

    # Entity Linking: Keep client/brand/project relationships updated
    try:
        from lib.entity_linker import run_linking

        print(f"\n{'=' * 50}")
        print("🔗 Entity Linking")
        print(f"{'=' * 50}\n")
        linking_results = run_linking(dry_run=False)
        results["entity_linking"] = linking_results["stats"]
    except (OSError, ValueError, KeyError, ImportError) as e:
        logger.warning("Entity linking failed: %s", e)
        results["entity_linking"] = {"error": str(e)}

    # V5 Detection Pipeline: DEPRECATED — archived in Brief 29 (VR)
    # Signal detection now runs via lib/intelligence/engine.py
    # See docs/audits/v4_v5_reconciliation_20260221.md
    results["v5_pipeline"] = {"status": "deprecated", "note": "Archived in Brief 29 (VR)"}

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
    except (OSError, ValueError, KeyError, ImportError) as e:
        logger.warning("Inbox enrichment failed: %s", e, exc_info=True)
        results["inbox_enrichment"] = {"error": str(e)}

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", nargs="*", help="Specific sources to collect")
    args = parser.parse_args()

    collect_all(args.sources)
