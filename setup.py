#!/usr/bin/env python3
"""
MOH TIME OS Setup - Initialize the system.
"""

import os
import sys
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent))

from lib.state_store import get_store


def main():
    print("═══════════════════════════════════════")
    print("  MOH TIME OS - Setup")
    print("═══════════════════════════════════════")
    
    # Ensure directories exist
    base = Path(__file__).parent
    dirs = [
        base / "data",
        base / "data" / "cache",
        base / "config",
    ]
    
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ {d.relative_to(base)}")
    
    # Initialize database
    print("\nInitializing database...")
    store = get_store()
    print("  ✓ Database initialized")
    
    # Check for config files
    print("\nChecking configuration...")
    config_files = ['sources.yaml', 'intelligence.yaml', 'governance.yaml']
    for cf in config_files:
        path = base / "config" / cf
        if path.exists():
            print(f"  ✓ {cf}")
        else:
            print(f"  ✗ {cf} missing")
    
    print("\n═══════════════════════════════════════")
    print("  Setup complete!")
    print("═══════════════════════════════════════")
    print("""
Next steps:

1. Run first sync:
   python -m cli.main sync

2. Run analysis:
   python -m cli.main run

3. View priorities:
   python -m cli.main priorities

4. Start API server:
   python api/server.py
""")


if __name__ == '__main__':
    main()
