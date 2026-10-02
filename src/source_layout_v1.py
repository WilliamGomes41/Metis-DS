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
    """Only repeated five-line markers in a separate left margin are excluded.

    Require three increasing markers beside prose and five actual lines per step.
    Single numbers, clinical inline spans, lists and ambiguous columns remain.
    """
    groups = defaultdict(list)
    prose_by_page = defaultdict(list)
    for fragment in fragments:
        prose_by_page[fragment["source_page"]].extend(
            s for s in fragment.get("_pdf_spans", []) if re.search(r"[A-Za-zÀ-ÿ]", s["text"]))
    for fragment in fragments:
        spans = fragment.get("_pdf_spans", [])
        for span in spans:
            if not re.fullmatch(r"\d+", span["text"].strip()):
                continue
            value = int(span["text"])
            box = span["bbox"]
            page_prose = prose_by_page[fragment["source_page"]]
            peers = [s for s in page_prose
                     if abs(s["bbox"][1] - box[1]) < 4 and s["bbox"][0] >= box[2] + 8]
            if peers and value >= 20 and value % 5 == 0 and box[2] + 8 <= min(s["bbox"][0] for s in page_prose):
                groups[round(box[0] / 4)].append((fragment, span, value))
    accepted = set()
    possible = {(row[0]["fragment_id"], row[1]["raw_start"]) for rows in groups.values() for row in rows}
    for candidates in groups.values():
        candidates.sort(key=lambda row: (row[0]["source_page"], row[1]["bbox"][1]))
        values = [row[2] for row in candidates]
        def five_lines_between(left, right):
            if left[0]["source_page"] != right[0]["source_page"]:
                return False  # Page boundaries remain ambiguous without a global line model.
            lo, hi = left[1]["bbox"][1], right[1]["bbox"][1]
            lines = {round(s["bbox"][1], 1) for s in prose_by_page[left[0]["source_page"]]
                     if lo - 4 <= s["bbox"][1] < hi - 4}
            return len(lines) == 5
        if (len(values) >= 3 and all(b - a == 5 for a, b in zip(values, values[1:]))
                and all(five_lines_between(a, b) for a, b in zip(candidates, candidates[1:]))):
            accepted.update((row[0]["fragment_id"], row[1]["raw_start"]) for row in candidates)
    for fragment in fragments:
        exclusions = []
        findings = []
        for span in fragment.pop("_pdf_spans", []):
            if (fragment["fragment_id"], span["raw_start"]) in accepted:
                exclusions.append({**span, "reason": "repeated_five_line_left_margin"})
            elif (fragment["fragment_id"], span["raw_start"]) in possible:
                findings.append({**span, "reason": "ambiguous_margin_number_retained"})
        if exclusions:
            fragment["source_text_view"] = text_view(fragment["raw_text"], exclusions)
        if findings:
            fragment["source_layout_findings"] = findings


def mapped_raw_spans(fragment: dict, *, start: int, end: int) -> list[dict]:
    result = []
    for span in fragment.get("_raw_source_mapping", []):
        lo, hi = max(start, span["start"]), min(end, span["end"])
        if lo >= hi:
            continue
        exact = span["raw_end"] - span["raw_start"] == span["end"] - span["start"]
        result.append({"fragment_id": span["fragment_id"],
                       "raw_start": span["raw_start"] + lo - span["start"] if exact else span["raw_start"],
                       "raw_end": span["raw_start"] + hi - span["start"] if exact else span["raw_end"],
                       "source_page": span.get("source_page"), "bbox": span.get("bbox")})
    return result
