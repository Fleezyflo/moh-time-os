#!/usr/bin/env python3
"""Reject *-full.json data dumps from being committed."""
import sys

files = sys.argv[1:]
blocked = [f for f in files if f.endswith("-full.json")]

if blocked:
    print("ERROR: Cannot commit data dump files:")
    for f in blocked:
        print(f"  - {f}")
    sys.exit(1)

sys.exit(0)
