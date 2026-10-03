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


def _bound_error(code, **finding):
    error = ValueError(code)
    error.finding = deepcopy(finding)
    return error


def bind_fields(raw: object, *, selected: list[dict], candidate_text: str, proposed_type: str) -> dict:
    if not isinstance(raw, dict) or set(raw) != set(FIELDS):
        raise ValueError("source_bound_fields_invalid")
    from src.object_taxonomy_v1 import normalize_visible_prose
    if normalize_visible_prose(" ".join(s["text"] for s in selected)) != candidate_text:
        raise ValueError("source_bound_candidate_text_mismatch")
    values, evidence = {}, {}
    for field, entry in raw.items():
        if not isinstance(entry, dict) or set(entry) != {"span", "missing_reason"}:
            raise _bound_error("source_bound_field_invalid", field=field, evidence_ref=entry)
        span, reason = entry["span"], entry["missing_reason"]
        if span is None:
            if reason not in MISSING:
                raise _bound_error("source_bound_missing_reason_required", field=field, evidence_ref=entry)
            evidence[field] = deepcopy(entry)
            continue
        if reason is not None or not isinstance(span, dict) or set(span) != {"block_id", "start", "end"}:
            raise _bound_error("source_bound_field_invalid", field=field, evidence_ref=entry)
        start, end = span["start"], span["end"]
        if type(start) is not int or type(end) is not int or start < 0 or end <= start:
            raise _bound_error("source_bound_field_bounds_invalid", field=field, evidence_ref=entry)
        owner = next((s for s in selected if s["block_id"] == span["block_id"] and s["start"] <= start < end <= s["end"]), None)
        if owner is None:
            raise _bound_error("source_bound_field_outside_candidate", field=field, evidence_ref=entry)
        text = owner["text"][start-owner["start"]:end-owner["start"]]
        # The existing passage reconstruction normalizes visible whitespace.
        text = normalize_visible_prose(text)
        if not text or text not in candidate_text:
            raise _bound_error("source_bound_field_not_literal", field=field, evidence_ref=entry)
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

# Additive contract for context of new v2 proposals; legacy v2 fields stay readable.
CONTEXT_KEY = 'source_bound_context'
CONTEXT_VERSION = 'source-bound-context-v1'
CONTEXT_ROLES = ('target_group', 'timing', 'condition', 'exception', 'negation', 'scope',
                 'list_introduction', 'row_header', 'column_header', 'support')
CONTEXT_REASONS = ('context_uncertain', 'scope_not_stated', 'layout_ambiguous', 'relation_uncertain')
MAX_CONTEXT_REFERENCES = 256


def context_evidence_schema(span: dict) -> dict:
    return {'type': 'array', 'maxItems': MAX_CONTEXT_REFERENCES, 'items': {
        'type': 'object', 'additionalProperties': False,
        'properties': {'role': {'type': 'string', 'enum': list(CONTEXT_ROLES)},
                       'span': {'anyOf': [deepcopy(span), {'type': 'null'}]},
                       'unresolved_reason': {'type': ['string', 'null'], 'enum': [None, *CONTEXT_REASONS]}},
        'required': ['role', 'span', 'unresolved_reason']}}


