#!/usr/bin/env python3
"""KO-1 (#995): count knowledge objects per derived state and per invalid combination.

Read-only. Every PostgreSQL session opens with ``default_transaction_read_only``
on, and no startup migration or reconciliation runs. Only counts are printed,
never document ids, object ids, titles or text.

    python scripts/ko_state_inventory.py --counts-only

In App Service SSH, copy the reviewed script to /tmp and use the app's interpreter:

    METIS_DIAGNOSTIC_APP_ROOT=/app python /tmp/ko_state_inventory.py --counts-only

Exit codes: 0 classified, 2 a knowledge object without a state.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("METIS_DIAGNOSTIC_APP_ROOT", Path(__file__).resolve().parents[1])).resolve()
sys.path[:0] = [str(ROOT / ".python_packages"), str(ROOT)]


def _read_only_sessions() -> None:
    options = os.environ.get("PGOPTIONS", "")
    os.environ["PGOPTIONS"] = f"{options} -c default_transaction_read_only=on".strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--counts-only", action="store_true", required=True,
                        help="required: the script only ever prints counts")
    parser.add_argument("--json", action="store_true", help="print one JSON object instead of lines")
    args = parser.parse_args()
    _read_only_sessions()

    from src.console_asgi import compose_console
    from src.review.knowledge_object_state_v1 import count_states, snapshot_ko_states

    console, _ = compose_console()
    rows = []
    documents = 0
    for envelope in console.list_envelopes():
        documents += 1
        rows.extend(snapshot_ko_states(console, envelope))
    counts = count_states(rows)
    counts["documents"] = documents
    if args.json:
        print(json.dumps(counts, sort_keys=True))
    else:
        print(f"documents={documents}")
        print(f"not_knowledge_object={counts['not_knowledge_object']}")
        for state, n in counts["states"].items():
            print(f"{state}={n}")
        for code, n in counts["invalid"].items():
            print(f"invalid.{code}={n}")
        print(f"invalid_total={counts['invalid_total']}")
        print(f"ko_state_unclassified={counts['ko_state_unclassified']}")
    return 2 if counts["ko_state_unclassified"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
