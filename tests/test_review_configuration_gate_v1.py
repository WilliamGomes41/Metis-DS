"""H2 slice 2b-3: de publicatiepoort leest de opgeslagen B10-reviewconfiguratie.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import pytest

from src.four_eyes_v1 import publish_authorization_contract
from src.review_configuration_v1 import CONTRACT
from test_t4_single_knowledge_path_invariants import _allowed_candidate, _allowed_source, _binding, _stamp_hash

UPLOADER = "uploader-anne"


def _config(option, reviewers, *, four_eyes=False, readers=(), source="chosen"):
    return {"contract": CONTRACT, "option": option, "four_eyes_required": four_eyes, "reviewers": list(reviewers),
            "readers": list(readers), "revision": 1, "locked_at": None, "source": source}


def _contract(approvers, configuration, *, uploader_id=UPLOADER, high_risk=False):
    obj = _allowed_candidate()
    if high_risk:
        obj.setdefault("risk", {})["risk_level"] = "high"
        obj["risk"]["requires_second_review"] = True
    obj = _stamp_hash(obj)
    return publish_authorization_contract(
        obj=obj, bindings=[_binding(obj, reviewer) for reviewer in approvers], uploader_id=uploader_id,
        immutable_locator=None, fragments=_allowed_source(), review_configuration=configuration)


@pytest.mark.parametrize("four_eyes", [False, True])
def test_two_others_one_named_reviewer_is_not_done(four_eyes):
    contract = _contract(["rev-a"], _config("two_others", ["rev-a", "rev-b"], four_eyes=four_eyes))
    assert contract["authorization_ok"] is False
    assert "review_configuration_approval_missing" in contract["authorization_blockers"]


@pytest.mark.parametrize("four_eyes", [False, True])
@pytest.mark.parametrize("high_risk", [False, True])
def test_two_others_both_named_reviewers_is_done_without_third_approval(four_eyes, high_risk):
    contract = _contract(["rev-a", "rev-b"], _config("two_others", ["rev-a", "rev-b"], four_eyes=four_eyes),
                         high_risk=high_risk)
    assert contract["authorization_blockers"] == []
    assert contract["authorization_ok"] is True
    assert contract["four_eyes_satisfied"] is True


@pytest.mark.parametrize("four_eyes", [False, True])
def test_two_others_uploader_plus_one_named_reviewer_is_not_done(four_eyes):
    contract = _contract([UPLOADER, "rev-a"], _config("two_others", ["rev-a", "rev-b"], four_eyes=four_eyes))
    assert contract["authorization_ok"] is False
    assert "review_configuration_approval_missing" in contract["authorization_blockers"]


def test_uploader_sole_chosen_uploader_approval_is_done():
    contract = _contract([UPLOADER], _config("uploader_sole", []))
    assert contract["authorization_blockers"] == []
    assert contract["authorization_ok"] is True


def test_uploader_sole_chosen_without_uploader_approval_is_not_done():
    contract = _contract(["rev-a"], _config("uploader_sole", []))
    assert "review_configuration_approval_missing" in contract["authorization_blockers"]


def test_uploader_sole_high_risk_object_still_needs_four_eyes():
    # OPENVRAAG-2b3-1: hoog-risico onder uploader_sole blijft fail-closed.
    contract = _contract([UPLOADER], _config("uploader_sole", []), high_risk=True)
    assert "four_eyes_required" in contract["authorization_blockers"]


def test_one_other_chosen_unconfigured_approver_and_reader_never_count():
    configuration = _config("one_other", ["rev-a"], readers=["reader-x"])
    for approvers in (["reader-x"], ["rev-z"], [UPLOADER]):
        contract = _contract(approvers, configuration)
        assert "review_configuration_approval_missing" in contract["authorization_blockers"], approvers
    assert _contract(["rev-a"], configuration)["authorization_ok"] is True


def test_one_other_chosen_four_eyes_needs_uploader_and_configured_reviewer():
    configuration = _config("one_other", ["rev-a"], four_eyes=True)
    assert "four_eyes_required" in _contract(["rev-a"], configuration)["authorization_blockers"]
    assert "four_eyes_required" in _contract(["rev-a", "rev-z"], configuration)["authorization_blockers"]
    assert _contract([UPLOADER, "rev-a"], configuration)["authorization_ok"] is True


def test_legacy_default_with_two_reviewers_keeps_current_behaviour():
    # OPENVRAAG-2b2-4: legacy met twee reviewers houdt het huidige gedrag (één andere volstaat).
    configuration = _config("one_other", ["rev-a", "rev-b"], source="legacy_default", four_eyes=False)
    assert _contract(["rev-a"], configuration) == _contract(["rev-a"], None)
    assert _contract(["rev-z"], configuration) == _contract(["rev-z"], None)


@pytest.mark.parametrize("uploader_id", ["", "   ", None])
def test_missing_uploader_id_fails_closed_with_own_code(uploader_id):
    contract = _contract(["rev-a"], None, uploader_id=uploader_id)
    assert "uploader_identity_missing" in contract["authorization_blockers"]
    assert contract["authorization_ok"] is False


def _ready_with_envelope(tmp_path, monkeypatch, mutate):
    from tests import test_vsa_publish_readiness_ui_v1 as ready
    console, accounts, receipt, _source = ready._console_with_document(tmp_path)
    ready._complete_review(console, accounts, receipt)
    sid = receipt["snapshot_id"]
    assert console.publication_readiness(sid)["publish_allowed"] is True
    original = console._envelope

    def tampered(snapshot_id, *args, **kwargs):
        envelope = original(snapshot_id, *args, **kwargs)
        mutate(envelope, accounts)
        return envelope

    monkeypatch.setattr(console, "_envelope", tampered)
    return console.publication_readiness(sid)


def test_gate_reads_stored_chosen_configuration(tmp_path, monkeypatch):
    def mutate(envelope, accounts):
        envelope["review_configuration"] = _config("one_other", ["rev-elsewhere"])
    readiness = _ready_with_envelope(tmp_path, monkeypatch, mutate)
    assert readiness["publish_allowed"] is False
    assert "review_configuration_approval_missing" in readiness["blockers"]


def test_gate_refuses_invalid_stored_configuration(tmp_path, monkeypatch):
    def mutate(envelope, accounts):
        envelope["review_configuration"] = {"contract": CONTRACT, "option": "everyone"}
    readiness = _ready_with_envelope(tmp_path, monkeypatch, mutate)
    assert readiness["publish_allowed"] is False
    assert "review_configuration_invalid" in readiness["blockers"]


@pytest.mark.parametrize("value", ["", None])
def test_gate_missing_uploader_id_fails_closed(tmp_path, monkeypatch, value):
    def mutate(envelope, accounts):
        envelope["uploader_account_id"] = value
    readiness = _ready_with_envelope(tmp_path, monkeypatch, mutate)
    assert readiness["publish_allowed"] is False
    assert "uploader_identity_missing" in readiness["blockers"]
