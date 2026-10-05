"""Issue #460: delegated, bounded read access; no domain mutations.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
import json
import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.g2_source_store import AzureBlobSourceStore, build_g2_locator
from src.metis_mcp_auth_v1 import McpAuthenticator, McpConfig
from src.metis_mcp_queries_v1 import McpQueries, McpQueryError
from src.metis_mcp_v1 import TOOLS, redact
from src.operations_console_app import create_console_app
from src.processing_evidence_export_v1 import processing_evidence_tables
from src.review_ledger import read_events
from test_vsa_review_workboard_v1 import _system, _login

TENANT = '11111111-1111-4111-8111-111111111111'
AUDIENCE = '22222222-2222-4222-8222-222222222222'
CLIENT = '33333333-3333-4333-8333-333333333333'
OID = '44444444-4444-4444-8444-444444444444'
CONFIG = McpConfig('https://testserver/mcp', TENANT, AUDIENCE, CLIENT)


class IdentityStore:
    def __init__(self, account):
        self.account, self.blocked, self.calls = account, False, []

    @contextmanager
    def _connect(self):
        yield self

    def execute(self, sql, args):
        assert sql.startswith('SELECT ') and 'NOT e.blocked' in sql
        assert args == (TENANT, OID)
        self.calls.append(sql)
        return SimpleNamespace(fetchone=lambda: None if self.blocked else self.account)


@pytest.fixture
def signed():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    claims = dict(tid=TENANT, oid=OID, aud=AUDIENCE, iss=CONFIG.issuer, ver='2.0',
                  azp=CLIENT, scp='Metis.Read2', iat=int(time.time()), nbf=int(time.time())-1,
                  exp=int(time.time())+300, roles=['Metis.Reviewer', 'Metis.Publisher'])
    return key, claims


def authenticator(account, signed):
    key, claims = signed
    store = IdentityStore(account)
    auth = McpAuthenticator(CONFIG, SimpleNamespace(store=store))
    auth.keys = SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key=key.public_key()))
    return auth, store, jwt.encode(claims, key, algorithm='RS256')


@pytest.mark.parametrize('change', [
    {'aud': CLIENT}, {'iss': 'https://evil.example'}, {'tid': CLIENT}, {'azp': AUDIENCE},
    {'scp': ''}, {'scp': 'Metis.Read'}, {'scp': 'Metis.Read20'},
    {'scp': 'Metis.Read2.extra'},
    {'ver': '1.0'}, {'exp': 1}, {'nbf': int(time.time())+10000},
    {'oid': 'not-an-identity'}, {'roles': 'Metis.Publisher'},
])
def test_signed_tokens_enforce_resource_delegation_and_time(signed, change):
    auth, store, _ = authenticator({'account_id': 'a', 'roles': ['publisher']}, signed)
    key, claims = signed
    claims.update(change)
    with pytest.raises(HTTPException) as error:
        auth(jwt.encode(claims, key, algorithm='RS256'))
    assert error.value.status_code == 401
    assert store.calls == []


def test_stale_token_cannot_override_block_or_current_roles(signed):
    auth, store, token = authenticator({'account_id': 'a', 'roles': ['reviewer']}, signed)
    assert auth(token)['roles'] == ['reviewer']
    store.blocked = True
    with pytest.raises(HTTPException) as error:
        auth(token)
    assert error.value.status_code == 403
    store.blocked = False
    store.account['roles'] = []
    with pytest.raises(HTTPException):
        auth(token)
    key, claims = signed
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(HTTPException) as error:
        auth(jwt.encode(claims, other_key, algorithm='RS256'))
    assert error.value.status_code == 401


@pytest.fixture
def connection(tmp_path, monkeypatch, signed):
    console, accounts, first, second = _system(tmp_path)
    auth, identity_store, token = authenticator(accounts['reviewer_a'], signed)
    import src.metis_mcp_v1 as mcp
    monkeypatch.setattr(mcp, 'configuration', lambda identity, origin: (CONFIG, 'Geconfigureerd; verbinding met ChatGPT nog testen'))
    monkeypatch.setattr(mcp, 'McpAuthenticator', lambda config, identity: auth)
    client = TestClient(create_console_app(console, trusted_origin='https://testserver'), base_url='https://testserver')
    def call(name, args=None):
        return client.post('/mcp', headers={'Authorization': 'Bearer '+token, 'MCP-Protocol-Version': '2025-11-25'},
                           json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': name, 'arguments': args or {}}})
    return console, accounts, first, second, client, call, identity_store, token


def test_protocol_auth_settings_and_unchanged_csrf(connection):
    console, accounts, first, second, client, call, store, token = connection
    assert client.post('/mcp', json={}).status_code == 401
    challenge = client.post('/mcp', json={}).headers['www-authenticate']
    assert 'resource_metadata=' in challenge
    expected_scope = f'api://{AUDIENCE}/Metis.Read2'
    assert f'scope="{expected_scope}"' in challenge
    metadata = client.get('/.well-known/oauth-protected-resource/mcp').json()
    assert metadata['resource'] == CONFIG.resource
    assert metadata['scopes_supported'] == [expected_scope]
    headers = {'Authorization': 'Bearer '+token}
    response = client.post('/mcp', headers=headers, json={'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-06-18'}})
    assert response.json()['result']['protocolVersion'] == '2025-06-18'
    assert client.post('/mcp', headers=headers, json={'jsonrpc': '2.0', 'method': 'notifications/initialized'}).status_code == 202
    listing = client.post('/mcp', headers=headers, json={'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}).json()['result']['tools']
    assert all(t['annotations']['readOnlyHint'] for t in listing)
    assert 'get_system_status' not in [t['name'] for t in listing]
    assert call('delete_document').json()['error']['code'] == -32602
    assert call('search_documents', {'limit': 5000}).json()['error']['code'] == -32602
    assert call('get_document', {'snapshot_id': '../../secret'}).json()['error']['code'] == -32602
    assert client.get('/mcp', headers=headers).status_code == 405
    assert client.post('/mcp', headers={**headers, 'Origin': 'https://evil.example'}, json={}).status_code == 403
    assert client.post('/login', data={}).status_code == 403
    assert client.get('/settings/chatgpt').status_code == 401
    # Session cookies alone never authorize MCP.
    session = console.authenticate('reviewer.a', __import__('test_vsa_review_workboard_v1').TEST_PASSWORD)
    from src.operations_console_app import COOKIE
    client.cookies.set(COOKIE, session['token'])
    assert 'ChatGPT-koppeling' in client.get('/settings').text
    settings = client.get('/settings/chatgpt')
    assert settings.status_code == 200 and CONFIG.resource in settings.text
    assert 'Configuratie voor de beheerder' not in settings.text
    assert client.post('/mcp', json={}).status_code == 401
    store.blocked = True
    assert call('search_documents').status_code == 403


def test_scope_export_equivalence_and_no_domain_writes(connection):
    console, accounts, first, second, client, call, store, token = connection
    before = deepcopy(console._envelopes), deepcopy(console._bindings), read_events(console._ledger_path)
    objects_before = {sid: console.snapshot_objects(sid, include_blocked=True) for sid in console._envelopes}
    rows = call('search_documents').json()['result']['structuredContent']['items']
    assert [r['snapshot_id'] for r in rows] == [first['snapshot_id']]
    assert call('get_document', {'snapshot_id': second['snapshot_id']}).json()['result']['isError']
    assert call('get_storage_status', {'snapshot_id': first['snapshot_id']}).json()['result']['isError']
    sid = first['snapshot_id']
    objects, revision = console.snapshot_objects_and_revision(sid, include_blocked=True)
    expected, _ = processing_evidence_tables(snapshot_id=sid, revision=revision, envelope=console._envelope(sid), objects=objects)
    evidence = call('get_processing_evidence', {'snapshot_id': sid, 'table': 'validation_findings'}).json()['result']['structuredContent']
    assert evidence['items'] == expected['validation_findings'][:25]
    assert evidence['objects_revision'] == revision
    assert 'binary_path' not in json.dumps(call('get_document', {'snapshot_id': sid}).json())
    for name in ('get_passages', 'get_review_history', 'get_publication_status'):
        assert not call(name, {'snapshot_id': sid}).json()['result']['isError']
    assert call('compare_versions', {'snapshot_id': sid, 'other_snapshot_id': second['snapshot_id']}).json()['result']['isError']
    assert before == (console._envelopes, console._bindings, read_events(console._ledger_path))
    assert objects_before == {s: console.snapshot_objects(s, include_blocked=True) for s in console._envelopes}
    # Grant removed between requests: no cached document entitlement.
    console._envelopes[sid]['named_reviewers'] = []
    assert call('get_document', {'snapshot_id': sid}).json()['result']['isError']


def test_disabled_endpoint_and_config_fail_closed(tmp_path, monkeypatch):
    console, _, _, _ = _system(tmp_path)
    monkeypatch.delenv('METIS_MCP_ENABLED', raising=False)
    client = TestClient(create_console_app(console))
    assert client.post('/mcp', json={}).status_code == 503
    monkeypatch.setenv('METIS_MCP_ENABLED', '1')
    assert TestClient(create_console_app(console)).post('/mcp', json={}).status_code == 503
    _login(client, 'publisher.carla')
    settings = client.get('/settings/chatgpt').text
    assert 'Configuratie voor de beheerder' in settings
    assert 'API-scope Metis.Read2 ' in settings


def test_lineage_preserves_source_locations_without_exposing_storage(connection):
    console, accounts, first, second, client, call, store, token = connection
    sid = first['snapshot_id']
    objects, revision = console.snapshot_objects_and_revision(sid, include_blocked=True)
    locator = {'section_path': ['Eenzaamheid', 'Aanbevelingen'], 'paragraph': 3}
    target = next(obj for obj in objects if obj.get('object_type') != 'document')
    target.setdefault('provenance', {})['source_fragments'] = [
        {'raw_object_id': 'raw-source-1', 'source_locator': locator, 'page': 2}]
    console._save_objects(sid, objects, expected_revision=revision)
    objects, revision = console.snapshot_objects_and_revision(sid, include_blocked=True)
    expected, _ = processing_evidence_tables(snapshot_id=sid, revision=revision,
                                            envelope=console._envelope(sid), objects=objects)
    evidence = call('get_processing_evidence', {'snapshot_id': sid, 'table': 'lineage',
                                              'object_id': target['object_id']}).json()['result']['structuredContent']
    expected_rows = [row for row in expected['lineage'] if row['object_id'] == target['object_id']]
    assert evidence['items'] == expected_rows[:25]
    assert any(row.get('locator') == locator for row in evidence['items'])
    assert console.snapshot_objects_and_revision(sid, include_blocked=True) == (objects, revision)
    assert redact({'locator': '/private/source.pdf', 'nested': {'token': 'secret',
                   'immutable_storage_locator': 'private-blob', 'page': 2}}) == {'nested': {'page': 2}}


def test_concurrent_probe_reads_and_safe_dependency_failure(monkeypatch):
    calls = []
    blob = SimpleNamespace(get_blob_properties=lambda **kw: (calls.append(kw) or SimpleNamespace(size=42)))
    store = AzureBlobSourceStore(blob_service_client=SimpleNamespace(get_blob_client=lambda **kw: blob))
    locator = build_g2_locator(sha256='a'*64, filename='test.pdf')
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(store.probe, [locator, locator])) == [{'status': 'present', 'size_bytes': 42}]*2
    assert len(calls) == 2
    def fail(**kw):
        raise RuntimeError('SECRET CONNECTION DETAILS')
    blob.get_blob_properties = fail
    assert store.probe(locator) == {'status': 'unavailable'}
    assert store.probe('https://evil.example/') == {'status': 'invalid_locator'}


def test_publisher_compare_publication_and_deletion_evidence(tmp_path):
    console, accounts, first, second = _system(tmp_path)
    queries = McpQueries(console, 'https://testserver')
    account, sid = accounts['publisher'], first['snapshot_id']
    result = queries.read(account, 'compare_versions', {'snapshot_id': sid, 'other_snapshot_id': second['snapshot_id']})
    assert result['objects_revision'] and result['other_objects_revision']
    console.canonical_publication_store = SimpleNamespace(active_publication_rows=lambda: [])
    assert queries.read(account, 'get_publication_status', {'snapshot_id': sid})['active_registry_object_count'] == 0
    assert queries.read(account, 'get_storage_status', {'snapshot_id': sid})['remote_source']['status'] == 'not_checked'
    console.canonical_publication_store = None
    console.delete_unpublished_snapshot(actor_id=accounts['researcher']['account_id'], snapshot_id=sid, confirmed=True, confirm_title='Document A')
    deleted = queries.read(account, 'get_storage_status', {'snapshot_id': sid})
    assert deleted['document_registered'] is False
    assert deleted['remote_source']['status'] == 'not_checked'
    assert len(deleted['deletion_events']) == 1


def test_transport_limits_and_safe_errors(connection, monkeypatch):
    console, accounts, first, second, client, call, store, token = connection
    headers = {'Authorization': 'Bearer '+token, 'Content-Type': 'application/json'}
    assert client.post('/mcp', headers=headers, content='x'*17000).status_code == 413
    assert client.post('/mcp', headers=headers, content='{').json()['error']['code'] == -32700
    assert client.post('/mcp', headers={**headers, 'MCP-Protocol-Version': 'invalid'}, json={}).status_code == 400
    assert client.post('/mcp', headers=headers, json=[]).status_code == 400
    def broken(*args, **kwargs):
        raise ValueError('DATABASE_SECRET_NOT_FOR_USER')
    monkeypatch.setattr(console, 'list_envelopes', broken)
    result = call('search_documents')
    assert result.json()['result']['isError']
    assert 'DATABASE_SECRET' not in result.text


# Reuse the repository's native PostgreSQL fixture; CI supplies this service.
from tests.test_workflow_chain_recovery_v1 import recovery_postgres, _install_schema  # noqa: E402,F401


def test_native_identity_read_and_block_survive_new_authenticator(recovery_postgres, tmp_path, signed):
    from src.console_entra_v1 import EntraConfig, EntraIdentity
    from src.workflows.workflow_identity_postgres_v1 import PostgresWorkflowIdentityStore
    store = PostgresWorkflowIdentityStore(recovery_postgres)
    store.verify_schema()
    identity = EntraIdentity(store, EntraConfig(TENANT, AUDIENCE, 'test-only-secret', 'https://testserver'))
    identity.prepare()
    key, claims = signed
    identity.sign_in(claims)
    with store._connect() as con:
        sessions_before = con.execute('SELECT count(*) AS n FROM workflow.sessions').fetchone()['n']
    def new_auth():
        auth = McpAuthenticator(CONFIG, identity)
        auth.keys = SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key=key.public_key()))
        return auth
    token = jwt.encode(claims, key, algorithm='RS256')
    assert new_auth()(token)['roles'] == ['publisher', 'reviewer']
    with store._connect() as con:
        assert con.execute('SELECT count(*) AS n FROM workflow.sessions').fetchone()['n'] == sessions_before
        con.execute('UPDATE workflow.entra_identities SET blocked=true WHERE tenant_id=%s AND object_id=%s', (TENANT, OID))
    with pytest.raises(HTTPException) as error:
        new_auth()(token)
    assert error.value.status_code == 403


def test_entra_navigation_does_not_intercept_mcp_discovery(tmp_path, monkeypatch):
    from src.console_entra_v1 import EntraConfig
    from src.operations_console_v1 import ConsoleError
    import src.console_entra_v1 as entra
    console, _, _, _ = _system(tmp_path)
    def deny(token):
        raise ConsoleError('not_authenticated')
    identity = SimpleNamespace(config=EntraConfig(TENANT, AUDIENCE, 'test-only-secret', 'https://testserver'), session_account=deny)
    monkeypatch.setattr(entra, 'install_entra', lambda *args: identity)
    monkeypatch.setenv('METIS_MCP_ENABLED', '1')
    monkeypatch.setenv('METIS_MCP_AUDIENCE', AUDIENCE)
    monkeypatch.setenv('METIS_MCP_CLIENT_ID', CLIENT)
    client = TestClient(create_console_app(console, trusted_origin='https://testserver'), base_url='https://testserver')
    assert client.get('/.well-known/oauth-protected-resource/mcp', follow_redirects=False).status_code == 200
    assert client.get('/.well-known/oauth-protected-resource', follow_redirects=False).status_code == 200
    assert client.get('/mcp', follow_redirects=False).status_code == 401
    assert client.get('/settings/chatgpt', follow_redirects=False).status_code == 303
    assert client.post('/accounts/access', data={}).status_code == 403


def test_processing_evidence_uses_only_current_object_versions(monkeypatch):
    import src.metis_mcp_queries_v1 as queries_module

    old = {"object_id": "obj-1", "object_version": "1.0"}
    current = {"object_id": "obj-1", "object_version": "1.1"}
    envelope = {
        "snapshot_id": "snap-1",
        "sha256": "source-sha",
        "named_reviewers": [],
        "uploader_account_id": "researcher",
    }

    class Console:
        def _envelope(self, snapshot_id):
            assert snapshot_id == "snap-1"
            return envelope

        def snapshot_objects_and_revision(self, snapshot_id, include_blocked=False):
            assert snapshot_id == "snap-1"
            assert include_blocked is True
            return [old, current], "rev-1"

    captured = {}

    def fake_processing_evidence_tables(*, snapshot_id, revision, envelope, objects):
        captured["objects"] = objects
        return {"forensic_trace": []}, []

    monkeypatch.setattr(queries_module, "processing_evidence_tables", fake_processing_evidence_tables)
    queries = McpQueries(Console(), "https://testserver")
    result = queries.read(
        {"account_id": "publisher", "roles": ["publisher"]},
        "get_processing_evidence",
        {"snapshot_id": "snap-1", "table": "forensic_trace"},
    )
    assert result["items"] == []
    assert captured["objects"] == [current]
