"""Protocol v2.21 wave A: context-aware splitter + testable reject function.

Maps Protocol v2.16 tiny-objects, Protocol v2.17 chrome, and Protocol v2.18
trailing-clause / identical-``clean_text``. Does not invent object types.
Chrome / nav / list numbers / loose labels / empty / too-short are filtered
BEFORE object creation. Stamps attach to the following advice sentence.
Trailing clauses attach to the previous meaningful sentence. Freeze bytes
and locators stay exact (derived extract only).

Minimum meaning threshold (documented, tested):

    MINIMUM_MEANING_WORDS = 3

    An inhoudelijk candidate that is not an official heading and not a
    short real definition MUST contain at least three words after ordinary
    whitespace normalisation and trailing-punctuation strip. Official
    headings (including ``Inleiding``) and short real definitions are
    explicit exceptions and MUST NOT be dropped.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from src.atomic_split_v1 import split_meaning_units
from src.object_taxonomy_v1 import (
    extract_object_type,
    is_continuation_fragment,
    is_kennisplatform_chrome_text,
    is_list_number_only,
    is_lone_trailing_word,
    is_raw_timestamp,
    is_strength_stamp,
    is_tiny_confirmable_text,
    is_truncated_sentence,
    looks_like_structural_heading,
    normalize_visible_prose,
    stamp_value,
)


MINIMUM_MEANING_WORDS = 3

REJECT_EMPTY = "empty"
REJECT_NOT_STANDALONE = "not_standalone_meaning"
REJECT_BELOW_THRESHOLD = "below_minimum_meaning_threshold"
REJECT_STAMP_ONLY = "stamp_only"
REJECT_NUMBER_ONLY = "number_only"
REJECT_NAV_ONLY = "nav_only"
REJECT_LABEL_ONLY = "label_only"
REJECT_CONTINUATION = "grammatical_continuation"
REJECT_DUPLICATE = "identical_clean_text"

KEEP_SHORT_DEFINITION = "short_real_definition"
KEEP_OFFICIAL_HEADING = "official_heading"

PRE_OBJECT_FILTER_REASONS = frozenset(
    {
        REJECT_EMPTY,
        REJECT_NAV_ONLY,
        REJECT_NUMBER_ONLY,
        REJECT_LABEL_ONLY,
        REJECT_BELOW_THRESHOLD,
        REJECT_NOT_STANDALONE,
    }
)

_SHORT_DEFINITION_CUE_RE = re.compile(
    r"\b(?:is een|is het|zijn een|zijn het|wordt genoemd|wordt omschreven|"
    r"definitie|betekent|omvat)\b",
    re.I,
)
_DEICTIC_IS_RE = re.compile(
    r"^(?:dit|deze|dat|het|er|hier|zo)\s+is\b",
    re.I,
)
_TERM_IS_RE = re.compile(
    r"^[A-ZÁÉÍÓÚÄËÏÖÜÀÈÂÊÎÔÛ][\w-]*(?:\s+[\w-]+){0,3}\s+is\s+\S",
)


@dataclass(frozen=True)
class RejectDecision:
    """Unit-testable reject outcome. ``exception`` names an explicit keep."""

    rejected: bool
    reason: str | None = None
    exception: str | None = None


def word_count(text: str) -> int:
    blob = normalize_visible_prose(text)
    blob = re.sub(r"[.!?]+$", "", blob)
    return len(blob.split()) if blob else 0


def is_official_heading_text(text: str, *, is_heading: bool = False) -> bool:
    """True for real source headings, including Inleiding. Not chrome."""
    blob = normalize_visible_prose(text)
    if not blob or is_kennisplatform_chrome_text(blob) or is_strength_stamp(blob):
        return False
    if is_heading:
        return True
    return looks_like_structural_heading(blob)


def is_short_real_definition(text: str) -> bool:
    """True for a short definition sentence that MUST NOT be dropped."""
    blob = normalize_visible_prose(text)
    if not blob:
        return False
    if is_kennisplatform_chrome_text(blob) or is_strength_stamp(blob):
        return False
    if is_list_number_only(blob) or is_raw_timestamp(blob):
        return False
    if _DEICTIC_IS_RE.match(blob):
        return bool(_SHORT_DEFINITION_CUE_RE.search(blob))
    if _SHORT_DEFINITION_CUE_RE.search(blob):
        return True
    return bool(_TERM_IS_RE.match(blob))


def reject_candidate(
    text: str,
    *,
    previous_text: str | None = None,
    seen_clean_texts: Iterable[str] | None = None,
    is_heading: bool = False,
) -> RejectDecision:
    """Reject fragments that MUST NOT become standalone inhoudelijk objects.

    Reasons are explicit. Official headings and short real definitions are
    tested exceptions and MUST NOT be dropped, even when short. Home / Tools
    / Richtlijnen / Meedenken are chrome. Inleiding is not chrome.
    """
    blob = normalize_visible_prose(text)
    if not blob:
        return RejectDecision(True, REJECT_EMPTY)

    official = is_official_heading_text(blob, is_heading=is_heading)
    short_def = is_short_real_definition(blob)
    seen = {normalize_visible_prose(item) for item in (seen_clean_texts or ()) if item}

    if is_kennisplatform_chrome_text(blob):
        return RejectDecision(True, REJECT_NAV_ONLY)
    if is_strength_stamp(blob):
        return RejectDecision(True, REJECT_STAMP_ONLY)
    if is_list_number_only(blob):
        return RejectDecision(True, REJECT_NUMBER_ONLY)
    if is_raw_timestamp(blob):
        return RejectDecision(True, REJECT_NOT_STANDALONE)

    if blob in seen:
        return RejectDecision(True, REJECT_DUPLICATE)

    if official:
        return RejectDecision(False, None, KEEP_OFFICIAL_HEADING)

    if not official and is_continuation_fragment(blob):
        return RejectDecision(True, REJECT_CONTINUATION)

    if short_def:
        return RejectDecision(False, None, KEEP_SHORT_DEFINITION)

    if word_count(blob) < MINIMUM_MEANING_WORDS:
        if is_lone_trailing_word(blob):
            return RejectDecision(True, REJECT_LABEL_ONLY)
        return RejectDecision(True, REJECT_BELOW_THRESHOLD)

    if is_tiny_confirmable_text(blob):
        return RejectDecision(True, REJECT_NOT_STANDALONE)

    if previous_text and is_continuation_fragment(blob):
        return RejectDecision(True, REJECT_CONTINUATION)

    return RejectDecision(False, None)


def filter_before_object_creation(text: str, *, is_heading: bool = False) -> str | None:
    """Discard reason if chrome / nav / number / label / empty / too-short.

    MUST run before a knowledge object is created. Stamps and grammatical
    continuations are not discarded here: the splitter consumes them
    (stamp → following advice; continuation → previous sentence).
    Official headings and short real definitions return None.
    """
    decision = reject_candidate(text, is_heading=is_heading)
    if decision.rejected and decision.reason in PRE_OBJECT_FILTER_REASONS:
        return decision.reason
    return None


def _merge_text(left: str, right: str) -> str:
    return re.sub(r"\s+", " ", f"{left} {right}").strip()


def _unique_meaning_units(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in rows:
        key = normalize_visible_prose(item.get("clean_text") or item.get("text") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def split_context_aware_units(
    fragments: Iterable[dict[str, Any]],
    *,
    document_id: str,
) -> list[dict[str, Any]]:
    """Split fragments into complete independently readable meaning units.

    Each emitted inhoudelijk unit has ``clean_text`` plus the source fragment
    id(s) that carry the v2.11 locator. Stamps are a property of the
    following advice sentence, not objects. Trailing clauses attach to the
    previous sentence. Chrome / nav / list numbers are filtered first.
    Identical ``clean_text`` from the same freeze is emitted once.
    """
    meaning_units: list[dict[str, Any]] = []
    pending_stamp: str | None = None
    pending_truncated: dict[str, Any] | None = None
    last_content: dict[str, Any] | None = None

    def emit_unit(spec_item: dict[str, Any]) -> None:
        nonlocal pending_stamp, last_content
        if pending_stamp and spec_item.get("object_type") != "heading":
            spec_item["proposed_recommendation_strength"] = pending_stamp
            pending_stamp = None
        meaning_units.append(spec_item)
        if spec_item.get("object_type") != "heading":
            last_content = spec_item

    def continuation_target() -> dict[str, Any] | None:
        if pending_truncated is not None:
            return pending_truncated
        return last_content

    def attach_continuation(unit: str, fragment: dict[str, Any]) -> bool:
        target = continuation_target()
        if target is None:
            return False
        if unit in target["text"]:
            return True
        target["text"] = _merge_text(target["text"], unit)
        target["clean_text"] = target["text"]
        extra_id = fragment.get("fragment_id")
        if extra_id and extra_id not in target["source_fragment_ids"]:
            target["source_fragment_ids"].append(extra_id)
        return True

    for fragment in fragments:
        text = (fragment.get("clean_text") or fragment.get("raw_text") or "").strip()
        if not text:
            continue
        object_type, _proposed = extract_object_type(fragment)
        is_heading = object_type == "heading"
        pre = filter_before_object_creation(text, is_heading=is_heading)
        if is_kennisplatform_chrome_text(text) or pre == REJECT_NAV_ONLY:
            continue
        if is_strength_stamp(text):
            pending_stamp = stamp_value(text)
            continue
        if is_list_number_only(text) or is_raw_timestamp(text) or pre == REJECT_NUMBER_ONLY:
            continue
        if pre in {REJECT_LABEL_ONLY, REJECT_EMPTY}:
            continue
        if (
            not is_heading
            and pre in {REJECT_BELOW_THRESHOLD, REJECT_NOT_STANDALONE}
            and not is_short_real_definition(text)
            and not is_official_heading_text(text)
        ):
            continue
        units = split_meaning_units(text, is_heading=is_heading)
        for index, unit in enumerate(units, 1):
            seen = {
                normalize_visible_prose(item.get("clean_text") or item.get("text") or "")
                for item in meaning_units
            }
            previous = (pending_truncated or last_content or {}).get("text")
            decision = reject_candidate(
                unit,
                previous_text=previous,
                seen_clean_texts=seen,
                is_heading=is_heading,
            )
            if decision.rejected and decision.reason == REJECT_NAV_ONLY:
                continue
            if decision.rejected and decision.reason == REJECT_STAMP_ONLY:
                pending_stamp = stamp_value(unit)
                continue
            if decision.rejected and decision.reason == REJECT_NUMBER_ONLY:
                continue
            if decision.rejected and decision.reason == REJECT_EMPTY:
                continue
            if decision.rejected and decision.reason == REJECT_DUPLICATE:
                continue
            if (
                decision.rejected
                and decision.reason == REJECT_CONTINUATION
                and not is_heading
            ):
                attach_continuation(unit, fragment)
                continue
            if pending_truncated is not None:
                emit_unit(pending_truncated)
                pending_truncated = None
            if decision.rejected and decision.reason in {
                REJECT_BELOW_THRESHOLD,
                REJECT_LABEL_ONLY,
                REJECT_NOT_STANDALONE,
            }:
                continue
            if not is_heading and is_tiny_confirmable_text(unit):
                continue
            fake = {**fragment, "clean_text": unit, "raw_text": unit}
            if not is_heading:
                if fake.get("heading") == unit or is_strength_stamp(str(fake.get("heading") or "")):
                    fake["heading"] = None
            unit_type, unit_proposed = extract_object_type(fake)
            if is_heading:
                unit_type, unit_proposed = "heading", "heading"
            suffix = f"-u{index:02d}" if len(units) > 1 else ""
            spec_item: dict[str, Any] = {
                "object_id": f"{document_id}-{fragment['fragment_id']}{suffix}",
                "object_type": unit_type,
                "text": unit,
                "clean_text": unit,
                "source_fragment_ids": [fragment["fragment_id"]],
                "section_path": [
                    part
                    for part in (fragment.get("section_path") or [])
                    if not is_strength_stamp(str(part)) and not is_kennisplatform_chrome_text(str(part))
                ],
                "heading": None
                if is_strength_stamp(str(fragment.get("heading") or ""))
                or is_kennisplatform_chrome_text(str(fragment.get("heading") or ""))
                else fragment.get("heading"),
                "review_track": "clinical",
                "relations": [],
                "confirmed_relations": [],
            }
            if unit_proposed:
                spec_item["proposed_object_type"] = unit_proposed
            if (
                not is_heading
                and pending_truncated is None
                and is_truncated_sentence(unit)
                and not is_tiny_confirmable_text(unit)
            ):
                pending_truncated = spec_item
            else:
                emit_unit(spec_item)
    if pending_truncated is not None:
        emit_unit(pending_truncated)
    return _unique_meaning_units(meaning_units)
