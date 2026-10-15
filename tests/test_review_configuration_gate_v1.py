"""H2 slice 2b-3: de publicatiepoort leest de opgeslagen B10-reviewconfiguratie.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from copy import deepcopy

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


# --- Review #631 ---------------------------------------------------------------

def _readiness_with_bindings(tmp_path, configuration, rows):
    """A: console-onafhankelijkheid zonder goedgekeurd object (alleen de console-poort beslist)."""
    from tests import test_vsa_publish_readiness_ui_v1 as ready
    console, accounts, receipt, _source = ready._console_with_document(tmp_path)
    sid = receipt["snapshot_id"]
    envelope = console._envelope(sid)
    bert = accounts["reviewer"]["account_id"]
    envelope["review_configuration"] = configuration(bert)
    objects = console.snapshot_objects(sid)
    target = next(obj for obj in objects if obj.get("object_type") != "document")
    bindings = [{"valid": True, "decision": "approve", "object_id": target["object_id"], "reviewer_id": bert,
                 **row} for row in rows]
    return console.technical_publication_readiness(snapshot_id=sid, envelope=envelope, objects=objects,
                                                   bindings=bindings)


@pytest.mark.parametrize(("name", "configuration", "rows"), [
    ("two_others_one_of_two", lambda bert: _config("two_others", [bert, "rev-elsewhere"]), [{}]),
    ("reject_binding", lambda bert: _config("one_other", [bert]), [{"decision": "reject"}]),
    ("invalid_binding", lambda bert: _config("one_other", [bert]), [{"valid": False}]),
    ("unknown_object", lambda bert: _config("one_other", [bert]), [{"object_id": "elders"}]),
])
def test_console_independence_uses_configured_approval_over_eligible_reviewers(tmp_path, name, configuration, rows):
    readiness = _readiness_with_bindings(tmp_path, configuration, rows)
    assert readiness["independence_satisfied"] is False, name
    assert readiness["publish_allowed"] is False, name
    assert "second_named_reviewer_required" in readiness["blockers"], name


def test_console_independence_not_met_with_open_objects_or_without_source_text(tmp_path):
    # A2 (Metis optie b): open objecten tellen mee; zonder brontekst MOET de check dicht.
    readiness = _readiness_with_bindings(tmp_path, lambda bert: _config("one_other", [bert]), [{}])
    assert readiness["independence_satisfied"] is False


def test_uploader_sole_high_risk_object_is_refused_with_dutch_message():
    # OPENVRAAG-2b3-1: hoe een tweede reviewer wordt toegevoegd, beslist William.
    from src.operations_console_app import BLOCKER_LABELS
    contract = _contract([UPLOADER], _config("uploader_sole", []), high_risk=True)
    assert contract["authorization_ok"] is False
    assert "review_configuration_uploader_sole_high_risk" in contract["authorization_blockers"]
    message = BLOCKER_LABELS["review_configuration_uploader_sole_high_risk"]
    assert "hoog-risico" in message and "tweede benoemde reviewer" in message
    assert "review_configuration_uploader_sole_high_risk" not in _contract(
        [UPLOADER], _config("uploader_sole", []))["blockers"]


@pytest.mark.parametrize("uploader_id", ["", "   "])
def test_validate_configuration_refuses_blank_uploader(uploader_id):
    from src.review_configuration_v1 import validate_configuration
    with pytest.raises(ValueError) as error:
        validate_configuration(_config("one_other", ["rev-a"]), uploader_id=uploader_id)
    assert str(error.value) == "uploader_identity_missing"


# --- Review #631 A2 (Metis optie b) en punt 2 --------------------------------------

def _harness(tmp_path):
    from tests import test_vsa_publish_readiness_ui_v1 as ready
    console, accounts, receipt, _source = ready._console_with_document(tmp_path)
    return ready, console, accounts, receipt["snapshot_id"], receipt


def test_console_independence_counts_open_content_object(tmp_path):
    ready, console, accounts, sid, _ = _harness(tmp_path)
    bert = accounts["reviewer"]["account_id"]
    first, second = [o for o in console.snapshot_objects(sid) if o.get("object_type") == "unclassified"][:2]
    console.review_object(actor_id=bert, snapshot_id=sid, object_id=first["object_id"], decision="approve",
                          confirmed_object_type="explanation")
    envelope = console._envelope(sid)
    envelope["review_configuration"] = _config("one_other", [bert])
    readiness = console.technical_publication_readiness(snapshot_id=sid, envelope=envelope)
    assert readiness["independence_satisfied"] is False
    assert "second_named_reviewer_required" in readiness["blockers"]
    assert readiness["publish_allowed"] is False


def test_fully_reviewed_fixture_with_chosen_configuration_stays_publishable(tmp_path, monkeypatch):
    def mutate(envelope, accounts):
        envelope["review_configuration"] = _config("one_other", [accounts["reviewer"]["account_id"]])
    readiness = _ready_with_envelope(tmp_path, monkeypatch, mutate)
    assert readiness["independence_satisfied"] is True
    assert readiness["publish_allowed"] is True, readiness["blockers"]


def _participation(console, accounts, sid, reviewer_id):
    return console.manage_review_participation(
        actor_id=accounts["publisher"]["account_id"], snapshot_id=sid, action="add_required",
        reviewer_id=reviewer_id, reason="Extra reviewer", command_id="cmd-deelname",
        expected_revision=console.objects_revision(sid))


@pytest.mark.parametrize("option", ["uploader_sole", "one_other"])
def test_chosen_configuration_wins_over_participation_policy(tmp_path, monkeypatch, option):
    from src.operations_console_v1 import ConsoleError
    ready, console, accounts, sid, receipt = _harness(tmp_path)
    ready._complete_review(console, accounts, receipt)
    extra = console.create_account(username="extra.dirk", password=ready.TEST_PASSWORD, roles=("reviewer",))["account_id"]
    bert = accounts["reviewer"]["account_id"]
    chosen = _config(option, [] if option == "uploader_sole" else [bert])
    original = console._envelope

    def with_choice(snapshot_id, *args, **kwargs):
        envelope = original(snapshot_id, *args, **kwargs)
        envelope["review_configuration"] = deepcopy(chosen)
        return envelope

    monkeypatch.setattr(console, "_envelope", with_choice)
    with pytest.raises(ConsoleError) as error:
        _participation(console, accounts, sid, extra)
    assert error.value.code == "review_configuration_chosen_wins"
    assert console._envelope(sid).get("review_policy") is None


def test_legacy_document_participation_unchanged(tmp_path):
    ready, console, accounts, sid, receipt = _harness(tmp_path)
    ready._complete_review(console, accounts, receipt)
    assert console._envelope(sid)["review_configuration"]["source"] == "legacy_default"
    extra = console.create_account(username="extra.dirk", password=ready.TEST_PASSWORD, roles=("reviewer",))["account_id"]
    _participation(console, accounts, sid, extra)
    assert extra in console._envelope(sid)["named_reviewers"]
    assert console._envelope(sid)["review_policy"] is not None
