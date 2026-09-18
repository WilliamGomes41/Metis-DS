import pytest

from src.abstain_catalog_v1 import ABSTAIN_REASONS, SENTENCES, sentence_for


def test_public_abstain_catalog_is_closed_and_nonempty():
    assert ABSTAIN_REASONS == frozenset(SENTENCES)
    assert all(reason and sentence.strip() for reason, sentence in SENTENCES.items())


def test_protocol_required_public_reasons_are_present():
    required = {
        "empty_published_corpus",
        "required_concept_not_present",
        "required_relation_not_present",
        "structured_constraint_mismatch",
        "patient_specific_context_not_available",
        "conflicting_evidence",
        "below_confidence_threshold",
        "version_context_not_satisfied",
    }
    assert required <= ABSTAIN_REASONS


def test_unknown_public_abstain_reason_fails_fast():
    with pytest.raises(ValueError, match="unknown_abstain_reason:not_a_real_reason"):
        sentence_for("not_a_real_reason")
