"""Source-selection reads: bounded I/O, isolated request state, unchanged decisions.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: beschikbaarheid
# release-control-evidence: releasebewijs
"""
from collections import Counter
from copy import deepcopy
import cProfile
import io
import pstats
import time

import pytest
from tests.test_review_render_source_reuse import review_client
from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore


def _durable(console, sid):
    store = console.workflow_document_store
    return {"envelope": store.get_envelope(sid), "objects": store.list_document_objects(sid)}


def _persist(console, durable, *, independent=False):
    store = console.workflow_document_store
    if independent:
        store = PostgresConcurrentWorkflowDocumentStore(store.config)
    store.write_bundle(envelope=durable['envelope'], objects=durable['objects'])


@pytest.fixture
def postgres_selection(review_client, request, monkeypatch):
    console, client, sid = review_client
    # Exclude background discovery from the single-request measurement.
    for handler in client.app.router.on_shutdown:
        if getattr(handler, "__name__", "") == "stop" and handler.__self__.__class__.__name__ == "SourceProcessingDispatcher":
            client.portal.call(handler)
    durable = _durable(console, sid)
    # Synthetic nested replay evidence exercises copying/JSON costs; the rows
    # and every subsequent read/write remain in the actual PostgreSQL store.
    durable['envelope'].setdefault('semantic_replay', {}).setdefault('provider_evidence', {})['diagnostic_fixture'] = [
        {'index': i, 'spans': [{'start': i, 'end': i+20}], 'text': 'source evidence'}
        for i in range(4000)
    ]
    _persist(console, durable)
    durable = _durable(console, sid)
    calls = Counter()
    for method, counter in [('get_envelope', 'get_envelope'), ('list_envelopes', 'list_envelopes'),
                            ('list_document_objects', 'objects')]:
        original = getattr(console.workflow_document_store, method)
        def counted(*args, _original=original, _counter=counter, **kwargs):
            calls[_counter] += 1
            return _original(*args, **kwargs)
        monkeypatch.setattr(console.workflow_document_store, method, counted)
    return console, client, sid, durable, calls


def test_http_source_selection_has_bounded_document_reads(postgres_selection, monkeypatch):
    console, client, sid, durable, calls = postgres_selection
    before = deepcopy(durable)
    profile = cProfile.Profile()
    started = time.perf_counter()
    # cProfile in the route thread, not the TestClient caller thread.
    endpoint = next(r for r in client.app.routes if getattr(r,'path',None)=='/source-selection')
    original = endpoint.dependant.call
    def measured(*args, **kwargs):
        return profile.runcall(original, *args, **kwargs)
    endpoint.dependant.call = measured
    try:
        response = client.get('/source-selection', params={'document':sid})
    finally:
        endpoint.dependant.call = original
    assert response.status_code == 200
    assert durable == before
    stream = io.StringIO()
    pstats.Stats(profile, stream=stream).sort_stats('cumulative').print_stats(12)
    print('READ_COST',dict(calls),'seconds',round(time.perf_counter()-started,3))
    print(stream.getvalue())
    assert calls['get_envelope'] <= 1, 'Repeated full document loads within one overview'
    assert calls['objects'] <= 1, 'Repeated object loads within one overview'
    assert _durable(console, sid) == before


@pytest.mark.parametrize('review_client', [None, 'retained'], indirect=True)
def test_http_output_matches_unscoped_read_and_next_request_is_fresh(postgres_selection, monkeypatch):
    from uuid import UUID
    import src.vorming.source_selection_ui_v1 as ui
    console, client, sid, durable, calls = postgres_selection
    durable['envelope']['semantic_replay']['provider_evidence']['diagnostic_fixture'] = []
    _persist(console, durable)
    monkeypatch.setattr(ui.uuid, 'uuid4', lambda: UUID(int=1))
    before = deepcopy(durable)
    endpoint = next(r for r in client.app.routes if getattr(r,'path',None)=='/source-selection')
    scoped = endpoint.dependant.call
    endpoint.dependant.call = scoped.__wrapped__
    try:
        expected = client.get('/source-selection', params={'document':sid})
    finally:
        endpoint.dependant.call = scoped
    calls.clear()
    actual = client.get('/source-selection', params={'document':sid})
    assert actual.status_code == expected.status_code == 200
    assert actual.text == expected.text
    assert durable == before
    assert calls['list_envelopes'] == 0 and calls['objects'] <= 1
    assert calls['get_envelope'] == 1
    assert _durable(console, sid) == before
    durable['envelope']['title'] = 'Updated authoritative title'
    _persist(console, durable)
    fresh = client.get('/source-selection', params={'document':sid})
    assert fresh.status_code == 200 and 'Updated authoritative title' in fresh.text
    durable['envelope']['named_reviewers'] = []
    _persist(console, durable)
    denied = client.get('/source-selection', params={'document':sid})
    # The existing HTML error handler returns 400 for this denial.
    assert denied.status_code == 400
    assert "Je bent niet aangewezen als beoordelaar" in denied.text
    assert 'Updated authoritative title' not in denied.text


