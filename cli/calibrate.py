#!/usr/bin/env python3

import argparse
import os
import sys

# Allow running as a script without installation.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from moh_time_os.engine.calibration import ingest_rejections
from moh_time_os.engine.tasks_board import ensure_board_lists


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--account", required=True)
    args = p.parse_args()

    lists = ensure_board_lists(args.account)
    res = ingest_rejections(account=args.account, rejected_list_id=lists.rejected)
    print(res)


if __name__ == "__main__":
    main()
