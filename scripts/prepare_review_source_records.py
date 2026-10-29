#!/usr/bin/env python3
"""Explicitly prepare one existing immutable extraction for selective Review reads.

Uses the existing console configuration and kernel authorization. This is never
run by GET/startup. Operators supply the exact current objectset revision.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True)
    parser.add_argument('--actor', required=True)
    parser.add_argument('--expected-revision', required=True)
    args = parser.parse_args()
    from src.console_asgi import build_app
    console = build_app().state.operations_kernel
    reference = console.prepare_review_source_views(actor_id=args.actor,
        snapshot_id=args.snapshot, expected_revision=args.expected_revision)
    print(json.dumps(reference, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
