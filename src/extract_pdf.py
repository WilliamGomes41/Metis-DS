#!/usr/bin/env python3
"""V&VN Data Service - deterministic PDF extractor v0.1.

Transforms PDF text blocks into raw knowledge objects conforming to
schemas/knowledge_object.schema.json. This is intentionally conservative:
ambiguous clinical logic is marked needs_review rather than inferred.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import fitz
from jsonschema import Draft202012Validator

PARSER_VERSION = "pdf-blocks-0.1.0"


def clean_text(text: str) -> str:
    text = text.replace("\u00ad", "")
    # Repair line-break hyphenation while preserving ordinary hyphens.
    text = re.sub(r"(?<=\w)-\n(?=\w)", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def block_style(block: dict[str, Any]) -> tuple[float, bool]:
    sizes = []
    bold = False
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            if span.get("text", "").strip():
                sizes.append(float(span.get("size", 0)))
                font = str(span.get("font", "")).lower()
                bold = bold or "bold" in font or "semibold" in font
    return (max(sizes) if sizes else 0.0, bold)


def classify_block(text: str, max_size: float, bold: bool) -> str:
    t = text.strip()
    lower = t.lower()
    if not t:
        return "background"
    if lower.startswith("risicofactoren scorelijst"):
        return "score_rule"
    if t in {"DOEN", "OVERWEEG", "AFRADEN", "NIET DOEN"}:
        return "stamp"
    if max_size >= 16 or (bold and max_size >= 13 and len(t) < 120):
        return "section"
    if "•" in t or re.match(r"^(controleer|informeer|overleg|gebruik|verwijs|adviseer|overweeg)\b", lower):
        return "recommendation"
    return "background"


def iter_blocks(page: fitz.Page):
    data = page.get_text("dict")
    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        lines = []
        for line in block.get("lines", []):
            text = "".join(span.get("text", "") for span in line.get("spans", []))
            lines.append(text)
        raw = "\n".join(lines).strip()
        if not raw:
            continue
        max_size, bold = block_style(block)
        yield {
            "raw": raw,
            "clean": clean_text(raw),
            "bbox": block.get("bbox"),
            "max_size": max_size,
            "bold": bold,
        }


def build_object(*, doc_id: str, title: str, url: str, version: str | None,
                 page_no: int, sequence: int, obj_type: str, text: str,
                 section_path: list[str], heading: str | None,
                 parent_id: str | None = None) -> dict[str, Any]:
    object_id = f"{doc_id}-p{page_no:03d}-o{sequence:03d}"
    status = "needs_review" if obj_type in {"recommendation", "score_rule", "condition", "decision"} else "machine_processed"
    return {
        "object_id": object_id,
        "document_id": doc_id,
        "parent_object_id": parent_id,
        "object_type": obj_type,
        "source": {
            "title": title,
            "publisher": "V&VN",
            "source_url": url,
            "source_type": "pdf",
            "publication_date": None,
            "version": version,
            "source_page": page_no,
        },
        "structure": {
            "section_path": section_path,
            "heading": heading,
            "sequence": sequence,
        },
        "content": {
            "raw_text": text,
            "clean_text": clean_text(text),
            "context_text": " > ".join(section_path) if section_path else None,
            "target_group": ["verpleegkundige", "verzorgende", "verpleegkundig specialist"],
            "care_setting": ["eerste lijn"],
            "topic": ["osteoporose", "fractuurpreventie"],
        },
        "logic": None,
        "governance": {
            "validation_status": status,
            "validated_by": None,
            "validation_date": None,
            "valid_from": None,
            "valid_until": None,
        },
        "technical": {
            "parser_version": PARSER_VERSION,
            "chunk_method": "pdf_layout_block",
            "content_hash": hash_text(clean_text(text)),
            "embedding_model": None,
            "embedding_version": None,
        },
    }


def extract(pdf_path: Path, source_url: str, title: str, doc_id: str,
            version: str | None, pages: list[int] | None = None) -> list[dict[str, Any]]:
    doc = fitz.open(pdf_path)
    selected = pages or list(range(1, len(doc) + 1))
    objects: list[dict[str, Any]] = []
    section_stack: list[str] = []
    sequence = 0

    for page_no in selected:
        page = doc[page_no - 1]
        page_height = page.rect.height
        for b in iter_blocks(page):
            text = b["clean"]
            x0, y0, x1, y1 = b["bbox"]
            # Ignore page numbers / recurring very top whitespace-like furniture.
            if y0 > page_height - 55 and re.fullmatch(r"\d+", text):
                continue
            if text == str(page_no):
                continue

            obj_type = classify_block(text, b["max_size"], b["bold"])
            heading = None
            if obj_type == "stamp":
                continue
            if obj_type == "section":
                heading = text.replace("\n", " ").strip()
                if heading in {"DOEN", "OVERWEEG", "AFRADEN", "NIET DOEN"}:
                    continue
                # Simple v0.1 heading stack: major heading replaces stack; subheading appends.
                if b["max_size"] >= 20:
                    section_stack = [heading]
                elif b["max_size"] >= 15:
                    section_stack = section_stack[:1] + [heading] if section_stack else [heading]
                else:
                    section_stack = section_stack + [heading]
                path = section_stack.copy()
            else:
                path = section_stack.copy()

            sequence += 1
            objects.append(build_object(
                doc_id=doc_id,
                title=title,
                url=source_url,
                version=version,
                page_no=page_no,
                sequence=sequence,
                obj_type=obj_type,
                text=b["raw"],
                section_path=path,
                heading=heading,
            ))
    return objects


def validate(objects: list[dict[str, Any]], schema_path: Path) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = []
    for i, obj in enumerate(objects):
        for err in validator.iter_errors(obj):
            errors.append(f"object[{i}] {obj.get('object_id')}: {err.message}")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--schema", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--document-id", required=True)
    ap.add_argument("--version")
    ap.add_argument("--pages", help="Comma-separated 1-based pages, e.g. 15,16")
    args = ap.parse_args()

    pages = [int(x) for x in args.pages.split(",")] if args.pages else None
    objects = extract(args.pdf, args.source_url, args.title, args.document_id, args.version, pages)
    errors = validate(objects, args.schema)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for obj in objects:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    counts: dict[str, int] = {}
    statuses: dict[str, int] = {}
    for obj in objects:
        counts[obj["object_type"]] = counts.get(obj["object_type"], 0) + 1
        s = obj["governance"]["validation_status"]
        statuses[s] = statuses.get(s, 0) + 1

    report = {
        "parser_version": PARSER_VERSION,
        "input": str(args.pdf),
        "pages": pages or "all",
        "object_count": len(objects),
        "object_types": counts,
        "validation_statuses": statuses,
        "schema_valid": not errors,
        "schema_errors": errors,
        "known_limitations": [
            "Some mathematical/comparison glyphs in the PDF text layer are not extracted reliably.",
            "Clinical conditions are not inferred when the source text layer is incomplete.",
            "Tables are retained as score_rule blocks in v0.1; row-level parsing is a later step."
        ],
    }
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
