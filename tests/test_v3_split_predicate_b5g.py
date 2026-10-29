"""B5-g: a split Dutch verb cluster is one contiguous predicate literal.

# release-control-evidence: scope/belofte
# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import pytest

from src.vorming.semantic_passage_v1 import SemanticPassageError
from src.vorming.source_evidence_resolution_v1 import resolve_proposal_evidence
from src.vorming.source_bound_fields_v2 import evidence_schema as schema_v2
from src.vorming.source_bound_fields_v3 import evidence_schema as schema_v3
from tests.test_recommendation_context_v3 import prepare

TEXT = "De huid wordt dagelijks gecontroleerd."


def span():
    return {"block_id": "b", "literal": "x", "occurrence": None, "start": 0, "end": 1}


def test_v3_schema_asks_for_one_contiguous_predicate():
    v3 = schema_v3(span())["properties"]["predicate_span"]["description"]
    assert "contiguous" in v3 and "words between" in v3
    assert "contiguous" not in schema_v2(span())["properties"]["predicate_span"]["description"]


def with_predicate(literal):
    def mutate(p):
        fields = p["objects"][0]["field_evidence"]
        block = p["objects"][0]["spans"][0]["block_id"]
        fields["predicate_span"] = {"span": {"block_id": block, "literal": literal, "occurrence": None},
                                    "missing_reason": None}
        fields["subject_span"] = {"span": {"block_id": block, "literal": "De huid", "occurrence": None},
                                  "missing_reason": None}
    return mutate


def test_contiguous_cluster_with_words_between_is_kept_literally():
    _, _, obj, _ = prepare(TEXT, mutate=with_predicate("wordt dagelijks gecontroleerd"))
    assert obj["metadata"]["admission"]["predicate_span"] == "wordt dagelijks gecontroleerd"
    assert "predicate_missing" not in obj["metadata"]["admission"]["reason_codes"]


def test_verb_parts_without_the_words_between_stay_rejected():
    # No multi-span predicate: the omitted words keep the literal unresolvable.
    _, _, obj, _ = prepare(TEXT, mutate=with_predicate("wordt gecontroleerd"), allow_empty=True)
    assert obj is None
    ref = {"block_id": "b", "literal": "wordt gecontroleerd", "occurrence": None}
    proposal = {"objects": [{"field_evidence": {"predicate_span": {"span": ref}}}]}
    blocks = [{"block_id": "b", "text": TEXT}]
    with pytest.raises(SemanticPassageError, match="semantic_evidence_literal_not_found"):
        resolve_proposal_evidence(proposal, blocks=blocks, evidence_blocks=blocks, field_contract_v3=True)
