#!/usr/bin/env python3
"""
MOH TIME OS - Main entry point.
"""

import sys
from pathlib import Path

# Ensure package is in path
sys.path.insert(0, str(Path(__file__).parent))

from cli.main import main

if __name__ == '__main__':
    main()
