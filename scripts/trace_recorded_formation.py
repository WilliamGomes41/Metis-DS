#!/usr/bin/env python3
"""Project a forensic trace from recorded evidence. No network, provider, or writes."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.forensic_trace_v1 import compare_traces, load_evidence, load_gold, trace, write_outputs


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path, help="processing-evidence ZIP or forensic-evidence-v1 JSON")
    parser.add_argument("--gold", type=Path, help="forensic-gold-v1 expectation file")
    parser.add_argument("--candidate", type=Path, help="second evidence file for a same-source differential")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    evidence = load_evidence(args.evidence)
    gold = load_gold(args.gold) if args.gold else None
    result = trace(evidence, gold)
    write_outputs(result, args.output)
    differential_path = args.output / "forensic_differential.json"
    if args.candidate:
        other = trace(load_evidence(args.candidate), gold)
        differential = compare_traces(result, other)
        differential_path.write_text(
            json.dumps(differential, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    else:
        differential_path.unlink(missing_ok=True)
    verdicts = result["summary"]["verdicts"] or {"ungraded": result["summary"]["span_count"]}
    print(json.dumps({"comparison": result["summary"]["comparison"], "verdicts": verdicts}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
