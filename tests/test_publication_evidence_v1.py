"""Publication observations are read-only and cannot grant publication authority.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag durable authority stale recovery
# release-control-evidence: toegang
# release-control-evidence: releasebewijs
# release-control-evidence: slop
"""
from copy import deepcopy
from pathlib import Path
import json
import subprocess
import sys

import pytest
from src.publication.publication_evidence_v1 import collect_publication, publication_report
from src.operations_console_v1 import ConsoleError
from tests.test_durable_publication_console_v1 import MemoryCanonicalStore, _ready_console

pytestmark = [pytest.mark.release_control_scope_belofte, pytest.mark.release_control_opslag,
              pytest.mark.release_control_toegang, pytest.mark.release_control_releasebewijs,
              pytest.mark.release_control_slop]


def observation():
    return {'schema':'publication-evidence-v1', 'snapshot_id':'snap-1', 'source_hash':'a'*64,
        'revision_sha256':'b'*64, 'consistent':True, 'errors':{},
        'observed_at':'2026-10-14T12:00:00+00:00', 'finished_at':'2026-10-14T12:00:01+00:00',
        'runtime':{'runtime_id':'1'*32, 'version':'a'*40},
        'release':{'release_id':'release-1', 'snapshot_id':'snap-1', 'source_hash':'a'*64,
                   'published_at':'2026-10-14T11:00:00+00:00', 'items':[['obj-1','1.0','c'*64]]},
        'registry_items':[['obj-1','1.0','c'*64]]}


def test_exact_release_restart_and_missing_end_to_end_obligations():
    before = observation()
    after = deepcopy(before)
    after.update(observed_at='2026-10-14T12:01:00+00:00', finished_at='2026-10-14T12:01:01+00:00',
                 runtime={'runtime_id':'2'*32, 'version':'a'*40})
    report = publication_report(before, after_restart=after)
    assert report['exact_release_active'] is True
    assert report['same_release_after_process_restart'] is True
    assert report['end_to_end_proven'] is False
    assert 'product_http_readback_not_supplied' in report['missing_evidence']
    after['runtime'] = before['runtime']
    report = publication_report(before, after_restart=after)
    assert report['same_release_after_process_restart'] is False
    assert 'distinct_process_restart_not_proven' in report['missing_evidence']


@pytest.mark.parametrize('change, conflict', [
    (lambda o: o['release'].update(source_hash='d'*64), 'release_identity_disagrees'),
    (lambda o: o.update(registry_items=[]), 'active_registry_differs_from_release'),
    (lambda o: o['release'].update(items=[['obj-1','1.0','bad']]), 'release_items_invalid'),
])
def test_identity_and_withdrawal_do_not_become_serving_success(change, conflict):
    raw = observation()
    change(raw)
    result = publication_report(raw)
    assert result['exact_release_active'] is False
    assert conflict in result['identity_conflicts']


def test_authorized_collection_after_real_publish_does_not_mutate_domain(tmp_path, *, production_console):
    console, accounts, receipt = _ready_console(tmp_path, production_console=production_console)
    authority = console.canonical_publication_store
    publisher = accounts['publisher']['account_id']
    sid = receipt['snapshot_id']
    initial = collect_publication(console, actor_id=publisher, snapshot_id=sid)
    assert initial['release'] is None
    console.publish(actor_id=publisher, snapshot_id=sid)
    persisted = _domain_state(console)
    releases = deepcopy(authority.release_for_snapshot(sid))
    read = collect_publication(console, actor_id=publisher, snapshot_id=sid)
    assert publication_report(read)['exact_release_active'] is True
    assert authority.release_for_snapshot(sid) == releases
    assert _domain_state(console) == persisted
    with pytest.raises(ConsoleError, match='publisher_role_required'):
        collect_publication(console, actor_id=accounts['reviewer']['account_id'], snapshot_id=sid)


def test_export_joins_publication_without_browser_and_does_not_overwrite(tmp_path):
    raw = tmp_path/'publication.json'
    raw.write_text(json.dumps(observation()))
    command = [sys.executable, 'scripts/export_section_incident.py', '--publication', str(raw), '--output', str(tmp_path/'export')]
    subprocess.run(command, check=True)
    report = json.loads((tmp_path/'export/incident.json').read_text())
    assert report['publication']['exact_release_active'] is True
    assert 'publication' in report['input_sha256']
    assert subprocess.run(command, capture_output=True).returncode == 2


