"""HTTP withdrawal is an explicit command over the existing authority.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from src.canonical_publication_postgres_v1 import CanonicalPublicationStoreError, PostgresCanonicalPublicationStore
from src.operations_console_app import create_console_app
from src.publish_readiness_ui_v1 import install_publish_readiness_ui
from tests.test_vsa_publish_readiness_ui_v1 import _console_with_document, TEST_PASSWORD


class Authority(PostgresCanonicalPublicationStore):
    """UI/facade test double; separate native tests prove the SQL transaction."""
    def __init__(self, envelope):
        self.release = dict(release_id="r1", release_version="1", release_owner="publisher.carla",
                            published_at="2026-09-01T00:00:00+00:00", snapshot_id=envelope["snapshot_id"],
                            source_sha256=envelope["sha256"], source_locator=envelope["immutable_storage_locator"],
                            logical_document_id="logical-1", objects=[])
        self.state = "published"
        self.writes = 0
        self.commands = []

    def release_for_snapshot(self, sid):
        return deepcopy(self.release) if sid == self.release["snapshot_id"] else None

    def active_publication_rows(self):
        return []

    def withdraw_logical_document(self, **command):
        self.commands.append(command)
        if not command["reason"].strip():
            raise CanonicalPublicationStoreError("canonical_withdrawal_reason_required")
        if command["expected_release_id"] != self.release["release_id"]:
            raise CanonicalPublicationStoreError("canonical_expected_release_changed")
        repeated = self.state == "withdrawn"
        self.writes += not repeated
        self.state = "withdrawn"
        return {"status": "PASS", "release_id": self.release["release_id"], "idempotent": repeated}


def _system(tmp_path, monkeypatch):
    console, accounts, receipt, _ = _console_with_document(tmp_path)
    authority = Authority(receipt)
    console.canonical_publication_store = authority
    monkeypatch.setattr(console, "document_release_serving_status", lambda *a, **kw: {
        "release_status": authority.state,
        "serving_status": "active" if authority.state == "published" else "inactive",
    })
    app = create_console_app(console, trusted_origin="https://testserver")
    install_publish_readiness_ui(app, console)
    client = TestClient(app, base_url="https://testserver", headers={"Origin": "https://testserver"})
    payload = dict(snapshot_id=receipt["snapshot_id"], expected_release_id="r1", reason="Bron ingetrokken", withdraw_confirmed="yes")
    return console, authority, client, payload


def _login(client, name="publisher.carla"):
    assert client.post("/login", data={"username": name, "password": TEST_PASSWORD}, follow_redirects=False).status_code == 303


def test_http_withdrawal_role_origin_confirmation_reason_and_expected_release(tmp_path, monkeypatch):
    console, authority, client, payload = _system(tmp_path, monkeypatch)
    assert client.post("/publish/withdraw", data=payload).status_code == 401
    _login(client, "reviewer.bert")
    assert client.post("/publish/withdraw", data=payload).status_code == 403
    _login(client)
    assert client.post("/publish/withdraw", data=payload, headers={"Origin": "https://evil.test"}).status_code == 403
    for field in ("withdraw_confirmed", "reason", "expected_release_id"):
        assert client.post("/publish/withdraw", data={**payload, field: ""}).status_code == 400
    stale = client.post("/publish/withdraw", data={**payload, "expected_release_id": "old"})
    assert stale.status_code == 409
    assert authority.writes == 0
    page = client.get("/publish")
    assert 'name="expected_release_id" value="r1"' in page.text
    assert client.post("/publish/withdraw", data=payload).status_code == 200
    assert authority.commands[-1]["actor"] == "publisher.carla"
    assert authority.commands[-1]["logical_document_id"] == "logical-1"
    assert authority.commands[-1]["withdrawn_at"]
    assert client.post("/publish/withdraw", data=payload).status_code == 200
    assert authority.writes == 1
    page = client.get("/publish")
    assert 'data-publication-state="withdrawn"' in page.text
    assert "status <b>ingetrokken</b>" in page.text.lower()
    assert "data-withdraw-form" not in page.text


@pytest.mark.parametrize("state", ["superseded", "withdrawn", "unavailable", "legacy"])
def test_inactive_unknown_or_legacy_release_never_offers_withdrawal(tmp_path, monkeypatch, state):
    console, authority, client, payload = _system(tmp_path, monkeypatch)
    _login(client)
    if state == "unavailable":
        def fail(*args):
            raise CanonicalPublicationStoreError("offline")
        monkeypatch.setattr(authority, "release_for_snapshot", fail)
    elif state == "legacy":
        authority.release["logical_document_id"] = ""
    else:
        authority.state = state
    response = client.get("/publish")
    # The task page already handles an unavailable authority explicitly. A
    # navigation badge read must not replace that result with a generic error.
    assert response.status_code == 200
    if state == "unavailable":
        assert 'data-publication-state="authority_unavailable"' in response.text
        assert "Publicatiestatus onbekend" in response.text
    assert "data-withdraw-form" not in response.text
    assert "data-publish-form" not in response.text
    assert authority.writes == 0


def test_committed_withdrawal_reports_pending_projection_and_retry_repairs_it(tmp_path, monkeypatch):
    console, authority, client, payload = _system(tmp_path, monkeypatch)
    _login(client)
    with monkeypatch.context() as patch:
        patch.setattr(console, "_sync_snapshot_from_authority", lambda *args: (_ for _ in ()).throw(OSError("disk full")))
        response = client.post("/publish/withdraw", data=payload)
    assert response.status_code == 200
    assert 'data-withdrawal-result="pending"' in response.text
    assert 'name="expected_release_id" value="r1"' in response.text
    assert "Publicatie ingetrokken" in response.text
    assert authority.state == "withdrawn"
    response = client.post("/publish/withdraw", data=payload)
    assert 'data-withdrawal-result="current"' in response.text
    assert console._envelope(payload["snapshot_id"])["state"] == "withdrawn"
    assert authority.writes == 1


def test_lost_commit_response_is_reported_as_unknown_and_same_command_is_safe(tmp_path, monkeypatch):
    console, authority, client, payload = _system(tmp_path, monkeypatch)
    _login(client)
    original = authority.withdraw_logical_document
    def lost_response(**command):
        original(**command)
        raise CanonicalPublicationStoreError("canonical_postgres_write_failed")
    with monkeypatch.context() as patch:
        patch.setattr(authority, "withdraw_logical_document", lost_response)
        response = client.post("/publish/withdraw", data=payload)
    assert response.status_code == 503
    assert "Uitkomst niet bevestigd" in response.text
    assert 'name="expected_release_id" value="r1"' in response.text
    assert "niet uitgevoerd" not in response.text
    assert client.post("/publish/withdraw", data=payload).status_code == 200
    assert authority.writes == 1


def test_kernel_requires_expected_release_before_connecting():
    store = object.__new__(PostgresCanonicalPublicationStore)
    with pytest.raises(CanonicalPublicationStoreError, match="canonical_expected_release_required"):
        store.withdraw_logical_document(logical_document_id="logical", expected_release_id="", actor="publisher", reason="reason", withdrawn_at="2026-09-01T00:00:00Z")
