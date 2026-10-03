"""Actual producer -> transform -> admission -> review/export contract.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json
from copy import deepcopy

import pytest

from src.pre_review_semantic_v1 import semantic_spec_from_fragments
from src.semantic_transform_generic_v1 import transform
from src.admission_gate_v1 import apply_admission_gate
from src.source_bound_fields_v3 import FIELDS, VERSION, MODE
from src.semantic_replay_v1 import stable_json_hash


def source(text, heading=None):
    path = ["Aanbevelingen"] + ([heading] if heading else [])
    rows = [{"fragment_id": "core", "fragment_hash": "core-hash", "raw_text": text,
             "clean_text": text, "section_path": path,
             "source_locator": {"locator_type": "web_line_range", "locator_value": "lines:2-2"}}]
    if heading:
        rows.insert(0, {"fragment_id": "heading", "fragment_hash": "heading-hash",
            "raw_text": heading, "clean_text": heading, "object_type": "heading",
            "section_path": path, "source_locator": {"locator_type": "web_line_range", "locator_value": "lines:1-1"}})
    return rows


def response_for(payload, text, *, heading=None, include_context=True, stamp=None):
    data = json.loads(payload["input"][1]["content"])
    block = next(b for b in data["source_blocks"] if text in b["text"])
    def ref(literal, owner=block):
        return {"block_id": owner["block_id"], "literal": literal, "occurrence": None}
    fields = {field: {"span": None, "missing_reason": "not_applicable"} for field in FIELDS}
    fields["subject_span"] = fields["actor_span"] = {"span": None, "missing_reason": "not_stated"}
    core = text.removesuffix(" " + stamp) if stamp else text
    for field, literal in {"predicate_span": core.split()[0], "type_evidence_spans": core.split()[0],
                           "recommended_action": core, "action_object_or_goal": core.split()[-1],
                           "recommendation_evidence_span": core}.items():
        fields[field] = {"span": ref(literal), "missing_reason": None}
    context = []
    if heading and include_context:
        owner = next(b for b in data["evidence_blocks"] if b["text"] == heading)
        context = [{"role": "condition", "span": ref(heading, owner), "unresolved_reason": None}]
        fields["scope_span"] = {"span": ref(heading, owner), "missing_reason": None}
    against = "geen" in core
    semantics = {"direction": "against" if against else "for", "direction_evidence": ref(core),
        "strength": "strong" if stamp else None, "strength_status": "explicit" if stamp else "not_stated",
        "strength_evidence": ref(stamp) if stamp else None}
    return {"objects": [{"spans": [ref(text)], "proposed_object_type": "recommendation",
        "recommendation_semantics": semantics, "field_evidence": fields, "context_evidence": context}],
        "relations": [], "abstain_reason": None}


def prepare(text="Gebruik geen zalf", *, heading=None, include_context=True, stamp=None, mutate=None, fragments=None):
    fragments = fragments if fragments is not None else source(text, heading)
    def provider(_url, _headers, payload, _timeout):
        proposal = response_for(payload, text, heading=heading, include_context=include_context, stamp=stamp)
        if mutate:
            mutate(proposal)
        return {"status": "completed", "output": [{"type": "message", "content": [
            {"type": "output_text", "text": json.dumps(proposal)}]}]}
    spec = semantic_spec_from_fragments(document_id="doc", title="Test", family="test", class_="richtlijn",
        fragments=fragments, content_kind="html", api_key="test", model="test", post_json=provider,
        field_contract_v3=True)
    manifest = {"canonical_source": {"source_id": "source", "title": "Test", "source_type": "html",
        "source_url": "test", "source_level": "national", "canonicality": "canonical",
        "integrity_status": "verified", "source_checksum": "a"*64, "version": "1"}}
    rows = transform(spec, manifest, fragments)
    rows = apply_admission_gate(rows, klasse="richtlijn", fragments=fragments, document_version="1", source_hash="a"*64)
    obj = next(o for o in rows if (o.get("metadata") or {}).get("source_bound_fields"))
    return spec, rows, obj, fragments


@pytest.mark.parametrize("text", ["Gebruik geen zalf", "Mobiliseer dagelijks", "Gebruik geen zalf."])
def test_literal_imperative_without_actor_or_terminal_punctuation(text):
    _, _, obj, _ = prepare(text)
    admission = obj["metadata"]["admission"]
    assert admission["gate_result"] == "allowed", admission["reason_codes"]
    assert admission["actor_span"] == "" and admission["subject_span"] == ""
    assert obj["metadata"]["source_bound_fields"]["version"] == VERSION
    assert obj["metadata"]["semantic_passage"]["formation_mode"] == MODE
    assert obj["governance"]["validation_status"] == "needs_review"


def test_strength_metadata_does_not_make_a_complete_core_incomplete():
    _, _, obj, _ = prepare("Gebruik geen zalf. Sterk – tegen", stamp="Sterk – tegen")
    assert obj["metadata"]["admission"]["gate_result"] == "allowed"
    assert obj["metadata"]["admission"]["recommendation_evidence_span"] == "Gebruik geen zalf."


def test_conditional_imperative_keeps_condition_without_inventing_actor():
    text = "Als de klachten toenemen, bespreek de voorkeuren"
    def mutate(proposal):
        fields = proposal["objects"][0]["field_evidence"]
        fields["predicate_span"]["span"]["literal"] = "bespreek"
        fields["type_evidence_spans"]["span"]["literal"] = "bespreek"
    _, _, obj, _ = prepare(text, mutate=mutate)
    admission = obj["metadata"]["admission"]
    assert admission["gate_result"] == "allowed", admission["reason_codes"]
    assert admission["recommendation_evidence_span"] == text
    assert admission["actor_span"] == ""


def test_external_scope_is_bound_revalidated_and_visible_in_review_export():
    heading = "Bij een natte plek:"
    _, rows, obj, _ = prepare(heading=heading)
    a = obj["metadata"]["admission"]
    assert a["gate_result"] == "allowed", a["reason_codes"]
    assert a["scope_span"] == heading
    from src.operations_console_app import _knowledge_review_html, _source_bound_fields_html
    assert heading in _knowledge_review_html(obj, rows)
    assert heading in _source_bound_fields_html(obj)
    from src.processing_evidence_export_v1 import processing_evidence_tables
    tables, _ = processing_evidence_tables(snapshot_id="snap", revision="r", envelope={}, objects=rows)
    field = next(r for r in tables["proposal_fields"] if r["object_id"] == obj["object_id"] and r["field"] == "scope_span")
    assert field["value"] == heading and field["producer_status"] == "source_bound_proposal"


def test_known_heading_condition_missing_from_proposal_stays_blocked():
    _, _, obj, _ = prepare(heading="Bij een natte plek:", include_context=False)
    assert obj["metadata"]["admission"]["gate_result"] == "blocked"
    assert "recommendation_scope_context_missing" in obj["metadata"]["admission"]["reason_codes"]


def test_incomplete_action_stays_blocked_even_without_punctuation_requirement():
    _, _, obj, _ = prepare("Gebruik geen")
    assert "recommendation_core_incomplete" in obj["metadata"]["admission"]["reason_codes"]


def test_short_core_cannot_hide_source_qualifiers():
    def mutate(p):
        ref = p["objects"][0]["field_evidence"]["recommendation_evidence_span"]["span"]
        ref["literal"] = "Gebruik geen zalf"
    _, _, obj, _ = prepare("Gebruik geen zalf bij kwetsbare patiënten", mutate=mutate)
    assert "recommendation_core_omits_source" in obj["metadata"]["admission"]["reason_codes"]


def test_field_offsets_are_rebound_even_if_attacker_recomputes_binding_hash():
    _, rows, obj, fragments = prepare()
    altered = deepcopy(rows)
    target = next(o for o in altered if o["object_id"] == obj["object_id"])
    bound = target["metadata"]["source_bound_fields"]
    bound["evidence"]["recommended_action"]["span"]["end"] = 999
    bound["binding_hash"] = stable_json_hash({k: v for k, v in bound.items() if k != "binding_hash"})
    gated = apply_admission_gate(altered, klasse="richtlijn", fragments=fragments, document_version="1", source_hash="a"*64)
    assert next(o for o in gated if o["object_id"] == obj["object_id"])["metadata"]["admission"]["gate_result"] == "blocked"


def test_stale_context_invalidates_the_source_bound_fields():
    _, rows, obj, fragments = prepare(heading="Bij een natte plek:")
    changed = deepcopy(rows)
    target = next(o for o in changed if o["object_id"] == obj["object_id"])
    target["metadata"]["source_bound_context"]["entries"][0]["text"] = "Andere situatie"
    gated = apply_admission_gate(changed, klasse="richtlijn", fragments=fragments, document_version="1", source_hash="a"*64)
    assert next(o for o in gated if o["object_id"] == obj["object_id"])["metadata"]["admission"]["gate_result"] == "blocked"


def test_deleting_coverage_metadata_cannot_hide_unstructured_source_scope():
    fragments = [{**source("Bij een natte plek:")[0], "fragment_id": "scope", "fragment_hash": "scope-hash"},
                 source("Gebruik geen zalf")[0]]
    _, rows, obj, _ = prepare(fragments=fragments)
    changed = deepcopy(rows)
    target = next(o for o in changed if o["object_id"] == obj["object_id"])
    target["metadata"].pop("recommendation_coverage", None)
    gated = apply_admission_gate(changed, klasse="richtlijn", fragments=fragments, document_version="1", source_hash="a"*64)
    admission = next(o for o in gated if o["object_id"] == obj["object_id"])["metadata"]["admission"]
    assert "recommendation_scope_context_missing" in admission["reason_codes"]


def test_scope_context_cannot_substitute_for_announced_list_items():
    _, _, obj, _ = prepare("Gebruik de volgende maatregelen:", heading="Bij een natte plek:")
    assert "recommendation_list_missing" in obj["metadata"]["admission"]["reason_codes"]
