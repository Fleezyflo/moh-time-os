#!/usr/bin/env python3
"""Run UI checks (typecheck, lint, format) via pnpm."""

import subprocess
import sys
from pathlib import Path

UI_DIR = Path("time-os-ui")

COMMANDS = {
    "typecheck": ["pnpm", "run", "typecheck"],
    "lint": ["pnpm", "run", "lint"],
    "format": ["pnpm", "run", "format:check"],
}


def main() -> int:
    """Main entry point."""
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <typecheck|lint|format>")
        return 1

    check_type = sys.argv[1]

    if check_type not in COMMANDS:
        print(f"Unknown check type: {check_type}")
        print(f"Valid types: {', '.join(COMMANDS.keys())}")
        return 1

    if not UI_DIR.exists():
        # No UI directory, skip
        return 0

    cmd = COMMANDS[check_type]

    try:
        result = subprocess.run(
            cmd,
            cwd=UI_DIR,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(f"UI {check_type} failed:")
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr)
            return 1

        return 0

    except FileNotFoundError:
        print("pnpm not found. Install pnpm to run UI checks.")
        return 1
    except Exception as e:
        print(f"Error running UI {check_type}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