def bind_context(raw: object, *, fragments: list[dict]) -> list[dict]:
    """Rebuild literal context; source geometry/proximity does not resolve semantics."""
    from src.semantic_passage_v1 import _reconstructed_blocks
    from src.source_layout_v1 import mapped_raw_spans
    if not isinstance(raw, list) or len(raw) > MAX_CONTEXT_REFERENCES:
        raise ValueError('source_bound_context_invalid')
    blocks = {public['block_id']: (public, source) for public, source in _reconstructed_blocks(fragments)}
    result = []
    for context_index, entry in enumerate(raw):
        if not isinstance(entry, dict) or set(entry) != {'role', 'span', 'unresolved_reason'}:
            raise _bound_error('source_bound_context_invalid', field='context_evidence', context_index=context_index, evidence_ref=entry)
        if entry['role'] not in CONTEXT_ROLES or entry['unresolved_reason'] not in (None, *CONTEXT_REASONS):
            raise _bound_error('source_bound_context_invalid', field='context_evidence', context_index=context_index, evidence_ref=entry)
        span = entry['span']
        text, mapping, source_refs = '', [], []
        if span is None:
            if entry['unresolved_reason'] is None:
                raise _bound_error('source_bound_context_reason_required', field='context_evidence', context_index=context_index, evidence_ref=entry)
        else:
            if not isinstance(span, dict) or set(span) != {'block_id', 'start', 'end'} or span['block_id'] not in blocks:
                raise _bound_error('source_bound_context_unknown_block', field='context_evidence', context_index=context_index, evidence_ref=entry)
            public, source = blocks[span['block_id']]
            lo, hi = span['start'], span['end']
            if type(lo) is not int or type(hi) is not int or not 0 <= lo < hi <= len(public['text']):
                raise _bound_error('source_bound_context_bounds_invalid', field='context_evidence', context_index=context_index, evidence_ref=entry)
            text = public['text'][lo:hi]
            if not text.strip():
                raise _bound_error('source_bound_context_empty', field='context_evidence', context_index=context_index, evidence_ref=entry)
            mapping = mapped_raw_spans(source, start=lo, end=hi)
            ids = {r['fragment_id'] for r in mapping if r.get('kind') != 'join_separator'}
            source_refs = [{'fragment_id': f['fragment_id'], 'fragment_hash': f['fragment_hash'],
                            'source_locator': deepcopy(f.get('source_locator'))}
                           for f in fragments if f['fragment_id'] in ids]
        result.append({**deepcopy(entry), 'text': text, 'source_mapping': mapping, 'source_refs': source_refs})
    if len({stable_json_hash(r) for r in result}) != len(result):
        raise ValueError('source_bound_context_duplicate')
    return result


def context_record(entries: list[dict], *, obj: dict) -> dict:
    from src.source_context_review_v1 import literal_identity
    return {'version': CONTEXT_VERSION, 'target_object_id': obj['object_id'],
            'target_object_version_at_binding': obj['object_version'],
            'target_literal_hash': literal_identity(obj), 'source': deepcopy(obj['source']), 'entries': deepcopy(entries)}


def validated_context(obj: dict, fragments: list[dict], source_hash: str) -> list[dict]:
    record = (obj.get('metadata') or {}).get(CONTEXT_KEY)
    if record is None:
        return []
    if not isinstance(record, dict) or set(record) != {'version', 'target_object_id', 'target_object_version_at_binding',
                                                     'target_literal_hash', 'source', 'entries'}:
        raise ValueError('source_bound_context_invalid')
    entries = record['entries']
    if not isinstance(entries, list):
        raise ValueError('source_bound_context_invalid')
    raw = [{key: row[key] for key in ('role', 'span', 'unresolved_reason')} for row in entries]
    rebuilt = bind_context(raw, fragments=fragments)
    expected = context_record(rebuilt, obj=obj)
    # Existing context semantics allow classification-only target version changes.
    expected['target_object_version_at_binding'] = record['target_object_version_at_binding']
    if record != expected or not source_hash or record['source'].get('source_checksum') != source_hash:
        raise ValueError('source_bound_context_stale')
    return rebuilt


def context_matches_target(obj: dict) -> bool:
    """Read-only identity check; literal source revalidation belongs to writes."""
    record = (obj.get('metadata') or {}).get(CONTEXT_KEY)
    if not isinstance(record, dict) or not isinstance(record.get('entries'), list):
        return False
    expected = context_record(record['entries'], obj=obj)
    expected['target_object_version_at_binding'] = record.get('target_object_version_at_binding')
    return bool(expected['target_object_version_at_binding']) and record == expected
