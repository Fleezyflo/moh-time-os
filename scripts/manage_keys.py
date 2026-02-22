#!/usr/bin/env python
"""
CLI for managing MOH Time OS API keys.

Usage:
    python scripts/manage_keys.py create --name "Dashboard" --role viewer [--expires-in 90d]
    python scripts/manage_keys.py list
    python scripts/manage_keys.py revoke --key-id <id>
    python scripts/manage_keys.py rotate --key-id <id>

Examples:
    # Create a viewer key that expires in 90 days
    python scripts/manage_keys.py create --name "Dashboard" --role viewer --expires-in 90

    # List all active keys
    python scripts/manage_keys.py list

    # Revoke a key
    python scripts/manage_keys.py revoke --key-id key_abc123def456

    # Rotate a key (creates new, revokes old)
    python scripts/manage_keys.py rotate --key-id key_abc123def456 --expires-in 180
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import store
from lib.security import KeyManager, KeyRole

log = logging.getLogger(__name__)


def _setup_logging() -> None:
    """Configure logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def _parse_expires_in(expires_str: str) -> int:
    """Parse expires-in argument (e.g., '90d' -> 90)."""
    if not expires_str:
        return 0

    # Simple parser: just strip 'd' and convert to int
    if expires_str.endswith("d"):
        try:
            return int(expires_str[:-1])
        except ValueError:
            raise ValueError(f"Invalid expires-in format: {expires_str}")

    try:
        return int(expires_str)
    except ValueError:
        raise ValueError(f"Invalid expires-in format: {expires_str}")


def cmd_create(args) -> int:
    """Create a new API key."""
    try:
        expires_in_days = None
        if args.expires_in:
            expires_in_days = _parse_expires_in(args.expires_in)

        role = KeyRole[args.role.upper()]

        manager = KeyManager()
        key, key_info = manager.create_key(
            name=args.name,
            role=role,
            expires_in_days=expires_in_days,
            created_by="cli",
        )

        # Print the key ONCE (only time it's visible)
        print("\n" + "=" * 70)
        print("API KEY CREATED - SAVE THIS NOW")
        print("=" * 70)
        print(f"Key ID:       {key_info.id}")
        print(f"Name:         {key_info.name}")
        print(f"Role:         {key_info.role.value}")
        print(f"Created:      {key_info.created_at}")
        if key_info.expires_at:
            print(f"Expires:      {key_info.expires_at}")
        print("\nAPI Key (save in a secure location):")
        print(f"  {key}")
        print("=" * 70)
        print("\nWarning: This key will not be displayed again!")
        print("=" * 70 + "\n")

        return 0

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        log.error(f"Failed to create key: {e}")
        print(f"Error: Failed to create API key: {e}", file=sys.stderr)
        return 1


def cmd_list(args) -> int:
    """List all API keys."""
    try:
        manager = KeyManager()
        keys = manager.list_keys(active_only=not args.all)

        if not keys:
            print("No API keys found.")
            return 0

        # Print header
        print("\n" + "=" * 120)
        print(
            f"{'ID':<20} {'Name':<20} {'Role':<10} {'Created':<20} {'Expires':<20} {'Status':<10} {'Last Used':<20}"
        )
        print("=" * 120)

        # Print keys
        for key in keys:
            status = "active" if key.is_active else "revoked"
            created = datetime.fromisoformat(key.created_at.replace("Z", "+00:00")).strftime(
                "%Y-%m-%d %H:%M"
            )
            expires = (
                datetime.fromisoformat(key.expires_at.replace("Z", "+00:00")).strftime(
                    "%Y-%m-%d %H:%M"
                )
                if key.expires_at
                else "never"
            )
            last_used = (
                datetime.fromisoformat(key.last_used_at.replace("Z", "+00:00")).strftime(
                    "%Y-%m-%d %H:%M"
                )
                if key.last_used_at
                else "never"
            )

            print(
                f"{key.id:<20} {key.name:<20} {key.role.value:<10} {created:<20} {expires:<20} {status:<10} {last_used:<20}"
            )

        print("=" * 120 + "\n")
        return 0

    except Exception as e:
        log.error(f"Failed to list keys: {e}")
        print(f"Error: Failed to list keys: {e}", file=sys.stderr)
        return 1