def test_only_complete_exact_route_evidence_proves_end_to_end():
    before = observation()
    after = deepcopy(before)
    after.update(observed_at='2026-10-14T12:01:00+00:00', finished_at='2026-10-14T12:01:01+00:00', runtime={'runtime_id':'2'*32, 'version':'a'*40})
    route = {'schema':'publication-route-evidence-v1', 'snapshot_id':'snap-1', 'source_hash':'a'*64,
        'review_revision_sha256':'b'*64,
        'publish_command':{'status':'PASS','release_id':'release-1','revision_sha256':'b'*64,
            'snapshot_id':'snap-1','source_hash':'a'*64,'request_id':'3'*32,
            'started_at':'2026-10-14T10:59:59+00:00','finished_at':'2026-10-14T11:00:01+00:00'},
        'reviewed_items':[{'object_id':'obj-1','object_version':'1.0','content_hash':'c'*64}],
        'readiness':{'publication_ready':True,'publish_allowed':True,'blockers':[], 'revision_sha256':'b'*64,'observed_at':'2026-10-14T10:59:58+00:00'},
        'browser_incident':{'schema':'metis.section-incident.v1','correlation':'response_request_id',
            'missing_evidence':[], 'contradictions':[], 'application':{'response_completed':True},
            'browser':{'route':'/publish','usability':'passed','status':200,'navigation':'loaded',
                       'final_location':'target','assertion':'section-visible-v1','response_complete':True}},
        'product_readbacks':[{'release_id':'release-1','status':200,'synthetic_fixture':False,
            'observed_at':raw['observed_at'], 'runtime_id':raw['runtime']['runtime_id'],
            'items':[{'object_id':'obj-1','object_version':'1.0','content_hash':'c'*64}]} for raw in (before,after)]}
    assert publication_report(before, after_restart=after, route_evidence=route)['end_to_end_proven'] is True
    route['product_readbacks'][1]['items'][0]['object_version'] = '2.0'
    report = publication_report(before, after_restart=after, route_evidence=route)
    assert report['end_to_end_proven'] is False
    assert 'product_http_readback_not_proven' in report['missing_evidence']


def test_unavailable_store_has_safe_error_and_no_private_data(tmp_path, *, production_console):
    console, accounts, receipt = _ready_console(tmp_path, production_console=production_console)
    authority = console.canonical_publication_store
    authority.release_for_snapshot = lambda sid: (_ for _ in ()).throw(RuntimeError('private source text'))
    result = collect_publication(console, actor_id=accounts['publisher']['account_id'], snapshot_id=receipt['snapshot_id'])
    assert result['errors']['release'] == 'publication_authority_read_unavailable'
    assert 'private source text' not in json.dumps(result)
    assert publication_report(result)['canonical_release_observed'] is False


def test_http_export_and_product_readback_after_new_instances(tmp_path, *, production_app, production_console):
    from fastapi.testclient import TestClient
    from src.operations_console_app import create_console_app
    from src.product_api_v1 import create_product_app
    from tests.test_product_api_v1 import registry, paths, headers
    from tests.test_durable_publication_console_v1 import TEST_PASSWORD
    from src.publication.durable_publication_console_v1 import DurablePublicationConsole
    console, accounts, receipt = _ready_console(tmp_path, production_console=production_console)
    authority = console.canonical_publication_store
    sid = receipt['snapshot_id']
    client = TestClient(production_app(console), base_url='https://testserver')
    assert client.get('/source-selection/publication-evidence', params={'document':sid}, follow_redirects=False).status_code == 401
    assert client.post('/login', data={'username':'reviewer.bert','password':TEST_PASSWORD}, follow_redirects=False).status_code == 303
    assert client.get('/source-selection/publication-evidence', params={'document':sid}).status_code == 403
    client.post('/login', data={'username':'publisher.carla','password':TEST_PASSWORD}, follow_redirects=False)
    # Real Publish room and command, no mocked authorization/readiness boundary.
    assert client.get('/publish').status_code == 200
    result = console.publish(actor_id=accounts['publisher']['account_id'], snapshot_id=sid)
    response = client.get('/source-selection/publication-evidence', params={'document':sid})
    assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
    read = response.json()
    assert publication_report(read)['exact_release_active'] is True
    oid = read['release']['items'][0][0]
    for iteration in range(2):
        product = TestClient(create_product_app('real', paths=paths(tmp_path), tenant_registry=registry(docs=('*',)),
            canonical_publication_store=authority, immutable_source_store=console.immutable_source_store))
        serving = product.get('/v1/knowledge/'+oid, headers=headers())
        assert serving.status_code == 200
        payload = serving.json()
        assert payload['release']['release_id'] == result['release_id']
        assert payload['synthetic_fixture'] is False
        assert payload['object_version'] == read['release']['items'][0][1]
        assert payload['content_hash'] == read['release']['items'][0][2]
        product.close()
    from tests.production_support import restart_production
    fresh = restart_production(console)
    assert json.loads(json.dumps(collect_publication(fresh,actor_id=accounts['publisher']['account_id'],snapshot_id=sid)['release'])) == read['release']
    assert _release_count(authority) == 1
    client.close()


