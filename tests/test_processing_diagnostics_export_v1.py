"""D2a.1/D2a.2 machine-readable processing diagnostics exports.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from copy import deepcopy

from fastapi.testclient import TestClient

from src.integrity_kernel import stamp_canonical_hashes
from src.operations_console_app import create_console_app
from src.operations_console_v1 import OperationsConsole
from src.processing_diagnostics_v1 import (
    processing_diagnostic_rows,
    processing_diagnostics,
)


PASSWORD = "d2a1-secret"


def _system(tmp_path):
    console = OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "runtime",
    )
    researcher = console.create_account(
        username="researcher.d2a1",
        password=PASSWORD,
        roles=("researcher",),
    )
    reviewer = console.create_account(
        username="reviewer.d2a1",
        password=PASSWORD,
        roles=("reviewer",),
    )
    other = console.create_account(
        username="reviewer.other",
        password=PASSWORD,
        roles=("reviewer",),
    )
    publisher = console.create_account(
        username="publisher.d2a1",
        password=PASSWORD,
        roles=("publisher",),
    )
    receipt = console.ingest(
        actor_id=researcher["account_id"],
        filename="diagnostics.html",
        data=(
            b"<html><body><h1>Richtlijn</h1>"
            b"<p>Bespreek passende ondersteuning met de client.</p>"
            b"<p>Leg de gemaakte afspraken vast.</p>"
            b"</body></html>"
        ),
        content_type="text/html",
        ingest_kind="new",
        title="Diagnostiek",
        version="1.0",
        date="2026-09-24",
        live_url="",
        class_="richtlijn",
        family="diagnostiek",
        named_reviewers=[reviewer["account_id"]],
    )
    snapshot_id = str(receipt["snapshot_id"])
    rows = console._load_objects(snapshot_id)
    target = next(
        row
        for row in rows
        if row.get("object_type") not in {"document", "heading"}
        and row.get("proposed_object_type") != "heading"
    )
    target.setdefault("metadata", {})["admission"] = {
        "gate_result": "blocked",
        "reason_codes": [
            "incomplete_sentence",
            "recommendation_evidence_missing",
        ],
        "proposed_type": "recommendation",
        "section_role": "primary",
        "section_path": ["Richtlijn", "Aanbevelingen"],
    }
    target["proposed_object_type"] = "recommendation"
    target["metadata"]["passage_formation"] = {
        "strategy": "semantic",
        "reason": "semantic_free_text_required",
    }
    target["metadata"]["semantic_passage"] = {
        "selection_origin": "proposal_selected",
        "source_bound": True,
    }
    stamp_canonical_hashes(target)
    for row in rows:
        if row is target:
            continue
        if row.get("object_type") in {"document", "heading"} or row.get("proposed_object_type") == "heading":
            continue
        metadata = row.setdefault("metadata", {})
        metadata["admission"] = {
            "gate_result": "allowed",
            "reason_codes": [],
            "proposed_type": str(row.get("proposed_object_type") or "explanation"),
            "section_role": "regular",
            "section_path": ["Richtlijn"],
        }
        stamp_canonical_hashes(row)
    console._save_objects(snapshot_id, rows)
    return console, reviewer, other, publisher, snapshot_id


def _client(console: OperationsConsole) -> TestClient:
    return TestClient(
        create_console_app(console),
        base_url="https://testserver",
        raise_server_exceptions=False,
    )


def _login(client: TestClient, username: str) -> None:
    response = client.post(
        "/login",
        data={"username": username, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_export_matches_pure_projection_and_does_not_mutate_state(tmp_path) -> None:
    console, _reviewer, _other, _publisher, snapshot_id = _system(tmp_path)
    client = _client(console)
    _login(client, "reviewer.d2a1")

    before_objects = deepcopy(console.snapshot_objects(snapshot_id))
    before_envelope = deepcopy(console._envelope(snapshot_id))
    before_bindings = deepcopy(console.object_review_bindings(snapshot_id))
    before_revision = console.objects_revision(snapshot_id)
    expected = processing_diagnostics(before_objects)

    response = client.get(
        f"/review/processing-diagnostics?document={snapshot_id}"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot_id"] == snapshot_id
    assert payload["title"] == "Diagnostiek"
    assert payload["version"] == "1.0"
    assert payload["objects_revision"] == before_revision
    assert payload["diagnostics"] == expected
    assert payload["diagnostics"]["blocked_candidate_count"] == 1
    assert payload["diagnostics"]["issue_occurrence_count"] == 2

    assert console.snapshot_objects(snapshot_id) == before_objects
    assert console._envelope(snapshot_id) == before_envelope
    assert console.object_review_bindings(snapshot_id) == before_bindings
    assert console.objects_revision(snapshot_id) == before_revision


def test_detail_export_preserves_candidate_combinations_and_does_not_mutate_state(tmp_path) -> None:
    console, _reviewer, _other, _publisher, snapshot_id = _system(tmp_path)
    client = _client(console)
    _login(client, "reviewer.d2a1")

    before_objects = deepcopy(console.snapshot_objects(snapshot_id))
    before_envelope = deepcopy(console._envelope(snapshot_id))
    before_bindings = deepcopy(console.object_review_bindings(snapshot_id))
    before_revision = console.objects_revision(snapshot_id)
    expected = processing_diagnostic_rows(before_objects)

    response = client.get(
        f"/review/processing-diagnostics-detail?document={snapshot_id}"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot_id"] == snapshot_id
    assert payload["title"] == "Diagnostiek"
    assert payload["version"] == "1.0"
    assert payload["objects_revision"] == before_revision
    assert payload["rows"] == expected
    assert len(payload["rows"]) == 1

    row = payload["rows"][0]
    assert row["object_id"]
    assert row["candidate_text"]
    assert row["reason_codes"] == [
        "incomplete_sentence",
        "recommendation_evidence_missing",
    ]
    assert row["families"] == [
        "unit_completeness",
        "semantic_contract",
    ]
    assert row["proposed_type"] == "recommendation"
    assert row["section_role"] == "primary"
    assert row["section_path"] == ["Richtlijn", "Aanbevelingen"]
    assert row["formation_strategy"] == "semantic"
    assert row["formation_reason"] == "semantic_free_text_required"
    assert row["selection_origin"] == "proposal_selected"

    assert console.snapshot_objects(snapshot_id) == before_objects
    assert console._envelope(snapshot_id) == before_envelope
    assert console.object_review_bindings(snapshot_id) == before_bindings
    assert console.objects_revision(snapshot_id) == before_revision


def test_export_requires_authentication_reviewer_role_and_assignment(tmp_path) -> None:
    console, _reviewer, _other, _publisher, snapshot_id = _system(tmp_path)
    paths = (
        "/review/processing-diagnostics",
        "/review/processing-diagnostics-detail",
    )

    for path in paths:
        anonymous = _client(console)
        response = anonymous.get(f"{path}?document={snapshot_id}")
        assert response.status_code == 401
        assert "not_authenticated" in response.text

        publisher_client = _client(console)
        _login(publisher_client, "publisher.d2a1")
        response = publisher_client.get(f"{path}?document={snapshot_id}")
        assert response.status_code == 403
        assert "reviewer_role_required" in response.text

        other_client = _client(console)
        _login(other_client, "reviewer.other")
        response = other_client.get(f"{path}?document={snapshot_id}")
        assert response.status_code == 400
        assert "reviewer_not_named_on_snapshot" in response.text


def test_export_unknown_snapshot_fails_and_control_page_links_to_export(tmp_path) -> None:
    console, _reviewer, _other, _publisher, snapshot_id = _system(tmp_path)
    client = _client(console)
    _login(client, "reviewer.d2a1")

    for path in (
        "/review/processing-diagnostics",
        "/review/processing-diagnostics-detail",
    ):
        missing = client.get(f"{path}?document=snap-does-not-exist")
        assert missing.status_code == 400
        assert "unknown_snapshot" in missing.text

    control = client.get(f"/review?document={snapshot_id}&task=control")
    assert control.status_code == 200
    assert (
        f'href="/review/processing-diagnostics?document={snapshot_id}"'
        in control.text
    )
    assert "Exporteer diagnostiek als JSON" in control.text
    assert (
        f'href="/review/processing-diagnostics-detail?document={snapshot_id}"'
        in control.text
    )
    assert "Exporteer detaildiagnostiek als JSON" in control.text