def test_overlapping_http_reads_are_isolated_and_exceptions_clear_scope(postgres_selection, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    import src.vorming.source_selection_ui_v1 as ui
    from src.operations_console_v1 import ConsoleError
    console, client, sid, durable, calls = postgres_selection
    durable['envelope']['semantic_replay']['provider_evidence']['diagnostic_fixture'] = []
    _persist(console, durable)
    original_title = durable['envelope']['title']
    entered, release = Event(), Event()
    original = ui.projection
    def blocked(*args, **kwargs):
        if not entered.is_set():
            entered.set()
            assert release.wait(5)
        return original(*args, **kwargs)
    monkeypatch.setattr(ui,'projection',blocked)
    with ThreadPoolExecutor() as pool:
        first = pool.submit(client.get, '/source-selection', params={'document':sid})
        try:
            assert entered.wait(3)
            durable['envelope']['title'] = 'Concurrent new title'
            _persist(console, durable, independent=True)
            second = client.get('/source-selection', params={'document':sid})
            assert second.status_code == 200 and 'Concurrent new title' in second.text
        finally:
            release.set()
        earlier = first.result(3)
    assert earlier.status_code == 200 and original_title in earlier.text
    assert 'Concurrent new title' not in earlier.text
    def fail(*args, **kwargs):
        raise ConsoleError('workflow_document_unavailable')
    monkeypatch.setattr(ui,'projection',fail)
    endpoint = next(r for r in client.app.routes if getattr(r,'path',None)=='/source-selection')
    scoped = endpoint.dependant.call
    cleaned = []
    def observed(*args, **kwargs):
        try:
            return scoped(*args, **kwargs)
        finally:
            # Check in the worker that ran the scope, not the caller thread.
            cleaned.append(console._document_reads() is None)
    endpoint.dependant.call = observed
    try:
        assert client.get('/source-selection', params={'document': sid}).status_code >= 400
        monkeypatch.setattr(ui,'projection',original)
        assert client.get('/source-selection', params={'document': sid}).status_code == 200
    finally:
        endpoint.dependant.call = scoped
    assert cleaned == [True, True]


@pytest.mark.parametrize("postgres_selection", ["runtime", "concurrent"], indirect=True)
def test_no_start_form_skips_revision_and_stale_start_is_rejected(postgres_selection, monkeypatch, request):
    console, client, sid, durable, calls = postgres_selection
    durable['envelope']['semantic_replay']['provider_evidence']['diagnostic_fixture'] = []
    _persist(console, durable)
    expected_revision = console.objects_revision(sid)
    original_revision = console.objects_revision
    captured = []
    def changed_during_read(snapshot_id):
        durable['objects'][0]['text'] = 'A concurrent edit'
        _persist(console, durable, independent=request.node.callspec.params['postgres_selection'] == 'concurrent')
        value = original_revision(snapshot_id)
        captured.append(value)
        return value
    monkeypatch.setattr(console,'objects_revision',changed_during_read)
    response = client.get('/source-selection', params={'document':sid})
    assert response.status_code == 200
    assert 'action="/source-selection/start"' not in response.text
    assert captured == []  # No unused whole-history precondition on progress GET.
    changed_during_read(sid)
    monkeypatch.setattr(console,'objects_revision',original_revision)
    assert console.objects_revision(sid) != expected_revision
    before = deepcopy(durable)
    from src.operations_console_v1 import ConsoleError
    command = console.reserve_source_selection
    errors = []
    def observed_command(**kwargs):
        assert console._document_reads() is None
        try:
            return command(**kwargs)
        except ConsoleError as exc:
            errors.append(exc.code)
            raise
    monkeypatch.setattr(console, 'reserve_source_selection', observed_command)
    response = client.post('/source-selection/start', data={
        'document':sid, 'command_id':'stale-read-proof', 'expected_revision':expected_revision},
        follow_redirects=False)
    assert response.status_code == 400
    assert errors == ["snapshot_object_write_conflict"], errors
    assert durable == before
    assert _durable(console, sid) == before


def test_receipt_remains_detached_and_write_reads_do_not_use_render_data(postgres_selection):
    console, client, sid, durable, calls = postgres_selection
    receipt = console._receipt(durable['envelope'])
    assert 'semantic_replay' not in receipt
    receipt['named_reviewers'].clear()
    assert durable['envelope']['named_reviewers']
    before_pin = dict(console._objects_expected_revs())
    with console.document_read_operation():
        console.list_envelopes()
        original = console.snapshot_objects(sid)
        original_revision = console.objects_revision(sid)
        original[0]['text'] = 'Changing caller copy'
        assert console.snapshot_objects(sid)[0].get('text') != 'Changing caller copy'
        assert console._objects_expected_revs() == before_pin
        durable['objects'][0]['text'] = 'Fresh write-side value'
        _persist(console, durable, independent=True)
        write_rows = console._load_objects(sid, remember=True)
        assert write_rows[0]['text'] == 'Fresh write-side value'
        assert console._objects_expected_revs()[sid] != original_revision
    assert console._document_reads() is None
