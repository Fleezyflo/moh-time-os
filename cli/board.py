#!/usr/bin/env python3

import argparse
import os
import sys

# Allow running as a script without installation.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from moh_time_os.engine.tasks_board import ensure_board_lists, write_board_from_collector_outputs


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--account", required=True)
    p.add_argument("--chat", default="moh_time_os/out/chat-unread-full.json")
    p.add_argument("--gmail", default="moh_time_os/out/gmail-unread-threads.json")
    p.add_argument("--calendar", default="moh_time_os/out/calendar-next-24h.json")
    p.add_argument("--throttle-ms", type=int, default=80)
    p.add_argument("--max-items", type=int, default=80)
    args = p.parse_args()

    lists = ensure_board_lists(args.account)
    res = write_board_from_collector_outputs(
        account=args.account,
        lists=lists,
        chat_json_path=args.chat,
        gmail_json_path=args.gmail,
        calendar_json_path=args.calendar,
        throttle_ms=args.throttle_ms,
        max_items=args.max_items,
    )
    print(res)


if __name__ == "__main__":
    main()
