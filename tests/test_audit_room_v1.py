"""Audit room v1: bounded creation flow, generic store and read-only audit evidence."""
# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from src.audit_room_v1 import AuditRegistry, install_audit_routes
from src.operations_console_app import create_console_app
from src.operations_console_v1 import OperationsConsole


def _system(tmp_path, *, with_document: bool = False):
    console = OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources",
        runtime=tmp_path / "runtime",
    )
    researcher = console.create_account(
        username="anne",
        password="anne-secret",
        roles=("researcher",),
        display_name="Anne",
    )
    receipt = None
    if with_document:
        reviewer = console.create_account(
            username="bert",
            password="bert-secret",
            roles=("reviewer",),
            display_name="Bert",
        )
        receipt = console.ingest(
            actor_id=researcher["account_id"],
            filename="kwaliteit.html",
            content_type="text/html",
            data=b"<html><body><h1>Kwaliteit</h1><p>Een volledige bronpassage.</p></body></html>",
            ingest_kind="new",
            title="Kwaliteit",
            version="1.0",
            date="2026-09-10",
            live_url="",
            class_="richtlijn",
            family="kwaliteit",
            named_reviewers=[reviewer["account_id"]],
        )
    app = create_console_app(console)
    install_audit_routes(app, console)
    client = TestClient(app)
    response = client.post(
        "/login",
        data={"username": "anne", "password": "anne-secret"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return console, client, researcher, receipt


def test_audit_room_exposes_two_real_types_without_generic_workflow_engine(tmp_path):
    _console, client, _researcher, _receipt = _system(tmp_path)

    home = client.get("/audit")
    assert home.status_code == 200
    assert "Nieuwe audit" in home.text
    assert "Experiment" in home.text
    assert "Documentkwaliteit" in home.text
    assert "Publicatiecontrole" in home.text
    assert "Techniek &amp; release" in home.text
    assert home.text.count("Later beschikbaar") == 2

    new = client.get("/audit/new")
    assert new.status_code == 200
    assert '/audit/new?type=experiment' in new.text
    assert '/audit/new?type=document_quality' in new.text
    assert '/audit/new?type=publication' not in new.text


def test_audit_is_shared_nav_room_and_separate_home_meta_tile(tmp_path):
    _console, client, _researcher, _receipt = _system(tmp_path)

    home = client.get("/")
    assert home.status_code == 200
    assert '<a href="/audit">Audit</a>' in home.text
    assert home.text.count('<a class="home-tile') == 4
    assert "Onderzoeken &amp; controleren" in home.text
    assert 'class="review-control-card" href="/audit"' in home.text
    assert "Open Audit" in home.text

    audit = client.get("/audit")
    assert audit.status_code == 200
    assert '<a href="/audit" aria-current="page">Audit</a>' in audit.text


def test_generic_registry_persists_opaque_type_payload(tmp_path):
    console, _client, researcher, _receipt = _system(tmp_path)
    registry = AuditRegistry(console.runtime)

    created = registry.create(
        audit_type="future_type",
        title="Toekomstige audit",
        actor_id=researcher["account_id"],
        payload={"anything": {"works": True}},
    )
    restarted = AuditRegistry(console.runtime)
    stored = restarted.get_audit(created["audit_id"])

    assert stored == created
    assert stored["audit_type"] == "future_type"
    assert stored["payload"] == {"anything": {"works": True}}
    assert "experiment" not in stored


def test_researcher_can_create_experiment_audit_and_reopen_it(tmp_path):
    console, client, researcher, _receipt = _system(tmp_path)

    response = client.post(
        "/audit",
        data={
            "audit_type": "experiment",
            "title": "Passagevorming september 2026",
            "question": "Is de kandidaatroute beter zonder verlies van brontrouw?",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("/audit/audit-")

    detail = client.get(location)
    assert detail.status_code == 200
    assert "Passagevorming september 2026" in detail.text
    assert "Dataset vastzetten" in detail.text
    assert "Nog niet beschikbaar" in detail.text

    rows = AuditRegistry(console.runtime).list_audits()
    assert len(rows) == 1
    row = rows[0]
    assert row["created_by"] == researcher["account_id"]
    assert row["audit_type"] == "experiment"
    assert row["payload"]["state"] == "setup"
    assert row["payload"]["baseline"]["id"] == "production_passage_formation"
    assert row["payload"]["candidate"]["id"] == "source_bound_semantic_passage_formation"

    stored = json.loads((console.runtime / "audits" / f'{row["audit_id"]}.json').read_text(encoding="utf-8"))
    assert stored == row


def test_document_quality_is_second_real_audit_without_changing_store_shape(tmp_path):
    console, client, researcher, receipt = _system(tmp_path, with_document=True)
    assert receipt is not None
    before_envelopes = console.list_envelopes()
    before_revision = console.objects_revision(receipt["snapshot_id"])

    response = client.post(
        "/audit",
        data={
            "audit_type": "document_quality",
            "title": "Kwaliteitsmomentopname",
            "snapshot_id": receipt["snapshot_id"],
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    row = AuditRegistry(console.runtime).list_audits()[0]
    assert row["audit_type"] == "document_quality"
    assert set(row) == {"audit_id", "audit_type", "title", "created_by", "created_at", "updated_at", "payload"}
    assert row["created_by"] == researcher["account_id"]
    assert row["payload"]["snapshot_id"] == receipt["snapshot_id"]
    assert row["payload"]["snapshot_revision"] == before_revision
    assert "coverage" in row["payload"]
    assert "blocked_object_ids" in row["payload"]

    detail = client.get(response.headers["location"])
    assert detail.status_code == 200
    assert "Read-only momentopname" in detail.text
    assert "Dekking per brononderdeel" in detail.text
    assert console.list_envelopes() == before_envelopes
    assert console.objects_revision(receipt["snapshot_id"]) == before_revision


def test_disabled_audit_type_cannot_be_created_by_posting_it_directly(tmp_path):
    console, client, _researcher, _receipt = _system(tmp_path)

    response = client.post(
        "/audit",
        data={
            "audit_type": "publication",
            "title": "Niet toegestaan",
            "question": "Mag dit publiceren?",
        },
    )
    assert response.status_code == 400
    assert "Auditvorm niet beschikbaar" in response.text
    assert AuditRegistry(console.runtime).list_audits() == []


def test_audit_creation_does_not_touch_canonical_or_publication_state(tmp_path):
    console, client, _researcher, _receipt = _system(tmp_path)

    before_envelopes = console.list_envelopes()
    response = client.post(
        "/audit",
        data={
            "audit_type": "experiment",
            "title": "Veilige proef",
            "question": "Verandert deze audit niets buiten de auditruimte?",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert console.list_envelopes() == before_envelopes == []
    assert not (console.runtime / "published_projection.jsonl").exists()
    assert not (console.runtime / "release_manifests").exists()
