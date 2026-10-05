"""Versioned recommendation evidence in a literal core and applicable context.

V2 is deliberately not reinterpreted. This module is a successor reader/writer
behind the existing producer, transformer and admission boundary.
"""
from __future__ import annotations

import re
from copy import deepcopy

from src.object_taxonomy_v1 import normalize_visible_prose
from src.semantic_replay_v1 import stable_json_hash
from src.source_bound_fields_v2 import (
    FIELDS as V2_FIELDS, FIELD_DESCRIPTIONS, MISSING, TYPE_FIELDS as V2_TYPE_FIELDS,
    bind_fields as bind_v2, evidence_schema as schema_v2,
)

VERSION = "source-bound-fields-v3"
MODE = "semantic-source-bound-v3"
ADMISSION_VERSION = "recommendation-core-admission-v3"
FIELDS = tuple(f for f in V2_FIELDS if f != "actor_of_scope") + (
    "actor_span", "target_group_span", "scope_span",
)
TYPE_FIELDS = {**V2_TYPE_FIELDS, "recommendation": (
    "recommended_action", "action_object_or_goal", "recommendation_evidence_span",
)}
CONTEXT_FIELDS = {
    "actor_span": {"scope"}, "target_group_span": {"target_group"},
    "scope_span": {"scope", "condition", "row_header", "column_header"},
    "condition_span": {"condition"},
}


def evidence_schema(span):
    schema = schema_v2(span)
    template = schema["properties"].pop("actor_of_scope")
    for name, description in {
        "actor_span": "Explicit performing actor, if stated. Never invent an actor for an imperative.",
        "target_group_span": "Literal patient/target group; distinguish it from the performer.",
        "scope_span": "Literal application scope/clinical situation, including an applicable heading.",
    }.items():
        schema["properties"][name] = {**deepcopy(template), "description": description}
    schema["required"] = list(FIELDS)
    schema["properties"]["recommendation_evidence_span"]["description"] = (
        "Entire normative core, including negation and qualifiers, excluding list number and strength stamp. "
        "Do not abbreviate it or omit any clinical words. Necessary lists may be exact context references."
    )
    schema["properties"]["condition_span"]["description"] = (
        "Literal condition in the core or an explicitly supplied condition-role context entry. "
        "An external condition must also be present in context_evidence; proximity alone is insufficient."
    )
    return schema


def bind_fields(raw, *, selected, candidate_text, proposed_type, context=()):
    if not isinstance(raw, dict) or set(raw) != set(FIELDS):
        raise ValueError("source_bound_fields_invalid")
    if normalize_visible_prose(" ".join(s["text"] for s in selected)) != candidate_text:
        raise ValueError("source_bound_candidate_text_mismatch")
    values = {}
    for field, entry in raw.items():
        if not isinstance(entry, dict) or set(entry) != {"span", "missing_reason"}:
            raise ValueError("source_bound_field_invalid")
        owners = list(selected)
        for row in context:
            if (field in CONTEXT_FIELDS and row["role"] in CONTEXT_FIELDS[field]
                    and row["span"] and not row["unresolved_reason"]):
                owners.append({**row["span"], "text": row["text"]})
        # Reuse the established closed span/bounds/literal validator. No free
        # text or offset coercion is accepted by the successor contract.
        legacy_field = field if field in V2_FIELDS else "actor_of_scope"
        legacy = {f: {"span": None, "missing_reason": "not_applicable"} for f in V2_FIELDS}
        legacy[legacy_field] = entry
        corpus = normalize_visible_prose(" ".join(s["text"] for s in owners))
        bound = bind_v2(legacy, selected=owners, candidate_text=corpus, proposed_type=proposed_type)
        if legacy_field in bound["values"]:
            values[field] = bound["values"][legacy_field]
    payload = {"version": VERSION, "candidate_text": candidate_text,
               "proposed_type": proposed_type, "values": values, "evidence": deepcopy(raw),
               "context_hash": stable_json_hash(list(context))}
    return {**payload, "binding_hash": stable_json_hash(payload)}


def bound_values(record, *, text, proposed_type, context=()):
    try:
        return _bound_values(record, text=text, proposed_type=proposed_type, context=context)
    except (KeyError, TypeError) as exc:
        raise ValueError("source_bound_fields_invalid") from exc