def cmd_revoke(args) -> int:
    """Revoke an API key."""
    try:
        manager = KeyManager()
        success = manager.revoke_key(args.key_id)

        if success:
            print(f"Successfully revoked key: {args.key_id}")
            return 0
        else:
            print(f"Key not found: {args.key_id}", file=sys.stderr)
            return 1

    except Exception as e:
        log.error(f"Failed to revoke key: {e}")
        print(f"Error: Failed to revoke key: {e}", file=sys.stderr)
        return 1


def cmd_rotate(args) -> int:
    """Rotate an API key (create new, revoke old)."""
    try:
        expires_in_days = None
        if args.expires_in:
            expires_in_days = _parse_expires_in(args.expires_in)

        manager = KeyManager()
        result = manager.rotate_key(
            key_id=args.key_id,
            expires_in_days=expires_in_days,
        )

        if result:
            new_key, new_key_info = result

            # Print the new key ONCE
            print("\n" + "=" * 70)
            print("API KEY ROTATED - SAVE NEW KEY NOW")
            print("=" * 70)
            print(f"Old Key ID:   {args.key_id}")
            print(f"New Key ID:   {new_key_info.id}")
            print(f"Name:         {new_key_info.name}")
            print(f"Role:         {new_key_info.role.value}")
            print(f"Created:      {new_key_info.created_at}")
            if new_key_info.expires_at:
                print(f"Expires:      {new_key_info.expires_at}")
            print("\nNew API Key (save in a secure location):")
            print(f"  {new_key}")
            print("=" * 70)
            print("\nWarning: This key will not be displayed again!")
            print("=" * 70 + "\n")

            return 0
        else:
            print(f"Key not found or rotation failed: {args.key_id}", file=sys.stderr)
            return 1

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        log.error(f"Failed to rotate key: {e}")
        print(f"Error: Failed to rotate key: {e}", file=sys.stderr)
        return 1


def main() -> int:
    """Main entry point."""
    _setup_logging()

    # Ensure database is initialized
    if not store.db_exists():
        store.init_db()

    parser = argparse.ArgumentParser(
        description="Manage MOH Time OS API keys",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    subparsers.required = True

    # Create command
    create_parser = subparsers.add_parser("create", help="Create a new API key")
    create_parser.add_argument("--name", required=True, help="Human-readable name for the key")
    create_parser.add_argument(
        "--role",
        required=True,
        choices=["viewer", "operator", "admin"],
        help="Role for the key",
    )
    create_parser.add_argument(
        "--expires-in",
        help="Days until expiration (e.g., '90d' or '90'). Omit for no expiration.",
    )
    create_parser.set_defaults(func=cmd_create)

    # List command
    list_parser = subparsers.add_parser("list", help="List all API keys")
    list_parser.add_argument(
        "--all",
        action="store_true",
        help="Include revoked keys",
    )
    list_parser.set_defaults(func=cmd_list)

    # Revoke command
    revoke_parser = subparsers.add_parser("revoke", help="Revoke an API key")
    revoke_parser.add_argument("--key-id", required=True, help="Key ID to revoke")
    revoke_parser.set_defaults(func=cmd_revoke)

    # Rotate command
    rotate_parser = subparsers.add_parser(
        "rotate", help="Rotate an API key (create new, revoke old)"
    )
    rotate_parser.add_argument("--key-id", required=True, help="Key ID to rotate")
    rotate_parser.add_argument(
        "--expires-in",
        help="Days until expiration for the new key",
    )
    rotate_parser.set_defaults(func=cmd_rotate)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
