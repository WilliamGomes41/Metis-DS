"""Atomic support repair and command-local review evidence on PostgreSQL.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag durable concurrent stale recovery
# release-control-evidence: toegang kwaliteit slop releasebewijs
"""
from threading import Thread

import pytest
from fastapi.testclient import TestClient

from src.deterministic_review_repair_v1 import REPAIR_SUPPORT_RELATION
from src.review_ledger import append_event, buffer_events, read_events, verify_ledger
from tests.production_support import restart_production


def _durable(console):
    from src.workflows.workflow_chain_recovery_v1 import PostgresWorkflowRecoveryAdapter
    state = PostgresWorkflowRecoveryAdapter(console.canonical_publication_store).export_state()
    return {key: value for key, value in state.items() if key.endswith('tables') or key == 'entra_identities'}


def _ready(production_console, azure=False):
    from tests.test_durable_publication_console_v1 import MemorySourceStore
    from tests.semantic_fixture_support import bind_fixture_selections
    console = production_console(azure=azure, immutable_source_store=MemorySourceStore(),
        processing_binder=lambda console: None, environment={'CONSOLE_PUBLIC_ORIGIN':'https://testserver'})
    author = console.create_account(username='author', password='fixture-password', roles=['researcher'])
    reviewer = console.create_account(username='reviewer', password='fixture-password', roles=['reviewer'])
    bind_fixture_selections(console)
    receipt = console.ingest(actor_id=author['account_id'], filename='support.html', content_type='text/html',
        data=b'<html><h1>Begrippen</h1><p>Een observatie is een systematische waarneming.</p><p>Een controle beschrijft de waargenomen verandering.</p></html>',
        ingest_kind='new', title='Support evidence', version='1', date='2026-10-20', live_url='',
        class_='richtlijn', family='support-evidence', named_reviewers=[reviewer['account_id']])
    sid = receipt['snapshot_id']
    objects = [o for o in console.snapshot_objects(sid) if o['object_type'] not in {'document','heading'}
               and o.get('proposed_object_type') != 'heading']
    assert len(objects) == 2
    support, claim = objects
    payload = {'snapshot_id':sid, 'object_id':support['object_id'], 'claim_object_id':claim['object_id'],
               'snapshot_revision':console.objects_revision(sid), 'suitability':'alleen_onderbouwing',
               'comment':'Deze passage onderbouwt de tweede passage.', 'repair_kind':REPAIR_SUPPORT_RELATION}
    app = console._metis_test_application
    client = TestClient(app, base_url='https://testserver', headers={'Origin':'https://testserver'}, raise_server_exceptions=False)
    assert client.post('/login', data={'username':'reviewer','password':'fixture-password'}, follow_redirects=False).status_code == 303
    return console, client, sid, support, claim, payload


@pytest.mark.parametrize('azure', [False, True])
def test_support_repair_http_commits_both_objects_and_evidence_then_restarts(production_console, azure):
    from src.serving_relations_v1 import binding_relations
    console, client, sid, support, claim, payload = _ready(production_console, azure)
    before = _durable(console)
    source_bytes = dict(console.immutable_source_store.blobs)
    identity = {k:console._envelope(sid).get(k) for k in ['snapshot_id','logical_document_id','working_revision_id','sha256','immutable_storage_locator']}
    response = client.post('/review/resolve', data=payload, follow_redirects=False)
    assert response.status_code == 303, response.text
    assert console.immutable_source_store.blobs==source_bytes
    assert {k:console._envelope(sid).get(k) for k in identity}==identity
    current = {o['object_id']:o for o in console.snapshot_objects(sid)}
    assert all(current[o['object_id']]['governance']['validation_status']=='needs_review' for o in [support,claim])
    assert any(r.get('relation_type')=='supported_by' and r.get('target_object_id')==support['object_id']
               for r in binding_relations(current[claim['object_id']]))
    assert any(e['event_type']=='review_audit_evidence' and e['details'].get('decision')=='repair_support'
               for e in read_events(console._ledger_path))
    assert verify_ledger(console._ledger_path)==[]
    assert console.publication_readiness(sid)['publication_ready'] is False
    committed = _durable(console)
    assert committed['tables'] == before['tables']  # No canonical release/serving mutation.
    fresh = restart_production(console)
    assert _durable(fresh)==committed
    assert fresh.snapshot_objects(sid)==console.snapshot_objects(sid)
    client.close()


