"""HTTP withdrawal is an explicit command over the existing authority.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import re

import pytest
from fastapi.testclient import TestClient

from src.canonical_publication_postgres_v1 import CanonicalPublicationStoreError, PostgresCanonicalPublicationStore
from tests.test_vsa_publish_readiness_ui_v1 import _console_with_document, TEST_PASSWORD


def _release_state(authority, release_id):
    with authority._connect() as connection:
        return connection.execute('SELECT status FROM publication_releases WHERE release_id=%s',
                                  (release_id,)).fetchone()['status']


def _system(tmp_path, monkeypatch, *, production_app, production_console):
    from tests.test_vsa_publish_readiness_ui_v1 import _complete_review
    console, accounts, receipt, _ = _console_with_document(tmp_path, production_console=production_console)
    _complete_review(console, accounts, receipt)
    result = console.publish(actor_id=accounts['publisher']['account_id'], snapshot_id=receipt['snapshot_id'])
    assert result['status'] == 'PASS'
    authority = console.canonical_publication_store
    authority.writes, authority.commands = 0, []
    withdraw = authority.withdraw_logical_document
    def observed(**command):
        authority.commands.append(command)
        result = withdraw(**command)
        authority.writes += not result['idempotent']
        return result
    monkeypatch.setattr(authority, 'withdraw_logical_document', observed)
    app = production_app(console, trusted_origin='https://testserver')
    client = TestClient(app, base_url='https://testserver', headers={'Origin': 'https://testserver'})
    payload = dict(snapshot_id=receipt['snapshot_id'], expected_release_id=result['release_id'],
                   reason='Bron ingetrokken', withdraw_confirmed='yes')
    return console, authority, client, payload


def _login(client, name="publisher.carla"):
    assert client.post("/login", data={"username": name, "password": TEST_PASSWORD}, follow_redirects=False).status_code == 303


def test_http_withdrawal_role_origin_confirmation_reason_and_expected_release(tmp_path, monkeypatch, *, production_app, production_console):
    console, authority, client, payload = _system(tmp_path, monkeypatch, production_app=production_app, production_console=production_console)
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
    assert f'name="expected_release_id" value="{payload["expected_release_id"]}"' in page.text
    assert client.post("/publish/withdraw", data=payload).status_code == 200
    assert authority.commands[-1]["actor"] == "publisher.carla"
    assert authority.commands[-1]["logical_document_id"] == console._envelope(payload["snapshot_id"])["logical_document_id"]
    assert authority.commands[-1]["withdrawn_at"]
    assert client.post("/publish/withdraw", data=payload).status_code == 200
    assert authority.writes == 1
    page = client.get("/publish")
    assert 'data-publication-state="withdrawn"' in page.text
    assert "status <b>ingetrokken</b>" in page.text.lower()
    assert "data-withdraw-form" not in page.text


@pytest.mark.parametrize("state", ["superseded", "withdrawn", "unavailable", "legacy"])
def test_inactive_unknown_or_legacy_release_never_offers_withdrawal(tmp_path, monkeypatch, state, *, production_app, production_console):
    console, authority, client, payload = _system(tmp_path, monkeypatch, production_app=production_app, production_console=production_console)
    _login(client)
    if state == "unavailable":
        def fail(*args):
            raise CanonicalPublicationStoreError("offline")
        monkeypatch.setattr(authority, "release_for_snapshot", fail)
    elif state == "superseded":
        from tests.test_live_v1_working_v2_v1 import _complete_review
        accounts = {a['username']: a for a in console.list_accounts()}
        sid = payload['snapshot_id']
        successor = console.create_review_successor(
            actor_id=accounts['researcher.anne']['account_id'], snapshot_id=sid,
            command_id='supersession-fixture', reason='Nieuwe beoordeling',
            expected_revision=console.objects_revision(sid),
            policy={'contract': 'explicit-review-v1', 'revision': 1,
                    'primary': accounts['reviewer.bert']['account_id'], 'assignments': []})
        _complete_review(console, reviewer_id=accounts['reviewer.bert']['account_id'],
                         snapshot_id=successor['snapshot_id'])
        assert console.publish(actor_id=accounts['publisher.carla']['account_id'],
                               snapshot_id=successor['snapshot_id'])['status'] == 'PASS'
        assert console.document_release_serving_status(sid)['release_status'] == 'superseded'
    elif state == "legacy":
        # Prepare the pre-lineage canonical representation in the owned test DB.
        with authority._connect() as connection:
            connection.execute("UPDATE audit_events SET details=details - 'logical_document_id' - 'working_revision_id' "
                               "WHERE entity_id=%s AND event_type='release_published'", (payload['expected_release_id'],))
    else:
        with authority._connect() as connection:
            connection.execute('UPDATE publication_releases SET status=%s WHERE release_id=%s',
                               (state, payload['expected_release_id']))
    response = client.get("/publish", params={"document": payload["snapshot_id"]})
    # The task page already handles an unavailable authority explicitly. A
    # navigation badge read must not replace that result with a generic error.
    assert response.status_code == 200
    if state == "unavailable":
        assert 'data-publication-state="authority_unavailable"' in response.text
        assert "Publicatiestatus onbekend" in response.text
    # A real successor has its own active card. Only this historical document
    # must lose its mutation forms.
    card = re.search(r'<article[^>]*data-publish-document="' + re.escape(payload['snapshot_id'])
                     + r'"[^>]*>(.*?)</article>', response.text, re.S)
    assert card
    assert "data-withdraw-form" not in card.group(1)
    assert "data-publish-form" not in card.group(1)
    assert authority.writes == 0


def test_committed_withdrawal_reports_pending_projection_and_retry_repairs_it(tmp_path, monkeypatch, *, production_app, production_console):
    console, authority, client, payload = _system(tmp_path, monkeypatch, production_app=production_app, production_console=production_console)
    _login(client)
    with monkeypatch.context() as patch:
        patch.setattr(console, "_sync_snapshot_from_authority", lambda *args: (_ for _ in ()).throw(OSError("injected PostgreSQL readback failure")))
        response = client.post("/publish/withdraw", data=payload)
    assert response.status_code == 200
    assert 'data-withdrawal-result="pending"' in response.text
    assert f'name="expected_release_id" value="{payload["expected_release_id"]}"' in response.text
    assert "Publicatie ingetrokken" in response.text
    assert _release_state(authority, payload["expected_release_id"]) == "withdrawn"
    response = client.post("/publish/withdraw", data=payload)
    assert 'data-withdrawal-result="current"' in response.text
    assert console._envelope(payload["snapshot_id"])["state"] == "withdrawn"
    assert authority.writes == 1


def test_lost_commit_response_is_reported_as_unknown_and_same_command_is_safe(tmp_path, monkeypatch, *, production_app, production_console):
    console, authority, client, payload = _system(tmp_path, monkeypatch, production_app=production_app, production_console=production_console)
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
    assert f'name="expected_release_id" value="{payload["expected_release_id"]}"' in response.text
    assert "niet uitgevoerd" not in response.text
    assert client.post("/publish/withdraw", data=payload).status_code == 200
    assert authority.writes == 1


def test_kernel_requires_expected_release_before_connecting():
    store = object.__new__(PostgresCanonicalPublicationStore)
    with pytest.raises(CanonicalPublicationStoreError, match="canonical_expected_release_required"):
        store.withdraw_logical_document(logical_document_id="logical", expected_release_id="", actor="publisher", reason="reason", withdrawn_at="2026-09-01T00:00:00Z")
