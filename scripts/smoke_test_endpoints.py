#!/usr/bin/env python3
"""
Smoke-test every GET endpoint in MOH Time OS.

Hits each endpoint once, logs status code and first 200 chars of response.
Skips POST/PUT/DELETE/PATCH (mutations) to avoid side effects.
Uses real entity IDs found from list endpoints where possible.

Usage:
    python scripts/smoke_test_endpoints.py [--base http://localhost:8420] [--out smoke_results.json]

Output: JSON file with every result, plus a summary at the end.
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)


BASE = "http://localhost:8420"

# All GET endpoints extracted from server.py, spec_router.py,
# intelligence_router.py, paginated_router.py, sse_router.py, action_router.py.
#
# {param} placeholders use PLACEHOLDER_ prefix so we can substitute real IDs.
# Endpoints with entity IDs are tested twice: once with a real ID (if found),
# once with a dummy to verify 404 handling vs 500 crash.

STATIC_GET_ENDPOINTS = [
    # server.py — no params
    "/",
    "/api/overview",
    "/api/time/blocks",
    "/api/time/summary",
    "/api/commitments",
    "/api/commitments/untracked",
    "/api/commitments/due",
    "/api/commitments/summary",
    "/api/capacity/lanes",
    "/api/capacity/utilization",
    "/api/capacity/forecast",
    "/api/capacity/debt",
    "/api/clients/health",
    "/api/clients/at-risk",
    "/api/clients/linking-stats",
    "/api/tasks",
    "/api/delegations",
    "/api/data-quality",
    "/api/team",
    "/api/calendar",
    "/api/inbox",
    "/api/decisions",
    "/api/bundles",
    "/api/bundles/rollbackable",
    "/api/bundles/summary",
    "/api/calibration",
    "/api/priorities",
    "/api/priorities/filtered",
    "/api/filters",
    "/api/priorities/advanced",
    "/api/events",
    "/api/week",
    "/api/emails",
    "/api/insights",
    "/api/anomalies",
    "/api/notifications",
    "/api/notifications/stats",
    "/api/approvals",
    "/api/governance",
    "/api/governance/history",
    "/api/sync/status",
    "/api/status",
    "/api/health",
    "/api/ready",
    "/api/debug/config",
    "/api/metrics",
    "/api/debug/db",
    "/api/summary",
    "/api/search?q=test",
    "/api/team/workload",
    "/api/priorities/grouped",
    "/api/clients",
    "/api/clients/portfolio",
    "/api/projects",
    "/api/projects/candidates",
    "/api/projects/enrolled",
    "/api/projects/detect",
    "/api/digest/weekly",
    "/api/dependencies",
    "/api/control-room/proposals",
    "/api/control-room/issues",
    "/api/control-room/watchers",
    "/api/control-room/fix-data",
    "/api/control-room/couplings",
    "/api/control-room/clients",
    "/api/control-room/team",
    "/api/control-room/health",
    "/api/command/client-health",
    "/api/command/team-load",
    "/api/command/decisions",
    "/api/command/week-strip",
    "/api/command/findings",
    "/api/command/staleness",
    "/api/command/weight-review",
    # spec_router (prefix /api/v2)
    "/api/v2/clients",
    "/api/v2/inbox",
    "/api/v2/inbox/recent",
    "/api/v2/inbox/counts",
    "/api/v2/issues",
    "/api/v2/team",
    "/api/v2/engagements",
    "/api/v2/health",
    "/api/v2/priorities",
    "/api/v2/projects",
    "/api/v2/events",
    "/api/v2/invoices",
    "/api/v2/proposals",
    "/api/v2/watchers",
    "/api/v2/couplings",
    "/api/v2/fix-data",
    "/api/v2/intelligence/critical",
    "/api/v2/intelligence/briefing",
    "/api/v2/intelligence/signals",
    "/api/v2/intelligence/signals/summary",
    "/api/v2/intelligence/signals/active",
    "/api/v2/intelligence/signals/history",
    "/api/v2/intelligence/patterns",
    "/api/v2/intelligence/patterns/catalog",
    "/api/v2/intelligence/proposals",
    "/api/v2/intelligence/scores/portfolio",
    "/api/v2/intelligence/entity/portfolio",
    "/api/v2/search?q=test",
    "/api/v2/projects/asana-context",
    "/api/v2/notifications/mutes",
    "/api/v2/notifications/analytics",
    "/api/v2/chat/analytics",
    "/api/v2/financial/detail",
    # intelligence_router (prefix /api/v2/intelligence)
    "/api/v2/intelligence/portfolio/overview",
    "/api/v2/intelligence/portfolio/risks",
    "/api/v2/intelligence/portfolio/trajectory",
    "/api/v2/intelligence/clients/compare",
    "/api/v2/intelligence/team/distribution",
    "/api/v2/intelligence/team/capacity",
    "/api/v2/intelligence/projects/health",
    "/api/v2/intelligence/financial/aging",
    "/api/v2/intelligence/snapshot",
    "/api/v2/intelligence/critical",
    "/api/v2/intelligence/briefing",
    "/api/v2/intelligence/signals",
    "/api/v2/intelligence/signals/summary",
    "/api/v2/intelligence/signals/active",
    "/api/v2/intelligence/signals/history",
    "/api/v2/intelligence/signals/export",
    "/api/v2/intelligence/signals/thresholds",
    "/api/v2/intelligence/patterns",
    "/api/v2/intelligence/patterns/catalog",
    "/api/v2/intelligence/proposals",
    "/api/v2/intelligence/scores/portfolio",
    "/api/v2/intelligence/scores/history/summary",
    "/api/v2/intelligence/entity/portfolio",
    "/api/v2/intelligence/changes",
    "/api/v2/intelligence/data-quality",
    "/api/v2/intelligence/audit-trail",
    "/api/v2/intelligence/attention-debt",
    "/api/v2/intelligence/performance",
    "/api/v2/intelligence/calibration/report",
    "/api/v2/intelligence/calibration/briefing",
    # paginated_router (prefix /api/v2/paginated)
    "/api/v2/paginated/tasks",
    "/api/v2/paginated/signals",
    "/api/v2/paginated/clients",
    "/api/v2/paginated/invoices",
    # sse_router (prefix /api/v2)
    "/api/v2/events/history",
    # action_router (prefix /api/actions)
    "/api/actions/pending",
    "/api/actions/history",
]

# Parameterized GET endpoints — will substitute real IDs at runtime
PARAMETERIZED_GET_ENDPOINTS = [
    # server.py
    ("/api/clients/{client_id}/health", "client_id"),
    ("/api/clients/{client_id}/projects", "client_id"),
    ("/api/tasks/{task_id}", "task_id"),
    ("/api/day/2026-03-10", None),  # date param, static
    ("/api/bundles/{bundle_id}", "bundle_id"),
    ("/api/data-quality/preview/ancient", None),
    ("/api/data-quality/preview/stale", None),
    ("/api/control-room/proposals/{proposal_id}", "proposal_id"),
    ("/api/control-room/evidence/client/{entity_id}", "client_id"),
    ("/api/clients/{client_id}", "client_id"),
    ("/api/projects/{project_id}", "project_id"),
    ("/api/command/client-health/{client_id}", "client_id"),
    ("/api/command/team-load/{member_name}", "member_name"),
    ("/api/command/findings/{finding_id}", "finding_id"),
    # spec_router
    ("/api/v2/clients/{client_id}", "client_id"),
    ("/api/v2/clients/{client_id}/snapshot", "client_id"),
    ("/api/v2/clients/{client_id}/invoices", "client_id"),
    ("/api/v2/clients/{client_id}/ar-aging", "client_id"),
    ("/api/v2/clients/{client_id}/signals", "client_id"),
    ("/api/v2/clients/{client_id}/team", "client_id"),
    ("/api/v2/clients/{client_id}/email-participants", "client_id"),
    ("/api/v2/clients/{client_id}/attachments", "client_id"),
    ("/api/v2/clients/{client_id}/invoice-detail", "client_id"),
    ("/api/v2/issues/{issue_id}", "issue_id"),
    ("/api/v2/engagements/{engagement_id}", "engagement_id"),
    ("/api/v2/proposals/{proposal_id}", "proposal_id"),
    ("/api/v2/evidence/client/{entity_id}", "client_id"),
    ("/api/v2/tasks/{task_id}/asana-detail", "task_id"),
    ("/api/v2/team/{person_id}/calendar-detail", "person_id"),
    # intelligence_router
    ("/api/v2/intelligence/clients/{client_id}/profile", "client_id"),
    ("/api/v2/intelligence/clients/{client_id}/tasks", "client_id"),
    ("/api/v2/intelligence/clients/{client_id}/communication", "client_id"),
    ("/api/v2/intelligence/clients/{client_id}/trajectory", "client_id"),
    ("/api/v2/intelligence/clients/{client_id}/compare", "client_id"),
    ("/api/v2/intelligence/team/{person_id}/profile", "person_id"),
    ("/api/v2/intelligence/team/{person_id}/trajectory", "person_id"),
    ("/api/v2/intelligence/projects/{project_id}/state", "project_id"),
    ("/api/v2/intelligence/scores/client/{client_id}", "client_id"),
    ("/api/v2/intelligence/scores/project/{project_id}", "project_id"),
    ("/api/v2/intelligence/scores/person/{person_id}", "person_id"),
    ("/api/v2/intelligence/entity/client/{client_id}", "client_id"),
    ("/api/v2/intelligence/entity/person/{person_id}", "person_id"),
]


def fetch(url: str, timeout: int = 120) -> tuple[int, str, float]:
    """GET a URL, return (status_code, body_preview, elapsed_seconds)."""
    start = time.time()
    try:
        resp = httpx.get(url, headers={"Accept": "application/json"}, timeout=timeout)
        body = resp.text[:300]
        return resp.status_code, body, time.time() - start
    except httpx.ConnectError as e:
        return 0, f"CONNECTION_ERROR: {e}", time.time() - start
    except httpx.TimeoutException as e:
        return 0, f"TIMEOUT: {e}", time.time() - start
    except Exception as e:
        return 0, f"ERROR: {e}", time.time() - start


def _fetch_json(base: str, path: str) -> dict | list | None:
    """GET a JSON endpoint, return parsed body or None on failure."""
    try:
        resp = httpx.get(
            f"{base}{path}",
            headers={"Accept": "application/json"},
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as exc:
        logger.debug("JSON fetch %s failed: %s", path, exc)
    return None


def _extract_first_id(data: dict | list | None, *keys: str) -> str:
    """Pull the first item's ID from a standard list response."""
    if data is None:
        return ""
    if isinstance(data, dict):
        items = data.get("data", data.get("items", []))
    else:
        items = data
    if isinstance(items, list) and items:
        first = items[0]
        for key in keys:
            val = first.get(key, "")
            if val:
                return str(val)
    return ""


