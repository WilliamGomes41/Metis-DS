"""Open the exact source passage for a knowledge object (Protocol v2.11 locators).

From every knowledge object the reviewer MUST be able to open the exact source
passage. Locators remain v2.11: PDF ``page_bbox``; HTML ``web_line_range`` on
freeze bytes that are never reserialized. Provenance-only-in-JSON is not enough.
Missing or empty source_locator fails closed.
"""
from __future__ import annotations

import re
from bisect import bisect_right
from html import unescape
from html.parser import HTMLParser
from io import BytesIO
from itertools import groupby
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


_DOCUMENT_BLOCK_TAGS = {"p", "div", "section", "article", "h1", "h2", "h3", "h4",
                        "h5", "h6", "li", "tr", "td", "th", "br", "hr", "pre"}


def document_visible_prose(freeze_bytes: bytes, content_kind: str) -> str:
    """Display the whole frozen text, without executing uploaded HTML.

    Block separators preserve readable paragraphs and table cells. This is a
    disposable display projection; source bytes and locators are untouched.
    """
    text = freeze_bytes.decode("utf-8")
    if content_kind != "html":
        return text

    class DocumentParser(_VisibleProseParser):
        blocks = _DOCUMENT_BLOCK_TAGS

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            super().handle_starttag(tag, attrs)
            if not self._skip and tag.lower() in self.blocks:
                self.parts.append("\n")

        def handle_endtag(self, tag: str) -> None:
            super().handle_endtag(tag)
            if not self._skip and tag.lower() in self.blocks:
                self.parts.append("\n")

    parser = DocumentParser()
    parser.feed(text)
    parser.close()
    return "\n".join(
        line for raw in "".join(parser.parts).splitlines()
        if (line := re.sub(r"\s+", " ", raw).strip())
    )


def _web_character_span(text: str, freeze_bytes: bytes, value: str) -> tuple[int, int]:
    """Resolve the frozen locator before making any display transformations."""
    try:
        byte_span = parse_web_byte_span(value)
        if byte_span is not None:
            start, end = byte_span
            if end > len(freeze_bytes):
                raise OpenOriginalError("unsupported_locator")
            # A locator that splits a UTF-8 character cannot identify display text.
            return len(freeze_bytes[:start].decode("utf-8")), len(freeze_bytes[:end].decode("utf-8"))
        start_line, end_line = parse_web_line_range(value)
        lines = text.splitlines(keepends=True)
        if end_line > len(lines):
            raise OpenOriginalError("unsupported_locator")
        start = sum(map(len, lines[: start_line - 1]))
        return start, start + sum(map(len, lines[start_line - 1 : end_line]))
    except (ValueError, UnicodeError) as exc:
        raise OpenOriginalError("unsupported_locator") from exc


def _html_locator_blocks(source: str) -> list[dict[str, Any]]:
    """Reuse the default-root extractor's ordinal and chrome-skipping rules."""
    from src.extract_html_v1 import VisibleHTMLParser

    # Path.read_text, used by extract_html, normalises CRLF/CR. Keep a mapping
    # back to the untouched freeze for the character positions recorded below.
    removed = [match.start() + 1 - index for index, match in enumerate(re.finditer("\r\n", source))]
    text = source.replace("\r\n", "\n").replace("\r", "\n")
    line_starts = [0] + [match.end() for match in re.finditer("\n", text)]

    def source_position(position: int) -> int:
        return position + bisect_right(removed, position)

    class LocatedBlocksParser(VisibleHTMLParser):
        def _position(self) -> int:
            line, column = self.getpos()
            return line_starts[line - 1] + column

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            previous = self.current
            super().handle_starttag(tag, attrs)
            if self.current is not None and self.current is not previous:
                self.current["source_start"] = source_position(self._position())

        def handle_endtag(self, tag: str) -> None:
            previous_count = len(self.blocks)
            super().handle_endtag(tag)
            if len(self.blocks) > previous_count:
                self.blocks[-1]["source_end"] = source_position(text.index(">", self._position()) + 1)

    parser = LocatedBlocksParser()
    parser.feed(text)  # Match extract_html: incomplete final blocks are not emitted.
    return parser.blocks


def _html_ordinal_span(value: str, blocks: list[dict[str, Any]]) -> tuple[int, int] | None:
    """An unresolved ordinal must never fall back to marking its entire line."""
    match = re.fullmatch(r"lines:\d+(?:-\d+)?;(h[1-6]|p|li):([1-9]\d*)", value)
    if match is None:
        return None
    tag, ordinal = match.groups()
    start_line, end_line = parse_web_line_range(value)
    matches = [block for block in blocks if (
        block["tag"] == tag and block["ordinal"] == int(ordinal)
        and block["start_line"] == start_line and block["end_line"] == end_line
    )]
    if len(matches) != 1:
        return None
    return matches[0]["source_start"], matches[0]["source_end"]


def _source_segments(
    text: str, spans: list[tuple[int, int]], offset: int = 0
) -> list[tuple[str, bool]]:
    """Split text against ordered, disjoint source ranges without duplicating it."""
    segments: list[tuple[str, bool]] = []
    cursor = 0
    for start, end in spans:
        if end <= offset:
            continue
        if start >= offset + len(text):
            break
        start, end = max(0, start - offset), min(len(text), end - offset)
        if start > cursor:
            segments.append((text[cursor:start], False))
        segments.append((text[start:end], True))
        cursor = end
    if cursor < len(text):
        segments.append((text[cursor:], False))
    return segments


