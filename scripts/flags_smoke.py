#!/usr/bin/env python3
"""
Feature flags smoke test.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.features import is_enabled, REGISTRY

print("Registered flags:")
for d in REGISTRY.get_definitions():
    print(f"  {d['name']}: {d['current']} (default: {d['default']})")

assert is_enabled("offline_mode"), "offline_mode should be True by default"
print("✅ Feature flags working")