def _bound_values(record, *, text, proposed_type, context):
    keys = {"version", "candidate_text", "proposed_type", "values", "evidence", "context_hash", "binding_hash"}
    if not isinstance(record, dict) or set(record) != keys:
        raise ValueError("source_bound_fields_invalid")
    payload = {k: v for k, v in record.items() if k != "binding_hash"}
    if record["version"] != VERSION or stable_json_hash(payload) != record["binding_hash"]:
        raise ValueError("source_bound_fields_invalid")
    if (record["candidate_text"] != text or record["proposed_type"] != proposed_type
            or record["context_hash"] != stable_json_hash(list(context))):
        raise ValueError("source_bound_fields_stale")
    if set(record["evidence"]) != set(FIELDS) or set(record["values"]) - set(FIELDS):
        raise ValueError("source_bound_fields_invalid")
    for field, entry in record["evidence"].items():
        if not isinstance(entry, dict) or set(entry) != {"span", "missing_reason"}:
            raise ValueError("source_bound_field_invalid")
        if entry["span"] is None:
            if entry["missing_reason"] not in MISSING or field in record["values"]:
                raise ValueError("source_bound_fields_invalid")
            continue
        if entry["missing_reason"] is not None or field not in record["values"]:
            raise ValueError("source_bound_fields_invalid")
        span = entry["span"]
        if (not isinstance(span, dict) or set(span) != {"block_id", "start", "end"}
                or not isinstance(span["block_id"], str) or type(span["start"]) is not int
                or type(span["end"]) is not int or not 0 <= span["start"] < span["end"]):
            raise ValueError("source_bound_field_bounds_invalid")
        if field == "type_evidence_spans" and not isinstance(record["values"][field], list):
            raise ValueError("source_bound_fields_invalid")
        literals = record["values"][field] if field == "type_evidence_spans" else [record["values"][field]]
        for literal in literals:
            if not isinstance(literal, str) or not literal:
                raise ValueError("source_bound_field_not_literal")
            if literal not in text and not any(
                row["role"] in CONTEXT_FIELDS.get(field, ()) and row["span"]
                and not row["unresolved_reason"] and literal == normalize_visible_prose(row["text"])
                and entry["span"] == row["span"] for row in context
            ):
                # Context fields can point at a subspan, not necessarily the
                # complete heading. Compare the exact relative literal too.
                valid = False
                for row in context:
                    ref, owner = entry["span"], row["span"]
                    if (row["role"] in CONTEXT_FIELDS.get(field, ()) and owner
                            and not row["unresolved_reason"] and ref["block_id"] == owner["block_id"]
                            and owner["start"] <= ref["start"] < ref["end"] <= owner["end"]):
                        valid |= literal == normalize_visible_prose(row["text"][ref["start"]-owner["start"]:ref["end"]-owner["start"]])
                if not valid:
                    raise ValueError("source_bound_field_not_literal")
    return deepcopy(record["values"])


def recommendation_codes(row, *, context):
    """Conservative source tests, not a proof of clinical truth/completeness."""
    core = str(row.get("recommendation_evidence_span") or "")
    codes = []
    for field in TYPE_FIELDS["recommendation"]:
        if not row.get(field):
            codes.append(f"recommendation_{field}_missing")
    if not core:
        return codes
    action = str(row.get("recommended_action") or "")
    goal = str(row.get("action_object_or_goal") or "")
    if action and action not in core or goal and goal not in core:
        codes.append("recommendation_core_field_mismatch")
    text = str(row.get("candidate_text") or "")
    prefix, found, suffix = text.partition(core)
    # Never hide unselected qualifiers by labelling a short sentence the core.
    strength = (row.get("proposed_recommendation_semantics") or {}).get("strength_evidence_span") or ""
    if not found or (prefix.strip() and not re.fullmatch(r"\d+[.)]", prefix.strip())):
        codes.append("recommendation_core_omits_source")
    if suffix.strip() and suffix.strip() != strength.strip():
        codes.append("recommendation_core_omits_source")
    # A literal imperative may omit its grammatical subject. Do not trust a
    # producer-supplied syntactic flag or infer an actor from general knowledge.
    imperative_text = core
    if re.match(r"^(?:Als|Wanneer|Indien|Bij)\b", core, re.I) and "," in core:
        imperative_text = core.split(",", 1)[1].lstrip()
    imperative = re.match(
        r"^(?:Breng|Overweeg|Gebruik|Stel|Zet|Pas|Evalueer|Consulteer|Wees|Controleer|"
        r"Bespreek|Verwijs|Start|Stop|Vermijd|Houd|Neem|Bied|Adviseer|Beoordeel|Monitor|"
        r"Meet|Geef|Vraag|Onderzoek|Leg|Voorkom|Was|Droog|Mobiliseer|Behandel|Overleg)\b", imperative_text, re.I,
    )
    if not row.get("subject_span") and not imperative:
        codes.append("recommendation_subject_missing")
    if not row.get("predicate_span"):
        codes.append("predicate_missing")
    if re.search(r"\b(?:en|of|geen|niet|bij|met|als|wanneer|tenzij|voor)\s*$", core, re.I):
        codes.append("recommendation_core_incomplete")
    if core.rstrip().endswith(":") and not any(
        r["span"] and not r["unresolved_reason"]
        and (r["role"] == "list_introduction" or (
            r["role"] == "timing" and re.match(r"^\s*[•·*-]\s+\S+\s+\S", r["text"])
        ))
        and normalize_visible_prose(r["text"]) not in core
        and not r["text"].rstrip().endswith(":")
        for r in context
    ):
        codes.append("recommendation_list_missing")
    return codes