def discover_ids(base: str) -> dict[str, str]:
    """Hit list endpoints to find real entity IDs for parameterized tests."""
    ids: dict[str, str] = {}

    # Client ID
    clients = _fetch_json(base, "/api/v2/clients")
    cid = _extract_first_id(clients, "client_id", "id", "gid")
    if cid:
        ids["client_id"] = cid

    # Task ID
    tasks = _fetch_json(base, "/api/tasks?limit=1")
    tid = _extract_first_id(tasks, "task_id", "id", "gid")
    if tid:
        ids["task_id"] = tid

    # Project ID
    projects = _fetch_json(base, "/api/v2/projects")
    pid = _extract_first_id(projects, "project_id", "id", "gid")
    if pid:
        ids["project_id"] = pid

    # Person ID from team
    team = _fetch_json(base, "/api/v2/team")
    person_id = _extract_first_id(team, "person_id", "id", "name")
    if person_id:
        ids["person_id"] = person_id
        # Also extract member_name
        if isinstance(team, dict):
            items = team.get("data", team.get("items", []))
        else:
            items = team if isinstance(team, list) else []
        if isinstance(items, list) and items:
            ids["member_name"] = str(items[0].get("name", person_id))

    # Issue ID
    issues = _fetch_json(base, "/api/v2/issues")
    iid = _extract_first_id(issues, "issue_id", "id")
    if iid:
        ids["issue_id"] = iid

    # Proposal ID
    proposals = _fetch_json(base, "/api/v2/proposals")
    prop_id = _extract_first_id(proposals, "proposal_id", "id")
    if prop_id:
        ids["proposal_id"] = prop_id

    # Engagement ID
    engs = _fetch_json(base, "/api/v2/engagements")
    eid = _extract_first_id(engs, "engagement_id", "id")
    if eid:
        ids["engagement_id"] = eid

    # Bundle ID
    bundles = _fetch_json(base, "/api/bundles?limit=1")
    bid = _extract_first_id(bundles, "bundle_id", "id")
    if bid:
        ids["bundle_id"] = bid

    # Finding ID
    findings = _fetch_json(base, "/api/command/findings")
    fid = _extract_first_id(findings, "finding_id", "id")
    if fid:
        ids["finding_id"] = fid

    return ids