def test_invalid_publication_is_refused_without_release(tmp_path, *, production_console):
    console, accounts, receipt = _ready_console(tmp_path, production_console=production_console)
    authority = console.canonical_publication_store
    with pytest.raises(ConsoleError) as denied:
        console.publish(actor_id=accounts['reviewer']['account_id'], snapshot_id=receipt['snapshot_id'])
    assert denied.value.code == 'publisher_role_required'
    assert _release_count(authority) == 0
    console.immutable_source_store.blobs.clear()
    result = console.publish(actor_id=accounts['publisher']['account_id'], snapshot_id=receipt['snapshot_id'])
    assert result['status'] == 'BLOCKED'
    assert _release_count(authority) == 0
    assert console._envelope(receipt['snapshot_id'])['state'] == 'captured_not_published'


def test_registry_query_is_bounded_parameterized_and_read_only():
    from contextlib import contextmanager
    from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore, PostgresCanonicalConfig
    calls = []
    class Connection:
        def execute(self, query, parameters):
            calls.append((query, parameters))
            return self
        def fetchall(self):
            return [{'object_id':'obj-1','object_version':'1.0','content_hash':'c'*64}]
    class Store(PostgresCanonicalPublicationStore):
        @contextmanager
        def _connect(self):
            yield Connection()
    store = Store(PostgresCanonicalConfig(dsn="postgresql://localhost/test"))
    assert store.active_release_items('release-1') == [{'object_id':'obj-1','object_version':'1.0','content_hash':'c'*64}]
    sql, params = calls[0]
    assert params == ('release-1',2049)
    assert "r.state='active'" in sql and 'LIMIT %s' in sql
    assert 'canonical_json' not in sql


def test_registry_outage_preserves_already_observed_commit(tmp_path, *, production_console):
    console, accounts, receipt = _ready_console(tmp_path, production_console=production_console)
    authority = console.canonical_publication_store
    console.publish(actor_id=accounts['publisher']['account_id'], snapshot_id=receipt['snapshot_id'])
    authority.active_release_items = lambda release_id: (_ for _ in ()).throw(OSError('private database message'))
    read = collect_publication(console, actor_id=accounts['publisher']['account_id'],snapshot_id=receipt['snapshot_id'])
    report = publication_report(read)
    assert report['canonical_release_observed'] is True
    assert report['exact_release_active'] is False
    assert 'active_registry_read_missing' in report['missing_evidence']
    assert 'private database message' not in json.dumps(read)


def test_actual_publication_boundaries_correlate_without_rerunning_readiness(tmp_path, monkeypatch, *, production_app, production_console):
    from fastapi.testclient import TestClient
    from src.operations_console_app import create_console_app
    from src.request_diagnostics_v1 import RequestDiagnostics, _LOGGER
    from src.publication.publication_evidence_v1 import publication_route_from_events
    from tests.test_durable_publication_console_v1 import TEST_PASSWORD
    console, accounts, receipt = _ready_console(tmp_path, production_console=production_console)
    authority = console.canonical_publication_store
    events = []
    monkeypatch.setattr(_LOGGER, 'info', lambda fmt, payload: events.append(json.loads(payload)))
    client = TestClient(production_app(console), base_url='https://testserver')
    client.post('/login', data={'username':'publisher.carla','password':TEST_PASSWORD})
    response = client.post('/publish', data={'snapshot_id':receipt['snapshot_id'],'publish_confirmed':'yes'}, follow_redirects=False)
    assert response.status_code == 303
    observed = collect_publication(console,actor_id=accounts['publisher']['account_id'],snapshot_id=receipt['snapshot_id'])
    evidence = publication_route_from_events(observed,events)
    assert evidence['publish_command']['request_id'] == response.headers['x-metis-request-id']
    assert evidence['readiness']['publication_ready'] is True
    assert evidence['reviewed_items'][0]['content_hash'] == observed['release']['items'][0][2]
    checked = next(row for row in events if row.get('event') == 'publication_checked')
    duplicated = publication_route_from_events(observed,events+[checked])
    assert duplicated['boundary_evidence_missing'] == 'publication_boundaries_missing_or_duplicate'
    assert 'source_locator' not in json.dumps(events)
    client.close()


