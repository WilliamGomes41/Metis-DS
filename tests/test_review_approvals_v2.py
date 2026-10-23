"""review-configuration-v2: wie mag beoordelen staat los van hoeveel goedkeuringen verplicht zijn.

Besluit William 2026-10-23: aantal aangewezen beoordelaars is niet het aantal
verplichte goedkeuringen. Vier ogen is een expliciete keuze bij twee personen;
inhoudsgebonden vier ogen kan de eis alleen verhogen. v1 blijft ongewijzigd.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import pytest

from src.four_eyes_v1 import historical_requires_four_eyes, publish_authorization_contract, requires_four_eyes
from src.operations_console_v1 import ConsoleError
from src.review_configuration_v1 import (
    CONTRACT, CONTRACT_V2, configured_approval, policy_for_configuration, validate_configuration,
)
from src.review_policy_v1 import CONTRACT as POLICY
from test_t4_single_knowledge_path_invariants import _allowed_candidate, _allowed_source, _binding, _stamp_hash

UPLOADER = "uploader-anne"


def _v2(option, reviewers, *, four_eyes=False, readers=()):
    return {"contract": CONTRACT_V2, "option": option, "four_eyes_required": four_eyes,
            "reviewers": list(reviewers), "readers": list(readers), "revision": 1, "locked_at": None,
            "source": "chosen"}


def _object(*, high_risk=False, policy=None):
    obj = _allowed_candidate()
    if high_risk:
        obj.setdefault("risk", {})["risk_level"] = "high"
    if policy is not None:
        obj.setdefault("metadata", {})["review_policy"] = policy
    return _stamp_hash(obj)


def _contract(approvers, configuration=None, *, high_risk=False, policy=None, bindings=None):
    obj = _object(high_risk=high_risk, policy=policy)
    rows = [_binding(obj, reviewer) for reviewer in approvers] if bindings is None else bindings(obj)
    return publish_authorization_contract(
        obj=obj, bindings=rows, uploader_id=UPLOADER, immutable_locator=None,
        fragments=_allowed_source(), review_configuration=configuration)


# 1 + 3: twee aangewezen, vier ogen uit: één bevoegde goedkeuring volstaat.
@pytest.mark.parametrize(("option", "reviewers", "approver"), [
    ("two_others", ["rev-a", "rev-b"], "rev-a"),
    ("two_others", ["rev-a", "rev-b"], "rev-b"),
    ("uploader_and_other", ["rev-a"], "rev-a"),
    ("uploader_and_other", ["rev-a"], UPLOADER),
])
def test_two_designated_without_four_eyes_one_approval_suffices(option, reviewers, approver):
    contract = _contract([approver], _v2(option, reviewers))
    assert contract["authorization_blockers"] == []
    assert contract["four_eyes_required"] is False


# 2 + 3: vier ogen aan: beide aangewezen personen moeten geldig goedkeuren.
@pytest.mark.parametrize(("option", "reviewers", "first", "second"), [
    ("two_others", ["rev-a", "rev-b"], "rev-a", "rev-b"),
    ("uploader_and_other", ["rev-a"], UPLOADER, "rev-a"),
])
def test_two_designated_with_four_eyes_needs_both(option, reviewers, first, second):
    configuration = _v2(option, reviewers, four_eyes=True)
    assert "four_eyes_required" in _contract([first], configuration)["authorization_blockers"]
    assert "four_eyes_required" in _contract([second], configuration)["authorization_blockers"]
    assert _contract([first, second], configuration)["authorization_blockers"] == []


# 4: de uploader telt alleen als die is aangewezen.
def test_uploader_counts_only_when_designated():
    for configuration in (_v2("two_others", ["rev-a", "rev-b"]), _v2("one_other", ["rev-a"])):
        assert "review_configuration_approval_missing" in _contract([UPLOADER], configuration)["authorization_blockers"]
    assert configured_approval(_v2("uploader_and_other", ["rev-a"]), {UPLOADER}, uploader_id=UPLOADER) == (True, False)


# 5: een lezer of niet-aangewezen account telt nooit.
def test_reader_and_undesignated_never_count():
    configuration = _v2("two_others", ["rev-a", "rev-b"], readers=["reader-x"])
    for approvers in (["reader-x"], ["rev-z"], ["reader-x", "rev-z"]):
        assert "review_configuration_approval_missing" in _contract(approvers, configuration)["authorization_blockers"]


# 6: inhoudsgebonden vier ogen blijft gelden bij vier ogen uit.
def test_content_four_eyes_raises_the_requirement():
    configuration = _v2("two_others", ["rev-a", "rev-b"])
    assert "four_eyes_required" in _contract(["rev-a"], configuration, high_risk=True)["authorization_blockers"]
    assert "four_eyes_required" in _contract(["rev-a", "rev-z"], configuration, high_risk=True)["authorization_blockers"]
    assert _contract(["rev-a", "rev-b"], configuration, high_risk=True)["authorization_blockers"] == []
    both = _v2("uploader_and_other", ["rev-a"])
    assert _contract([UPLOADER, "rev-a"], both, high_risk=True)["authorization_blockers"] == []


# 6 + besluit 3: een policy met één reviewer overschrijft inhoudsrisico niet meer.
def test_single_reviewer_policy_no_longer_overrides_content_four_eyes():
    policy = {"contract": POLICY, "revision": 1, "primary": "rev-a", "assignments": []}
    risky = _object(high_risk=True, policy=policy)
    assert requires_four_eyes(risky) is True
    contract = _contract(["rev-a"], policy=policy, high_risk=True)
    assert "four_eyes_required" in contract["authorization_blockers"]
    assert _contract(["rev-a", "rev-z"], policy=policy, high_risk=True)["four_eyes_satisfied"] is True
    # Al gepubliceerde releases worden herverifieerd met de regel waaronder ze zijn uitgegeven.
    assert historical_requires_four_eyes(risky) is False


# 7: historische configuraties behouden hun plicht.
@pytest.mark.parametrize("four_eyes", [False, True])
def test_v1_two_others_still_needs_both(four_eyes):
    v1 = {**_v2("two_others", ["rev-a", "rev-b"], four_eyes=four_eyes), "contract": CONTRACT}
    assert "review_configuration_approval_missing" in _contract(["rev-a"], v1)["authorization_blockers"]


# 8: dubbele of verouderde goedkeuringen tellen niet als tweede.
def test_duplicate_or_stale_approvals_cannot_complete_four_eyes():
    configuration = _v2("two_others", ["rev-a", "rev-b"], four_eyes=True)
    twice = _contract([], configuration, bindings=lambda obj: [_binding(obj, "rev-a"), _binding(obj, "rev-a")])
    assert "four_eyes_required" in twice["authorization_blockers"]

    def stale(obj):
        row = _binding(obj, "rev-b")
        row["canonical_object_hash"] = "other-passage"
        return [_binding(obj, "rev-a"), row]
    assert "four_eyes_required" in _contract([], configuration, bindings=stale)["authorization_blockers"]


@pytest.mark.parametrize(("option", "reviewers", "four_eyes", "code"), [
    ("one_other", ["rev-a"], True, "review_configuration_four_eyes_needs_two_reviewers"),
    ("uploader_sole", [], True, "review_configuration_four_eyes_needs_two_reviewers"),
    ("two_others", ["rev-a"], False, "review_configuration_reviewers_missing"),
    ("uploader_and_other", [UPLOADER], False, "review_configuration_uploader_not_other_reviewer"),
])
def test_v2_validation_refuses_inconsistent_choices(option, reviewers, four_eyes, code):
    with pytest.raises(ValueError, match=code):
        validate_configuration(_v2(option, reviewers, four_eyes=four_eyes), uploader_id=UPLOADER)


@pytest.mark.parametrize(("option", "reviewers", "four_eyes", "primary", "required"), [
    ("uploader_sole", [], False, UPLOADER, []),
    ("one_other", ["rev-a"], False, "rev-a", []),
    ("uploader_and_other", ["rev-a"], True, UPLOADER, ["rev-a"]),
    ("two_others", ["rev-a", "rev-b"], True, "rev-a", ["rev-b"]),
    ("uploader_and_other", ["rev-a"], False, None, None),
    ("two_others", ["rev-a", "rev-b"], False, None, None),
])
def test_policy_only_where_it_expresses_the_same_duty(option, reviewers, four_eyes, primary, required):
    policy = policy_for_configuration(_v2(option, reviewers, four_eyes=four_eyes), uploader_id=UPLOADER)
    if primary is None:
        assert policy is None
    else:
        assert policy["primary"] == primary
        assert [r["reviewer_id"] for r in policy["assignments"]] == required


# --- Kernel: receive_source, review en publicatiegereedheid -------------------------------------

@pytest.fixture
def kernel(tmp_path, *, production_console):
    from tests.test_vsa_publish_readiness_ui_v1 import MemorySourceStore
    from tests.semantic_fixture_support import bind_fixture_selections
    source = MemorySourceStore()
    console = production_console(processing_binder=bind_fixture_selections, root=tmp_path,
                                 source_store=tmp_path / "sources" / "private", runtime=tmp_path / "runtime",
                                 immutable_source_store=source)
    console.test_source_store = source
    ids = {name: console.create_account(username=name, password="fixture-only-" + name,
                                        roles=roles)["account_id"]
           for name, roles in (("anne", ("researcher", "reviewer")), ("bert", ("reviewer",)),
                               ("carla", ("reviewer",)), ("dirk", ("reviewer",)))}
    bind_fixture_selections(console)
    return console, ids


def _ingest(console, ids, choice, **extra):
    from tests.test_vsa_publish_readiness_ui_v1 import HTML_FIXTURE
    command = dict(actor_id=ids["anne"], filename="continentie.html", data=HTML_FIXTURE.read_bytes(),
                   content_type="text/html", ingest_kind="new", title="Continentie", version="1.0",
                   date="2025-04-01", live_url="https://example.test/continentie", class_="richtlijn",
                   family="continentie", named_reviewers=[], review_choice={"contract": CONTRACT_V2, **choice})
    command.update(extra)
    return console.ingest(**command)


def _choice(option, reviewers, *, four_eyes=False):
    return {"option": option, "four_eyes_required": four_eyes, "reviewers": reviewers, "readers": []}


def _finish_review(console, sid, reviewer):
    """Eén reviewer rondt alle passages af, zoals de readiness-fixture."""
    import tests.test_vsa_publish_readiness_ui_v1 as ready
    ready._complete_review(console, {"reviewer": {"account_id": reviewer}}, {"snapshot_id": sid})


@pytest.mark.parametrize(("option", "reviewers", "approver"), [
    ("two_others", ["bert", "carla"], "carla"),
    ("uploader_and_other", ["bert"], "anne"),
])
def test_kernel_one_of_two_without_four_eyes_completes_review(kernel, option, reviewers, approver):
    console, ids = kernel
    sid = _ingest(console, ids, _choice(option, [ids[r] for r in reviewers]))["snapshot_id"]
    envelope = console._envelope(sid)
    assert envelope.get("review_policy") is None
    assert envelope["review_configuration"]["contract"] == CONTRACT_V2
    _finish_review(console, sid, ids[approver])
    readiness = console.publication_readiness(sid)
    assert not {"review_configuration_approval_missing", "four_eyes_required",
                "required_policy_review_missing"} & set(readiness["blockers"]), readiness["blockers"]


def test_kernel_one_of_two_restart_keeps_the_same_result(kernel, tmp_path, production_console):
    console, ids = kernel
    sid = _ingest(console, ids, _choice("two_others", [ids["bert"], ids["carla"]]))["snapshot_id"]
    _finish_review(console, sid, ids["bert"])
    before = console.publication_readiness(sid)["blockers"]
    from tests.semantic_fixture_support import bind_fixture_selections
    from tests.test_vsa_publish_readiness_ui_v1 import MemorySourceStore
    restarted = production_console(processing_binder=bind_fixture_selections, root=tmp_path,
                                   source_store=tmp_path / "sources" / "private", runtime=tmp_path / "runtime",
                                   immutable_source_store=MemorySourceStore())
    review = {"review_configuration_approval_missing", "four_eyes_required", "required_policy_review_missing"}
    assert not review & set(before)
    assert not review & set(restarted.publication_readiness(sid)["blockers"])


def test_kernel_four_eyes_with_two_colleagues_needs_the_second(kernel):
    console, ids = kernel
    sid = _ingest(console, ids, _choice("two_others", [ids["bert"], ids["carla"]], four_eyes=True))["snapshot_id"]
    policy = console._envelope(sid)["review_policy"]
    assert policy["primary"] == ids["bert"] and policy["assignments"][0]["reviewer_id"] == ids["carla"]
    _finish_review(console, sid, ids["bert"])
    assert "required_policy_review_missing" in console.publication_readiness(sid)["blockers"]


def test_kernel_undesignated_reviewer_cannot_review(kernel):
    console, ids = kernel
    sid = _ingest(console, ids, _choice("two_others", [ids["bert"], ids["carla"]]))["snapshot_id"]
    assert set(console._envelope(sid)["named_reviewers"]) == {ids["bert"], ids["carla"]}
    target = next(o for o in console.snapshot_objects(sid) if o.get("object_type") == "unclassified")
    for outsider in (ids["dirk"], ids["anne"]):
        with pytest.raises(ConsoleError, match="reviewer_not_named_on_snapshot"):
            console.review_object(actor_id=outsider, snapshot_id=sid, object_id=target["object_id"],
                                  decision="approve", confirmed_object_type="explanation")


def test_kernel_refuses_four_eyes_for_one_person_and_foreign_policy(kernel):
    console, ids = kernel
    with pytest.raises(ConsoleError, match="review_configuration_four_eyes_needs_two_reviewers"):
        _ingest(console, ids, _choice("one_other", [ids["bert"]], four_eyes=True))
    foreign = {"contract": POLICY, "revision": 1, "primary": ids["bert"],
               "assignments": [{"reviewer_id": ids["carla"], "participation": "required"}]}
    with pytest.raises(ConsoleError, match="review_configuration_policy_conflict"):
        _ingest(console, ids, _choice("two_others", [ids["bert"], ids["carla"]]), review_policy=foreign)


# 8: een correctieverzoek van de andere aangewezen persoon wordt niet genegeerd.
def test_kernel_revise_by_the_other_designated_person_is_not_overridden(kernel):
    console, ids = kernel
    sid = _ingest(console, ids, _choice("two_others", [ids["bert"], ids["carla"]]))["snapshot_id"]
    target = next(o for o in console.snapshot_objects(sid) if o.get("object_type") == "unclassified")
    console.review_object(actor_id=ids["carla"], snapshot_id=sid, object_id=target["object_id"],
                          decision="revise", comment="Klopt niet met de bron.")
    try:
        console.review_object(actor_id=ids["bert"], snapshot_id=sid, object_id=target["object_id"],
                              decision="approve", confirmed_object_type="explanation")
    except ConsoleError:
        pass
    current = next(o for o in console.snapshot_objects(sid) if o["object_id"] == target["object_id"])
    assert (current.get("governance") or {}).get("validation_status") != "approved"
    assert console.publication_readiness(sid)["publish_allowed"] is False


# 8: gelijktijdige reviews op dezelfde revisie: de tweede wordt geweigerd.
def test_kernel_concurrent_reviews_on_one_revision_conflict(kernel):
    console, ids = kernel
    sid = _ingest(console, ids, _choice("two_others", [ids["bert"], ids["carla"]]))["snapshot_id"]
    target = next(o for o in console.snapshot_objects(sid) if o.get("object_type") == "unclassified")
    revision = console.objects_revision(sid)
    console.review_object(actor_id=ids["bert"], snapshot_id=sid, object_id=target["object_id"],
                          decision="approve", confirmed_object_type="explanation", expected_revision=revision)
    with pytest.raises(ConsoleError, match="snapshot_object_write_conflict"):
        console.review_object(actor_id=ids["carla"], snapshot_id=sid, object_id=target["object_id"],
                              decision="revise", comment="Gelijktijdig.", expected_revision=revision)


# 9: beslisboom-PDF houdt zijn route waar een policy dezelfde plicht uitdrukt.
@pytest.mark.parametrize(("option", "reviewers", "four_eyes"), [
    ("uploader_sole", [], False), ("one_other", ["bert"], False), ("two_others", ["bert", "carla"], True),
])
def test_kernel_decision_tree_pdf_route_kept(kernel, option, reviewers, four_eyes):
    from tests.decision_tree_test_support import pdf_data
    console, ids = kernel
    receipt = _ingest(console, ids, _choice(option, [ids[r] for r in reviewers], four_eyes=four_eyes),
                      class_="beslisboom", filename="boom.pdf", data=pdf_data(), content_type="application/pdf",
                      live_url="")
    assert console._envelope(receipt["snapshot_id"])["review_policy"] is not None


# Without a policy a decision tree would lose its graph review, PDF and JSON freeze alike.
@pytest.mark.parametrize("source", ["pdf", "json"])
def test_kernel_decision_tree_one_of_two_is_refused_explicitly(kernel, source):
    from tests.decision_tree_test_support import pdf_data
    from tests.test_v225_beslisboom_path import _boom_freeze_bytes
    console, ids = kernel
    data, name, kind = (pdf_data(), "boom.pdf", "application/pdf") if source == "pdf" else \
        (_boom_freeze_bytes(), "boom.json", "application/json")
    with pytest.raises(ConsoleError, match="decision_tree_needs_all_reviewers_required"):
        _ingest(console, ids, _choice("two_others", [ids["bert"], ids["carla"]]), class_="beslisboom",
                filename=name, data=data, content_type=kind, live_url="")
    assert console.list_envelopes() == []
