"""Audit room v1: bounded creation flow, generic store and read-only audit evidence."""
# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
from __future__ import annotations

import hashlib
import json

from fastapi.testclient import TestClient

from src.audit_room_v1 import AuditRegistry, install_audit_routes
from src.operations_console_app import create_console_app
from src.operations_console_v1 import OperationsConsole


class _MemoryArchiveStore:
    def __init__(self) -> None:
        self.data: dict[str, bytes] = {}

    def store_verified(self, *, audit_id: str, data: bytes, sha256: str) -> str:
        assert hashlib.sha256(data).hexdigest() == sha256
        locator = f"memory-audit://{audit_id}"
        self.data[locator] = bytes(data)
        return locator

    def load_verified(self, locator: str, *, expected_sha256: str) -> bytes:
        data = self.data[locator]
        assert hashlib.sha256(data).hexdigest() == expected_sha256
        return data

    def delete_verified(self, locator: str) -> bool:
        return self.data.pop(locator, None) is not None


def _system(
    tmp_path,
    *,
    with_document: bool = False,
    semantic_safety_post_json=None,
    deployed_commit_path=None,
    archive_store=None,
):
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
    install_audit_routes(
        app,
        console,
        semantic_safety_post_json=semantic_safety_post_json,
        deployed_commit_path=deployed_commit_path,
        archive_store=archive_store,
    )
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
    assert "/audit/llm-settings" not in home.text
    assert home.text.count("Later beschikbaar") == 2

    new = client.get("/audit/new")
    assert new.status_code == 200
    assert '/audit/new?type=experiment' in new.text
    assert '/audit/new?type=document_quality' in new.text
    assert '/audit/new?type=publication' not in new.text


def test_audit_moves_out_of_primary_navigation_and_under_settings(tmp_path):
    _console, client, _researcher, _receipt = _system(tmp_path)

    home = client.get("/")
    assert home.status_code == 200
    assert '<a href="/audit">Audit</a>' not in home.text
    assert home.text.count('<a class="home-tile') == 4
    assert "Onderzoeken &amp; controleren" not in home.text
    assert 'class="review-control-card" href="/audit"' not in home.text

    settings = client.get("/settings")
    assert settings.status_code == 200
    assert 'href="/audit"' in settings.text
    assert "Audit &amp; diagnostiek" in settings.text

    audit = client.get("/audit")
    assert audit.status_code == 200
    assert "Audit &amp; diagnostiek" in audit.text
    assert '<a href="/settings" aria-current="page">Instellingen</a>' in audit.text


