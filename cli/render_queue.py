#!/usr/bin/env python3

import argparse
import json
import os
import sys

# Allow running as a script without installation.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from moh_time_os.engine.render_html import render_operator_html


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--chat", default="moh_time_os/out/chat-unread-full.json")
    p.add_argument("--gmail", default="moh_time_os/out/gmail-unread-threads.json")
    p.add_argument("--calendar", default="moh_time_os/out/calendar-next-24h.json")
    p.add_argument("--out", default="moh_time_os/out/queue.html")
    args = p.parse_args()

    chat = json.loads(open(args.chat, "r", encoding="utf-8").read())
    gmail = json.loads(open(args.gmail, "r", encoding="utf-8").read())
    cal = json.loads(open(args.calendar, "r", encoding="utf-8").read())

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    render_operator_html(args.out, calendar_events=cal, chat_unread=chat, gmail_threads=gmail, meta={"chat": args.chat, "gmail": args.gmail, "calendar": args.calendar})
    print(f"OK: wrote {args.out}")


if __name__ == "__main__":
    main()
