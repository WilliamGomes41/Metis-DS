#!/usr/bin/env python3
"""Reproject a processing-evidence ZIP and check selected source lineage.

This does not mutate the snapshot. A selected candidate whose recorded coverage
lineage can be followed must not keep UNKNOWN source_span_id or source_text.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.forensic_trace_v1 import load_evidence, source_lineage_acceptance, trace, write_outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path, help="processing-evidence ZIP or forensic-evidence JSON")
    parser.add_argument("--output", type=Path, help="optional directory for the reprojected trace")
    args = parser.parse_args(argv)
    evidence = load_evidence(args.evidence)
    result = trace(evidence)
    if args.output:
        write_outputs(result, args.output)
        rows = []
        import csv
        import io
        text = (args.output / "forensic_trace.csv").read_text(encoding="utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(text)))
    else:
        from src.forensic_trace_v1 import _csv_row
        rows = [_csv_row(record, result["summary"]["trace_evidence_status"]) for record in result["records"]]
    acceptance = source_lineage_acceptance(rows)
    print(json.dumps(acceptance, ensure_ascii=False, indent=2, sort_keys=True))
    failed = (
        acceptance["selected_candidates_with_resolvable_lineage_and_unknown_source_span"]
        or acceptance["selected_candidates_with_resolvable_lineage_and_unknown_source_text"]
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
