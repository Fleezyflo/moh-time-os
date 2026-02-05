#!/usr/bin/env python3
"""MOH Time OS CLI (v0.1)

Commands:
- init-db
- discover (deep config discovery)

Planned:
- ingest (collectors)
- normalize
- propose
- audit
- dry-run
"""

import argparse
import os
import sqlite3
import time
import sys

# Allow running as a script without installation.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH_DEFAULT = os.path.expanduser("~/.clawdbot/moh_time_os.sqlite")
SCHEMA_PATH = os.path.join(ROOT, "schema", "schema.sql")


def init_db(db_path: str) -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = f.read()
    con = sqlite3.connect(db_path)
    try:
        con.executescript(schema)
        con.commit()
    finally:
        con.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=DB_PATH_DEFAULT)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db")

    d = sub.add_parser("discover")
    d.add_argument("--account", required=True, help="Google account email (gog account)")
    d.add_argument("--days", type=int, default=90, help="Lookback window for discovery")
    d.add_argument("--out", default="moh_time_os/out", help="Output directory for reports")
    d.add_argument("--skip-tasks", action="store_true", help="Skip Google Tasks during discovery")
    d.add_argument("--skip-gmail", action="store_true", help="Skip Gmail during discovery")
    d.add_argument("--skip-calendar", action="store_true", help="Skip Calendar during discovery")
    d.add_argument("--skip-chat", action="store_true", help="Skip Google Chat during discovery")
    d.add_argument("--chat-max-spaces", type=int, default=200, help="Max spaces to sample for chat discovery")
    d.add_argument("--chat-pages-per-space", type=int, default=10, help="Max pages per space (50 msgs/page) for chat discovery")

    args = p.parse_args()

    if args.cmd == "init-db":
        init_db(args.db)
        print(f"OK: initialized {args.db} at {int(time.time()*1000)}")
        return

    if args.cmd == "discover":
        from moh_time_os.engine.discovery import DiscoveryConfig, run_discovery

        res = run_discovery(
            args.db,
            DiscoveryConfig(
                account=args.account,
                days=args.days,
                out_dir=args.out,
                include_gmail=not args.skip_gmail,
                include_calendar=not args.skip_calendar,
                include_tasks=not args.skip_tasks,
                include_chat=not args.skip_chat,
                chat_max_spaces=args.chat_max_spaces,
                chat_pages_per_space=args.chat_pages_per_space,
            ),
        )
        if not res.get("ok"):
            raise SystemExit(1)
        print("OK")
        print(f"report: {res['reportPath']}")
        print(f"proposal: {res['proposalPath']}")
        print(f"proposalId: {res['proposalId']}")
        return


if __name__ == "__main__":
    main()
