"""Closed source-reference evidence contract; never model-authored field prose."""
from __future__ import annotations

from copy import deepcopy
from src.semantic_replay_v1 import stable_json_hash

VERSION = "source-bound-fields-v2"
KEY = "source_bound_fields"
MODE = "semantic-source-bound-v2"
TYPE_FIELDS = {
    "recommendation": ("actor_of_scope", "recommended_action", "action_object_or_goal", "recommendation_evidence_span"),
    "definition": ("defined_term", "definiens_span"),
    "condition": ("condition_span", "condition_target"),
    "exception": ("exception_span", "exception_target"),
    "factual_finding": ("factual_claim_span",),
    "explanation": ("support_span", "supported_object"),
}
FIELDS = tuple(dict.fromkeys(("subject_span", "predicate_span", "type_evidence_spans") + tuple(f for fields in TYPE_FIELDS.values() for f in fields)))
MISSING = ("not_stated", "uncertain", "not_applicable")

FIELD_DESCRIPTIONS = {
    "subject_span": "Literal subject of the selected statement, preserving attribution where present.",
    "predicate_span": "Literal predicate of that subject, preserving negation and modality.",
    "type_evidence_spans": "Literal wording that supports the proposed object type. For a recommendation, select the recommendation cue or normative statement. This is distinct from evidence of strong/weak recommendation strength. Missing type evidence leaves the proposal unclassified or blocked; never invent it.",
    "actor_of_scope": "Literal actor, target group or scope of the recommendation.",
    "recommended_action": "Literal action being recommended, including a negation when stated.",
    "action_object_or_goal": "Literal object or goal of the recommended action.",
    "recommendation_evidence_span": "Literal wording establishing that the statement is a recommendation; it may overlap other fields.",
    "defined_term": "Literal term being defined.",
    "definiens_span": "Literal definition of the term.",
    "condition_span": "Literal condition, preserving its qualifiers.",
    "condition_target": "Literal statement or action to which the condition applies.",
    "exception_span": "Literal exception, preserving its qualifiers.",
    "exception_target": "Literal statement or action to which the exception applies.",
    "support_span": "Literal explanation or supporting statement.",
    "supported_object": "Literal statement being explained or supported.",
    "factual_claim_span": "Literal factual finding, preserving uncertainty, numbers and attribution.",
}


def evidence_schema(span: dict) -> dict:
    item = {"type": "object", "additionalProperties": False,
            "properties": {"span": {"anyOf": [deepcopy(span), {"type": "null"}]},
                           "missing_reason": {"type": ["string", "null"], "enum": [None, *MISSING]}},
            "required": ["span", "missing_reason"]}
    return {"type": "object", "additionalProperties": False,
            "properties": {field: {**deepcopy(item), "description": FIELD_DESCRIPTIONS[field]}
                           for field in FIELDS}, "required": list(FIELDS)}


def bind_fields(raw: object, *, selected: list[dict], candidate_text: str, proposed_type: str) -> dict:
    if not isinstance(raw, dict) or set(raw) != set(FIELDS):
        raise ValueError("source_bound_fields_invalid")
    from src.object_taxonomy_v1 import normalize_visible_prose
    if normalize_visible_prose(" ".join(s["text"] for s in selected)) != candidate_text:
        raise ValueError("source_bound_candidate_text_mismatch")
    values, evidence = {}, {}
    for field, entry in raw.items():
        if not isinstance(entry, dict) or set(entry) != {"span", "missing_reason"}:
            raise ValueError("source_bound_field_invalid")
        span, reason = entry["span"], entry["missing_reason"]
        if span is None:
            if reason not in MISSING:
                raise ValueError("source_bound_missing_reason_required")
            evidence[field] = deepcopy(entry)
            continue
        if reason is not None or not isinstance(span, dict) or set(span) != {"block_id", "start", "end"}:
            raise ValueError("source_bound_field_invalid")
        start, end = span["start"], span["end"]
        if type(start) is not int or type(end) is not int or start < 0 or end <= start:
            raise ValueError("source_bound_field_bounds_invalid")
        owner = next((s for s in selected if s["block_id"] == span["block_id"] and s["start"] <= start < end <= s["end"]), None)
        if owner is None:
            raise ValueError("source_bound_field_outside_candidate")
        text = owner["text"][start-owner["start"]:end-owner["start"]]
        # The existing passage reconstruction normalizes visible whitespace.
        text = normalize_visible_prose(text)
        if not text or text not in candidate_text:
            raise ValueError("source_bound_field_not_literal")
        values[field] = [text] if field == "type_evidence_spans" else text
        evidence[field] = deepcopy(entry)
    payload = {"version": VERSION, "candidate_text": candidate_text,
               "proposed_type": proposed_type, "values": values, "evidence": evidence}
    return {**payload, "binding_hash": stable_json_hash(payload)}


def bound_values(record: object, *, text: str, proposed_type: str) -> dict:
    """Reject stale evidence on correction/type changes, without heuristic repair."""
    if not isinstance(record, dict) or set(record) != {"version", "candidate_text", "proposed_type", "values", "evidence", "binding_hash"}:
        raise ValueError("source_bound_fields_invalid")
    payload = {k: v for k, v in record.items() if k != "binding_hash"}
    if record["version"] != VERSION or record["binding_hash"] != stable_json_hash(payload):
        raise ValueError("source_bound_fields_invalid")
    if record["candidate_text"] != text or record["proposed_type"] != proposed_type:
        raise ValueError("source_bound_fields_stale")
    if not isinstance(record["values"], dict) or set(record["values"]) - set(FIELDS):
        raise ValueError("source_bound_fields_invalid")
    evidence = record["evidence"]
    if not isinstance(evidence, dict) or set(evidence) != set(FIELDS):
        raise ValueError("source_bound_fields_invalid")
    for field, entry in evidence.items():
        if not isinstance(entry, dict) or set(entry) != {"span", "missing_reason"}:
            raise ValueError("source_bound_fields_invalid")
        if entry["span"] is None:
            if entry["missing_reason"] not in MISSING or field in record["values"]:
                raise ValueError("source_bound_fields_invalid")
        elif entry["missing_reason"] is not None or field not in record["values"]:
            raise ValueError("source_bound_fields_invalid")
    for field, value in record["values"].items():
        literals = value if field == "type_evidence_spans" else [value]
        if not isinstance(literals, list) or not literals or any(not isinstance(v, str) or not v or v not in text for v in literals):
            raise ValueError("source_bound_field_not_literal")
    return deepcopy(record["values"])


def apply_bound_fields(candidate: dict) -> list[str]:
    """Replace derived fields atomically; invalid evidence leaves them empty."""
    for field in FIELDS:
        candidate[field] = [] if field == "type_evidence_spans" else ""
    try:
        values = bound_values(candidate.get(KEY),
                              text=str(candidate.get("candidate_text") or ""),
                              proposed_type=str(candidate.get("proposed_type") or ""))
    except ValueError as exc:
        return [str(exc)]
    candidate.update(values)
    return []
