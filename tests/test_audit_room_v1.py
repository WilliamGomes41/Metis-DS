"""Audit room v1: bounded creation flow and persistence evidence."""
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


def _system(tmp_path):
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
    app = create_console_app(console)
    install_audit_routes(app, console)
    client = TestClient(app)
    response = client.post(
        "/login",
        data={"username": "anne", "password": "anne-secret"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return console, client, researcher


def test_audit_room_offers_generic_creation_but_only_experiment_is_enabled(tmp_path):
    _console, client, _researcher = _system(tmp_path)

    home = client.get("/audit")
    assert home.status_code == 200
    assert "Nieuwe audit" in home.text
    assert "Experiment" in home.text
    assert "Documentkwaliteit" in home.text
    assert "Publicatiecontrole" in home.text
    assert "Techniek &amp; release" in home.text
    assert home.text.count("Later beschikbaar") >= 3

    new = client.get("/audit/new")
    assert new.status_code == 200
    assert '/audit/new?type=experiment' in new.text
    assert '/audit/new?type=document_quality' not in new.text


def test_researcher_can_create_experiment_audit_and_reopen_it_after_registry_restart(tmp_path):
    console, client, researcher = _system(tmp_path)

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

    restarted = AuditRegistry(console.runtime)
    rows = restarted.list_audits()
    assert len(rows) == 1
    row = rows[0]
    assert row["created_by"] == researcher["account_id"]
    assert row["audit_type"] == "experiment"
    assert row["experiment"]["state"] == "setup"
    assert row["experiment"]["baseline"]["id"] == "production_passage_formation"
    assert row["experiment"]["candidate"]["id"] == "source_bound_semantic_passage_formation"

    stored = json.loads((console.runtime / "audits" / f'{row["audit_id"]}.json').read_text(encoding="utf-8"))
    assert stored == row


def test_disabled_audit_type_cannot_be_created_by_posting_it_directly(tmp_path):
    console, client, _researcher = _system(tmp_path)

    response = client.post(
        "/audit",
        data={
            "audit_type": "publication",
            "title": "Niet toegestaan",
            "question": "Mag dit publiceren?",
        },
    )
    assert response.status_code == 400
    assert "kan nog niet worden aangemaakt" in response.text
    assert AuditRegistry(console.runtime).list_audits() == []


def test_audit_creation_does_not_touch_canonical_or_publication_state(tmp_path):
    console, client, _researcher = _system(tmp_path)

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