def test_researcher_archives_audit_to_external_store_and_reads_it_back(tmp_path):
    archive_store = _MemoryArchiveStore()
    console, client, researcher, _receipt = _system(tmp_path, archive_store=archive_store)
    before_envelopes = console.list_envelopes()

    created = AuditRegistry(console.runtime).create(
        audit_type="experiment",
        title="Te archiveren audit",
        actor_id=researcher["account_id"],
        payload={"state": "setup", "question": "Bewaar dit bewijs."},
    )

    detail = client.get(f'/audit/{created["audit_id"]}')
    assert detail.status_code == 200
    assert "Archiveren" in detail.text

    response = client.post(
        f'/audit/{created["audit_id"]}/archive',
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == f'/audit/archive/{created["audit_id"]}'
    assert AuditRegistry(console.runtime).get_audit(created["audit_id"]) is None

    reference_path = console.runtime / "audits" / f'{created["audit_id"]}.json'
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    assert reference["record_kind"] == "archived_audit_ref"
    assert "payload" not in reference
    assert reference["audit_id"] == created["audit_id"]
    assert reference["archive_locator"] in archive_store.data
    assert not (console.runtime / "audits" / "archive-index").exists()

    archive = client.get("/audit/archive")
    assert archive.status_code == 200
    assert "Te archiveren audit" in archive.text

    archived = client.get(response.headers["location"])
    assert archived.status_code == 200
    assert "Gearchiveerde audit" in archived.text
    assert "alleen-lezen" in archived.text
    assert "Bewaar dit bewijs." in archived.text
    assert "Archiveren" not in archived.text
    assert console.list_envelopes() == before_envelopes
    assert not (console.runtime / "published_projection.jsonl").exists()


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



def test_frozen_semantic_safety_run_uses_shared_provider_and_persists_only_audit_evidence(
    tmp_path,
    monkeypatch,
):
    baseline_commit = "79b35616725da3a1f42a938c2f5a874ca16cfad0"
    deployed_commit = "47e7652574ee37f91fbd58e5ffa16b2dfd44b378"
    monkeypatch.setenv("METIS_LLM_MODEL", "test-model")
    monkeypatch.setenv("METIS_LLM_API_KEY", "shared-provider-secret")
    marker = tmp_path / "deployed_commit.txt"
    marker.write_text(deployed_commit + "\n", encoding="utf-8")

    def full_source_model(_url: str, _headers: dict, payload: dict, _timeout: int) -> dict:
        block = json.loads(payload["input"][1]["content"])["source_blocks"][0]
        return {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                {
                                    "objects": [
                                        {
                                            "spans": [
                                                {
                                                    "block_id": block["block_id"],
                                                    "start": 0,
                                                    "end": len(block["text"]),
                                                }
                                            ],
                                            "proposed_object_type": "unclassified",
                                        }
                                    ],
                                    "abstain_reason": None,
                                }
                            ),
                        }
                    ],
                }
            ]
        }

    console, client, researcher, _receipt = _system(
        tmp_path,
        semantic_safety_post_json=full_source_model,
        deployed_commit_path=marker,
    )
    before_envelopes = console.list_envelopes()

    page = client.get("/audit/semantic-safety")
    assert page.status_code == 200
    assert "Frozen semantic safety" in page.text
    assert "Frozen audit uitvoeren" in page.text
    assert baseline_commit in page.text
    assert deployed_commit in page.text

    response = client.post("/audit/semantic-safety/run", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/audit/audit-")

    rows = AuditRegistry(console.runtime).list_audits()
    assert len(rows) == 1
    row = rows[0]
    assert row["created_by"] == researcher["account_id"]
    assert row["audit_type"] == "experiment"
    assert row["payload"]["state"] == "semantic_safety_completed"
    report = row["payload"]["safety_report"]
    assert report["machine_safety_pass"] is True
    assert report["candidate_pass_count"] == 5
    assert report["requires_human_review"] is True
    assert report["model"] == "test-model"
    assert report["suite_baseline_commit"] == baseline_commit
    assert report["deployed_commit"] == deployed_commit
    assert "shared-provider-secret" not in json.dumps(row, ensure_ascii=False)

    detail = client.get(response.headers["location"])
    assert detail.status_code == 200
    assert "Machinecheck PASS" in detail.text
    assert "geen activatiebesluit" in detail.text
    assert console.list_envelopes() == before_envelopes
    assert not (console.runtime / "published_projection.jsonl").exists()
    assert not (console.runtime / "release_manifests").exists()


def test_frozen_semantic_safety_run_accepts_later_valid_deployment_commit(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("METIS_LLM_MODEL", "test-model")
    monkeypatch.setenv("METIS_LLM_API_KEY", "shared-provider-secret")
    marker = tmp_path / "deployed_commit.txt"
    later_commit = "a" * 40
    marker.write_text(later_commit + "\n", encoding="utf-8")

    def full_source_model(_url: str, _headers: dict, payload: dict, _timeout: int) -> dict:
        block = json.loads(payload["input"][1]["content"])["source_blocks"][0]
        return {
            "output": [{
                "type": "message",
                "content": [{
                    "type": "output_text",
                    "text": json.dumps({
                        "objects": [{
                            "spans": [{
                                "block_id": block["block_id"],
                                "start": 0,
                                "end": len(block["text"]),
                            }],
                            "proposed_object_type": "unclassified",
                        }],
                        "abstain_reason": None,
                    }),
                }],
            }]
        }

    console, client, _researcher, _receipt = _system(
        tmp_path,
        semantic_safety_post_json=full_source_model,
        deployed_commit_path=marker,
    )

    page = client.get("/audit/semantic-safety")
    assert "Frozen audit uitvoeren" in page.text
    assert later_commit in page.text
    assert "79b35616725da3a1f42a938c2f5a874ca16cfad0" in page.text

    response = client.post("/audit/semantic-safety/run", follow_redirects=False)
    assert response.status_code == 303
    report = AuditRegistry(console.runtime).list_audits()[0]["payload"]["safety_report"]
    assert report["suite_baseline_commit"] == "79b35616725da3a1f42a938c2f5a874ca16cfad0"
    assert report["deployed_commit"] == later_commit


def test_frozen_semantic_safety_run_fails_closed_on_invalid_packaged_commit(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("METIS_LLM_MODEL", "test-model")
    monkeypatch.setenv("METIS_LLM_API_KEY", "shared-provider-secret")
    marker = tmp_path / "deployed_commit.txt"
    marker.write_text("not-a-commit\n", encoding="utf-8")

    console, client, _researcher, _receipt = _system(
        tmp_path,
        deployed_commit_path=marker,
    )

    page = client.get("/audit/semantic-safety")
    assert "Run geblokkeerd" in page.text
    assert "geldige packaged deployment-commit ontbreekt" in page.text
    assert "Frozen audit uitvoeren" not in page.text

    response = client.post("/audit/semantic-safety/run")
    assert response.status_code == 200
    assert "Geen geldige packaged deployment-commit beschikbaar" in response.text
    assert AuditRegistry(console.runtime).list_audits() == []


def test_frozen_semantic_safety_run_fails_closed_without_packaged_commit(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("METIS_LLM_MODEL", "test-model")
    monkeypatch.setenv("METIS_LLM_API_KEY", "shared-provider-secret")
    console, client, _researcher, _receipt = _system(
        tmp_path,
        deployed_commit_path=tmp_path / "missing-deployed-commit.txt",
    )

    page = client.get("/audit/semantic-safety")
    assert "Run geblokkeerd" in page.text
    assert "Frozen audit uitvoeren" not in page.text

    response = client.post("/audit/semantic-safety/run")
    assert response.status_code == 200
    assert "Geen geldige packaged deployment-commit beschikbaar" in response.text
    assert AuditRegistry(console.runtime).list_audits() == []
