#!/usr/bin/env python3
"""Compare forensic_trace.csv with coverage, lineage and source-stage tables.

Resolvable lineage is decided only from those tables. The trace flag
lineage_resolvable is ignored.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.forensic_trace_v1 import (
    _csv_row, _read_csv, independent_source_lineage_acceptance, load_evidence, trace, write_outputs,
)


def _tables(path: Path) -> dict[str, list[dict]]:
    with ZipFile(path) as archive:
        return {
            "trace_rows": _read_csv(archive, "forensic_trace.csv"),
            "coverage_rows": _read_csv(archive, "coverage.csv"),
            "lineage_rows": _read_csv(archive, "lineage.csv"),
            "stage_rows": _read_csv(archive, "source_stages.csv"),
            "view_rows": _read_csv(archive, "source_views.csv"),
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path, help="processing-evidence ZIP")
    parser.add_argument("--output", type=Path, help="directory for the reprojected trace")
    args = parser.parse_args(argv)
    stored = _tables(args.evidence)
    before = independent_source_lineage_acceptance(**stored)
    evidence = load_evidence(args.evidence)
    result = trace(evidence)
    if args.output:
        write_outputs(result, args.output)
    after_rows = [_csv_row(record, result["summary"]["trace_evidence_status"]) for record in result["records"]]
    after = independent_source_lineage_acceptance(
        trace_rows=after_rows,
        coverage_rows=stored["coverage_rows"],
        lineage_rows=stored["lineage_rows"],
        stage_rows=stored["stage_rows"],
        view_rows=stored["view_rows"],
    )
    print(json.dumps({"stored_trace": before, "reprojected_trace": after}, ensure_ascii=False, indent=2, sort_keys=True))
    failed = (
        after["selected_candidates_missing_trace"]
        or after["selected_candidates_with_resolvable_lineage_and_unknown_source_span"]
        or after["selected_candidates_with_resolvable_lineage_and_unknown_source_text"]
        or after["projected_source_text_mismatch"]
        or after["projected_source_range_mismatch"]
        or after["selected_remainder_cross_contamination"]
        or after["lineage_conflicts"]
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