def main():
    parser = argparse.ArgumentParser(description="Smoke-test all GET endpoints")
    parser.add_argument("--base", default=BASE, help="Base URL")
    parser.add_argument("--out", default="smoke_results.json", help="Output file")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    print("=== MOH Time OS Endpoint Smoke Test ===")
    print(f"Base: {base}")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print()

    # Phase 1: Discover real entity IDs
    print("[1/3] Discovering entity IDs from list endpoints...")
    ids = discover_ids(base)
    print(f"  Found IDs: {json.dumps(ids, indent=2)}")
    print()

    results = []
    counts = {"pass": 0, "fail_500": 0, "fail_other": 0, "error": 0, "skip": 0}

    # Phase 2: Test static endpoints
    print(f"[2/3] Testing {len(STATIC_GET_ENDPOINTS)} static GET endpoints...")
    for endpoint in STATIC_GET_ENDPOINTS:
        url = f"{base}{endpoint}"
        status, body, elapsed = fetch(url)

        is_ok = 200 <= status < 500
        is_500 = status >= 500

        if is_ok:
            counts["pass"] += 1
        elif is_500:
            counts["fail_500"] += 1
        elif status == 0:
            counts["error"] += 1
        else:
            counts["fail_other"] += 1

        result = {
            "endpoint": endpoint,
            "url": url,
            "status": status,
            "elapsed_s": round(elapsed, 2),
            "ok": is_ok,
            "body_preview": body[:200],
        }
        results.append(result)

        symbol = "✓" if is_ok else "✗"
        print(f"  {symbol} [{status:3d}] {elapsed:.1f}s {endpoint}")
        if is_500:
            # Print error detail for 500s
            print(f"         BODY: {body[:150]}")

    print()

    # Phase 3: Test parameterized endpoints
    param_endpoints_to_test = []
    for template, id_key in PARAMETERIZED_GET_ENDPOINTS:
        if id_key is None:
            # Static param (like date)
            param_endpoints_to_test.append((template, None, template))
        elif id_key in ids:
            real_url = template.replace(f"{{{id_key}}}", ids[id_key])
            param_endpoints_to_test.append((template, id_key, real_url))
        else:
            # Use dummy ID to check for 500 vs 404
            dummy_url = template.replace(f"{{{id_key}}}", "SMOKE_TEST_DUMMY_ID")
            param_endpoints_to_test.append((template, id_key, dummy_url))

    print(f"[3/3] Testing {len(param_endpoints_to_test)} parameterized GET endpoints...")
    for template, id_key, resolved in param_endpoints_to_test:
        url = f"{base}{resolved}"
        status, body, elapsed = fetch(url)

        # For parameterized: 404 with dummy ID is acceptable
        using_dummy = id_key and id_key not in ids
        is_ok = 200 <= status < 500
        is_500 = status >= 500

        if is_ok:
            counts["pass"] += 1
        elif is_500:
            counts["fail_500"] += 1
        elif status == 0:
            counts["error"] += 1
        else:
            counts["fail_other"] += 1

        result = {
            "endpoint": template,
            "resolved_url": resolved,
            "id_key": id_key,
            "id_value": ids.get(id_key, "SMOKE_TEST_DUMMY_ID") if id_key else None,
            "using_dummy": using_dummy,
            "status": status,
            "elapsed_s": round(elapsed, 2),
            "ok": is_ok,
            "body_preview": body[:200],
        }
        results.append(result)

        dummy_note = " (dummy ID)" if using_dummy else ""
        symbol = "✓" if is_ok else "✗"
        print(f"  {symbol} [{status:3d}] {elapsed:.1f}s {resolved}{dummy_note}")
        if is_500:
            print(f"         BODY: {body[:150]}")

    # Summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    total = len(results)
    print(f"  Total endpoints tested: {total}")
    print(f"  ✓ Passed (2xx-4xx):     {counts['pass']}")
    print(f"  ✗ Server errors (5xx):  {counts['fail_500']}")
    print(f"  ✗ Client errors:        {counts['fail_other']}")
    print(f"  ✗ Connection errors:    {counts['error']}")
    print()

    if counts["fail_500"] > 0:
        print("FAILING ENDPOINTS (500):")
        for r in results:
            if r["status"] >= 500:
                print(f"  {r['status']} {r.get('resolved_url', r['endpoint'])}")
                print(f"       {r['body_preview'][:120]}")
        print()

    # Write full results
    output = {
        "test_time": datetime.now(timezone.utc).isoformat(),
        "base_url": base,
        "discovered_ids": ids,
        "summary": {
            "total": total,
            "passed": counts["pass"],
            "server_errors_500": counts["fail_500"],
            "client_errors": counts["fail_other"],
            "connection_errors": counts["error"],
        },
        "results": results,
    }

    with open(args.out, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Full results written to: {args.out}")
    print()

    # Exit code: 0 if no 500s, 1 if any 500s
    if counts["fail_500"] > 0:
        print(f"VERDICT: FAIL — {counts['fail_500']} endpoints returning 500")
        sys.exit(1)
    else:
        print(f"VERDICT: PASS — zero 500 errors across {total} endpoints")
        sys.exit(0)


if __name__ == "__main__":
    main()
