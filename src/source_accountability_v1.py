"""Source-only evidence in the existing passage register, never review approval.

Classifications are proposals. Legacy v1 requires human disposition; v2 source
usage is derived by source_containers_v1 under its versioned, reversible policy.
Missing classifications mean unknown source use, not proven missing knowledge.
"""
from copy import deepcopy

from src.semantic_replay_v1 import stable_json_hash

VERSION = "source-accountability-v1"
CONTAINERS_VERSION = "source-accountability-v2"
KEY = "source_accountability"
ROLES = {
    "metadata": ("document_metadata", "page_furniture"),
    "structure": ("navigation", "document_structure"),
    "unresolved": ("unformed_meaning", "uncertain_source_role"),
}


def assessment_schema(span):
    return {"type": "array", "maxItems": 8192, "items": {
        "type": "object", "additionalProperties": False,
        "properties": {"span": deepcopy(span),
            "role": {"type": "string", "enum": list(ROLES)},
            "reason": {"type": "string", "enum": [r for reasons in ROLES.values() for r in reasons]}},
        "required": ["span", "role", "reason"]}}


def validate_assessments(raw, blocks, selected):
    """Validate locations and disjointness, not the truth of a semantic role."""
    if not isinstance(raw, list) or len(raw) > 8192:
        raise ValueError("source_assessment_invalid")
    by_id = {b["block_id"]: b for b in blocks}
    occupied = [s for obj in selected for s in obj.get("spans") or []]
    result = []
    for row in raw:
        if (not isinstance(row, dict) or set(row) != {"span", "role", "reason"}
                or not isinstance(row.get("role"), str) or row.get("role") not in ROLES or row.get("reason") not in ROLES[row["role"]]):
            raise ValueError("source_assessment_invalid")
        span = row["span"]
        if (not isinstance(span, dict) or set(span) != {"block_id", "start", "end"}
                or not isinstance(span["block_id"], str) or span["block_id"] not in by_id
                or type(span["start"]) is not int or type(span["end"]) is not int
                or not 0 <= span["start"] < span["end"] <= len(by_id[span["block_id"]]["text"])):
            raise ValueError("source_assessment_bounds_invalid")
        if any(s["block_id"] == span["block_id"] and
               max(s["start"], span["start"]) < min(s["end"], span["end"]) for s in occupied):
            raise ValueError("source_assessment_overlap")
        occupied.append(span)
        result.append(deepcopy(row))
    return result


def record(*, text, spans, assessment=None, version=VERSION):
    if version not in {VERSION, CONTAINERS_VERSION}:
        raise ValueError("source_accountability_version_invalid")
    row = {"version": version, "record_kind": "source_passage", "text": text,
           "spans": deepcopy(spans), "proposed_role": (assessment or {}).get("role", "unresolved"),
           "reason": (assessment or {}).get("reason", "uncertain_source_role" if version == CONTAINERS_VERSION else "unformed_meaning")}
    return {**row, "binding_hash": stable_json_hash(row)}


def evidence_of(obj):
    md = obj.get("metadata") or {}
    raw = md.get(KEY)
    if not isinstance(raw, dict):
        return {}
    payload = {k: v for k, v in raw.items() if k != "binding_hash"}
    semantic = md.get("semantic_passage") or {}
    if (set(payload) != {"version", "record_kind", "text", "spans", "proposed_role", "reason"}
            or raw.get("version") not in {VERSION, CONTAINERS_VERSION} or raw.get("record_kind") != "source_passage"
            or raw.get("binding_hash") != stable_json_hash(payload)
            or semantic.get("selection_origin") != "coverage_remainder"
            or raw.get("spans") != semantic.get("spans")
            or raw.get("text") != (obj.get("content") or {}).get("clean_text")
            or not isinstance(raw.get("proposed_role"), str) or raw.get("proposed_role") not in ROLES
            or raw.get("reason") not in ROLES[raw["proposed_role"]]):
        return {}
    return deepcopy(raw)


def is_source_record(obj):
    # The discriminator never grants closure or eligibility. A damaged record
    # remains source repair work, rather than becoming a clinical candidate.
    md = obj.get("metadata") or {}
    return (KEY in md and (md.get("semantic_passage") or {}).get("selection_origin") == "coverage_remainder")


def supplementary_targets(units):
    result = []
    for unit in units:
        row = unit.get(KEY)
        if not row or row["proposed_role"] != "unresolved":
            continue
        for span in row["spans"]:
            result.append({"span": deepcopy(span), "text": row["text"]})
    return result
