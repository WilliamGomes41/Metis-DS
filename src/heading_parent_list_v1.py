"""Document-body heading / parent-choice helpers.

TOC (inhoudsopgave) items are marked separately from body headings.
Parent-choice uses body headings and outline hierarchy. Invalid nearby
parents MUST NOT bind and MUST NOT be the default structure.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

_TOC_TITLES = frozenset(
    {
        "inhoudsopgave",
        "inhoud",
        "table of contents",
        "inhouds-opgave",
    }
)
_OUTLINE_RE = re.compile(r"^(\d+(?:\.\d+)*)\.?(?:\s+|$)")
_LEADER_PAGE_RE = re.compile(r"(?:[\s\.·•…]{2,})\d+\s*$")
HEADING_ROLE_TOC = "toc"
HEADING_ROLE_BODY = "body"


def heading_visible_text(obj: dict[str, Any]) -> str:
    content = obj.get("content") or {}
    return re.sub(
        r"\s+",
        " ",
        str(
            content.get("clean_text")
            or content.get("heading")
            or obj.get("clean_text")
            or obj.get("text")
            or ""
        ),
    ).strip()


def parse_outline_number(text: str) -> tuple[int, ...] | None:
    blob = re.sub(r"\s+", " ", text or "").strip()
    match = _OUTLINE_RE.match(blob)
    if not match:
        return None
    parts = tuple(int(part) for part in match.group(1).split("."))
    return parts or None


def title_without_outline(text: str) -> str:
    blob = re.sub(r"\s+", " ", text or "").strip()
    return _OUTLINE_RE.sub("", blob).strip().casefold()


def _normalize_heading_title(text: str) -> str:
    title = title_without_outline(text)
    title = _LEADER_PAGE_RE.sub("", title)
    return re.sub(r"\s+", " ", title).strip().casefold()


def _looks_like_toc_crumb(text: str) -> bool:
    blob = re.sub(r"\s+", " ", text or "").strip()
    return bool(_LEADER_PAGE_RE.search(blob))


def _heading_match_key(text: str) -> tuple[tuple[int, ...] | None, str]:
    return (parse_outline_number(text), _normalize_heading_title(text))


def is_toc_title(text: str) -> bool:
    blob = re.sub(r"\s+", " ", text or "").strip().casefold()
    return blob in _TOC_TITLES or blob.startswith("inhoudsopgave")


def is_heading_object(obj: dict[str, Any]) -> bool:
    if obj.get("object_type") == "document":
        return False
    for key in ("confirmed_object_type", "object_type", "proposed_object_type"):
        if obj.get(key) == "heading":
            return True
    return False


def _extract_index(obj: dict[str, Any], siblings: list[dict[str, Any]]) -> int:
    if obj.get("extract_index") is not None:
        try:
            return int(obj["extract_index"])
        except (TypeError, ValueError):
            pass
    try:
        return siblings.index(obj)
    except ValueError:
        for index, row in enumerate(siblings):
            if row.get("object_id") and row.get("object_id") == obj.get("object_id"):
                return index
        return 0


def _record_toc_entry(
    text: str,
    toc_outlines: set[tuple[int, ...]],
    toc_titles: set[str],
    last_outline: list[tuple[int, ...] | None],
    saw_page_suffix: list[bool],
) -> None:
    outline, title = _heading_match_key(text)
    if outline:
        toc_outlines.add(outline)
        last_outline[0] = outline
    if title:
        toc_titles.add(title)
    if _looks_like_toc_crumb(text):
        saw_page_suffix[0] = True


def _is_body_after_toc(
    text: str,
    toc_outlines: set[tuple[int, ...]],
    toc_titles: set[str],
    last_outline: tuple[int, ...] | None,
    saw_page_suffix: bool,
) -> bool:
    if _looks_like_toc_crumb(text):
        return False
    outline, title = _heading_match_key(text)
    if outline and outline in toc_outlines:
        return True
    if title and title in toc_titles:
        return True
    if saw_page_suffix:
        return True
    if outline and last_outline and outline < last_outline:
        return True
    return False


def _infer_roles(objects: list[dict[str, Any]]) -> dict[str, str]:
    headings = [row for row in objects if is_heading_object(row)]
    headings = sorted(headings, key=lambda row: _extract_index(row, objects))
    roles: dict[str, str] = {}
    in_toc = False
    toc_outlines: set[tuple[int, ...]] = set()
    toc_titles: set[str] = set()
    last_outline: list[tuple[int, ...] | None] = [None]
    saw_page_suffix = [False]
    for row in headings:
        explicit = row.get("heading_role")
        text = heading_visible_text(row)
        object_id = str(row.get("object_id") or id(row))
        if explicit in {HEADING_ROLE_TOC, HEADING_ROLE_BODY}:
            roles[object_id] = explicit
            if explicit == HEADING_ROLE_TOC or is_toc_title(text):
                in_toc = True
                _record_toc_entry(text, toc_outlines, toc_titles, last_outline, saw_page_suffix)
            elif explicit == HEADING_ROLE_BODY:
                in_toc = False
            continue
        if is_toc_title(text):
            roles[object_id] = HEADING_ROLE_TOC
            in_toc = True
            continue
        if in_toc:
            if _is_body_after_toc(
                text,
                toc_outlines,
                toc_titles,
                last_outline[0],
                saw_page_suffix[0],
            ):
                roles[object_id] = HEADING_ROLE_BODY
                in_toc = False
            else:
                roles[object_id] = HEADING_ROLE_TOC
                _record_toc_entry(text, toc_outlines, toc_titles, last_outline, saw_page_suffix)
            continue
        roles[object_id] = HEADING_ROLE_BODY
    return roles


def mark_heading_roles(objects: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [dict(row) for row in objects]
    roles = _infer_roles(rows)
    for row in rows:
        if not is_heading_object(row):
            continue
        object_id = str(row.get("object_id") or id(row))
        row["heading_role"] = roles.get(object_id) or row.get("heading_role") or HEADING_ROLE_BODY
    return rows


def heading_role(obj: dict[str, Any], siblings: Iterable[dict[str, Any]] | None = None) -> str:
    explicit = obj.get("heading_role")
    if explicit in {HEADING_ROLE_TOC, HEADING_ROLE_BODY}:
        return explicit
    marked = mark_heading_roles(siblings or [obj])
    object_id = obj.get("object_id")
    for row in marked:
        if object_id and row.get("object_id") == object_id:
            return str(row.get("heading_role") or HEADING_ROLE_BODY)
    text = heading_visible_text(obj)
    if is_toc_title(text):
        return HEADING_ROLE_TOC
    return HEADING_ROLE_BODY


def freeze_heading_anchors(objects: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """All heading source anchors, including TOC and near-duplicates."""
    return [row for row in mark_heading_roles(objects) if is_heading_object(row)]


def _dedup_key(obj: dict[str, Any]) -> tuple:
    text = heading_visible_text(obj)
    outline = parse_outline_number(text)
    title = title_without_outline(text)
    if outline:
        return ("n", outline, title)
    return ("t", title)


def _order_choice_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed = sorted(rows, key=lambda row: _extract_index(row, rows))
    out: list[dict[str, Any]] = []
    run: list[dict[str, Any]] = []

    def flush() -> None:
        run.sort(key=lambda row: parse_outline_number(heading_visible_text(row)) or ())
        out.extend(run)
        run.clear()

    for row in indexed:
        if parse_outline_number(heading_visible_text(row)):
            run.append(row)
        else:
            flush()
            out.append(row)
    flush()
    return out


def parent_choice_list(objects: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicated, hierarchically ordered body headings. TOC stays out."""
    marked = mark_heading_roles(objects)
    body = [
        row
        for row in marked
        if is_heading_object(row) and heading_role(row, marked) == HEADING_ROLE_BODY
    ]
    body.sort(key=lambda row: _extract_index(row, marked))
    seen: set[tuple] = set()
    unique: list[dict[str, Any]] = []
    for row in body:
        key = _dedup_key(row)
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return _order_choice_rows(unique)


