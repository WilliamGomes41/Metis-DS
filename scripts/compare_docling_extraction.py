"""Read-only concrete comparison; human expectations are required quality input."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.docling_pdf_v1 import extract as docling
from src.extract_pdf_v2 import extract as legacy


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--expected", required=True, type=Path,
                        help="JSON list of exact, human-selected source passages")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    rows = {name: extractor(args.pdf, document_id="comparison", source_id="source")
            for name, extractor in (("legacy", legacy), ("docling", docling))}
    comparisons = []
    for expected in json.loads(args.expected.read_text()):
        comparisons.append({"expected": expected, **{name: [
            {"text": row["clean_text"], "locator": row["source_locator"]}
            for row in fragments if expected in row["clean_text"]]
            for name, fragments in rows.items()}})
    result = {"source_sha256": hashlib.sha256(args.pdf.read_bytes()).hexdigest(),
              "passages": comparisons, "docling_metrics": rows["docling"].extraction_record["metrics"],
              "exclusions": rows["docling"].extraction_record["exclusions"],
              "quality_gain": "requires human review of contents, omissions and original marking"}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if all(item["docling"] for item in comparisons) else 2


if __name__ == "__main__":
    raise SystemExit(main())
