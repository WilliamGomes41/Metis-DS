#!/usr/bin/env python3
"""Read-only inventory of decision trees formed under the retired structural route.

Input: one or more JSON files holding envelopes (a list, or a mapping keyed by
snapshot id), exported by an operator. Output: JSON on stdout. This script
never writes, retries or re-routes anything.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.vorming.decision_tree_experiment_v1 import legacy_route_inventory  # noqa: E402


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: decision_tree_route_inventory.py ENVELOPES.json [...]", file=sys.stderr)
        return 2
    envelopes = []
    for name in argv:
        data = json.loads(Path(name).read_text(encoding="utf-8"))
        envelopes.extend(data.values() if isinstance(data, dict) else data)
    report = legacy_route_inventory(list(envelopes))
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 1 if report["attempts_reserved_before_cutover"] else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
