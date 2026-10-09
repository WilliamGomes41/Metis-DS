"""A02 durable representation acceptance, installed query/restart proof.
# release-control-evidence: scope/belofte opslag concurrent stale recovery
# release-control-evidence: toegang beschikbaarheid kwaliteit slop releasebewijs
"""
from copy import deepcopy
import json
import re

import pytest
from fastapi.testclient import TestClient
from tests.test_availability_repair import accounts, bind, provider, login, installed_app
from tests.test_workflow_transaction_v1 import workflow_postgres  # noqa: F401

ROUTES = [('/publish', {}), ('/review', {'work': 'all'}), ('/review', {}),
          ('/review', {'task': 'disposition'}), ('/review', {'task': 'individual'}),
          ('/review', {'task': 'detail'}), ('/review/bronpassage', {})]


def console_at(root, config=None):
    if config is not None:
        from tests.test_review_batch_atomic_postgres import _console
        return _console(root, config)
    from src.review_closure_v1 import ReviewClosureConsole
    return ReviewClosureConsole(root=root, source_store=root/'sources', runtime=root/'runtime')


@pytest.fixture(params=['local', 'postgres'])
def representation_backend(request):
    return request.getfixturevalue('workflow_postgres') if request.param == 'postgres' else None


def ingest(console):
    author, reviewer = accounts(console)
    def select(url, headers, payload, timeout):
        data = json.loads(payload['input'][1]['content'])
        if not data.get('selection_targets') and any('Gebruik geen zalf.' in b['text'] for b in data['source_blocks']):
            return provider(url, headers, payload, timeout)
        return {'status': 'completed', 'output': [{'type': 'message', 'content': [
            {'type': 'output_text', 'text': json.dumps({'objects': [], 'relations': [], 'abstain_reason': 'uncertain'})}]}]}
    bind(console, select)
    texts = ['Gebruik geen zalf.', *[f'Bronpassage {i} bevat informatie voor menselijke beoordeling.' for i in range(30)]]
    sid = console.ingest(actor_id=author, filename='fixture.html',
        data=('<html><body><h1>Adviezen</h1>'+''.join(f'<p>{t}</p>' for t in texts)+'</body></html>').encode(),
        content_type='text/html', ingest_kind='new', title='Fixture', version='1', date='2026-10-09',
        live_url='', class_='richtlijn', family='fixture', named_reviewers=[author, reviewer])['snapshot_id']
    return sid, author, reviewer


def query_for(console, sid, path, params):
    from src.source_accountability_v1 import is_source_record
    objects = console.snapshot_objects(sid)
    query = dict(params)
    if path != '/publish' and (params.get('task') or path == '/review/bronpassage'):
        query['document'] = sid
    if params.get('task') == 'detail':
        query.pop('task')
        query['object'] = next(o['object_id'] for o in objects if o.get('proposed_object_type') == 'recommendation')
    if path == '/review/bronpassage':
        query['object'] = next(o['object_id'] for o in objects if is_source_record(o))
    return query


def normalize(text):
    return re.sub(r'(name="(?:command_id|interaction_id)" value=")[^"]+', r'\1COMMAND', text)


@pytest.mark.parametrize('path,params', ROUTES)
def test_a02_zero_reconstruction_installed_routes_and_restart(representation_backend, tmp_path, monkeypatch, path, params):
    console = console_at(tmp_path, representation_backend)
    sid, author, reviewer = ingest(console)
    query = query_for(console, sid, path, params)
    with TestClient(installed_app(console)) as client:
        login(client)
        expected = client.get(path, params=query)
        assert expected.status_code == 200, expected.text

    import src.semantic_passage_v1 as semantic
    import src.knowledge_materialisation_v1 as materialisation
    calls = []
    original = semantic._reconstructed_blocks
    def counted(rows):
        calls.append(1)
        return original(rows)
    monkeypatch.setattr(semantic, '_reconstructed_blocks', counted)
    monkeypatch.setattr(materialisation, '_reconstructed_blocks', counted)
    for current in (console, console_at(tmp_path, representation_backend)):
        def forbidden(*args, **kwargs):
            pytest.fail('A02_QUERY_EXECUTED_SOURCE_PROCESSING')
        monkeypatch.setattr(current, '_extract', forbidden)
        monkeypatch.setattr(current, '_fragments_and_spec', forbidden)
        bind(current, forbidden)
        # Zero reconstruction must not depend on a ContextVar wrapper.
        monkeypatch.setattr(materialisation, '_source_reconstruction',
            type('DisabledScope', (), {'get': lambda self: None, 'set': lambda self, value: None,
                                       'reset': lambda self, token: None})())
        calls.clear()
        with TestClient(installed_app(current)) as client:
            login(client)
            response = client.get(path, params=query)
            assert response.status_code == 200, response.text
            assert normalize(response.text) == normalize(expected.text)
            assert not calls, ('A02_DURABLE_READ_RECONSTRUCTED', path, len(calls))
            login(client, 'reviewer')
            if path == '/publish':
                assert client.get(path, params=query).status_code == 403
        print('A02_DURABLE_READ='+json.dumps({'backend': 'postgres' if representation_backend else 'local',
              'route': path, 'reconstructions': len(calls), 'restart': current is not console}))