def validate_object_fields(obj, fragments):
    """Rebind stored field references from source, including after correction."""
    from src.semantic_passage_v1 import semantic_source_blocks
    from src.object_taxonomy_v1 import extract_object_type
    from src.source_bound_fields_v2 import validated_context
    metadata = obj.get("metadata") or {}
    record = metadata.get("source_bound_fields")
    blocks = {b["block_id"]: b for b in semantic_source_blocks(
        f for f in fragments if extract_object_type(f)[0] != "heading")}
    selected = []
    for span in (metadata.get("semantic_passage") or {}).get("spans") or []:
        block = blocks.get(span["block_id"])
        if not block or not 0 <= span["start"] < span["end"] <= len(block["text"]):
            raise ValueError("source_bound_field_bounds_invalid")
        selected.append({**span, "text": block["text"][span["start"]:span["end"]]})
    context = validated_context(obj, fragments, (obj.get("source") or {}).get("source_checksum"))
    rebuilt = bind_fields(record.get("evidence") if isinstance(record, dict) else None,
        selected=selected, candidate_text=(obj.get("content") or {}).get("clean_text") or "",
        proposed_type=obj.get("proposed_object_type") or "unclassified", context=context)
    if record != rebuilt:
        raise ValueError("source_bound_fields_invalid")


def _scope_present(scope, text):
    """Match a complete literal scope, tolerating case and terminal heading colon.

    Numbers, negation, conditions and word boundaries remain significant.
    """
    scope = normalize_visible_prose(scope).casefold().rstrip(": ")
    text = normalize_visible_prose(text).casefold()
    return bool(scope) and re.search(r"(?<!\w)" + re.escape(scope) + r"(?!\w)", text) is not None


def additional_context_codes(row, realization, *, obj=None, fragments=None):
    """Known scope cues must be realized; absence of cues proves no completeness."""
    core = str(row.get("recommendation_evidence_span") or "")
    realized = realization.get("realized") or []
    codes = []
    entries = []
    if obj is not None and fragments is not None:
        from src.semantic_passage_v1 import semantic_source_blocks
        from src.recommendation_coverage_v1 import inventory
        from src.object_taxonomy_v1 import extract_object_type
        spans = ((obj.get("metadata") or {}).get("semantic_passage") or {}).get("spans") or []
        entries = [item for item in inventory(semantic_source_blocks(
            f for f in fragments if extract_object_type(f)[0] != "heading"))
            if any(s["block_id"] == item["span"]["block_id"]
                and max(s["start"], item["span"]["start"]) < min(s["end"], item["span"]["end"])
                for s in spans)]
    for item in entries:
        cue = item.get("scope_cue")
        if cue and not _scope_present(cue["text"], core) and not any(
            _scope_present(cue["text"], r.get("text") or "")
            and r.get("role") in {"scope", "condition", "exception", "row_header", "column_header"}
            for r in realized
        ):
            codes.append("recommendation_scope_context_missing")
    for heading in row.get("section_path") or []:
        if (re.match(r"^(?:Bij|Als|Wanneer|Indien|Tenzij)\b", heading, re.I)
                or heading.rstrip().endswith(":")):
            if not _scope_present(heading, core) and not any(
                _scope_present(heading, r.get("text") or "")
                and r.get("role") in {"scope", "condition", "exception", "row_header", "column_header"}
                for r in realized
            ):
                codes.append("recommendation_scope_context_missing")
    return codes
