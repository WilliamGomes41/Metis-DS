"""Beslisboom review path: Klasse selects path / node / outcome.

Closed boom types exist only on Klasse=beslisboom. Product API boom serving
is not activated. Live kennisplatform REST is not the sole source of truth.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

from src.four_eyes_v1 import HIGH_RISK_FIELDS
from src.object_taxonomy_v1 import CLASS_ORDER, CLOSED_OBJECT_TYPES, source_class_of
from src.serving_relations_v1 import serving_relation_type

CLOSED_BOOM_TYPES = ("path", "node", "outcome")
CLOSED_KLASSEN = (
    "richtlijn",
    "handreiking",
    "artikel",
    "transcript",
    "podcast",
    "beslisboom",
)
RICHTLIJN_PATH_TYPES = CLOSED_OBJECT_TYPES
LIVE_REST_MARKER = "/wp-json/beslisboom/"
PLACEHOLDER_OUTCOME_RE = re.compile(r"^uitkomst\d+_\d+_titel$", re.I)
FUSED_CONDITION_RE = re.compile(
    r"^\s*(?:indien|wanneer|mits|als\b|bij (?:een |de )?(?:score|valrisico))",
    re.I,
)
BULLET_SPLIT_RE = re.compile(r"(?:^|\n)\s*[•*\-]\s+")
GEEN_ACTIE_RE = re.compile(r"\bgeen actie\b", re.I)
DOSAGE_UNIT_RE = re.compile(
    r"(?P<dosage>\d+(?:[.,]\d+)?)\s*(?P<unit>IE|IU|mg|mcg|µg|ug|ml)\b",
    re.I,
)


def review_path_for_klasse(klasse: str) -> str:
    if klasse not in CLOSED_KLASSEN:
        raise ValueError("invalid_class")
    return "boom" if klasse == "beslisboom" else "richtlijn"


def is_closed_boom_type(value: str | None) -> bool:
    return value in CLOSED_BOOM_TYPES


def is_confirmable_type_for_path(value: str | None, review_path: str) -> bool:
    if review_path == "boom":
        return is_closed_boom_type(value)
    return value in RICHTLIJN_PATH_TYPES


def scorelist_item_model() -> dict[str, Any]:
    return {"object_type": "node", "scorelist": True}


def boom_serving_activated() -> bool:
    return False


def class_outranks(heavier: str, lighter: str) -> bool:
    return CLASS_ORDER.get(heavier, 0) > CLASS_ORDER.get(lighter, 0)


def is_live_rest_url(url: str | None) -> bool:
    return LIVE_REST_MARKER in (url or "").lower()


def is_empty_or_placeholder_outcome(text: str | None) -> bool:
    blob = re.sub(r"\s+", " ", text or "").strip()
    if not blob:
        return True
    return bool(PLACEHOLDER_OUTCOME_RE.fullmatch(blob.replace(" ", ""))) or bool(
        PLACEHOLDER_OUTCOME_RE.fullmatch(blob)
    )


def _bullet_parts(text: str) -> list[str]:
    parts = [item.strip() for item in BULLET_SPLIT_RE.split(text or "") if item.strip()]
    return parts


def split_or_reject_multi_bullet_outcome(text: str) -> dict[str, Any]:
    parts = _bullet_parts(text)
    if len(parts) >= 2:
        return {"action": "split", "parts": parts}
    return {"action": "reject"}


def _is_multi_bullet_outcome(text: str) -> bool:
    return len(_bullet_parts(text)) >= 2 and ("•" in text or text.count("\n") >= 1)


def _looks_fused_condition(text: str) -> bool:
    return bool(FUSED_CONDITION_RE.search(text or ""))


def _confirmed_applies_if(obj: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in obj.get("confirmed_relations") or []:
        if serving_relation_type(row.get("relation_type")) != "applies_if":
            continue
        if not row.get("target_object_id"):
            continue
        if row.get("confirmed") is False:
            continue
        rows.append(row)
    return rows


def outcome_review_errors(obj: dict[str, Any], peers: Iterable[dict[str, Any]] | None = None) -> list[str]:
    errors: list[str] = []
    text = str((obj.get("content") or {}).get("clean_text") or "")
    if is_empty_or_placeholder_outcome(text):
        errors.append("empty_or_placeholder_outcome")
    if _is_multi_bullet_outcome(text):
        errors.append("multi_bullet_outcome")
    binds = _confirmed_applies_if(obj)
    peer_ids = {
        row.get("object_id")
        for row in (peers or [])
        if (row.get("confirmed_object_type") or row.get("object_type") or row.get("proposed_object_type"))
        in {"node", "path"}
    }
    valid = [row for row in binds if not peer_ids or row.get("target_object_id") in peer_ids]
    if not valid:
        if _looks_fused_condition(text):
            errors.append("condition_fused_into_outcome")
        else:
            errors.append("outcome_relation_unconfirmed")
    return list(dict.fromkeys(errors))


def outcome_strength_applies(obj: dict[str, Any]) -> bool:
    confirmed = obj.get("confirmed_object_type") or ""
    stored = obj.get("object_type") or ""
    proposed = obj.get("proposed_object_type") or ""
    if confirmed:
        return confirmed == "outcome"
    if stored and stored != "unclassified":
        return stored == "outcome"
    return proposed == "outcome"


def proposed_outcome_strength(text: str) -> str | None:
    blob = re.sub(r"\s+", " ", text or "").strip().casefold()
    if GEEN_ACTIE_RE.search(blob):
        return "niet_doen"
    if "niet doen" in blob or blob.startswith("niet_doen"):
        return "niet_doen"
    if "overweeg" in blob:
        return "overweeg"
    if re.search(r"\b(?:adviseer|aanbevel|verwijs|start|bespreek|doen)\w*\b", blob):
        return "doen"
    return None


def map_geen_actie(text: str) -> dict[str, Any]:
    return {"strength": "niet_doen", "no_action": True, "positive_advice": False}


def is_geen_actie_outcome(text: str | None) -> bool:
    return bool(GEEN_ACTIE_RE.search(text or ""))


def _family_of(obj: dict[str, Any]) -> str | None:
    md = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
    if md.get("family"):
        return str(md["family"])
    for topic in (obj.get("content") or {}).get("topic") or []:
        text = str(topic)
        if text.startswith("family:"):
            return text.split(":", 1)[1]
        if ":" not in text:
            return text
    return None


def _confirmed_type_of(obj: dict[str, Any]) -> str:
    if obj.get("confirmed_object_type"):
        return str(obj["confirmed_object_type"])
    md = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
    return str(md.get("confirmed_object_type") or "")


def preferred_same_family_advice(
    objs: Iterable[dict[str, Any]],
    *,
    family: str,
) -> dict[str, Any] | None:
    rows = [row for row in objs if _family_of(row) in {None, family}]
    richtlijn = [
        row
        for row in rows
        if source_class_of(row) == "richtlijn" and _confirmed_type_of(row) == "recommendation"
    ]
    if richtlijn:
        return richtlijn[0]
    boom = [
        row
        for row in rows
        if source_class_of(row) == "beslisboom" and _confirmed_type_of(row) == "outcome"
    ]
    if boom:
        return {**boom[0], "fills_missing_richtlijn": False}
    return None


def is_story_html_alone(*, filename: str | None, data: bytes | None) -> bool:
    name = Path(filename or "").name.lower()
    if name == "story.html":
        return True
    raw = data or b""
    lowered = raw.decode("utf-8", errors="replace").lower()
    markers = (
        'data-kennisplatform-player="boom"',
        "kennisplatform-boom-player",
        'class="boom-player"',
        "articulate-rise",
        "storyline-player",
        "window.playerconfig",
    )
    if name.endswith((".html", ".htm")) and any(marker in lowered for marker in markers):
        return True
    return False


def _usable_freeze_payload(data: bytes | None) -> dict[str, Any] | None:
    if not data:
        return None
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("kind") != "beslisboom-freeze":
        return None
    return payload


def is_live_rest_sole_source(
    *,
    data: bytes | None,
    live_url: str | None,
    filename: str | None,
) -> bool:
    if not is_live_rest_url(live_url):
        return False
    payload = _usable_freeze_payload(data)
    if payload is None:
        return True
    has_body = bool(payload.get("paths") or payload.get("nodes") or payload.get("outcomes"))
    return not has_body


def boom_freeze_errors(
    *,
    data: bytes | None,
    filename: str | None,
    live_url: str | None,
) -> list[str]:
    errors: list[str] = []
    if is_story_html_alone(filename=filename, data=data):
        errors.append("story_html_alone_insufficient")
    if is_live_rest_sole_source(data=data, live_url=live_url, filename=filename):
        errors.append("live_rest_sole_source")
    payload = _usable_freeze_payload(data)
    if payload is None:
        if not errors:
            errors.append("invalid_boom_freeze")
        return errors
    nodes = payload.get("nodes") or []
    outcomes = payload.get("outcomes") or []
    if not nodes or not outcomes:
        errors.append("empty_boom_freeze")
    return errors


def _applies_if_ids(raw: Any) -> list[str]:
    out: list[str] = []
    for item in raw or []:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        elif isinstance(item, dict):
            target = item.get("node_id") or item.get("path_id") or item.get("id")
            if target:
                out.append(str(target).strip())
    return out


def _json_string_byte_span(data: bytes, start: int) -> tuple[int, int, str]:
    if start >= len(data) or data[start:start + 1] != b'"':
        raise ValueError("boom_locator_unresolved")
    index = start + 1
    while index < len(data):
        byte = data[index]
        if byte == 0x5C:
            index += 2
            continue
        if byte == 0x22:
            end = index + 1
            return start, end, json.loads(data[start:end].decode("utf-8"))
        index += 1
    raise ValueError("boom_locator_unresolved")


class BoomLocator:
    """Exact v2.11 web_line_range locators into original freeze bytes."""

    _ID_KEY = re.compile(rb'"id"\s*:\s*')
    _TEXT_KEY = re.compile(rb'"text"\s*:\s*')

    @staticmethod
    def span_for_item(data: bytes, item_id: str, text: str) -> tuple[int, int]:
        encoded_id = json.dumps(item_id, ensure_ascii=False).encode("utf-8")
        pos = 0
        while True:
            match = BoomLocator._ID_KEY.search(data, pos)
            if match is None:
                break
            if data.startswith(encoded_id, match.end()):
                text_key = BoomLocator._TEXT_KEY.search(data, match.end())
                if text_key is not None:
                    start, end, decoded = _json_string_byte_span(data, text_key.end())
                    if decoded == text:
                        return start, end
            pos = match.end()
        encoded_text = json.dumps(text, ensure_ascii=False).encode("utf-8")
        index = data.find(encoded_text)
        if index >= 0:
            return index, index + len(encoded_text)
        raise ValueError("boom_locator_unresolved")

    @staticmethod
    def locator_value(data: bytes, item_id: str, text: str) -> str:
        start, end = BoomLocator.span_for_item(data, item_id, text)
        line_start = data[:start].count(b"\n") + 1
        line_end = line_start + data[start:end].count(b"\n")
        return f"lines:{line_start}-{line_end};bytes:{start}-{end}"


def derive_boom_risk_fields(item: dict[str, Any], text: str) -> tuple[list[str], dict[str, Any]]:
    fields: list[str] = []
    metadata: dict[str, Any] = {}
    for field in HIGH_RISK_FIELDS:
        value = item.get(field)
        if value not in (None, "", False, []):
            metadata[field] = value
            fields.append(field)
    match = DOSAGE_UNIT_RE.search(text or "")
    if match:
        metadata.setdefault("dosage", match.group("dosage"))
        metadata.setdefault("unit", match.group("unit"))
        if "dosage" not in fields:
            fields.append("dosage")
        if "unit" not in fields:
            fields.append("unit")
    return fields, metadata


def extract_boom_fragments(
    data: bytes,
    *,
    document_id: str,
    source_id: str,
) -> list[dict[str, Any]]:
    payload = _usable_freeze_payload(data)
    if payload is None:
        raise ValueError("invalid_boom_freeze")
    if not (payload.get("nodes") or []) or not (payload.get("outcomes") or []):
        raise ValueError("empty_boom_freeze")
    rows: list[dict[str, Any]] = []
    seq = 0
    for kind, items in (
        ("path", payload.get("paths") or []),
        ("node", payload.get("nodes") or []),
        ("outcome", payload.get("outcomes") or []),
    ):
        for item in items:
            text = str(item.get("text") or "").strip()
            seq += 1
            boom_id = str(item.get("id") or f"{kind}-{seq}")
            locator = BoomLocator.locator_value(data, boom_id, text)
            risk_fields, risk_metadata = derive_boom_risk_fields(item, text)
            fragment = {
                "fragment_id": f"{document_id}-boom-f{seq:04d}",
                "document_id": document_id,
                "source_id": source_id,
                "source_page": None,
                "bbox": None,
                "source_locator": {"locator_type": "web_line_range", "locator_value": locator},
                "raw_text": text,
                "clean_text": text,
                "section_path": [kind],
                "heading": None,
                "sequence": seq,
                "parser_version": "boom-freeze-v1",
                "boom_kind": kind,
                "boom_id": boom_id,
                "scorelist": bool(item.get("scorelist")),
                "applies_if": _applies_if_ids(item.get("applies_if")),
                "risk_fields": risk_fields,
                "risk_metadata": risk_metadata,
            }
            if kind == "outcome":
                strength = str(item.get("strength") or "").strip() or proposed_outcome_strength(text)
                if strength:
                    fragment["proposed_recommendation_strength"] = strength
                if is_geen_actie_outcome(text):
                    fragment["no_action"] = True
            fragment["fragment_hash"] = hashlib.sha256(
                json.dumps(
                    {key: fragment[key] for key in ("fragment_id", "clean_text", "source_locator")},
                    ensure_ascii=False,
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest()
            rows.append(fragment)
    return rows


def boom_spec_from_fragments(
    *,
    document_id: str,
    title: str,
    family: str,
    class_: str,
    fragments: list[dict[str, Any]],
) -> dict[str, Any]:
    id_by_boom: dict[str, str] = {}
    objects: list[dict[str, Any]] = [
        {
            "object_id": f"{document_id}-document",
            "object_type": "document",
            "text": title,
            "review_track": "technical",
        }
    ]
    for fragment in fragments:
        boom_id = str(fragment.get("boom_id") or fragment["fragment_id"])
        object_id = f"{document_id}-{boom_id}"
        id_by_boom[boom_id] = object_id
        kind = fragment.get("boom_kind")
        relations = []
        for target in fragment.get("applies_if") or []:
            relations.append({"relation_type": "applies_if", "target_object_id": f"{document_id}-{target}"})
        spec_item: dict[str, Any] = {
            "object_id": object_id,
            "object_type": "unclassified",
            "proposed_object_type": kind,
            "text": fragment["clean_text"],
            "clean_text": fragment["clean_text"],
            "source_fragment_ids": [fragment["fragment_id"]],
            "relations": relations,
            "review_track": "clinical",
            "scorelist": bool(fragment.get("scorelist")),
            "risk_fields": list(fragment.get("risk_fields") or []),
        }
        if fragment.get("proposed_recommendation_strength"):
            spec_item["proposed_recommendation_strength"] = fragment["proposed_recommendation_strength"]
        objects.append(spec_item)
    _ = id_by_boom
    return {
        "spec_version": "console-ingest-1.0",
        "document_id": document_id,
        "object_version": "1.0",
        "target_group": [],
        "care_setting": [],
        "topic": [family, f"class:{class_}", "source-kind:boom"],
        "objects": objects,
    }


def stamp_boom_flags(objects: list[dict[str, Any]], fragments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_fragment = {row["fragment_id"]: row for row in fragments}
    for obj in objects:
        refs = (obj.get("provenance") or {}).get("source_fragments") or []
        for ref in refs:
            raw = by_fragment.get(ref.get("raw_object_id"))
            if raw is None:
                continue
            if raw.get("scorelist"):
                obj["scorelist"] = True
                metadata = obj.setdefault("metadata", {})
                metadata["scorelist"] = True
            if raw.get("risk_fields"):
                risk = obj.setdefault("risk", {})
                fields = list(dict.fromkeys([*(risk.get("risk_fields") or []), *raw["risk_fields"]]))
                risk["risk_fields"] = fields
                if fields:
                    risk["requires_second_review"] = True
                    if risk.get("risk_level") not in {"high"}:
                        risk["risk_level"] = "high"
                metadata = obj.setdefault("metadata", {})
                for key, value in (raw.get("risk_metadata") or {}).items():
                    metadata[key] = value
            if raw.get("no_action"):
                obj["no_action"] = True
                obj.setdefault("metadata", {})["no_action"] = True
    return objects