def remove_binding(console, sid):
    from src.source_representation_v1 import _local_connection
    store = getattr(console, "workflow_document_store", None)
    if store is None:
        with _local_connection(console, write=True) as con:
            con.execute("DELETE FROM bindings WHERE snapshot_id=?", (sid,))
    else:
        with store._connect() as con:
            con.execute("DELETE FROM workflow.source_representation_bindings WHERE snapshot_id=%s", (sid,))


def test_a02_historical_migration_is_explicit_fenced_and_preserves_reviews(
        representation_backend, tmp_path, monkeypatch):
    from src.operations_console_v1 import ConsoleError
    from src.source_representation_v1 import load, SourceRepresentationError, MISSING
    console = console_at(tmp_path, representation_backend)
    sid, author, reviewer = ingest(console)
    envelope = deepcopy(console._envelope(sid))
    objects = deepcopy(console.snapshot_objects(sid))
    revision = console.objects_revision(sid)
    accepted = load(console, envelope).representation["representation_id"]
    remove_binding(console, sid)
    with pytest.raises(SourceRepresentationError, match=MISSING):
        load(console, envelope)
    original = console._extract_historical_source_for_migration
    def forbidden(*args, **kwargs):
        pytest.fail("HISTORICAL_GET_EXECUTED_MIGRATION")
    monkeypatch.setattr(console, "_extract_historical_source_for_migration", forbidden)
    with TestClient(installed_app(console)) as client:
        login(client)
        response = client.get("/publish")
        assert response.status_code == 200
    monkeypatch.setattr(console, "_extract_historical_source_for_migration", original)
    command = dict(actor_id=author, snapshot_id=sid, command_id="migration-a02",
                   expected_revision=revision, reason="explicit historical migration")
    with pytest.raises(ConsoleError):
        console.migrate_source_representation(**{**command, "actor_id": reviewer})
    with pytest.raises(ConsoleError):
        console.migrate_source_representation(**{**command, "expected_revision": "stale"})
    result = console.migrate_source_representation(**command)
    assert result["dry_run"] and result["representation_id"] == accepted
    with pytest.raises(SourceRepresentationError, match=MISSING):
        load(console, envelope)
    result = console.migrate_source_representation(**command, dry_run=False)
    assert not result["dry_run"] and result["representation_id"] == accepted
    assert console._envelope(sid) == envelope
    assert console.snapshot_objects(sid) == objects
    assert console.objects_revision(sid) == revision
    monkeypatch.setattr(console, "_extract_historical_source_for_migration", forbidden)
    assert console.migrate_source_representation(**command, dry_run=False)["idempotent"]
    with pytest.raises(ConsoleError, match="source_representation_successor_required"):
        console.migrate_source_representation(**command, correction_revision=1)



def native_accept_worker(args):
    import psycopg
    from psycopg.rows import dict_row
    from src.source_representation_v1 import accept_postgres, provenance
    dsn, envelope, record = args
    with psycopg.connect(dsn, row_factory=dict_row) as con:
        with con.transaction():
            return accept_postgres(con, envelope, record, provenance(envelope))