@pytest.mark.parametrize('azure', [False, True])
def test_late_support_audit_failure_rolls_back_all_pg_state(production_console, monkeypatch, azure):
    from src.serving_relations_v1 import binding_relations
    console, client, sid, support, claim, payload = _ready(production_console, azure)
    before = _durable(console)
    real = console._append_audit_evidence
    reached = []
    def fail_late(**command):
        event = real(**command)
        if command['decision']=='repair_support':
            assert any(r.get('relation_type')=='supported_by' and r.get('target_object_id')==support['object_id']
                       for r in binding_relations(console._current_object(sid, claim['object_id'])))
            reached.append(event)
            raise RuntimeError('injected_late_support_audit_failure')
        return event
    monkeypatch.setattr(console, '_append_audit_evidence', fail_late)
    response = client.post('/review/resolve', data=payload, follow_redirects=False)
    assert response.status_code == 500
    assert len(reached)==1
    assert _durable(console)==before
    assert _durable(restart_production(console))==before
    assert verify_ledger(console._ledger_path)==[]
    client.close()


def test_command_buffer_visibility_is_nested_context_local_and_copy_safe(production_console):
    from src.review_ledger import read_command_events
    console = production_console(processing_binder=lambda console: None)
    path = console._ledger_path
    def event(name):
        return append_event(path, event_type=name, object_id='fixture', object_version='1', actor='fixture', details={})
    before = read_events(path)
    observed = []
    with buffer_events(path):
        first = event('outer')
        with buffer_events(path):
            second = event('inner')
            assert read_command_events(path)[-2:]==[first,second]
            assert read_events(path)==before
            assert console.workflow_review_store.read_events_after(None, 100)==before
            thread = Thread(target=lambda: observed.append(read_command_events(path)))
            thread.start(); thread.join(timeout=5)
            assert not thread.is_alive() and observed==[before]
            copied = read_command_events(path)
            copied[-1]['details']['mutated']=True
            assert 'mutated' not in read_command_events(path)[-1]['details']
        try:
            with buffer_events(path):
                event('discarded')
                raise RuntimeError('discard this nested level')
        except RuntimeError:
            pass
        assert read_command_events(path)[-2:]==[first,second]
        assert read_events(path)==before
    assert read_events(path)[-2:]==[first,second]
    assert read_command_events(path)==read_events(path)
    assert verify_ledger(path)==[]
    committed = read_events(path)
    with pytest.raises(RuntimeError, match='discard outer'):
        with buffer_events(path):
            event('discarded-outer')
            assert read_command_events(path)[-1]['event_type']=='discarded-outer'
            raise RuntimeError('discard outer')
    assert read_command_events(path)==committed
    assert read_events(path)==committed


@pytest.mark.parametrize('rejection', ['wrong-role','not-named','stale','unknown-target'])
def test_support_resolve_guards_reject_without_any_pg_write(production_console, rejection):
    console, client, sid, support, claim, payload = _ready(production_console)
    if rejection=='wrong-role':
        client.post('/login', data={'username':'author','password':'fixture-password'})
    elif rejection=='not-named':
        console.create_account(username='outsider', password='fixture-password', roles=['reviewer'])
        client.post('/login', data={'username':'outsider','password':'fixture-password'})
    elif rejection=='stale':
        payload['snapshot_revision']='stale-revision'
    else:
        payload['claim_object_id']='nonexistent-claim'
    before = _durable(console)
    response = client.post('/review/resolve', data=payload, follow_redirects=False)
    assert response.status_code in {400,403,409}, response.text
    assert _durable(console)==before
    assert verify_ledger(console._ledger_path)==[]
    client.close()
