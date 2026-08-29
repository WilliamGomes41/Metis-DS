"""Closed object-type taxonomy for Protocol v2.12.

Extraction records structure and provenance only. The machine MAY propose a
type. A human MUST confirm before the type is published. unclassified is the
default, not a sixth advice type.
"""
from __future__ import annotations

import re
from typing import Any

from src.serving_relations_v1 import HISTORICAL_NON_SERVING_TYPES

CLOSED_OBJECT_TYPES = (
    "heading",
    "definition",
    "explanation",
    "condition",
    "exception",
    "recommendation",
)
CONTAINER_TYPES = frozenset({"document"})
DEFAULT_OBJECT_TYPE = "unclassified"
HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")
CLASS_ORDER = {
    "richtlijn": 4,
    "handreiking": 3,
    "artikel": 2,
    "transcript": 1,
    "podcast": 1,
}
HISTORICAL_FACT_TYPES = HISTORICAL_NON_SERVING_TYPES

_DEFINITION_RE = re.compile(r"\b(?:is een|wordt genoemd|definitie|betekent)\b", re.I)
_EXCEPTION_RE = re.compile(r"\b(?:behalve|tenzij|uitgezonderd|uitzondering)\b", re.I)
_CONDITION_RE = re.compile(r"\b(?:bij een|indien|wanneer|mits|voorwaarde)\b", re.I)
_EXPLANATION_RE = re.compile(r"\b(?:omdat|namelijk|daardoor|helpt omdat|verklaar)\b", re.I)
_RECOMMENDATION_RE = re.compile(
    r"\b(?:adviseer|aanbevel|gebruik|verwijs|bespreek|overleg|controleer|start)\w*\b",
    re.I,
)


def fragment_is_heading(fragment: dict[str, Any]) -> bool:
    loc = fragment.get("source_locator") or {}
    value = str(loc.get("locator_value") or "").lower()
    if loc.get("locator_type") == "web_line_range":
        return any(f";{tag}:" in value for tag in HEADING_TAGS)
    heading = re.sub(r"\s+", " ", str(fragment.get("heading") or "")).strip()
    text = re.sub(r"\s+", " ", str(fragment.get("clean_text") or fragment.get("raw_text") or "")).strip()
    return bool(heading and heading == text)


def propose_object_type(text: str, *, is_heading: bool = False) -> str | None:
    if is_heading:
        return "heading"
    blob = text or ""
    if _DEFINITION_RE.search(blob):
        return "definition"
    if _EXCEPTION_RE.search(blob):
        return "exception"
    if _CONDITION_RE.search(blob):
        return "condition"
    if _EXPLANATION_RE.search(blob):
        return "explanation"
    if _RECOMMENDATION_RE.search(blob):
        return "recommendation"
    return None


def extract_object_type(fragment: dict[str, Any]) -> tuple[str, str | None]:
    heading = fragment_is_heading(fragment)
    text = (fragment.get("clean_text") or fragment.get("raw_text") or "").strip()
    if heading:
        return "heading", "heading"
    return DEFAULT_OBJECT_TYPE, propose_object_type(text, is_heading=False)


def is_closed_confirmed_type(value: str | None) -> bool:
    return value in CLOSED_OBJECT_TYPES


def published_object_type(record: dict[str, Any]) -> str:
    """Return the type that may be served. Unconfirmed proposals are unclassified."""
    md = record.get("metadata") if "metadata" in record else record
    confirmed = md.get("confirmed_object_type")
    if confirmed:
        if confirmed in HISTORICAL_NON_SERVING_TYPES:
            return DEFAULT_OBJECT_TYPE
        return confirmed
    obj_type = md.get("object_type") or DEFAULT_OBJECT_TYPE
    if obj_type in HISTORICAL_NON_SERVING_TYPES:
        return DEFAULT_OBJECT_TYPE
    if obj_type == DEFAULT_OBJECT_TYPE:
        return DEFAULT_OBJECT_TYPE
    if obj_type in CONTAINER_TYPES:
        return obj_type
    if md.get("type_confirmed") is True:
        return obj_type
    if md.get("published_at") and obj_type not in {DEFAULT_OBJECT_TYPE, None, ""}:
        return obj_type
    if "confirmed_object_type" not in md and "proposed_object_type" not in md and obj_type != DEFAULT_OBJECT_TYPE:
        return obj_type
    return DEFAULT_OBJECT_TYPE


def source_class_of(record: dict[str, Any]) -> str | None:
    md = record.get("metadata") if "metadata" in record else record
    if md.get("source_class"):
        return md["source_class"]
    for topic in md.get("topic") or []:
        text = str(topic)
        if text.startswith("class:") and not text.startswith("class-weight:"):
            return text.split(":", 1)[1]
    return None


def locator_of(record: dict[str, Any]) -> dict[str, Any] | None:
    md = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    loc = md.get("source_locator")
    if isinstance(loc, dict) and str(loc.get("locator_value") or "").strip():
        return loc
    for frag in (record.get("provenance") or {}).get("source_fragments") or []:
        sl = frag.get("source_locator") or {}
        if str(sl.get("locator_value") or "").strip():
            return sl
    obj = record.get("knowledge_object") or record
    for frag in (obj.get("provenance") or {}).get("source_fragments") or []:
        sl = frag.get("source_locator") or {}
        if str(sl.get("locator_value") or "").strip():
            return sl
    return None


def type_fits_question(question_kind: str, object_type: str) -> bool:
    if object_type in {DEFAULT_OBJECT_TYPE, "heading", "document"}:
        return False
    if object_type in HISTORICAL_NON_SERVING_TYPES:
        return False
    if question_kind == "action_advice":
        return object_type in {"recommendation", "condition", "exception"}
    if question_kind == "definition":
        return object_type == "definition"
    if question_kind == "explanation":
        return object_type == "explanation"
    if object_type in CLOSED_OBJECT_TYPES:
        return True
    return False


def is_advice_weight(question_kind: str, object_type: str) -> bool:
    return question_kind == "action_advice" and object_type == "recommendation"
