#!/usr/bin/env python3
"""
Production Readiness Verification Script.

Run this before deploying to verify the system is properly configured.
Exit code 0 = all checks pass, non-zero = failures detected.

Usage:
    python scripts/verify_production.py [--api-url URL] [--token TOKEN]
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def ok(msg: str) -> None:
    print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")


def fail(msg: str) -> None:
    print(f"{Colors.RED}✗{Colors.RESET} {msg}")


def warn(msg: str) -> None:
    print(f"{Colors.YELLOW}⚠{Colors.RESET} {msg}")


def header(msg: str) -> None:
    print(f"\n{Colors.BOLD}=== {msg} ==={Colors.RESET}")


def check_env_vars() -> list[str]:
    """Check required and recommended environment variables."""
    header("Environment Variables")
    failures = []

    # Required
    intel_token = os.environ.get("INTEL_API_TOKEN")
    if intel_token:
        ok("INTEL_API_TOKEN is set")
    else:
        fail("INTEL_API_TOKEN not set - AUTH DISABLED IN PRODUCTION!")
        failures.append("INTEL_API_TOKEN")

    # Recommended
    slack_webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if slack_webhook:
        ok("SLACK_WEBHOOK_URL is set")
    else:
        warn("SLACK_WEBHOOK_URL not set - notifications won't deliver to Slack")

    return failures


def check_database() -> list[str]:
    """Check database exists and has expected structure."""
    header("Database")
    failures = []

    from lib.paths import db_path

    db_file = db_path()

    if not db_file.exists():
        fail(f"Database not found: {db_file}")
        failures.append("database_missing")
        return failures

    ok(f"Database exists: {db_file}")

    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # Count tables
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        table_count = cursor.fetchone()[0]

        if table_count >= 80:
            ok(f"Tables: {table_count} (expected ~83+)")
        else:
            fail(f"Tables: {table_count} (expected ~83+)")
            failures.append("table_count")

        # Count views
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='view'")
        view_count = cursor.fetchone()[0]
        ok(f"Views: {view_count}")

        conn.close()
    except Exception as e:
        fail(f"Database error: {e}")
        failures.append("database_error")

    return failures


def check_imports() -> list[str]:
    """Check critical imports work."""
    header("Module Imports")
    failures = []

    modules = [
        ("lib.intelligence.engine", "generate_intelligence_snapshot"),
        ("lib.intelligence.scoring", "score_dimension"),
        ("lib.intelligence.signals", "detect_all_signals"),
        ("lib.intelligence.patterns", "detect_all_patterns"),
        ("lib.query_engine", "QueryEngine"),
        ("api.auth", "require_auth"),
    ]

    for module_path, attr in modules:
        try:
            module = __import__(module_path, fromlist=[attr])
            getattr(module, attr)
            ok(f"{module_path}.{attr}")
        except Exception as e:
            fail(f"{module_path}.{attr}: {e}")
            failures.append(f"import_{module_path}")

    return failures


def check_pipeline() -> list[str]:
    """Check intelligence pipeline runs."""
    header("Intelligence Pipeline")
    failures = []

    try:
        from lib.intelligence.engine import generate_intelligence_snapshot

        result = generate_intelligence_snapshot()

        if result.get("pipeline_success", True):  # Older versions may not have this field
            ok("Pipeline executed successfully")
            scores = result.get("scores", result.get("scoring", {}))
            signals = result.get("signals", [])
            patterns = result.get("patterns", [])
            ok(f"  Scores: {len(scores) if isinstance(scores, dict) else 0} entities")
            ok(f"  Signals: {len(signals)} detected")
            ok(f"  Patterns: {len(patterns)} detected")
        else:
            fail("Pipeline execution failed")
            if result.get("pipeline_errors"):
                for err in result["pipeline_errors"]:
                    fail(f"  {err}")
            failures.append("pipeline_failed")

    except Exception as e:
        fail(f"Pipeline error: {e}")
        failures.append("pipeline_exception")

    return failures


def check_api(api_url: str, token: str | None) -> list[str]:
    """Check API endpoints respond correctly."""
    header("API Endpoints")
    failures = []

    try:
        import urllib.request
        import urllib.error
        import json

        def check_endpoint(path: str, expected_status: int, use_auth: bool = False) -> bool:
            url = f"{api_url}{path}"
            req = urllib.request.Request(url)

            if use_auth and token:
                req.add_header("Authorization", f"Bearer {token}")

            try:
                response = urllib.request.urlopen(req, timeout=10)
                status = response.getcode()
                if status == expected_status:
                    ok(f"{path} → {status}")
                    return True
                else:
                    fail(f"{path} → {status} (expected {expected_status})")
                    return False
            except urllib.error.HTTPError as e:
                if e.code == expected_status:
                    ok(f"{path} → {e.code}")
                    return True
                else:
                    fail(f"{path} → {e.code} (expected {expected_status})")
                    return False
            except Exception as e:
                fail(f"{path} → error: {e}")
                return False

        # Health check
        if not check_endpoint("/api/health", 200):
            failures.append("api_health")

        # Intelligence endpoints (require auth if token set)
        if token:
            if not check_endpoint("/api/v2/intelligence/portfolio/overview", 200, use_auth=True):
                failures.append("api_intel_auth")

            # Without token should fail
            if os.environ.get("INTEL_API_TOKEN"):
                if not check_endpoint("/api/v2/intelligence/portfolio/overview", 401, use_auth=False):
                    warn("Auth not enforced for intelligence endpoints!")

        # Stub endpoint should return 501
        req = urllib.request.Request(f"{api_url}/api/tasks/link", method="POST")
        try:
            urllib.request.urlopen(req, timeout=10)
            fail("POST /api/tasks/link → 200 (expected 501)")
            failures.append("stub_endpoint")
        except urllib.error.HTTPError as e:
            if e.code == 501:
                ok(f"POST /api/tasks/link → 501 (correctly not implemented)")
            else:
                fail(f"POST /api/tasks/link → {e.code} (expected 501)")
                failures.append("stub_endpoint")

    except ImportError:
        warn("Skipping API checks (urllib not available)")
    except Exception as e:
        fail(f"API check error: {e}")
        failures.append("api_error")

    return failures


def check_ui() -> list[str]:
    """Check UI build exists."""
    header("UI Build")
    failures = []

    ui_dist = PROJECT_ROOT / "time-os-ui" / "dist"

    if ui_dist.exists():
        ok(f"UI dist exists: {ui_dist}")

        # Check bundle size
        js_files = list(ui_dist.glob("**/*.js"))
        total_js = sum(f.stat().st_size for f in js_files)
        total_kb = total_js / 1024

        if total_kb < 600:
            ok(f"JS bundle size: {total_kb:.0f}KB")
        else:
            warn(f"JS bundle size: {total_kb:.0f}KB (consider optimizing)")
    else:
        fail(f"UI dist not found: {ui_dist}")
        failures.append("ui_missing")

    return failures


def main():
    parser = argparse.ArgumentParser(description="Verify production readiness")
    parser.add_argument("--api-url", default="http://localhost:8420", help="API base URL")
    parser.add_argument("--token", default=os.environ.get("INTEL_API_TOKEN"), help="API token")
    parser.add_argument("--skip-api", action="store_true", help="Skip API checks")
    args = parser.parse_args()

    print(f"{Colors.BOLD}MOH TIME OS - Production Readiness Check{Colors.RESET}")
    print("=" * 50)

    all_failures = []

    all_failures.extend(check_env_vars())
    all_failures.extend(check_database())
    all_failures.extend(check_imports())
    all_failures.extend(check_pipeline())

    if not args.skip_api:
        all_failures.extend(check_api(args.api_url, args.token))
    else:
        warn("Skipping API checks (--skip-api)")

    all_failures.extend(check_ui())

    # Summary
    header("Summary")
    if all_failures:
        fail(f"{len(all_failures)} check(s) failed: {', '.join(all_failures)}")
        print(f"\n{Colors.RED}❌ NOT READY FOR PRODUCTION{Colors.RESET}")
        sys.exit(1)
    else:
        ok("All checks passed")
        print(f"\n{Colors.GREEN}✅ READY FOR PRODUCTION{Colors.RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