def is_structurally_valid_parent(
    child: dict[str, Any],
    parent: dict[str, Any],
    objects: Iterable[dict[str, Any]] | None = None,
) -> bool:
    siblings = list(objects) if objects is not None else [child, parent]
    if heading_role(parent, siblings) != HEADING_ROLE_BODY:
        return False
    if heading_role(child, siblings) != HEADING_ROLE_BODY:
        return False
    child_outline = parse_outline_number(heading_visible_text(child))
    parent_outline = parse_outline_number(heading_visible_text(parent))
    if not child_outline or not parent_outline:
        return False
    if len(parent_outline) >= len(child_outline):
        return False
    return child_outline[: len(parent_outline)] == parent_outline


def default_structural_parent(
    child: dict[str, Any],
    objects: Iterable[dict[str, Any]],
) -> dict[str, Any] | None:
    marked = mark_heading_roles(objects)
    candidates = [
        row
        for row in marked
        if is_heading_object(row)
        and heading_role(row, marked) == HEADING_ROLE_BODY
        and row.get("object_id") != child.get("object_id")
        and is_structurally_valid_parent(child, row, marked)
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda row: len(parse_outline_number(heading_visible_text(row)) or ()),
    )


def parent_proposal_may_bind(
    child: dict[str, Any],
    parent: dict[str, Any],
    objects: Iterable[dict[str, Any]] | None = None,
) -> bool:
    if not is_heading_object(child) or not is_heading_object(parent):
        return True
    return is_structurally_valid_parent(child, parent, objects)
