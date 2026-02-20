#!/usr/bin/env python3
"""
Scheduled Collector — Canonical periodic collection entry point.

This is THE ONLY collection entry point that should be run periodically.
Triggered by cron every 15-30 minutes.

Features:
- Stale lock detection (PID check + TTL)
- Watchdog timeout to prevent hangs
- Guaranteed lock release on any exit
- Structured error reporting

Environment variables:
- COLLECTOR_LOCK_TTL_SECONDS: Max lock age before stale (default: 1200 = 20 min)
- SCHEDULED_COLLECT_TIMEOUT_SECONDS: Total wall-clock timeout (default: 600 = 10 min)
"""

import json
import os
import signal
import subprocess
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from datetime import UTC, datetime
from pathlib import Path

from lib import paths
from lib.state_tracker import mark_collected

OUT_DIR = paths.out_dir()

# Default total timeout for entire collection run (10 minutes)
DEFAULT_TIMEOUT_SECONDS = int(os.environ.get("SCHEDULED_COLLECT_TIMEOUT_SECONDS", "600"))

# V4 ingest is disabled by default (module may not exist)
ENABLE_V4_INGEST = os.environ.get("ENABLE_V4_INGEST", "0").lower() in ("1", "true", "yes")


class CollectionTimeoutError(Exception):
    """Raised when collection exceeds the watchdog timeout."""

    pass


class WatchdogTimer:
    """
    Watchdog timer that raises CollectionTimeoutError on expiry.

    Uses SIGALRM for wall-clock timeout enforcement.
    """

    def __init__(self, timeout_seconds: int):
        self.timeout_seconds = timeout_seconds
        self.expired = False
        self._old_handler = None

    def _timeout_handler(self, signum, frame):
        self.expired = True
        raise CollectionTimeoutError(
            f"Collection exceeded timeout of {self.timeout_seconds} seconds"
        )

    def __enter__(self):
        if self.timeout_seconds > 0:
            self._old_handler = signal.signal(signal.SIGALRM, self._timeout_handler)
            signal.alarm(self.timeout_seconds)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.timeout_seconds > 0:
            signal.alarm(0)  # Cancel alarm
            if self._old_handler is not None:
                signal.signal(signal.SIGALRM, self._old_handler)
        return False  # Don't suppress exceptions


