#!/usr/bin/env python3
"""Reject database files from being committed."""
import sys

BLOCKED_EXTENSIONS = {".db", ".sqlite", ".sqlite3"}

files = sys.argv[1:]
blocked = [f for f in files if any(f.endswith(ext) for ext in BLOCKED_EXTENSIONS)]

if blocked:
    print("ERROR: Cannot commit database files:")
    for f in blocked:
        print(f"  - {f}")
    sys.exit(1)

sys.exit(0)