class _LocatedDocumentParser(_VisibleProseParser):
    """Plain-text projection with source positions, including entity provenance."""

    blocks = _DOCUMENT_BLOCK_TAGS

    def __init__(self, source: str, spans: list[tuple[int, int]]) -> None:
        super().__init__()
        self.convert_charrefs = False
        self.source = source
        self.spans = spans
        self.line_starts = [0] + [m.end() for m in re.finditer("\n", source)]
        self.segments: list[tuple[str, bool]] = []

    def _position(self) -> int:
        line, column = self.getpos()
        return self.line_starts[line - 1] + column

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        super().handle_starttag(tag, attrs)
        if not self._skip and tag.lower() in self.blocks:
            self.segments.append(("\n", False))

    def handle_endtag(self, tag: str) -> None:
        super().handle_endtag(tag)
        if not self._skip and tag.lower() in self.blocks:
            self.segments.append(("\n", False))

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        position = self._position()
        if self.source[position : position + len(data)] != data:
            raise OpenOriginalError("unsupported_locator")
        self.segments.extend(_source_segments(data, self.spans, position))

    def _reference(self, prefix: str, name: str) -> None:
        if self._skip:
            return
        position = self._position()
        raw = prefix + name
        if self.source[position + len(raw) : position + len(raw) + 1] == ";":
            raw += ";"
        # A rendered entity is atomic: selecting only part of its spelling must
        # not claim that the complete displayed character was selected.
        marked = any(start <= position and position + len(raw) <= end for start, end in self.spans)
        self.segments.append((unescape(raw), marked))

    def handle_entityref(self, name: str) -> None:
        self._reference("&", name)

    def handle_charref(self, name: str) -> None:
        self._reference("&#", name)


def _normalise_document_segments(parts: list[tuple[str, bool]]) -> list[tuple[str, bool]]:
    """Apply document_visible_prose whitespace rules without losing provenance."""
    text = "".join(part for part, _ in parts)
    marks = b"".join(bytes([marked]) * len(part) for part, marked in parts)
    result: list[tuple[str, bool]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        previous_end = None
        for word in re.finditer(r"\S+", line):
            start, end = offset + word.start(), offset + word.end()
            if previous_end is None:
                if result:
                    result.append(("\n", False))
            else:
                result.append((" ", any(marks[previous_end:start])))
            for run in re.finditer(b"\x00+|\x01+", marks[start:end]):
                result.append((text[start + run.start() : start + run.end()], bool(run[0][0])))
            previous_end = end
        offset += len(line)
    return [("".join(part for part, _ in group), marked)
            for marked, group in groupby(result, key=lambda item: item[1])]


def full_document_segments(
    freeze_bytes: bytes, content_kind: str, locator: dict[str, Any] | list[dict[str, Any]]
) -> list[tuple[str, bool]]:
    """Return the full plain-text document with exact source-occurrence markers.

    The bool marks visible text covered by any locator on the original freeze,
    never a string-search match. Byte ranges take precedence over line ranges.
    Original bytes remain unchanged. Callers MUST escape every returned string
    before including it in HTML, even text decoded from character references.

    Invalid or unsupported locators raise OpenOriginalError. A valid locator
    covering only hidden content, markup, or part of an entity yields no marked
    text. The same holds for malformed HTML whose projection cannot be mapped
    reliably; callers should explicitly report that it cannot be highlighted.
    """
    locators = locator if isinstance(locator, list) else [locator]
    if not locators:
        raise OpenOriginalError("source_locator_missing")
    for item in locators:
        if not isinstance(item, dict) or not isinstance(item.get("locator_value"), str) or not item["locator_value"].strip():
            raise OpenOriginalError("source_locator_missing")
        if item.get("locator_type") != "web_line_range":
            raise OpenOriginalError("unsupported_locator")
    if content_kind not in {"html", "boom", "json"}:
        raise OpenOriginalError("locator_kind_mismatch")
    try:
        text = freeze_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise OpenOriginalError("unsupported_locator") from exc
    visible = document_visible_prose(freeze_bytes, content_kind)
    spans: list[tuple[int, int]] = []
    blocks = None
    for item in locators:
        value = item["locator_value"]
        span = _web_character_span(text, freeze_bytes, value)
        if content_kind == "html" and parse_web_byte_span(value) is None and ";" in value:
            if blocks is None:
                blocks = _html_locator_blocks(text)
            span = _html_ordinal_span(value, blocks)
            if span is None:
                return [(visible, False)] if visible else []
        spans.append(span)
    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    if content_kind != "html":
        return _source_segments(text, merged)
    parser = _LocatedDocumentParser(text, merged)
    try:
        parser.feed(text)
        parser.close()
        segments = _normalise_document_segments(parser.segments)
    except OpenOriginalError:
        return [(visible, False)] if visible else []
    # Entity callbacks can tokenize malformed HTML differently from the normal
    # prose parser. Preserve the established display and fail closed on marking.
    if "".join(part for part, _ in segments) != visible:
        return [(visible, False)] if visible else []
    return segments


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
    include_locators: bool = False,
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
    opened = {
        "locator_type": locator_type,
        "locator_value": value,
        "passage": passage,
        "reserialized": False,
    }
    if include_locators:
        opened["locators"] = [{**item, "locator_type": item.get("locator_type") or locator_type}
                              for item in ordered]
    return opened
