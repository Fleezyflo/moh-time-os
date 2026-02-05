#!/usr/bin/env python3
"""
Financial Pulse CLI

Usage:
    python -m moh_time_os.cli.pulse          # Show pulse
    python -m moh_time_os.cli.pulse -v       # With invoice detail
    python -m moh_time_os.cli.pulse -c GMG   # Filter by client
    python -m moh_time_os.cli.pulse --json   # JSON output
"""

import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.financial_pulse import financial_pulse

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Financial Pulse — Who owes us money?")
    parser.add_argument("--client", "-c", help="Filter by client name")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show invoice detail")
    parser.add_argument("--json", "-j", action="store_true", help="Output JSON")
    
    args = parser.parse_args()
    
    result = financial_pulse(client_filter=args.client, verbose=args.verbose)
    
    if args.json:
        import json
        print(json.dumps(result, indent=2))