def run_cmd(cmd: list, timeout: int = 60) -> dict:
    """Run command and return JSON output."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)  # noqa: S603
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
    start = now - timedelta(days=3)
    end = now + timedelta(days=7)

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

        gmail_collector.run_collection_cycle()

        status = gmail_collector.get_status()
        print(
            f"   → {status.get('total_messages', 0)} messages from {status.get('users_collected', 0)} users"
        )

        return status
    except Exception as e:
        print(f"   → Gmail error: {e}")
        traceback.print_exc()
        return {"error": str(e)}


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
        return {"error": str(e)}


def collect_chat():
    """Collect chat messages with mentions using direct API."""
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
        print(f"   → Chat error: {e}")
        traceback.print_exc()
        return {"error": str(e)}


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
        return {"error": str(e)}


def collect_xero():
    """Collect Xero AR/invoice data and sync to invoices table."""
    print("💰 Collecting xero...")
    try:
        import importlib.util

        xero_path = Path(__file__).parent / "xero_ops.py"
        spec = importlib.util.spec_from_file_location("xero_ops", xero_path)
        xero_ops = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(xero_ops)

        outstanding = xero_ops.get_outstanding_invoices()
        summary = xero_ops.get_ar_summary()

        data = {
            "collected_at": datetime.now(UTC).isoformat(),
            "outstanding": outstanding,
            "summary": summary,
        }

        out_path = OUT_DIR / "xero-ar.json"
        out_path.write_text(json.dumps(data, indent=2, default=str))
        mark_collected("xero")

        overdue = len([i for i in outstanding if i.get("is_overdue")])
        print(f"   → {len(outstanding)} invoices, {overdue} overdue")

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
            print(f"   → DB sync skipped: {db_err}")

        return data
    except Exception as e:
        print(f"   → Xero error: {e}")
        traceback.print_exc()
        return {"error": str(e)}


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
        print(f"   → Drive error: {e}")
        traceback.print_exc()
        return {"error": str(e)}


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
        print(f"   → Contacts error: {e}")
        traceback.print_exc()
        return {"error": str(e)}


def collect_all(
    sources: list = None,
    v4_ingest: bool = True,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict:
    """
    Collect from all sources, then run post-processing pipelines.

    Args:
        sources: List of source names to collect (None = all)
        v4_ingest: Whether to run V4 artifact ingestion
        timeout_seconds: Total wall-clock timeout (0 = no timeout)

    Returns:
        dict with results per source, or error info if failed/locked/timed out.
    """
    from lib.collector_registry import CollectorLock

    lock = CollectorLock()

    try:
        lock.__enter__()

        if not lock.acquired:
            print("❌ Another collector is already running. Exiting.")
            return {
                "status": "locked",
                "error": "Another collector is running",
                "timestamp": datetime.now(UTC).isoformat(),
            }

        try:
            with WatchdogTimer(timeout_seconds):
                return _collect_all_impl(sources, v4_ingest)
        except CollectionTimeoutError as e:
            print(f"\n❌ TIMEOUT: {e}")
            return {
                "status": "timeout",
                "error": str(e),
                "timeout_seconds": timeout_seconds,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        except Exception as e:
            print(f"\n❌ Collection failed with error: {e}")
            traceback.print_exc()
            return {
                "status": "error",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "timestamp": datetime.now(UTC).isoformat(),
            }
    finally:
        lock.__exit__(None, None, None)


def _collect_all_impl(sources: list = None, v4_ingest: bool = True) -> dict:
    """Internal implementation of collect_all (runs under lock + watchdog)."""
    from lib.collector_registry import get_all_sources

    all_sources = get_all_sources()
    sources = sources or all_sources

    print(f"\n{'=' * 50}")
    print(f"📡 Scheduled Collection — {datetime.now(UTC).isoformat()}")
    print(f"{'=' * 50}\n")

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

    results = {"status": "success", "timestamp": datetime.now(UTC).isoformat()}
    errors = []

    executor = ThreadPoolExecutor(max_workers=5)
    try:
        futures = {executor.submit(collectors[src]): src for src in sources if src in collectors}

        for future in as_completed(futures):
            src = futures[future]
            try:
                result = future.result(timeout=120)
                results[src] = result
                if isinstance(result, dict) and result.get("error"):
                    errors.append(src)
            except TimeoutError:
                print(f"  {src} timed out")
                results[src] = {"error": "timeout"}
                errors.append(src)
            except Exception as e:
                print(f"  {src} failed: {e}")
                results[src] = {"error": str(e)}
                errors.append(src)
    finally:
        # Don't wait for hung threads on shutdown - cancel pending and exit
        executor.shutdown(wait=False, cancel_futures=True)

    print(f"\n{'=' * 50}")
    print("✅ Collection complete")
    if errors:
        print(f"⚠️  Errors in: {', '.join(errors)}")
    print(f"{'=' * 50}\n")

    # V4 ingest is optional - only runs if ENABLE_V4_INGEST=1 AND module exists
    if v4_ingest and ENABLE_V4_INGEST:
        try:
            from v4_integration import ingest_from_collectors

            print(f"\n{'=' * 50}")
            print("📥 V4 Artifact Ingest")
            print(f"{'=' * 50}\n")
            v4_results = ingest_from_collectors()
            results["v4_ingest"] = v4_results
        except ImportError:
            # Module doesn't exist - skip silently (expected in most deployments)
            results["v4_ingest"] = {"status": "skipped", "reason": "module not found"}
        except Exception as e:
            print(f"  V4 ingest failed: {e}")
            results["v4_ingest"] = {"error": str(e)}
    elif v4_ingest and not ENABLE_V4_INGEST:
        results["v4_ingest"] = {"status": "disabled", "reason": "ENABLE_V4_INGEST not set"}

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

    try:
        from lib.v5 import TimeOSOrchestrator, get_db

        print(f"\n{'=' * 50}")
        print("🔍 V5 Signal Detection")
        print(f"{'=' * 50}\n")
        db = get_db()
        # auto_migrate=True ensures signals_v5 table exists
        orch = TimeOSOrchestrator(db, auto_migrate=True)
        v5_result = orch.run_full_pipeline()

        # Defensive access - handle partial/failed results
        signals_detected = 0
        issues_created = 0
        if isinstance(v5_result, dict):
            detection = v5_result.get("detection", {})
            if isinstance(detection, dict):
                signals_detected = detection.get("signals_detected", 0)
            issue_formation = v5_result.get("issue_formation", {})
            if isinstance(issue_formation, dict):
                issues_created = issue_formation.get("created", 0)

        print(f"  Signals: {signals_detected}")
        print(f"  Issues: {issues_created}")
        results["v5_pipeline"] = v5_result
    except Exception as e:
        print(f"  V5 pipeline failed: {e}")
        traceback.print_exc()
        results["v5_pipeline"] = {"status": "error", "error": str(e)}

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
        print(f"  Inbox enrichment failed: {e}")
        traceback.print_exc()
        results["inbox_enrichment"] = {"error": str(e)}

    if errors:
        results["status"] = "partial"
        results["errors"] = errors

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Canonical periodic collector for MOH TIME OS")
    parser.add_argument("--sources", nargs="*", help="Specific sources to collect")
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Total timeout in seconds (default: {DEFAULT_TIMEOUT_SECONDS})",
    )
    parser.add_argument(
        "--no-v4",
        action="store_true",
        help="Skip V4 artifact ingestion",
    )
    args = parser.parse_args()

    result = collect_all(
        sources=args.sources,
        v4_ingest=not args.no_v4,
        timeout_seconds=args.timeout,
    )

    if result.get("status") in ("locked", "timeout", "error"):
        sys.exit(1)
    elif result.get("status") == "partial":
        sys.exit(2)
    else:
        sys.exit(0)
