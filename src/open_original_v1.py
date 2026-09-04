"""Open the exact source passage for a knowledge object (Protocol v2.11 locators).

From every knowledge object the reviewer MUST be able to open the exact source
passage. Locators remain v2.11: PDF ``page_bbox``; HTML ``web_line_range`` on
freeze bytes that are never reserialized. Provenance-only-in-JSON is not enough.
Missing or empty source_locator fails closed.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from io import BytesIO
from typing import Any

from src.object_taxonomy_v1 import locator_of


class OpenOriginalError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def parse_web_line_range(locator_value: str) -> tuple[int, int]:
    # lines:4-7;p:1
    head = locator_value.split(";", 1)[0]
    if not head.startswith("lines:"):
        raise OpenOriginalError("unsupported_locator")
    span = head.split(":", 1)[1]
    start_s, _, end_s = span.partition("-")
    start = int(start_s)
    end = int(end_s or start_s)
    if start < 1 or end < start:
        raise OpenOriginalError("unsupported_locator")
    return start, end


def parse_web_byte_span(locator_value: str) -> tuple[int, int] | None:
    parts: dict[str, str] = {}
    for item in locator_value.split(";"):
        if ":" not in item:
            continue
        key, value = item.split(":", 1)
        parts[key] = value
    raw = parts.get("bytes")
    if raw is None:
        return None
    start_s, _, end_s = raw.partition("-")
    try:
        start = int(start_s)
        end = int(end_s or start_s)
    except ValueError as exc:
        raise OpenOriginalError("unsupported_locator") from exc
    if start < 0 or end <= start:
        raise OpenOriginalError("unsupported_locator")
    return start, end


def parse_page_bbox(locator_value: str) -> tuple[int, list[float]]:
    # page:1;bbox:x0,y0,x1,y1
    parts = dict(
        item.split(":", 1) for item in locator_value.split(";") if ":" in item
    )
    page = int(parts["page"])
    bbox = [float(item) for item in parts["bbox"].split(",")]
    if page < 1 or len(bbox) != 4:
        raise OpenOriginalError("unsupported_locator")
    return page, bbox


def passage_from_html_freeze(freeze_bytes: bytes, locator_value: str) -> str:
    """Read the exact freeze bytes. MUST NOT reserialize, pretty-print, or re-save."""
    span = parse_web_byte_span(locator_value)
    if span is not None:
        start, end = span
        if end > len(freeze_bytes):
            raise OpenOriginalError("unsupported_locator")
        return freeze_bytes[start:end].decode("utf-8")
    text = freeze_bytes.decode("utf-8")
    start, end = parse_web_line_range(locator_value)
    lines = text.splitlines()
    excerpt = lines[start - 1 : end]
    return "\n".join(excerpt)


class _VisibleProseParser(HTMLParser):
    """Display-only tag stripper. Locators stay on freeze bytes."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def researcher_visible_prose(passage: str) -> str:
    """Readable sentence for the researcher surface. Never tags or CSS classes."""
    text = passage or ""
    parser = _VisibleProseParser()
    parser.feed(text)
    parser.close()
    return re.sub(r"\s+", " ", "".join(parser.parts)).strip()


def passage_from_pdf_freeze(freeze_bytes: bytes, locator_value: str) -> str:
    import fitz

    page_no, bbox = parse_page_bbox(locator_value)
    doc = fitz.open(stream=BytesIO(freeze_bytes), filetype="pdf")
    try:
        page = doc[page_no - 1]
        rect = fitz.Rect(bbox)
        return page.get_text("text", clip=rect).strip()
    finally:
        doc.close()


def _fragment_locators(object_record: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not object_record:
        return []
    seen: set[tuple[str, str]] = set()
    locators: list[dict[str, Any]] = []
    bags = [object_record]
    provenance = object_record.get("provenance") or {}
    bags.append(provenance)
    nested = object_record.get("knowledge_object") or {}
    if nested:
        bags.append(nested)
        bags.append(nested.get("provenance") or {})
    for bag in bags:
        for frag in (bag.get("source_fragments") or []):
            sl = frag.get("source_locator") or {}
            key = (str(sl.get("locator_type") or ""), str(sl.get("locator_value") or "").strip())
            if not key[1] or key in seen:
                continue
            seen.add(key)
            locators.append(sl)
    return locators


def open_source_passage(
    *,
    freeze_bytes: bytes | None,
    content_kind: str,
    locator: dict[str, Any] | None,
    object_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    loc = locator if locator is not None else (locator_of(object_record or {}) if object_record else None)
    if not isinstance(loc, dict) or not str(loc.get("locator_value") or "").strip():
        raise OpenOriginalError("source_locator_missing")
    if freeze_bytes is None:
        raise OpenOriginalError("freeze_bytes_missing")
    locator_type = loc.get("locator_type")
    value = loc["locator_value"]
    extra = _fragment_locators(object_record)

    def _read(item: dict[str, Any]) -> str:
        kind = item.get("locator_type") or locator_type
        item_value = item["locator_value"]
        if kind == "web_line_range":
            if content_kind not in {"html", "boom", "json"}:
                raise OpenOriginalError("locator_kind_mismatch")
            return passage_from_html_freeze(freeze_bytes, item_value)
        if kind == "page_bbox":
            if content_kind != "pdf":
                raise OpenOriginalError("locator_kind_mismatch")
            return passage_from_pdf_freeze(freeze_bytes, item_value)
        raise OpenOriginalError("unsupported_locator")

    if locator_type not in {"web_line_range", "page_bbox"}:
        raise OpenOriginalError("unsupported_locator")
    parts: list[str] = []
    seen_parts: set[str] = set()
    ordered = [loc] + [item for item in extra if item.get("locator_value") != value]
    for item in ordered:
        piece = _read(item)
        if piece and piece not in seen_parts:
            seen_parts.add(piece)
            parts.append(piece)
    passage = "\n".join(parts) if parts else _read(loc)
    return {
        "locator_type": locator_type,
        "locator_value": value,
        "passage": passage,
        "reserialized": False,
    }
