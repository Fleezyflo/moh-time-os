#!/usr/bin/env python3
"""
Event Replay Tool.

Reconstructs entity state from audit events.

Usage:
    python scripts/replay_events.py --entity-type client --entity-id client-001
    python scripts/replay_events.py --entity-type client --entity-id client-001 --until 2024-01-15T12:00:00Z
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.audit import AuditStore, StateReplayer


def main():
    parser = argparse.ArgumentParser(description="Replay events to reconstruct state")
    parser.add_argument("--db", type=str, help="Database path (default: main DB)")
    parser.add_argument("--entity-type", required=True, help="Entity type")
    parser.add_argument("--entity-id", required=True, help="Entity ID")
    parser.add_argument("--until", type=str, help="Replay until timestamp")
    parser.add_argument("--events", action="store_true", help="Show all events")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    # Get database path
    if args.db:
        db_path = args.db
    else:
        from lib.paths import db_path as get_db_path

        db_path = str(get_db_path())

    if not Path(db_path).exists():
        print(f"Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    store = AuditStore(conn)
    replayer = StateReplayer(store)

    if args.events:
        # Show all events
        events = store.get_events(
            entity_type=args.entity_type,
            entity_id=args.entity_id,
        )

        if args.json:
            print(
                json.dumps(
                    [
                        {
                            "event_id": e.event_id,
                            "event_type": e.event_type,
                            "timestamp": e.timestamp,
                            "payload": e.payload,
                            "request_id": e.request_id,
                            "trace_id": e.trace_id,
                        }
                        for e in events
                    ],
                    indent=2,
                )
            )
        else:
            print(f"Events for {args.entity_type}/{args.entity_id}:")
            print("-" * 60)
            for e in events:
                print(f"[{e.timestamp}] {e.event_type}")
                print(f"  Event ID: {e.event_id}")
                if e.request_id:
                    print(f"  Request: {e.request_id}")
                if e.trace_id:
                    print(f"  Trace: {e.trace_id}")
                print(f"  Payload: {json.dumps(e.payload, indent=4)}")
                print()

    else:
        # Replay to get final state
        state = replayer.replay_entity(
            entity_type=args.entity_type,
            entity_id=args.entity_id,
            until=args.until,
        )

        if args.json:
            print(json.dumps(state, indent=2))
        else:
            print(f"Reconstructed state for {args.entity_type}/{args.entity_id}")
            if args.until:
                print(f"(as of {args.until})")
            print("-" * 60)
            print(json.dumps(state, indent=2))

    conn.close()


if __name__ == "__main__":
    main()
