"""Boundaries for skipping exact context during initial candidate selection.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: beschikbaarheid
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json
from functools import partial

import pytest

from src.vorming import bounded_formation_v1 as formation
from src.vorming.bounded_model_call_v1 import ModelCallLimits
from src.vorming.pre_review_semantic_v1 import _provider_proposal
from src.vorming.semantic_passage_v1 import semantic_source_blocks
from tests.test_recommendation_context_v3 import response_for, source


PARENT = "Overweeg maatregelen uit Tabel 1."
TABLE = "Houd de huid droog."
SUFFIX = "Controleer dagelijks de huid."
OTHER = "Mobiliseer dagelijks."


def _execute(monkeypatch, *, suffix="", exhaust=False):
    table_text = TABLE + suffix
    fragments = [
        dict(source(text)[0], fragment_id=f"limit-source-{index}", fragment_hash=f"limit-hash-{index}",
             section_path=path)
        for index, (text, path) in enumerate([
            (PARENT, ["Module", "Aanbevelingen"]),
            (table_text, ["Module", "Tabel 1"]),
            (OTHER, ["Andere module", "Aanbevelingen"]),
        ])
    ]
    fragments.insert(1, dict(source("Tabel 1")[0], fragment_id="limit-table-heading",
                             fragment_hash="limit-table-heading-hash", object_type="heading",
                             heading="Tabel 1", section_path=["Module", "Tabel 1"]))
    evidence_blocks = semantic_source_blocks(fragments)
    blocks = semantic_source_blocks([fragment for fragment in fragments
                                     if fragment.get("object_type") != "heading"])
    validator = {"document_id": "limit-check", "fragments": fragments,
                 "evidence_fragments": fragments, "field_contract_v3": True,
                 "allowed_candidate_block_ids": [block["block_id"] for block in blocks]}
    clock = [0.0]
    monkeypatch.setattr(formation.time, "monotonic", lambda: clock[0])
    requests = []

    def transport(_url, _headers, payload, _timeout):
        data = json.loads(payload["input"][1]["content"])
        requests.append(data)
        ref = data["formation_task"]["selectable_ranges"][0]
        owner = next(block for block in data["source_blocks"] if block["block_id"] == ref["block_id"])
        selected = owner["text"][ref["start"]:ref["end"]].strip()
        proposal = response_for(payload, selected)
        if selected == PARENT:
            table = next(block for block in data["evidence_blocks"] if block["text"] == table_text)
            proposal["objects"][0]["context_evidence"] = [{"role": "support", "span": {
                "block_id": table["block_id"], "literal": TABLE, "occurrence": None,
            }, "unresolved_reason": None}]
        return {"status": "completed", "output": [{"type": "message", "content": [{
            "type": "output_text", "text": json.dumps(proposal),
        }]}]}

    native_provider = partial(_provider_proposal, api_key="test", model="test",
                              post_json=transport, field_contract_v3=True)

    def provider(**kwargs):
        result = native_provider(**kwargs)
        if exhaust:
            # Expire the overall formation budget after the first fully resolved
            # provider result; no transport timeout or sleep is involved.
            clock[0] = 20.0
        return result

    proposal, evidence = formation.execute(
        blocks=blocks, evidence_blocks=evidence_blocks, validator_input=validator,
        provider=provider, limits=ModelCallLimits(total=10),
    )
    table_id = next(block["block_id"] for block in blocks if block["text"] == table_text)
    other_id = next(block["block_id"] for block in blocks if block["text"] == OTHER)
    return proposal, evidence, requests, table_id, other_id


@pytest.mark.parametrize("suffix", ["", " " + SUFFIX])
def test_budget_exhaustion_records_only_unconsumed_source(monkeypatch, suffix):
    proposal, evidence, requests, table_id, other_id = _execute(
        monkeypatch, suffix=suffix, exhaust=True,
    )
    assert [request["source_blocks"][0]["text"] for request in requests] == [PARENT]
    assert len(proposal["objects"]) == 1
    calls = [evidence, *evidence.get("supplementary_calls", [])]
    pending = [call for call in calls if call.get("error_code") == "source_task_budget_exhausted"]
    expected = ([{"block_id": table_id, "start": len(TABLE), "end": len(TABLE + suffix)}]
                if suffix else [])
    expected.append({"block_id": other_id, "start": 0, "end": len(OTHER)})
    assert [span for call in pending for span in call["target_spans"]] == expected
    progress = evidence["formation_progress"]
    assert progress["planned_task_count"] == 3
    assert progress["terminal_task_count"] == (1 if suffix else 2)
    assert progress["pending_task_count"] == (2 if suffix else 1)
    assert progress["pending_source_char_count"] == len(OTHER) + len(suffix)


def test_whitespace_only_remainder_is_omitted_but_independent_text_is_retained():
    from src.vorming.recommendation_task_plan_v1 import narrow_task

    def task_for(text):
        block = {"block_id": "table", "text": text, "position": 2}
        return {"task_id": "original", "source_blocks": [block], "evidence_blocks": [],
                "target_spans": [{"block_id": "table", "start": 0, "end": len(text)}]}

    whitespace = TABLE + " \n\t "
    task = task_for(whitespace)
    assert narrow_task(task, [{"block_id": "table", "start": len(TABLE),
                               "end": len(whitespace)}]) is None
    independent = TABLE + " " + SUFFIX
    task = task_for(independent)
    refs = [{"block_id": "table", "start": len(TABLE), "end": len(independent)}]
    remaining = narrow_task(task, refs)
    assert remaining["target_spans"] == refs
    assert remaining["source_blocks"] == [{"block_id": "table", "text": independent, "position": 2}]
    assert remaining["evidence_blocks"] == []
    assert task["target_spans"] == [{"block_id": "table", "start": 0, "end": len(independent)}]
