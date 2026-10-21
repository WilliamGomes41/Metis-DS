"""Deterministic source reconstruction before knowledge-object formation.

Extraction may cut one sentence at a line or paragraph boundary.  This module
repairs only a directly adjacent, grammatically evident continuation.  It does
not invent words and it keeps every original fragment id so the semantic
transform can still resolve the exact source locators.
"""
from __future__ import annotations

import re
import hashlib
import json
from contextvars import ContextVar
from functools import wraps
from copy import deepcopy
from typing import Any, Iterable

_RUN_CACHE = ContextVar("source_reconstruction_run_cache", default=None)


def with_reconstruction_cache(function):
    """Reuse identical immutable input within one operation, never across runs."""
    @wraps(function)
    def scoped(*args, **kwargs):
        if _RUN_CACHE.get() is not None:
            return function(*args, **kwargs)
        token = _RUN_CACHE.set({})
        try:
            return function(*args, **kwargs)
        finally:
            _RUN_CACHE.reset(token)
    return scoped

from src.object_taxonomy_v1 import (
    extract_object_type,
    has_terminal_sentence_boundary,
    is_continuation_fragment,
    is_kennisplatform_chrome_text,
    is_list_number_only,
    is_raw_timestamp,
    is_strength_stamp,
    normalize_visible_prose,
)


RECONSTRUCTION_VERSION = "source-reconstruction-v1.2.0"
STATUS_UNCHANGED = "unchanged"
STATUS_RECONSTRUCTED = "reconstructed"
STATUS_UNRESOLVED = "unresolved"
RULE_ADJACENT_GRAMMATICAL_CONTINUATION = "adjacent_grammatical_continuation"
_SOURCE_SPANS = "_source_reconstruction_spans"


def _fragment_text(fragment: dict[str, Any]) -> str:
    if "_raw_source_mapping" in fragment:
        return normalize_visible_prose(str(fragment.get("clean_text") or ""))
    if "source_text_view" in fragment:
        return fragment["source_text_view"]["text"]
    return normalize_visible_prose(
        str(fragment.get("clean_text") or fragment.get("raw_text") or "")
    )


def _source_fragment_ids(fragment: dict[str, Any]) -> list[str]:
    ids = list(fragment.get("source_fragment_ids") or [])
    fragment_id = fragment.get("fragment_id")
    if fragment_id and fragment_id not in ids:
        ids.append(str(fragment_id))
    return ids


def _is_boundary(fragment: dict[str, Any]) -> bool:
    text = _fragment_text(fragment)
    if not text:
        return True
    object_type, _proposal = extract_object_type(fragment)
    return bool(
        object_type == "heading"
        or is_strength_stamp(text)
        or is_kennisplatform_chrome_text(text)
        or is_list_number_only(text)
        or is_raw_timestamp(text)
    )


