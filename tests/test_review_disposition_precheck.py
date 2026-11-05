"""A static disposition conflict is refused before the review command prepares.

The suitability/decision table is trunk's ``ALLOWED_FINAL_BY_SUITABILITY``
written out literally, so a drift of the owner function fails here.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json
import logging
import re

import pytest

from src.operations_console_v1 import ConsoleError
from tests.test_v233_review_audit_regressions import review_system  # noqa: F401  (fixture)

CONFLICT = "review_disposition_conflict"

# (suitability, decision) -> literal outcome of trunk's rule. None means the
# rule does not refuse; "later" with a suitability is deferred, not refused.
TRUNK_TABLE = {
    ("ja", "approve"): None,
    ("ja", "revise"): None,
    ("ja", "reject"): None,
    ("ja", "later"): None,
    ("mist_context", "approve"): CONFLICT,
    ("mist_context", "revise"): None,
    ("mist_context", "reject"): None,
    ("mist_context", "later"): None,
    ("samenvoegen", "approve"): CONFLICT,
    ("samenvoegen", "revise"): None,
    ("samenvoegen", "reject"): None,
    ("samenvoegen", "later"): None,
    ("alleen_onderbouwing", "approve"): None,
    ("alleen_onderbouwing", "revise"): None,
    ("alleen_onderbouwing", "reject"): None,
    ("alleen_onderbouwing", "later"): None,
    ("geen_kenniseenheid", "approve"): CONFLICT,
    ("geen_kenniseenheid", "revise"): CONFLICT,
    ("geen_kenniseenheid", "reject"): None,
    ("geen_kenniseenheid", "later"): None,
    ("", "approve"): None,
    ("", "revise"): None,
    ("", "reject"): None,
    ("", "later"): None,
    ("onbekend", "approve"): CONFLICT,
    ("onbekend", "revise"): CONFLICT,
    ("onbekend", "reject"): CONFLICT,
    ("onbekend", "later"): None,
}

EINDOORDEEL = {"approve": "goedkeuren", "revise": "goedkeuren_na_correctie",
               "reject": "afwijzen", "later": "later_beoordelen"}


def _outcome(submission):
    from src.review.closed_review_loop_v1 import require_allowed_review_disposition
    try:
        require_allowed_review_disposition(submission)
    except ConsoleError as exc:
        return exc.code
    return None


def test_table_covers_every_trunk_suitability():
    from src.review.closed_review_loop_v1 import ALLOWED_FINAL_BY_SUITABILITY
    assert {s for s, _ in TRUNK_TABLE} == set(ALLOWED_FINAL_BY_SUITABILITY) | {"", "onbekend"}


@pytest.mark.parametrize(("suitability", "decision"), sorted(TRUNK_TABLE))
def test_rule_matches_trunk_table(suitability, decision):
    expected = TRUNK_TABLE[(suitability, decision)]
    # Decision field, the eindoordeel field (which wins through map_eindoordeel),
    # and padded suitability all reach the same outcome.
    assert _outcome({"suitability": suitability, "decision": decision}) == expected
    assert _outcome({"suitability": f" {suitability} ", "decision": "",
                     "eindoordeel": EINDOORDEEL[decision]}) == expected
    assert _outcome({"suitability": suitability or None, "decision": "approve",
                     "eindoordeel": EINDOORDEEL[decision]}) == expected


def _review_form(client, sid, oid, **overrides):
    page = client.get("/review", params={"document": sid, "object": oid})
    assert page.status_code == 200
    revision = re.search(r'name="snapshot_revision" value="([^"]+)"', page.text).group(1)
    return {"snapshot_id": sid, "object_id": oid, "snapshot_revision": revision,
            "suitability": "ja", "documentpositie_action": "dit_klopt",
            "type_action": "dit_klopt", "confirmed_object_type": "definition",
            "eindoordeel": "goedkeuren", "decision": "approve", "relation_review_ack": "1",
            **overrides}


def _review_event_count(console):
    with console.workflow_review_store._connect() as con:
        return con.execute("SELECT count(*) AS n FROM workflow.review_events").fetchone()["n"]


def _diagnostics(client, path, data):
    from src.request_diagnostics_v1 import _LOGGER
    seen = []

    class Capture(logging.Handler):
        def emit(self, record):
            text = record.getMessage()
            if text.startswith("metis_diagnostic "):
                seen.append(json.loads(text[len("metis_diagnostic "):]))

    handler = Capture()
    _LOGGER.addHandler(handler)
    try:
        response = client.post(path, data=data, follow_redirects=False)
    finally:
        _LOGGER.removeHandler(handler)
    finished = [e for e in seen if e.get("event") == "request_finished"]
    assert finished, "request_finished diagnostic missing"
    return response, finished[-1]


# Trunk (1f9deea) issued 26 queries for this conflicting POST on the prepared
# path of the review_system fixture: it prepared the envelope, source views,
# histories and bindings before the kernel refused.
TRUNK_PREPARED_CONFLICT_QUERIES = 26


def _phase_names(finished):
    paths = set(finished.get("phases") or {}) | set(finished.get("phase_tree") or {})
    return {name for path in paths for name in path.split("/")}


def _legacy_review_window(monkeypatch, console):
    # Existing-data compatibility branch: a document without a prepared review
    # window takes the serial command, which opens store_transaction first.
    monkeypatch.setattr(console.workflow_document_store, "review_command_window",
                        lambda *args, **kwargs: None)


def test_serial_path_conflict_is_refused_before_preparation(review_system, monkeypatch):
    console, client, sid, _actor, ids = review_system
    _legacy_review_window(monkeypatch, console)
    data = _review_form(client, sid, ids[0], suitability="geen_kenniseenheid")
    before = _review_event_count(console)
    response, finished = _diagnostics(client, "/review", data)
    assert response.status_code == 400, response.text[:300]
    assert CONFLICT in response.text
    assert _review_event_count(console) == before
    names = _phase_names(finished)
    assert "store_transaction" not in names, sorted(names)
    assert not any(name.startswith("source_") for name in names), sorted(names)


def test_prepared_path_conflict_issues_fewer_queries_than_trunk(review_system):
    console, client, sid, _actor, ids = review_system
    data = _review_form(client, sid, ids[0], suitability="geen_kenniseenheid")
    before = _review_event_count(console)
    response, finished = _diagnostics(client, "/review", data)
    assert response.status_code == 400, response.text[:300]
    assert CONFLICT in response.text
    assert _review_event_count(console) == before
    names = _phase_names(finished)
    assert not any(name.startswith("source_") for name in names), sorted(names)
    assert finished["db"]["db_queries"] < TRUNK_PREPARED_CONFLICT_QUERIES, finished["db"]


@pytest.mark.parametrize(("suitability", "decision"),
                         [pair for pair, code in sorted(TRUNK_TABLE.items())
                          if code == CONFLICT and pair[1] != "revise"])
@pytest.mark.parametrize("legacy", [False, True])
def test_kernel_conflict_never_prepares_inputs(review_system, monkeypatch, suitability, decision, legacy):
    from src.review import review_command_v1
    console, _client, sid, actor, ids = review_system
    if legacy:
        _legacy_review_window(monkeypatch, console)

    def prepared(*args, **kwargs):
        raise AssertionError("conflicting disposition reached input preparation")

    monkeypatch.setattr(review_command_v1, "_prepare_review_source_inputs", prepared)
    token = _review_form(_client, sid, ids[0])["snapshot_revision"]
    with pytest.raises(ConsoleError) as raised:
        console.review_object(actor_id=actor, snapshot_id=sid, object_id=ids[0], decision=decision,
                              suitability=suitability, comment="c", expected_revision=token,
                              _compact_result=not legacy)
    assert raised.value.code == CONFLICT


def test_authorization_still_precedes_the_disposition_rule(review_system):
    console, _client, sid, _actor, ids = review_system
    outsider = console.create_account(username="carla", password="carla-secret", roles=("reviewer",))
    with pytest.raises(ConsoleError) as raised:
        console.review_object(actor_id=outsider["account_id"], snapshot_id=sid, object_id=ids[0],
                              decision="approve", suitability="geen_kenniseenheid")
    assert raised.value.code == "reviewer_not_named_on_snapshot"
    researcher = console.create_account(username="dirk", password="dirk-secret", roles=("researcher",))
    with pytest.raises(ConsoleError) as raised:
        console.review_object(actor_id=researcher["account_id"], snapshot_id=sid, object_id=ids[0],
                              decision="approve", suitability="geen_kenniseenheid")
    assert raised.value.code != CONFLICT


def test_revise_keeps_the_structured_repair_flow(review_system):
    # A suitability that permits a correction still opens the structured repair.
    # One that never does is refused (test_review_disposition_choices, #987).
    from src.review.deterministic_review_repair_v1 import StructuredRepairRequired
    console, client, sid, actor, ids = review_system
    token = _review_form(client, sid, ids[0])["snapshot_revision"]
    with pytest.raises(StructuredRepairRequired):
        console.review_object(actor_id=actor, snapshot_id=sid, object_id=ids[0], decision="revise",
                              suitability="mist_context", comment="c", expected_revision=token)
