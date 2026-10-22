"""A reviewer reports a discrepancy between a knowledge object and its source.

The report is optional evidence on the reviewer's own revise/reject decision;
with a report the object cannot be approved unchanged. Kwaliteit & werkproces
counts the reports per formation route and model.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: metrics teller noemer
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from copy import deepcopy
import re

import pytest
from fastapi.testclient import TestClient

from src.closed_review_loop_v1 import REVIEW_AUDIT_EVIDENCE_EVENT
from src.operations_console_v1 import ConsoleError
from src.quality_metrics_app_v1 import capture
from src.quality_metrics_v1 import build_report
from src.review_ledger import read_events
from src.source_discrepancy_v1 import CATEGORIES, assert_allowed, normalize
from test_d5_4_review_interaction_evidence import PASSWORD, _system

AS_OF = "2026-10-22T00:00:00+00:00"


def test_categories_are_closed_and_canonical() -> None:
    assert normalize(["tekst_of_bronplek_wijkt_af", "context_ontbreekt", "context_ontbreekt", ""]) == [
        "context_ontbreekt", "tekst_of_bronplek_wijkt_af"]
    assert normalize(None) == []
    with pytest.raises(ConsoleError, match="source_discrepancy_invalid"):
        normalize(["parafrase"])
    for decision in ("approve", "later"):
        with pytest.raises(ConsoleError, match="source_discrepancy_requires_correction_or_rejection"):
            assert_allowed(["context_ontbreekt"], decision)
    for decision in ("revise", "reject"):
        assert_allowed(["context_ontbreekt"], decision) is None
    assert set(CATEGORIES) == {"context_ontbreekt", "betekenis_wijkt_af", "afbakening_onjuist",
                               "tekst_of_bronplek_wijkt_af"}


def _state(console, snapshot_id):
    return deepcopy((console._envelope(snapshot_id), console.snapshot_objects(snapshot_id),
                     console.object_review_bindings(snapshot_id)))


def _reports(console):
    return [e for e in read_events(console._ledger_path)
            if e["event_type"] == REVIEW_AUDIT_EVIDENCE_EVENT and e["details"].get("source_discrepancy")]


def test_reported_discrepancy_blocks_unchanged_approval_and_is_recorded_on_rejection(
        tmp_path, *, production_console) -> None:
    console, users, snapshot_id, object_id = _system(tmp_path, production_console=production_console)
    reviewer = users["reviewer_a"]["account_id"]
    before = _state(console, snapshot_id)
    command = dict(actor_id=reviewer, snapshot_id=snapshot_id, object_id=object_id,
                   source_discrepancy=["context_ontbreekt"])
    with pytest.raises(ConsoleError, match="source_discrepancy_requires_correction_or_rejection"):
        console.review_object(**command, decision="approve", confirmed_object_type="definition",
                              expected_revision=console.objects_revision(snapshot_id))
    with pytest.raises(ConsoleError, match="source_discrepancy_requires_correction_or_rejection"):
        console.review_object(**command, decision="later")
    with pytest.raises(ConsoleError, match="source_discrepancy_invalid"):
        console.review_object(**{**command, "source_discrepancy": ["onbekend"]}, decision="reject",
                              comment="Klopt niet")
    assert _state(console, snapshot_id) == before and _reports(console) == []

    text_before = next(o for o in console.snapshot_objects(snapshot_id)
                       if o["object_id"] == object_id)["content"]["clean_text"]
    console.review_object(**{**command, "source_discrepancy": ["betekenis_wijkt_af", "context_ontbreekt"]},
                          decision="reject", comment="De voorwaarde uit de bron ontbreekt.",
                          expected_revision=console.objects_revision(snapshot_id))
    [report] = _reports(console)
    assert report["object_id"] == object_id
    assert report["details"]["source_discrepancy"] == ["context_ontbreekt", "betekenis_wijkt_af"]
    assert report["details"]["decision"] == "reject"
    # A report is evidence only: the source-bound text is never changed by it.
    after = next(o for o in console.snapshot_objects(snapshot_id) if o["object_id"] == object_id)
    assert after["content"]["clean_text"] == text_before

    quality = build_report(capture(console, users["researcher"])["documents"], as_of=AS_OF)
    assert quality["source_discrepancies"]["reports"] == 1
    assert quality["source_discrepancies"]["critical"] == 0
    assert quality["source_discrepancies"]["categories"] == {"context_ontbreekt": 1, "betekenis_wijkt_af": 1}
    assert [row["reports"] for row in quality["source_discrepancies"]["by_formation"]] == [1]
    assert sum(r["source_discrepancy_reports"] for r in quality["routes"].values()) == 1
    assert quality["definition_version"] == "quality-workprocess-v1.1.0"


def test_heading_cannot_carry_a_discrepancy(tmp_path, *, production_console) -> None:
    console, users, snapshot_id, _ = _system(tmp_path, production_console=production_console)
    heading = next(o for o in console.snapshot_objects(snapshot_id) if o["object_type"] == "heading")
    with pytest.raises(ConsoleError, match="source_discrepancy_not_applicable"):
        console.review_object(actor_id=users["reviewer_a"]["account_id"], snapshot_id=snapshot_id,
                              object_id=heading["object_id"], decision="reject", comment="Geen kop",
                              source_discrepancy=["afbakening_onjuist"])


def _login(client, username):
    assert client.post("/login", data={"username": username, "password": PASSWORD},
                       follow_redirects=False).status_code == 303


def test_review_card_offers_the_report_and_keeps_input_when_approval_is_refused(
        tmp_path, *, production_app, production_console) -> None:
    console, users, snapshot_id, object_id = _system(tmp_path, production_console=production_console)
    client = TestClient(production_app(console), base_url="https://testserver")
    _login(client, users["reviewer_a"]["username"])
    card = client.get(f"/review?document={snapshot_id}&object={object_id}").text
    assert "Rapporteer een discrepantie (optioneel)" in card
    assert len(re.findall(r'name="source_discrepancy"', card)) == len(CATEGORIES)
    form = {"snapshot_id": snapshot_id, "object_id": object_id, "suitability": "ja",
            "eindoordeel": "goedkeuren", "type_action": "dit_klopt", "proposed_object_type": "definition",
            "confirmed_object_type": "definition", "documentpositie_action": "dit_klopt",
            "snapshot_revision": console.objects_revision(snapshot_id),
            "source_discrepancy": ["tekst_of_bronplek_wijkt_af"]}
    refused = client.post("/review", data=form, follow_redirects=False)
    assert refused.status_code == 400
    assert "ongewijzigd goedkeuren of later beoordelen kan niet" in refused.text
    assert re.search(r'value="tekst_of_bronplek_wijkt_af" checked', refused.text)
    assert _reports(console) == []
    rejected = client.post("/review", data={**form, "eindoordeel": "afwijzen", "comment": "Tekst wijkt af",
                                            "snapshot_revision": console.objects_revision(snapshot_id)},
                           follow_redirects=False)
    assert rejected.status_code == 303, rejected.text
    [report] = _reports(console)
    assert report["details"]["source_discrepancy"] == ["tekst_of_bronplek_wijkt_af"]
    quality = build_report(capture(console, users["researcher"])["documents"], as_of=AS_OF)
    assert quality["source_discrepancies"]["critical"] == 1


def test_report_travels_through_the_structured_correction(tmp_path, *, production_console) -> None:
    from src.deterministic_review_repair_v1 import StructuredRepairRequired
    console, users, snapshot_id, object_id = _system(tmp_path, production_console=production_console)
    reviewer = users["reviewer_a"]["account_id"]
    with pytest.raises(StructuredRepairRequired) as required:
        console.review_object(actor_id=reviewer, snapshot_id=snapshot_id, object_id=object_id,
                              decision="revise", eindoordeel="goedkeuren_na_correctie", suitability="ja",
                              type_action="type_wijzigen", confirmed_object_type="explanation",
                              comment="Dit is een toelichting", source_discrepancy=["betekenis_wijkt_af"],
                              expected_revision=console.objects_revision(snapshot_id))
    submission = required.value.submission
    assert submission["source_discrepancy"] == ["betekenis_wijkt_af"]
    assert _reports(console) == []
    console.submit_review_resolution(
        actor_id=reviewer, snapshot_id=snapshot_id, object_id=object_id,
        expected_revision=submission["expected_revision"], suitability="ja", comment=submission["comment"],
        repair_kind=console.repair_kind_for_submission(submission), type_action="type_wijzigen",
        confirmed_object_type="explanation", source_discrepancy=submission["source_discrepancy"])
    reports = _reports(console)
    assert [r["details"]["source_discrepancy"] for r in reports] == [["betekenis_wijkt_af"]]
    quality = build_report(capture(console, users["researcher"])["documents"], as_of=AS_OF)
    assert quality["source_discrepancies"]["reports"] == 1