def test_a02_concurrent_acceptance_conflict_rollback_and_immutable_carrier(
        representation_backend, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from src.source_representation_v1 import (
        load, accept_local, accept_postgres, provenance, SourceRepresentationError,
        stored_blocks, CONFLICT)
    from src.integrity_kernel import stable_hash
    console = console_at(tmp_path, representation_backend)
    sid, author, reviewer = ingest(console)
    envelope = console._envelope(sid)
    carrier = load(console, envelope)
    record = json.loads(json.dumps(carrier.representation))
    remove_binding(console, sid)
    def accept(_):
        store = getattr(console, "workflow_document_store", None)
        if store is None:
            return accept_local(console, envelope, record, provenance(envelope))
        with store._connect() as con:
            with con.transaction():
                return accept_postgres(con, envelope, record, provenance(envelope))
    store = getattr(console, "workflow_document_store", None)
    if store is None:
        with ThreadPoolExecutor(max_workers=4) as pool:
            assert set(pool.map(accept, range(4))) == {record["representation_id"]}
    else:
        import multiprocessing
        from concurrent.futures import ProcessPoolExecutor
        # Distinct processes/connections prove SQL ownership, not a Python lock.
        with ProcessPoolExecutor(max_workers=4, mp_context=multiprocessing.get_context("spawn")) as pool:
            args = (representation_backend.dsn, envelope, record)
            assert set(pool.map(native_accept_worker, [args] * 4)) == {record["representation_id"]}
    conflicting = deepcopy(record)
    conflicting["unexpected_conflicting_payload"] = True
    conflicting["payload_hash"] = stable_hash({k: v for k, v in conflicting.items() if k != "payload_hash"})
    store = getattr(console, "workflow_document_store", None)
    with pytest.raises(SourceRepresentationError, match=CONFLICT):
        if store is None:
            accept_local(console, envelope, conflicting, provenance(envelope))
        else:
            with store._connect() as con:
                with con.transaction():
                    accept_postgres(con, envelope, conflicting, provenance(envelope))
    assert load(console, envelope).representation == record
    fresh = load(console_at(tmp_path, representation_backend), envelope)
    with pytest.raises(SourceRepresentationError, match="carrier_immutable"):
        fresh[0]["raw_text"] = "changed"
    with pytest.raises(SourceRepresentationError, match="carrier_immutable"):
        fresh.representation["views"]["full"].clear()
    first = stored_blocks(fresh)
    first.clear()
    assert stored_blocks(fresh)
    if store is not None:
        remove_binding(console, sid)
        with pytest.raises(RuntimeError, match="injected_outer_failure"):
            with store._connect() as con:
                with con.transaction():
                    accept_postgres(con, envelope, record, provenance(envelope))
                    raise RuntimeError("injected_outer_failure")
        from src.source_representation_v1 import MISSING
        with pytest.raises(SourceRepresentationError, match=MISSING):
            load(console, envelope)
        accept(0)
        assert load(console, envelope).representation == record

def test_a02_rejection_changes_next_query_without_rebuilding_source(
        representation_backend, tmp_path, monkeypatch):
    from src.source_representation_v1 import load
    import src.semantic_passage_v1 as semantic
    import src.knowledge_materialisation_v1 as materialisation
    console = console_at(tmp_path, representation_backend)
    sid, author, reviewer = ingest(console)
    before_representation = load(console, console._envelope(sid)).representation
    obj = next(o for o in console.snapshot_objects(sid) if o.get("proposed_object_type") == "recommendation")
    def forbidden(*args, **kwargs):
        pytest.fail("OBJECT_REJECTION_REBUILT_WHOLE_SOURCE")
    monkeypatch.setattr(semantic, "_reconstructed_blocks", forbidden)
    monkeypatch.setattr(materialisation, "_reconstructed_blocks", forbidden)
    monkeypatch.setattr(console, "_extract", forbidden)
    bind(console, forbidden)
    with TestClient(installed_app(console)) as client:
        login(client)
        before = client.get("/review", params={"document": sid}).text
        console.review_object(actor_id=reviewer, snapshot_id=sid, object_id=obj["object_id"],
            decision="reject", comment="Niet geschikt voor dit kennisobject.",
            expected_revision=console.objects_revision(sid))
        after = client.get("/review", params={"document": sid}).text
        assert normalize(before) != normalize(after)
        assert client.get("/publish").status_code == 200
    assert load(console, console._envelope(sid)).representation == before_representation


def test_a02_native_schema_missing_fails_closed(representation_backend, tmp_path):
    if representation_backend is None:
        console = console_at(tmp_path)
        from src.source_representation_v1 import load, SourceRepresentationError, MISSING
        with pytest.raises(SourceRepresentationError, match=MISSING):
            load(console, {"snapshot_id": "unregistered"})
        return
    from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
    console = console_at(tmp_path, representation_backend)
    with console.workflow_document_store._connect() as con:
        con.execute("DROP TABLE workflow.source_representation_bindings")
    with pytest.raises(WorkflowDocumentStoreError, match="workflow_document_cutover_schema_missing"):
        console.workflow_document_store.verify_cutover_schema()
