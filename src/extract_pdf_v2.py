#!/usr/bin/env python3
"""Coordinate-preserving deterministic PDF extraction for Protocol v2.1."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import fitz

from src.integrity_kernel import schema_errors, stable_hash


PARSER_VERSION = "pdf-fragments-v2.2.0"
_HEADING_SIZE_TOLERANCE = 0.5
_OUTLINE_HEADING_RE = re.compile(
    r"^\s*(?P<number>\d+(?:\.\d+)*)(?:[.)])?\s+\S"
)
_TOC_HEADINGS = frozenset({"inhoud", "inhoudsopgave"})


def clean_text(text: str) -> str:
    text = text.replace("\u00ad", "")
    text = re.sub(r"(?<=\w)-\n(?=\w)", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def style(block: dict[str, Any]) -> tuple[float, bool]:
    sizes: list[float] = []
    bold = False
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            if span.get("text", "").strip():
                sizes.append(float(span.get("size", 0)))
                font = str(span.get("font", "")).lower()
                bold = bold or "bold" in font or "semibold" in font
    return (max(sizes) if sizes else 0.0, bold)


def classify(text: str, max_size: float, bold: bool) -> str:
    candidate = text.strip()
    if candidate in {"DOEN", "OVERWEEG", "AFRADEN", "NIET DOEN"}:
        return "stamp"
    if max_size >= 16 or (bold and max_size >= 13 and len(candidate) < 120):
        return "section"
    return "content"


def _outline_depth(text: str) -> int | None:
    match = _OUTLINE_HEADING_RE.match(text or "")
    if not match:
        return None
    return len(match.group("number").split("."))


def _is_toc_heading(text: str) -> bool:
    label = re.sub(r"\s+", " ", text or "").strip().casefold().rstrip(":")
    return label in _TOC_HEADINGS


def _heading_level(
    text: str,
    max_size: float,
    stack: list[tuple[int, str, float]],
) -> int:
    """Project one PDF heading onto a deterministic structural level.

    Outline numbering is stronger evidence than font size. A document title
    already on the stack shifts 1. to level 2 and 1.1 to level 3.
    Without such a title, numbered headings start at level 1.

    For unnumbered headings, equal font sizes are siblings and a smaller font
    nests below the deepest active visually larger heading.
    """

    depth = _outline_depth(text)
    if depth is not None:
        root_offset = 0
        if stack:
            root_level, root_text, _root_size = stack[0]
            root_is_document_title = (
                root_level == 1
                and _outline_depth(root_text) is None
                and not _is_toc_heading(root_text)
            )
            if root_is_document_title:
                root_offset = 1
        return min(6, depth + root_offset)

    if not stack:
        return 1

    for level, _active_text, active_size in reversed(stack):
        if abs(active_size - max_size) <= _HEADING_SIZE_TOLERANCE:
            return level

    for level, _active_text, active_size in reversed(stack):
        if active_size > max_size + _HEADING_SIZE_TOLERANCE:
            return min(6, level + 1)

    return 1


def _update_heading_stack(
    stack: list[tuple[int, str, float]],
    *,
    heading: str,
    max_size: float,
) -> list[tuple[int, str, float]]:
    level = _heading_level(heading, max_size, stack)
    kept = [item for item in stack if item[0] < level]
    kept.append((level, heading, max_size))
    return kept


def fragment_payload(x: dict[str, Any]) -> dict[str, Any]:
    return {
        key: x[key]
        for key in [
            "fragment_id",
            "document_id",
            "source_id",
            "source_page",
            "bbox",
            "source_locator",
            "raw_text",
            "clean_text",
            "section_path",
            "heading",
            "sequence",
            "parser_version",
        ]
    }


def page_bbox_locator(page_no: int, bbox: list[float]) -> dict[str, str]:
    coordinates = ",".join(f"{value:.6f}" for value in bbox)
    return {
        "locator_type": "page_bbox",
        "locator_value": f"page:{page_no};bbox:{coordinates}",
    }


def extract(
    pdf: Path,
    *,
    document_id: str,
    source_id: str,
    pages: list[int] | None = None,
) -> list[dict[str, Any]]:
    doc = fitz.open(pdf)
    selected = pages or list(range(1, len(doc) + 1))
    out: list[dict[str, Any]] = []
    stack: list[tuple[int, str, float]] = []
    seq = 0

    for page_no in selected:
        page = doc[page_no - 1]
        height = page.rect.height
        data = page.get_text("dict")
        for block in data.get("blocks", []):
            if block.get("type") != 0:
                continue

            lines = [
                "".join(span.get("text", "") for span in line.get("spans", []))
                for line in block.get("lines", [])
            ]
            raw = "\n".join(lines).strip()
            if not raw:
                continue

            cleaned = clean_text(raw)
            bbox = [float(value) for value in block.get("bbox", [0, 0, 0, 0])]
            if bbox[1] > height - 55 and re.fullmatch(r"\d+", cleaned):
                continue
            if cleaned == str(page_no):
                continue

            max_size, bold = style(block)
            kind = classify(cleaned, max_size, bold)
            heading: str | None = None
            if kind == "section":
                heading = cleaned.replace("\n", " ").strip()
                stack = _update_heading_stack(
                    stack,
                    heading=heading,
                    max_size=max_size,
                )
            path = [text for _level, text, _size in stack]

            seq += 1
            fragment_id = f"{document_id}-p{page_no:03d}-f{seq:03d}"
            row = {
                "fragment_id": fragment_id,
                "document_id": document_id,
                "source_id": source_id,
                "source_page": page_no,
                "bbox": bbox,
                "source_locator": page_bbox_locator(page_no, bbox),
                "raw_text": raw,
                "clean_text": cleaned,
                "section_path": path,
                "heading": heading,
                "sequence": seq,
                "parser_version": PARSER_VERSION,
                "fragment_hash": "0" * 64,
            }
            row["fragment_hash"] = stable_hash(fragment_payload(row))
            out.append(row)

    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--pages")
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    pages = [int(value) for value in args.pages.split(",")] if args.pages else None
    rows = extract(
        args.pdf,
        document_id=args.document_id,
        source_id=args.source_id,
        pages=pages,
    )
    errors: list[dict[str, Any]] = []
    for row in rows:
        for error in schema_errors(row, args.schema):
            errors.append({"fragment_id": row["fragment_id"], "error": error})

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )
    report = {
        "parser_version": PARSER_VERSION,
        "fragment_count": len(rows),
        "schema_valid": not errors,
        "schema_errors": errors,
        "coordinates": "captured",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
