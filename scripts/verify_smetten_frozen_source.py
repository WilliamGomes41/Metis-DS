#!/usr/bin/env python3
"""Reproduce frozen Smetten PDF provenance checks without storing the PDF.

This verifies extraction identity and reference locations. It does not assess
clinical completeness or call a semantic model.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from io import TextIOWrapper
from pathlib import Path
from zipfile import ZipFile

from src.extract_pdf_v2 import extract

DOCUMENT_ID = "console-smetten-richtlijn-smetten-1-0-62dfd76e"


def verify(pdf: Path, evidence_zip: Path, reference: Path) -> dict:
    draft = json.loads(reference.read_text(encoding="utf-8"))
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    if digest != draft["source_sha256"]:
        raise ValueError("frozen_pdf_hash_mismatch")
    rows = extract(pdf, document_id=DOCUMENT_ID, source_id="src-" + digest[:16])
    with ZipFile(evidence_zip) as archive:
        frozen = list(csv.DictReader(TextIOWrapper(
            archive.open("source_views.csv"), encoding="utf-8-sig", newline="")))
    current_by_id = {row["fragment_id"]: row["fragment_hash"] for row in rows}
    frozen_by_id = {row["fragment_id"]: row["fragment_hash"] for row in frozen}
    if current_by_id != frozen_by_id:
        raise ValueError("frozen_fragment_hash_mismatch")
    proc = subprocess.run(["pdftotext", "-layout", str(pdf), "-"],
                          text=True, capture_output=True, check=True)
    pages = proc.stdout.split("\f")
    norm = lambda s: re.sub(r"\s+", " ", s).strip().casefold()
    missing = [entry["reference_id"] for entry in draft["entries"]
               if not 1 <= entry["page"] <= len(pages)
               or norm(entry["anchor"]) not in norm(pages[entry["page"] - 1])]
    if missing:
        raise ValueError("draft_reference_anchor_not_in_pdf:" + ",".join(missing))
    return {"source_sha256": digest, "pdf_pages": len(pages) - int(not pages[-1].strip()),
            "fragment_ids_and_hashes_equal": len(rows),
            "draft_anchors_page_matched": len(draft["entries"]),
            "draft_status": draft["status"], "clinical_completeness": "not_evaluated"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--evidence-zip", required=True, type=Path)
    parser.add_argument("--reference", type=Path,
                        default=Path("docs/acceptance/smetten_reference_draft_pdf_v1.json"))
    args = parser.parse_args()
    print(json.dumps(verify(args.pdf, args.evidence_zip, args.reference),
                     ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
