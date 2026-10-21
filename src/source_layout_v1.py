"""Conservative PDF margin-line recognition and reversible derived text views."""
from __future__ import annotations

import re
from collections import defaultdict

VERSION = "source-layout-v1"


def text_view(raw: str, exclusions: list[dict]) -> dict:
    """Keep exact raw offsets; only supplied, verified layout spans are omitted."""
    removed = set()
    for exclusion in exclusions:
        start, end = exclusion["raw_start"], exclusion["raw_end"]
        if not (0 <= start < end <= len(raw)) or raw[start:end] != exclusion["text"]:
            raise ValueError("source_layout_bounds_invalid")
        removed.update(range(start, end))
    # Existing PDF cleanup removes soft hyphens and word hyphenation at line breaks.
    removed.update(i for i, ch in enumerate(raw) if ch == "\u00ad")
    for match in re.finditer(r"(?<=\w)-\n(?=\w)", raw):
        removed.update(range(match.start(), match.end()))
    chars = [(ch, i, i + 1) for i, ch in enumerate(raw) if i not in removed]
    mapped = []
    for ch, start, end in chars:
        if ch.isspace():
            if mapped and mapped[-1][0] == " ":
                if mapped[-1][2] == start:
                    mapped[-1] = (" ", mapped[-1][1], end)
            else:
                mapped.append((" ", start, end))
        else:
            mapped.append((ch, start, end))
    while mapped and mapped[0][0] == " ":
        mapped.pop(0)
    while mapped and mapped[-1][0] == " ":
        mapped.pop()
    segments = []
    for pos, (_ch, start, end) in enumerate(mapped):
        if (segments and end - start == 1
                and segments[-1]["raw_end"] == start
                and segments[-1]["raw_end"] - segments[-1]["raw_start"] == segments[-1]["end"] - segments[-1]["start"]):
            segments[-1].update(end=pos + 1, raw_end=end)
        else:
            segments.append({"start": pos, "end": pos + 1, "raw_start": start, "raw_end": end})
    return {"version": VERSION, "text": "".join(ch for ch, _, _ in mapped),
            "mapping": segments, "exclusions": exclusions}


def mark_pdf_layout(fragments: list[dict]) -> None:
    """Recognize document-wide line gutters; retain ambiguous numeric columns."""
    verified = _document_line_gutters(fragments)
    prose_by_page = defaultdict(list)
    for fragment in fragments:
        prose_by_page[fragment["source_page"]].extend(
            s for s in fragment.get("_pdf_spans", []) if re.search(r"[A-Za-zÀ-ÿ]", s["text"]))
    possible = set()
    for fragment in fragments:
        for span in fragment.get("_pdf_spans", []):
            if not re.fullmatch(r"\d+", span["text"].strip()):
                continue
            box = span["bbox"]
            page_prose = prose_by_page[fragment["source_page"]]
            if any(abs(s["bbox"][1] - box[1]) < 4 and s["bbox"][0] >= box[2] + 8
                   for s in page_prose):
                possible.add((fragment["fragment_id"], span["raw_start"]))
    for fragment in fragments:
        findings = []
        exclusions = []
        for span in fragment.pop("_pdf_spans", []):
            key = (fragment["fragment_id"], span["raw_start"])
            if key in verified:
                exclusion = {**span, "reason": "document_wide_five_line_gutter",
                             "recognition": verified[key]}
                exclusions.append(exclusion)
                findings.append(exclusion)
            elif key in possible:
                findings.append({**span, "reason": "ambiguous_margin_number_retained"})
        if findings:
            fragment["source_layout_findings"] = findings
        if exclusions:
            fragment["source_text_view"] = text_view(fragment["raw_text"], exclusions)


def mapped_raw_spans(fragment: dict, *, start: int, end: int) -> list[dict]:
    result = []
    for span in fragment.get("_raw_source_mapping", []):
        lo, hi = max(start, span["start"]), min(end, span["end"])
        if lo >= hi:
            continue
        if span.get("kind") == "join_separator":
            result.append({key: span[key] for key in
                           ("kind", "text", "left_fragment_id", "right_fragment_id")})
            continue
        exact = span["raw_end"] - span["raw_start"] == span["end"] - span["start"]
        result.append({"fragment_id": span["fragment_id"],
                       "raw_start": span["raw_start"] + lo - span["start"] if exact else span["raw_start"],
                       "raw_end": span["raw_start"] + hi - span["start"] if exact else span["raw_end"],
                       "source_page": span.get("source_page"), "bbox": span.get("bbox")})
    return result


def _document_line_gutters(fragments: list[dict]) -> dict:
    """Require document-wide sequence, outer alignment and body-line cadence.

    Short columns and local five-step tables are insufficient. Number widths
    change at 10/100/1000, so compare aligned right edges rather than left edges.
    """
    spans_by_page = defaultdict(list)
    columns = defaultdict(list)
    for fragment in fragments:
        page = fragment["source_page"]
        for span in fragment.get("_pdf_spans", []):
            spans_by_page[page].append(span)
            if re.fullmatch(r"\d+", span["text"].strip()):
                columns[round(span["bbox"][2] * 2) / 2].append(
                    (page, fragment["fragment_id"], span))
    result = {}
    for right_edge, rows in columns.items():
        rows.sort(key=lambda row: (row[0], row[2]["bbox"][1]))
        pages = {row[0] for row in rows}
        if len(rows) < 20 or len(pages) < 3:
            continue
        values = [int(row[2]["text"].strip()) for row in rows]
        if min(pages) != 1 or values[0] != 5 or any(b - a != 5 for a, b in zip(values, values[1:])):
            continue
        if any(span["bbox"][0] < right_edge + 8
               for page in pages for span in spans_by_page[page]
               if re.search(r"[A-Za-zÀ-ÿ]", span["text"])):
            continue
        intervals = []
        for left, right in zip(rows, rows[1:]):
            if left[0] != right[0]:
                continue
            ys = sorted(span["bbox"][1] for span in spans_by_page[left[0]]
                        if span["bbox"][0] >= right_edge + 8
                        and left[2]["bbox"][1] - 1 <= span["bbox"][1]
                        < right[2]["bbox"][1] - 1)
            baselines = []
            for y in ys:
                if not baselines or y - baselines[-1] > 1:
                    baselines.append(y)
            intervals.append(len(baselines))
        if not intervals or sum(n == 5 for n in intervals) / len(intervals) < .7:
            continue
        proof = {"classifier": "document-line-gutter-v1", "marker_count": len(rows),
                 "page_count": len(pages), "step": 5,
                 "five_line_intervals": sum(n == 5 for n in intervals),
                 "interval_count": len(intervals), "right_edge": right_edge}
        for _page, fragment_id, span in rows:
            result[(fragment_id, span["raw_start"])] = proof
    return result
