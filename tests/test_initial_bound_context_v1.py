"""Initial source tasks preserve exact parent context without duplicating it.

Synthetic source examples exercise the real producer/materialiser/Admission
chain. They are regression evidence, not a clinical quality acceptance set.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: beschikbaarheid
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json

import pytest

from src.vorming.admission_gate_v1 import apply_admission_gate
from src.vorming.pre_review_semantic_v1 import semantic_spec_from_fragments
from src.vorming.semantic_transform_generic_v1 import transform
from tests.test_recommendation_context_v3 import response_for, source


PARENT = "Overweeg maatregelen uit Tabel 1."
TABLE = "Houd de huid droog."
SUFFIX = "Controleer dagelijks de huid."
INDEPENDENT = "Mobiliseer dagelijks."


def _run(*, partial=False, context_status="bound"):
    table_text = TABLE + (" " + SUFFIX if partial else "")
    fragments = [
        dict(source(text)[0], fragment_id=f"source-{index}",
             fragment_hash=f"hash-{index}", section_path=path)
        for index, (text, path) in enumerate([
            (PARENT, ["Module", "Aanbevelingen"]),
            (table_text, ["Module", "Tabel 1"]),
            (INDEPENDENT, ["Andere module", "Aanbevelingen"]),
        ])
    ]
    fragments.insert(1, dict(source("Tabel 1")[0], fragment_id="table-heading",
                             fragment_hash="table-heading-hash", object_type="heading", heading="Tabel 1",
                             section_path=["Module", "Tabel 1"]))
    requests, checkpoints = [], []

    def provider(_url, _headers, payload, _timeout):
        data = json.loads(payload["input"][1]["content"])
        requests.append(data)
        ranges = data["formation_task"]["selectable_ranges"]
        by_id = {block["block_id"]: block for block in data["source_blocks"]}
        literals = [by_id[ref["block_id"]]["text"][ref["start"]:ref["end"]].strip()
                    for ref in ranges]
        # Follow the actual selectable ranges rather than guessing source from
        # the visible full block. This also exercises a partially consumed block.
        selected = literals[0]
        proposal = response_for(payload, selected)
        if selected == PARENT:
            owner = next(block for block in data["evidence_blocks"]
                         if block["text"] == table_text)
            literal = TABLE if partial else table_text
            if context_status == "rejected":
                literal = "Niet aanwezige brontekst."
            proposal["objects"][0]["context_evidence"] = [{
                "role": "support",
                "span": {"block_id": owner["block_id"], "literal": literal,
                         "occurrence": None},
                "unresolved_reason": "relation_uncertain" if context_status == "unresolved" else None,
            }]
        return {"status": "completed", "output": [{"type": "message", "content": [{
            "type": "output_text", "text": json.dumps(proposal),
        }]}]}

    spec = semantic_spec_from_fragments(
        document_id="initial-context", title="Synthetic guideline", family="test",
        class_="richtlijn", fragments=fragments, content_kind="html", api_key="test",
        model="test", post_json=provider, field_contract_v3=True,
        formation_context={"snapshot_id": "snap-initial-context", "source_sha256": "a" * 64,
                           "diagnostic_checkpoint": lambda phase, values: checkpoints.append((phase, values))},
    )
    manifest = {"canonical_source": {
        "source_id": "source", "title": "Synthetic guideline", "source_type": "html",
        "source_url": "test", "source_level": "national", "canonicality": "canonical",
        "integrity_status": "verified", "source_checksum": "a" * 64, "version": "1",
    }}
    rows = apply_admission_gate(
        transform(spec, manifest, fragments), klasse="richtlijn", fragments=fragments,
        document_version="1", source_hash="a" * 64,
    )
    candidates = [row for row in rows if row.get("metadata", {}).get("source_bound_fields")]
    evidence = next(values["provider_evidence"] for phase, values in reversed(checkpoints)
                    if phase == "formation_accounted")
    return candidates, requests, evidence


def test_initial_table_context_is_retained_on_parent_without_a_second_candidate():
    candidates, requests, evidence = _run()
    assert [row["content"]["clean_text"] for row in candidates] == [PARENT, INDEPENDENT]
    parent = candidates[0]
    entries = parent["metadata"]["source_bound_context"]["entries"]
    assert [(entry["role"], entry["text"]) for entry in entries] == [("support", TABLE)]
    assert entries[0]["source_refs"][0]["fragment_id"] == "source-1"
    assert parent["metadata"]["admission"]["gate_result"] == "allowed"
    assert candidates[1]["metadata"]["admission"]["gate_result"] == "allowed"
    assert [data["source_blocks"][0]["text"] for data in requests] == [PARENT, INDEPENDENT]
    assert evidence["formation_progress"]["planned_task_count"] == 3
    assert evidence["formation_progress"]["terminal_task_count"] == 3
    assert evidence["formation_progress"]["pending_task_count"] == 0


def test_initial_partial_context_keeps_the_unconsumed_suffix_selectable():
    candidates, requests, _ = _run(partial=True)
    assert [row["content"]["clean_text"] for row in candidates] == [PARENT, SUFFIX, INDEPENDENT]
    table_request = next(data for data in requests
                         if data["source_blocks"][0]["text"] == TABLE + " " + SUFFIX)
    selected = table_request["formation_task"]["selectable_ranges"]
    assert [(span["start"], span["end"]) for span in selected] == [(len(TABLE), len(TABLE + " " + SUFFIX))]
    parent_context = candidates[0]["metadata"]["source_bound_context"]["entries"]
    assert [entry["text"] for entry in parent_context] == [TABLE]
    assert candidates[1]["metadata"]["admission"]["gate_result"] == "allowed"


@pytest.mark.parametrize("context_status", ["unresolved", "rejected"])
def test_unresolved_or_rejected_parent_context_does_not_consume_the_table(context_status):
    candidates, requests, _ = _run(context_status=context_status)
    by_text = {row["content"]["clean_text"]: row for row in candidates}
    assert TABLE in by_text and INDEPENDENT in by_text
    assert by_text[TABLE]["metadata"]["admission"]["gate_result"] == "allowed"
    assert by_text[INDEPENDENT]["metadata"]["admission"]["gate_result"] == "allowed"
    table_request = next(data for data in requests if data["source_blocks"][0]["text"] == TABLE)
    assert [(span["start"], span["end"]) for span in table_request["formation_task"]["selectable_ranges"]] == [(0, len(TABLE))]
    if context_status == "unresolved":
        assert by_text[PARENT]["metadata"]["admission"]["gate_result"] == "blocked"
        assert "context_necessary_unresolved" in by_text[PARENT]["metadata"]["admission"]["reason_codes"]
    else:
        assert PARENT not in by_text
