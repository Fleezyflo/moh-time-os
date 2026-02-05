#!/usr/bin/env python3
"""Google Tasks backup + reset utilities for MOH Time OS.

- export: snapshot all tasklists + tasks (paged) to JSON
- wipe: delete all tasks in all lists (paged)
- ensure-lists: create MOH Time OS lists if missing

Notes:
- gogcli currently supports tasks list/create, but not list-delete; so "hard reset" = empty everything + create clean lists.
- This script is intentionally conservative: it backs up first.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone


def run(cmd: list[str], timeout: int = 180) -> dict:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed ({p.returncode}): {' '.join(cmd)}\n{p.stderr.strip()}")
    out = p.stdout.strip()
    return json.loads(out) if out else {}


def gog_base(account: str, *, force: bool = False) -> list[str]:
    base = ["gog", f"--account={account}", "--json", "--no-input"]
    if force:
        base.append("--force")
    return base


def list_tasklists(account: str) -> list[dict]:
    data = run(gog_base(account) + ["tasks", "lists", "list"])
    lists = data.get("tasklists") or data.get("lists") or data.get("items") or data.get("data") or []
    return lists


def list_tasks_paged(account: str, tasklist_id: str, include_completed: bool = True) -> list[dict]:
    tasks: list[dict] = []
    page = None
    while True:
        cmd = gog_base(account) + ["tasks", "list", tasklist_id, "--max=100"]
        if include_completed:
            cmd += ["--show-completed", "--show-hidden"]
        if page:
            cmd.append(f"--page={page}")
        data = run(cmd)
        chunk = data.get("tasks") or data.get("items") or data.get("data") or []
        tasks.extend(chunk)
        # gog returns Google Tasks API shape: nextPageToken is a string ("" when none)
        page = data.get("nextPageToken")
        if not page:
            break
    return tasks


def export_snapshot(account: str, out_path: str) -> None:
    lists = list_tasklists(account)
    snapshot = {
        "version": "MOHOS_TASKS_SNAPSHOT/v1",
        "account": account,
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "tasklists": [],
    }
    for tl in lists:
        tlid = tl.get("id") or tl.get("tasklistId")
        title = tl.get("title") or tl.get("name")
        if not tlid:
            continue
        tasks = list_tasks_paged(account, tlid, include_completed=True)
        snapshot["tasklists"].append({"id": tlid, "title": title, "raw": tl, "tasks": tasks})
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)


def wipe_all_tasks(account: str, throttle_ms: int = 120) -> dict:
    lists = list_tasklists(account)
    deleted = 0
    errors = []
    for tl in lists:
        tlid = tl.get("id") or tl.get("tasklistId")
        title = tl.get("title") or tl.get("name")
        if not tlid:
            continue
        tasks = list_tasks_paged(account, tlid, include_completed=True)
        for t in tasks:
            tid = t.get("id") or t.get("taskId")
            if not tid:
                continue
            cmd = gog_base(account, force=True) + ["tasks", "delete", tlid, tid]
            try:
                run(cmd)
                deleted += 1
                time.sleep(throttle_ms / 1000.0)
            except Exception as e:
                errors.append({"list": title, "tasklistId": tlid, "taskId": tid, "error": str(e)})
    return {"deleted": deleted, "errors": errors}


def ensure_lists(account: str, titles: list[str]) -> dict:
    existing = { (tl.get("title") or tl.get("name") or "").strip().lower(): tl for tl in list_tasklists(account) }
    created = []
    for title in titles:
        key = title.strip().lower()
        if key in existing:
            continue
        data = run(gog_base(account) + ["tasks", "lists", "create", title])
        created.append({"title": title, "result": data})
    return {"created": created}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--account", required=True)
    sub = p.add_subparsers(dest="cmd", required=True)

    ex = sub.add_parser("export")
    ex.add_argument("--out", required=True)

    w = sub.add_parser("wipe")
    w.add_argument("--throttle-ms", type=int, default=120)

    en = sub.add_parser("ensure-lists")
    en.add_argument("--titles", required=True, help="Comma-separated list titles")

    args = p.parse_args()

    if args.cmd == "export":
        export_snapshot(args.account, args.out)
        print(f"OK: exported to {args.out}")
        return

    if args.cmd == "wipe":
        res = wipe_all_tasks(args.account, throttle_ms=args.throttle_ms)
        print(json.dumps(res, indent=2))
        return

    if args.cmd == "ensure-lists":
        titles = [t.strip() for t in args.titles.split(",") if t.strip()]
        res = ensure_lists(args.account, titles)
        print(json.dumps(res, indent=2))
        return


if __name__ == "__main__":
    main()
