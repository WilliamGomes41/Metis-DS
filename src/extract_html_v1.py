#!/usr/bin/env python3
"""Deterministic local HTML extractor for V&VN Data Services Protocol v2.1.

The extractor never downloads remote content. It operates on a supplied local
HTML source file, preserving exact visible text and source-neutral locators.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

PARSER_VERSION = "html-visible-text-v1.0.0"
BLOCK_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li"}
SKIP_TAGS = {"script", "style", "noscript", "svg"}


def _stable_hash(value: dict[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class VisibleHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.current: dict[str, Any] | None = None
        self.blocks: list[dict[str, Any]] = []
        self.heading_stack: list[tuple[int, str]] = []
        self.counts: dict[str, int] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in SKIP_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth or tag not in BLOCK_TAGS:
            return
        self.counts[tag] = self.counts.get(tag, 0) + 1
        line, _ = self.getpos()
        self.current = {
            "tag": tag,
            "start_line": line,
            "end_line": line,
            "parts": [],
            "ordinal": self.counts[tag],
        }

    def handle_data(self, data: str) -> None:
        if self.skip_depth or not self.current:
            return
        self.current["parts"].append(data)
        self.current["end_line"] = self.getpos()[0]

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in SKIP_TAGS and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth or not self.current or self.current["tag"] != tag:
            return
        text = _clean(" ".join(self.current["parts"]))
        block = self.current
        self.current = None
        if not text:
            return
        level = int(tag[1]) if tag.startswith("h") and len(tag) == 2 and tag[1].isdigit() else None
        if level:
            self.heading_stack = [(lvl, txt) for lvl, txt in self.heading_stack if lvl < level]
            self.heading_stack.append((level, text))
            section_path = [txt for _, txt in self.heading_stack]
            heading = text
        else:
            section_path = [txt for _, txt in self.heading_stack]
            heading = self.heading_stack[-1][1] if self.heading_stack else None
        block.update({"text": text, "section_path": section_path, "heading": heading})
        self.blocks.append(block)


def extract(html_path: Path, *, document_id: str, source_id: str) -> list[dict[str, Any]]:
    parser = VisibleHTMLParser()
    parser.feed(html_path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for seq, block in enumerate(parser.blocks, 1):
        locator = f"lines:{block['start_line']}-{block['end_line']};{block['tag']}:{block['ordinal']}"
        base = {
            "fragment_id": f"{document_id}-html-f{seq:04d}",
            "document_id": document_id,
            "source_id": source_id,
            "source_page": None,
            "bbox": None,
            "source_locator": {"locator_type": "web_line_range", "locator_value": locator},
            "raw_text": block["text"],
            "clean_text": block["text"],
            "section_path": block["section_path"],
            "heading": block["heading"],
            "sequence": seq,
            "parser_version": PARSER_VERSION,
        }
        base["fragment_hash"] = _stable_hash(base)
        rows.append(base)
    return rows


def validate(rows: list[dict[str, Any]], schema_path: Path) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors: list[str] = []
    for i, row in enumerate(rows):
        for err in validator.iter_errors(row):
            errors.append(f"row[{i}] {'.'.join(map(str, err.absolute_path))}: {err.message}")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--document-id", required=True)
    ap.add_argument("--source-id", required=True)
    ap.add_argument("--schema", type=Path, default=Path("schemas/raw_fragment.schema.v1.1.json"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    a = ap.parse_args()
    rows = extract(a.input, document_id=a.document_id, source_id=a.source_id)
    errors = validate(rows, a.schema)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
    report = {
        "status": "PASS" if rows and not errors else "BLOCKED",
        "parser_version": PARSER_VERSION,
        "input": str(a.input),
        "fragment_count": len(rows),
        "schema_errors": errors,
    }
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
