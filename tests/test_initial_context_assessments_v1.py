"""Source-use narrowing preserves the existing unresolved-source recovery pass.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: recovery
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json

from src.vorming.pre_review_semantic_v1 import _semantic_execution_before_review
from tests.test_recommendation_context_v3 import response_for, source


def test_unresolved_assessment_is_retried_while_metadata_stays_source_only():
    advice = "Controleer dagelijks de huid."
    metadata = "Versie: 1.0"
    fragments = [
        dict(source(text)[0], fragment_id=str(index), fragment_hash=f"hash-{index}",
             section_path=["Advies" if index == 0 else "Documentgegevens"])
        for index, text in enumerate((advice, metadata))
    ]
    requests = []

    def provider(_url, _headers, payload, _timeout):
        data = json.loads(payload["input"][1]["content"])
        requests.append(data)
        if data["formation_task"]["phase"] == "initial":
            block = data["source_blocks"][0]
            answer = {"objects": [], "relations": [], "abstain_reason": None,
                      "source_assessments": [{
                          "span": {"block_id": block["block_id"], "literal": advice, "occurrence": None},
                          "role": "unresolved", "reason": "unformed_meaning",
                      }]}
        else:
            answer = response_for(payload, advice)
        return {"output": [{"type": "message", "content": [
            {"type": "output_text", "text": json.dumps(answer)},
        ]}]}

    units, replay = _semantic_execution_before_review(
        fragments, document_id="assessment-recovery", api_key="test", model="test",
        post_json=provider, field_contract_v3=True,
        formation_context={"snapshot_id": "assessment-snapshot", "source_sha256": "a" * 64},
    )
    assert [data["formation_task"]["phase"] for data in requests] == ["initial", "recovery"]
    assert [[block["text"] for block in data["source_blocks"]] for data in requests] == [[advice], [advice]]
    selected = [unit for unit in units
                if unit.get("semantic_passage", {}).get("selection_origin") == "proposal_selected"]
    assert [(unit["text"], unit["proposed_object_type"]) for unit in selected] == [(advice, "recommendation")], units
    assert metadata in [unit["text"] for unit in units]
    assessments = replay["proposal"]["source_assessments"]
    assert [(row["role"], row["reason"]) for row in assessments] == [("metadata", "document_metadata")]
