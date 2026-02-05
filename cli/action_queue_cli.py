#!/usr/bin/env python3

import argparse
import os
import sys

# Allow running as a script without installation.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from moh_time_os.engine.action_queue import (
    build_from_calendar_next24h,
    build_from_chat_unread,
    build_from_gmail_unread_threads,
    write_operator_view,
)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--chat", default="moh_time_os/out/chat-unread-full.json")
    p.add_argument("--gmail", default="moh_time_os/out/gmail-unread-threads.json")
    p.add_argument("--calendar", default="moh_time_os/out/calendar-next-24h.json")
    p.add_argument("--out", default="moh_time_os/out/OPERATOR_QUEUE.md")
    args = p.parse_args()

    chat_items = build_from_chat_unread(args.chat)
    cal_items = build_from_calendar_next24h(args.calendar)
    gmail_items = build_from_gmail_unread_threads(args.gmail)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    write_operator_view(
        args.out,
        chat_items=chat_items,
        cal_items=cal_items,
        gmail_items=gmail_items,
        meta={"chat": args.chat, "gmail": args.gmail, "calendar": args.calendar},
    )

    print(f"OK: wrote {args.out}")


if __name__ == "__main__":
    main()