def _same_section(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_path = [normalize_visible_prose(str(x)) for x in left.get("section_path") or []]
    right_path = [normalize_visible_prose(str(x)) for x in right.get("section_path") or []]
    return not left_path or not right_path or left_path == right_path


def _may_join(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_text = _fragment_text(left)
    right_text = _fragment_text(right)
    if not left_text or not right_text or _is_boundary(left) or _is_boundary(right):
        return False
    if has_terminal_sentence_boundary(left_text):
        return False
    if not _same_section(left, right):
        return False
    return is_continuation_fragment(right_text)


def _merge_text(left: str, right: str) -> str:
    return re.sub(r"\s+", " ", f"{left} {right}").strip()


def _with_status(fragment: dict[str, Any], status: str) -> dict[str, Any]:
    result = deepcopy(fragment)
    source_ids = _source_fragment_ids(result)
    text = _fragment_text(result)
    result["source_fragment_ids"] = source_ids
    result[_SOURCE_SPANS] = [
        {"start": 0, "end": len(text), "source_fragment_ids": source_ids}
    ]
    from src.source_layout_v1 import text_view
    view = result.get("source_text_view")
    if view is not None and text_view(str(result["raw_text"]), view["exclusions"]) != view:
        raise ValueError("source_layout_view_invalid")
    if view is None and str(result.get("raw_text") or "").strip():
        candidate_view = text_view(str(result["raw_text"]), [])
        if candidate_view["text"] == text:
            view = candidate_view
    result["_raw_source_mapping"] = [
        {**span, "fragment_id": result["fragment_id"], "source_page": result.get("source_page"), "bbox": result.get("bbox")}
        for span in (view or {}).get("mapping", [])
    ]
    result["clean_text"] = text
    result.pop("source_text_view", None)
    result["source_reconstruction"] = {
        "version": RECONSTRUCTION_VERSION,
        "status": status,
        "source_fragment_ids": source_ids,
    }
    return result


def _mark_unresolved_if_open(fragment: dict[str, Any]) -> dict[str, Any]:
    text = _fragment_text(fragment)
    if text and not _is_boundary(fragment) and not has_terminal_sentence_boundary(text):
        fragment["source_reconstruction"]["status"] = STATUS_UNRESOLVED
    return fragment


def _join(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(left)
    merged_text = _merge_text(_fragment_text(left), _fragment_text(right))
    merged["clean_text"] = merged_text
    merged["raw_text"] = merged_text
    source_ids = list(dict.fromkeys(_source_fragment_ids(left) + _source_fragment_ids(right)))
    merged["source_fragment_ids"] = source_ids
    right_offset = len(_fragment_text(left)) + 1
    merged[_SOURCE_SPANS] = list(left.get(_SOURCE_SPANS) or []) + [
        {
            **span,
            "start": int(span["start"]) + right_offset,
            "end": int(span["end"]) + right_offset,
        }
        for span in right.get(_SOURCE_SPANS) or []
    ]
    merged["_raw_source_mapping"] = list(left.get("_raw_source_mapping") or []) + [
        {"kind": "join_separator", "text": " ", "start": right_offset - 1, "end": right_offset,
         "left_fragment_id": _source_fragment_ids(left)[-1],
         "right_fragment_id": _source_fragment_ids(right)[0]}
    ] + [
        {**span, "start": span["start"] + right_offset, "end": span["end"] + right_offset}
        for span in right.get("_raw_source_mapping") or []
    ]
    merged["source_reconstruction"] = {
        "version": RECONSTRUCTION_VERSION,
        "status": STATUS_RECONSTRUCTED,
        "rule": RULE_ADJACENT_GRAMMATICAL_CONTINUATION,
        "source_fragment_ids": source_ids,
    }
    return merged


def reconstruct_source_fragments(
    fragments: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return source blocks reconstructed before semantic splitting.

    A block remains open across multiple adjacent continuation fragments until
    it reaches terminal punctuation.  An open block without a safe continuation
    is marked ``unresolved``; the admission gate can consequently keep the
    resulting incomplete object out of content review.
    """
    fragments = list(fragments)
    cache = _RUN_CACHE.get()
    key = None
    if cache is not None:
        try:
            key = hashlib.sha256(json.dumps(fragments, sort_keys=True, ensure_ascii=False,
                                          separators=(",", ":")).encode()).hexdigest()
        except (TypeError, ValueError):
            pass  # Cache support must not redefine the source input contract.
        if key in cache:
            return deepcopy(cache[key])
    reconstructed: list[dict[str, Any]] = []
    pending: dict[str, Any] | None = None

    for raw_fragment in fragments:
        current = _with_status(raw_fragment, STATUS_UNCHANGED)
        if not _fragment_text(current):
            continue
        if pending is None:
            pending = current
            continue
        if _may_join(pending, current):
            pending = _join(pending, current)
            continue
        reconstructed.append(_mark_unresolved_if_open(pending))
        pending = current

    if pending is not None:
        reconstructed.append(_mark_unresolved_if_open(pending))
    if cache is not None and key is not None:
        if len(cache) >= 8:
            cache.pop(next(iter(cache)))
        cache[key] = deepcopy(reconstructed)
    return reconstructed


def source_fragment_ids_for_text(
    fragment: dict[str, Any],
    *,
    start: int,
    end: int,
) -> list[str]:
    """Return only original fragments overlapping a semantic text slice."""
    ids: list[str] = []
    for span in fragment.get(_SOURCE_SPANS) or []:
        if int(span["start"]) < end and int(span["end"]) > start:
            for fragment_id in span.get("source_fragment_ids") or []:
                if fragment_id and fragment_id not in ids:
                    ids.append(fragment_id)
    return ids or _source_fragment_ids(fragment)