def test_ordinary_telemetry_failure_does_not_undo_publication(tmp_path, monkeypatch, *, production_console):
    from src.request_diagnostics_v1 import _LOGGER
    console, accounts, receipt = _ready_console(tmp_path, production_console=production_console)
    authority = console.canonical_publication_store
    monkeypatch.setattr(_LOGGER,'info',lambda *args: (_ for _ in ()).throw(OSError('offline')))
    result = console.publish(actor_id=accounts['publisher']['account_id'],snapshot_id=receipt['snapshot_id'])
    assert result['status'] == 'PASS'
    assert _release_count(authority) == 1


def test_revision_read_failure_remains_an_explicit_evidence_gap(tmp_path, monkeypatch, *, production_console):
    console, accounts, receipt = _ready_console(tmp_path, production_console=production_console)
    authority = console.canonical_publication_store
    console.publish(actor_id=accounts['publisher']['account_id'],snapshot_id=receipt['snapshot_id'])
    monkeypatch.setattr(console,'objects_revision',lambda sid: (_ for _ in ()).throw(OSError('private DB error')))
    read = collect_publication(console,actor_id=accounts['publisher']['account_id'],snapshot_id=receipt['snapshot_id'])
    assert read['release'] is not None
    assert read['errors']['revision'] == 'document_revision_read_unavailable'
    report = publication_report(read)
    assert report['end_to_end_proven'] is False
    assert 'document_identity_missing' in report['missing_evidence']


def _release_count(authority):
    with authority._connect() as connection:
        return connection.execute("SELECT count(*) AS n FROM publication_releases").fetchone()['n']


def _domain_state(console):
    from src.workflows.workflow_chain_recovery_v1 import PostgresWorkflowRecoveryAdapter
    state = PostgresWorkflowRecoveryAdapter(console.canonical_publication_store).export_state()
    return {key: value for key, value in state.items() if key.endswith('tables') or key == 'entra_identities'}


def test_repeat_publish_reuses_active_release_and_cannot_reactivate_withdrawal(tmp_path, *, production_console):
    """Protocol 4.3.1 describes existing repeat semantics without a second cutover."""
    from tests.production_support import restart_production

    console, accounts, receipt = _ready_console(tmp_path, production_console=production_console)
    publisher = accounts['publisher']['account_id']
    sid = receipt['snapshot_id']
    first = console.publish(actor_id=publisher, snapshot_id=sid)
    assert first['status'] == 'PASS'
    release_before = collect_publication(console, actor_id=publisher, snapshot_id=sid)['release']
    objects_before = deepcopy(console.snapshot_objects(sid))

    restarted = restart_production(console)
    repeated = restarted.publish(actor_id=publisher, snapshot_id=sid)
    assert repeated['status'] == 'PASS'
    assert repeated['release_id'] == first['release_id']
    assert _release_count(restarted.canonical_publication_store) == 1
    assert collect_publication(restarted, actor_id=publisher, snapshot_id=sid)['release'] == release_before
    assert restarted.snapshot_objects(sid) == objects_before

    restarted.withdraw_document(actor_id=publisher, snapshot_id=sid,
                                expected_release_id=first['release_id'], reason='Protocol alignment test')
    after_withdrawal = restart_production(restarted)
    refused = after_withdrawal.publish(actor_id=publisher, snapshot_id=sid)
    assert refused['status'] == 'BLOCKED'
    assert 'release_withdrawn' in refused['blockers']
    assert _release_count(after_withdrawal.canonical_publication_store) == 1
    assert not after_withdrawal.canonical_publication_store.active_release_items(first['release_id'])
