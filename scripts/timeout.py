#!/usr/bin/env python3
"""
Portable timeout wrapper - works on macOS and Linux.

Matches GNU timeout semantics:
- Exit code 124 on timeout
- Forwards stdout/stderr in real-time
- Propagates child exit codes

Usage:
    python scripts/timeout.py <seconds> -- <command> [args...]
    python scripts/timeout.py 60 -- make ci
    python scripts/timeout.py 10 -- sleep 5  # exits 0 (completes)
    python scripts/timeout.py 2 -- sleep 10  # exits 124 (timeout)

Self-test:
    python scripts/timeout.py --self-test
"""

import argparse
import signal
import subprocess
import sys
import time
from typing import NoReturn

# GNU timeout exit code for timeout
EXIT_TIMEOUT = 124


def run_with_timeout(seconds: float, command: list[str]) -> int:
    """
    Run command with wall-clock timeout.

    Returns:
        - Command's exit code if it completes in time
        - 124 if timeout occurred (matches GNU timeout)
    """
    try:
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
        )
    except FileNotFoundError:
        print(f"timeout: {command[0]}: command not found", file=sys.stderr)
        return 127
    except PermissionError:
        print(f"timeout: {command[0]}: permission denied", file=sys.stderr)
        return 126

    start = time.monotonic()
    deadline = start + seconds

    # Use select for non-blocking reads on Unix
    import selectors

    sel = selectors.DefaultSelector()

    if proc.stdout:
        sel.register(proc.stdout, selectors.EVENT_READ)
    if proc.stderr:
        sel.register(proc.stderr, selectors.EVENT_READ)

    try:
        while proc.poll() is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                # Timeout - kill the process
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                return EXIT_TIMEOUT

            # Wait for output with timeout
            ready = sel.select(timeout=min(remaining, 0.1))
            for key, _ in ready:
                data = key.fileobj.readline()
                if data:
                    if key.fileobj == proc.stdout:
                        sys.stdout.write(data)
                        sys.stdout.flush()
                    else:
                        sys.stderr.write(data)
                        sys.stderr.flush()

        # Process completed - drain remaining output
        if proc.stdout:
            for line in proc.stdout:
                sys.stdout.write(line)
        if proc.stderr:
            for line in proc.stderr:
                sys.stderr.write(line)

        return proc.returncode or 0

    except KeyboardInterrupt:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
        return 130  # Standard exit for SIGINT

    finally:
        sel.close()


def self_test() -> int:
    """Run self-tests to verify timeout behavior."""
    print("Running timeout.py self-tests...")
    failures = 0

    # Test 1: Command completes within timeout
    print("  Test 1: Command completes within timeout...", end=" ")
    exit_code = run_with_timeout(5.0, ["python3", "-c", "print('hello')"])
    if exit_code == 0:
        print("✅ PASS")
    else:
        print(f"❌ FAIL (expected 0, got {exit_code})")
        failures += 1

    # Test 2: Command times out
    print("  Test 2: Command times out...", end=" ")
    exit_code = run_with_timeout(0.5, ["python3", "-c", "import time; time.sleep(10)"])
    if exit_code == EXIT_TIMEOUT:
        print("✅ PASS")
    else:
        print(f"❌ FAIL (expected {EXIT_TIMEOUT}, got {exit_code})")
        failures += 1

    # Test 3: Command fails with non-zero exit
    print("  Test 3: Command exits non-zero...", end=" ")
    exit_code = run_with_timeout(5.0, ["python3", "-c", "import sys; sys.exit(42)"])
    if exit_code == 42:
        print("✅ PASS")
    else:
        print(f"❌ FAIL (expected 42, got {exit_code})")
        failures += 1

    # Test 4: Command not found
    print("  Test 4: Command not found...", end=" ")
    exit_code = run_with_timeout(1.0, ["nonexistent_command_xyz"])
    if exit_code == 127:
        print("✅ PASS")
    else:
        print(f"❌ FAIL (expected 127, got {exit_code})")
        failures += 1

    if failures == 0:
        print("✅ All self-tests passed!")
        return 0
    else:
        print(f"❌ {failures} test(s) failed")
        return 1


def main() -> NoReturn:
    parser = argparse.ArgumentParser(
        description="Portable timeout wrapper (matches GNU timeout semantics)",
        usage="%(prog)s <seconds> -- <command> [args...]\n       %(prog)s --self-test",
    )
    parser.add_argument("seconds", nargs="?", type=float, help="Timeout in seconds")
    parser.add_argument("--self-test", action="store_true", help="Run self-tests")
    parser.add_argument("command", nargs="*", help="Command to run (after --)")

    # Handle -- separator
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        args_before = sys.argv[1:idx]
        command_after = sys.argv[idx + 1 :]

        if len(args_before) == 0 or args_before[0] == "--self-test":
            args = parser.parse_args(args_before)
        else:
            # Parse seconds from args_before
            try:
                seconds = float(args_before[0])
            except (ValueError, IndexError):
                parser.print_help()
                sys.exit(1)

            if not command_after:
                print("timeout: missing command", file=sys.stderr)
                sys.exit(1)

            sys.exit(run_with_timeout(seconds, command_after))
    else:
        args = parser.parse_args()

    if args.self_test:
        sys.exit(self_test())

    if args.seconds is None:
        parser.print_help()
        sys.exit(1)

    if not args.command:
        print("timeout: missing command", file=sys.stderr)
        sys.exit(1)

    sys.exit(run_with_timeout(args.seconds, args.command))


if __name__ == "__main__":
    main()
