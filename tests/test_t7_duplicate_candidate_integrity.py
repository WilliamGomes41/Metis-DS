"""T7 duplicate occurrences must retain the materialised candidate as a whole.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: opslag durable recovery
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
import hashlib
import json

import pytest

from src.knowledge_materialisation_v1 import materialise_knowledge_candidates
from src.knowledge_path_v1 import content_reviewable, source_lineage_resolves
from src.semantic_passage_v1 import (
    semantic_source_blocks, semantic_units_from_proposal, source_coverage_records,
)
from src.source_occurrence_authority_v1 import prefer_authoritative_exact_occurrences
from tests.test_t7_creator_cut import _fragment

TEXT = "Oedeem is een ophoping van vocht."


def selection_fixture(selected):
    fragments = [_fragment("summary", TEXT), _fragment("primary", TEXT)]
    fragments[0]["section_path"] = ["Richtlijn", "Samenvatting"]
    fragments[1]["section_path"] = ["Richtlijn", "2 Aanbevelingen"]
    blocks = semantic_source_blocks(fragments)
    proposal = {"objects": [
        {"spans": [{"block_id": blocks[i]["block_id"], "start": 0, "end": len(TEXT)}],
         "proposed_object_type": "definition"} for i in selected],
        "relations": [], "abstain_reason": None if selected else "uncertain"}
    decisions = semantic_units_from_proposal(fragments, document_id="doc", proposal=proposal)
    candidates = materialise_knowledge_candidates(decisions, document_id="doc", fragments=fragments)
    coverage = source_coverage_records(fragments, document_id="doc", proposal=proposal)
    return fragments, candidates, coverage


def without_occurrence_evidence(row):
    value = deepcopy(row)
    metadata = value.get("metadata", {})
    metadata.pop("source_occurrence_authority", None)
    if not metadata:
        value.pop("metadata", None)
    return value


@pytest.mark.parametrize("selected", [(0,), (1,), (0, 1)])
@pytest.mark.parametrize("reverse", [False, True])
def test_dedup_preserves_one_existing_materialised_candidate_whole(selected, reverse):
    fragments, candidates, coverage = selection_fixture(selected)
    expected = candidates[-1]  # primary wins only when actually selected
    inputs = candidates + coverage
    before = deepcopy(inputs)
    [actual] = prefer_authoritative_exact_occurrences(list(reversed(inputs)) if reverse else inputs)
    assert without_occurrence_evidence(actual) == expected
    assert inputs == before
    authority = actual["metadata"]["source_occurrence_authority"]
    assert authority["principal_section_role"] == ("primary" if 1 in selected else "summary")
    assert len(authority["alternate_occurrences"]) == 1
    assert actual["source_fragment_ids"] == expected["source_fragment_ids"]
    assert actual["semantic_passage"] == expected["semantic_passage"]
    spans = actual["semantic_passage"]["spans"]
    material = "|".join(f'{s["block_id"]}:{s["start"]}:{s["end"]}' for s in spans)
    assert actual["object_id"] == "doc-sem-" + hashlib.sha256(material.encode()).hexdigest()[:16]
    assert source_lineage_resolves(actual, fragments=fragments)


def test_source_only_duplicates_stay_source_records():
    _, candidates, coverage = selection_fixture(())
    assert candidates == []
    [actual] = prefer_authoritative_exact_occurrences(coverage)
    assert actual["semantic_passage"]["selection_origin"] == "coverage_remainder"
    assert "source_accountability" in actual
    assert actual["source_fragment_ids"] == ["primary"]
    assert not content_reviewable(actual)


def test_dedup_never_transfers_a_binding_from_the_other_candidate():
    from src.integrity_kernel import stamp_canonical_hashes
    from src.review_duty_v1 import exact_current_approver_ids
    fragments, candidates, coverage = selection_fixture((0, 1))
    [chosen] = prefer_authoritative_exact_occurrences(candidates + coverage)
    def canonical(candidate):
        return stamp_canonical_hashes({
            "object_id": candidate["object_id"], "object_version": "1.0",
            "object_type": "definition", "confirmed_object_type": "definition",
            "content": {"clean_text": candidate["clean_text"]},
            "metadata": {"semantic_passage": candidate["semantic_passage"]},
            "governance": {"validation_status": "approved"}, "provenance": {},
        })
    summary, actual = canonical(candidates[0]), canonical(chosen)
    binding = {"valid": True, "decision": "approve", "reviewer_id": "bert",
        "object_id": summary["object_id"], "object_version": summary["object_version"],
        "confirmed_object_type": "definition",
        "canonical_object_hash": summary["provenance"]["canonical_object_hash"]}
    before = deepcopy(binding)
    assert chosen["object_id"] == candidates[1]["object_id"]
    assert exact_current_approver_ids(actual, [binding]) == ()
    assert binding == before


@pytest.mark.parametrize("both", [False, True])
def test_real_ingest_review_and_restart_keep_selected_identity_and_source(tmp_path, both):
    from src.operations_console_v1 import OperationsConsole
    from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing
    from src.object_taxonomy_v1 import extract_object_type
    def console():
        return OperationsConsole(root=tmp_path, source_store=tmp_path / "sources",
                                 runtime=tmp_path / "runtime")
    state = console()
    author = state.create_account(username="anne", password="anne-secret", roles=("researcher",))
    reviewer = state.create_account(username="bert", password="bert-secret", roles=("reviewer",))
    def provider(_url, _headers, payload, _timeout):
        blocks = json.loads(payload["input"][1]["content"])["source_blocks"]
        selected = [b for b in blocks if both or "Samenvatting" in b["section_path"]]
        result = {"objects": [{"spans": [{"block_id": b["block_id"], "start": 0, "end": len(b["text"])}],
                  "proposed_object_type": "definition", "recommendation_semantics": None}
                  for b in selected], "relations": [], "abstain_reason": None}
        return {"output": [{"type": "message", "content": [
            {"type": "output_text", "text": json.dumps(result)}]}]}
    bind_pre_review_semantic_processing(state, environ={
        "METIS_PASSAGE_FORMATION_MODE": "semantic-source-bound-v1",
        "METIS_LLM_API_KEY": "fixture", "METIS_LLM_MODEL": "fixture"},
        post_json=provider)
    html = ("<html><body><h1>Richtlijn</h1><h2>Samenvatting</h2><p>" + TEXT +
            "</p><h2>2 Aanbevelingen</h2><p>" + TEXT + "</p></body></html>").encode()
    receipt = state.ingest(actor_id=author["account_id"], filename="duplicates.html",
        content_type="text/html", data=html, ingest_kind="new", title="Duplicates",
        version="1.0", date="2026-10-07", live_url="", class_="richtlijn",
        family="test", named_reviewers=[reviewer["account_id"]])
    sid = receipt["snapshot_id"]
    rows = state.snapshot_objects(sid)
    [candidate] = [o for o in rows if content_reviewable(o)]
    envelope = state._envelope(sid)
    path, _ = state._verified_source_bytes(envelope)
    fragments = state._read_source_fragments(envelope, path)
    blocks = semantic_source_blocks(f for f in fragments if extract_object_type(f)[0] != "heading")
    chosen = next(b for b in blocks if
                  ("2 Aanbevelingen" if both else "Samenvatting") in b["section_path"])
    span = {"block_id": chosen["block_id"], "start": 0, "end": len(chosen["text"])}
    assert candidate["metadata"]["semantic_passage"]["spans"] == [span]
    digest = hashlib.sha256(f'{span["block_id"]}:0:{span["end"]}'.encode()).hexdigest()[:16]
    assert candidate["object_id"] == envelope["document_id"] + "-sem-" + digest
    assert [r["raw_object_id"] for r in candidate["provenance"]["source_fragments"]] == chosen["source_fragment_ids"]
    assert source_lineage_resolves(candidate, fragments=fragments)
    state.review_object(actor_id=reviewer["account_id"], snapshot_id=sid,
        object_id=candidate["object_id"], decision="approve", confirmed_object_type="definition")
    stored_rows = state.snapshot_objects(sid)
    stored_bindings = state.object_review_bindings(sid)
    restored = console()
    assert restored.snapshot_objects(sid) == stored_rows
    assert restored.object_review_bindings(sid) == stored_bindings
    assert any(b["valid"] and b["object_id"] == candidate["object_id"] for b in stored_bindings)
