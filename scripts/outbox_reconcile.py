"""
Outbox Reconciliation CLI — inspect and manage side-effect outbox intents.

Usage:
    python scripts/outbox_reconcile.py status
    python scripts/outbox_reconcile.py list [--status pending|failed|fulfilled] [--handler calendar|email|...]
    python scripts/outbox_reconcile.py inspect <intent_id>
    python scripts/outbox_reconcile.py retry <intent_id>
    python scripts/outbox_reconcile.py force-fulfill <intent_id> [--external-id <id>]

Commands:
    status          Show counts by status (pending/fulfilled/failed)
    list            List intents with optional filters
    inspect         Show full details of a single intent
    retry           Reset a failed intent to pending for re-execution
    force-fulfill   Mark an intent as fulfilled (when external effect is
                    confirmed but local state was not updated)

This tool exists so an operator can:
1. See which intents are pending (not yet executed)
2. See which failed (external call error)
3. See which may have succeeded externally but failed locally
4. Re-run or force-reconcile safely
5. Confirm no duplicates will occur during repair
"""

import argparse
import json
import sys
from pathlib import Path

# Add repo root to path
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lib.outbox import SideEffectOutbox  # noqa: E402


def cmd_status(outbox: SideEffectOutbox, _args: argparse.Namespace) -> int:
    """Show outbox status summary."""
    stats = outbox.get_stats()
    print("Outbox Status")
    print("=" * 40)
    print(f"  Pending:   {stats['pending']:>6}")
    print(f"  Fulfilled: {stats['fulfilled']:>6}")
    print(f"  Failed:    {stats['failed']:>6}")
    print(f"  Total:     {stats['total']:>6}")
    print()

    if stats["pending"] > 0 or stats["failed"] > 0:
        print("Action needed:")
        if stats["pending"] > 0:
            print(
                f"  {stats['pending']} intent(s) are pending — may need execution or investigation"
            )
        if stats["failed"] > 0:
            print(f"  {stats['failed']} intent(s) failed — use 'list --status failed' to inspect")
        return 1

    print("All intents fulfilled. No action needed.")
    return 0


def cmd_list(outbox: SideEffectOutbox, args: argparse.Namespace) -> int:
    """List intents with optional filters."""
    intents = outbox.get_all_intents(
        status=args.status,
        handler=args.handler,
        limit=args.limit,
    )

    if not intents:
        print("No intents found matching filters.")
        return 0

    # Header
    print(
        f"{'ID':<24} {'Status':<10} {'Handler':<14} {'Action':<18} {'External ID':<20} {'Created'}"
    )
    print("-" * 110)

    for intent in intents:
        ext_id = intent.get("external_resource_id") or ""
        if len(ext_id) > 18:
            ext_id = ext_id[:15] + "..."
        print(
            f"{intent['id']:<24} "
            f"{intent['status']:<10} "
            f"{intent['handler']:<14} "
            f"{intent['action']:<18} "
            f"{ext_id:<20} "
            f"{intent['created_at']}"
        )

    print(f"\n{len(intents)} intent(s) shown.")
    return 0


def cmd_inspect(outbox: SideEffectOutbox, args: argparse.Namespace) -> int:
    """Show full details of a single intent."""
    intent = outbox.get_intent(args.intent_id)
    if not intent:
        print(f"Intent not found: {args.intent_id}")
        return 1

    print("Intent Details")
    print("=" * 60)
    for key, value in intent.items():
        if key == "payload":
            try:
                parsed = json.loads(value)
                print(f"  {key}: {json.dumps(parsed, indent=4)}")
            except (json.JSONDecodeError, TypeError):
                print(f"  {key}: {value}")
        else:
            print(f"  {key}: {value}")

    # Risk assessment
    print()
    if intent["status"] == "pending":
        print("Assessment: This intent was recorded but never completed.")
        print("  - The external call may not have been made (safe to retry)")
        print("  - OR the external call succeeded but mark_fulfilled was not called")
        print("    (check the external system before retrying)")
    elif intent["status"] == "failed":
        print(f"Assessment: External call failed with error: {intent.get('error', 'unknown')}")
        print("  - Use 'retry' to reset to pending for re-execution")
        print("  - Use 'force-fulfill' if external effect was actually created")
    elif intent["status"] == "fulfilled":
        ext_id = intent.get("external_resource_id", "none")
        print(f"Assessment: Fulfilled. External resource ID: {ext_id}")
        print("  - This intent will block duplicate execution on retry (safe)")

    return 0


def cmd_retry(outbox: SideEffectOutbox, args: argparse.Namespace) -> int:
    """Reset a failed intent to pending for re-execution."""
    intent = outbox.get_intent(args.intent_id)
    if not intent:
        print(f"Intent not found: {args.intent_id}")
        return 1

    if intent["status"] != "failed":
        print(f"Cannot retry: intent is '{intent['status']}', not 'failed'")
        return 1

    success = outbox.reset_failed_to_pending(args.intent_id)
    if success:
        print(f"Intent {args.intent_id} reset to pending.")
        print("It will be re-executed on next handler invocation with the same idempotency key.")
    else:
        print(f"Failed to reset intent {args.intent_id}")
        return 1
    return 0


def cmd_force_fulfill(outbox: SideEffectOutbox, args: argparse.Namespace) -> int:
    """Force-mark an intent as fulfilled."""
    intent = outbox.get_intent(args.intent_id)
    if not intent:
        print(f"Intent not found: {args.intent_id}")
        return 1

    if intent["status"] == "fulfilled":
        print(f"Intent is already fulfilled (external_id={intent.get('external_resource_id')})")
        return 0

    ext_id = args.external_id
    if not ext_id:
        print("WARNING: No --external-id provided.")
        print("This means we cannot track which external resource was created.")
        response = input("Continue anyway? [y/N] ")
        if response.lower() != "y":
            print("Aborted.")
            return 1

    success = outbox.force_fulfill(args.intent_id, external_resource_id=ext_id)
    if success:
        print(f"Intent {args.intent_id} force-fulfilled.")
        print(f"External resource ID: {ext_id or 'not set'}")
        print("Future retries with the same idempotency key will see this as fulfilled.")
    else:
        print(f"Failed to force-fulfill intent {args.intent_id}")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Outbox Reconciliation CLI — manage side-effect intents"
    )
    parser.add_argument(
        "--db",
        help="Path to database (default: auto-detect from lib.db)",
        default=None,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # status
    sub.add_parser("status", help="Show outbox status summary")

    # list
    list_p = sub.add_parser("list", help="List intents")
    list_p.add_argument("--status", choices=["pending", "fulfilled", "failed"])
    list_p.add_argument("--handler")
    list_p.add_argument("--limit", type=int, default=50)

    # inspect
    inspect_p = sub.add_parser("inspect", help="Inspect a single intent")
    inspect_p.add_argument("intent_id")

    # retry
    retry_p = sub.add_parser("retry", help="Reset failed intent to pending")
    retry_p.add_argument("intent_id")

    # force-fulfill
    ff_p = sub.add_parser("force-fulfill", help="Force-mark intent as fulfilled")
    ff_p.add_argument("intent_id")
    ff_p.add_argument("--external-id", help="External resource ID to record")

    args = parser.parse_args()
    outbox = SideEffectOutbox(db_path=args.db)

    commands = {
        "status": cmd_status,
        "list": cmd_list,
        "inspect": cmd_inspect,
        "retry": cmd_retry,
        "force-fulfill": cmd_force_fulfill,
    }

    return commands[args.command](outbox, args)


if __name__ == "__main__":
    sys.exit(main())
