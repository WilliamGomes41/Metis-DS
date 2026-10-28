"""Real HTTP regression for the document path left expensive after passage reads.

# release-control-evidence: scope/belofte toegang kwaliteit metrics releasebewijs
"""
from collections import Counter
from copy import deepcopy
import re

import pytest

from tests.test_review_render_source_reuse import review_client  # noqa: F401


@pytest.mark.parametrize('task', ['individual', 'batch', 'inventory'])
def test_document_tasks_use_compact_inputs_and_prepared_source(review_client, monkeypatch, task):
    import src.vorming.knowledge_materialisation_v1 as materialisation

    console, client, sid = review_client
    before = deepcopy(console.snapshot_objects(sid))
    envelope_before = deepcopy(console._envelope(sid))
    counts = Counter()
    equality = materialisation._SourceNumber.__eq__

    def compare(self, other):
        counts['source_comparisons'] += 1
        return equality(self, other)

    monkeypatch.setattr(materialisation._SourceNumber, '__eq__', compare)
    real_status = console.processing_status
    real_envelope = console.workflow_document_store.get_envelope
    real_objects = console.workflow_document_store.list_document_objects

    def status(*args, **kwargs):
        counts['deep_status'] += 1
        return real_status(*args, **kwargs)

    def envelope(*args, **kwargs):
        counts['full_envelope'] += 1
        return real_envelope(*args, **kwargs)

    def objects(*args, **kwargs):
        counts['objectset'] += 1
        return real_objects(*args, **kwargs)

    monkeypatch.setattr(console, 'processing_status', status)
    monkeypatch.setattr(console.workflow_document_store, 'get_envelope', envelope)
    monkeypatch.setattr(console.workflow_document_store, 'list_document_objects', objects)
    response = client.get('/review', params={'document': sid, 'task': task})
    assert response.status_code == 200
    assert not counts['source_comparisons'], counts
    assert not counts['deep_status'], counts
    assert not counts['full_envelope'], counts
    assert counts['objectset'] == 1, counts
    assert console.snapshot_objects(sid) == before
    assert console._envelope(sid) == envelope_before


@pytest.mark.parametrize('review_client', ['large'], indirect=True)
@pytest.mark.parametrize('task', ['individual', 'inventory'])
def test_document_queue_pages_preserve_every_candidate(review_client, task):
    console, client, sid = review_client
    before = deepcopy(console.snapshot_objects(sid))
    candidates = {o['object_id'] for o in before
                  if (o.get('metadata') or {}).get('semantic_passage', {}).get('spans')}
    seen = set()
    for page in (1, 2, 3):
        response = client.get('/review', params={'document': sid, 'task': task, 'queue_page': page})
        assert response.status_code == 200
        ids = set(re.findall(r'object=([^&"#]+)', response.text)) & candidates
        assert ids and len(ids) <= 25
        assert not seen & ids
        seen.update(ids)
        assert f'pagina {page} van 3' in response.text
    assert seen == candidates
    assert console.snapshot_objects(sid) == before


def test_complete_document_does_not_transfer_processing_archives(review_client, monkeypatch):
    import src.console_performance_v1 as performance

    console, client, sid = review_client
    sizes = []
    monkeypatch.setattr(performance._LOGGER, 'info', lambda _format, *args: sizes.append(args[-1]))
    params = {'document': sid, 'task': 'individual'}
    assert client.get('/review', params=params).status_code == 200
    baseline = sizes[-1]
    store = console.workflow_document_store
    envelope = store.get_envelope(sid)
    envelope.setdefault('semantic_replay', {}).setdefault('provider_evidence', {})['large_fixture'] = [
        {'index': i, 'text': 'synthetic archived processing evidence' * 8} for i in range(10000)]
    store.write_bundle(envelope=envelope)
    before = deepcopy(store.get_envelope(sid))
    response = client.get('/review', params=params)
    assert response.status_code == 200
    assert sizes[-1] <= baseline + 1024, 'GET transferred an unused multi-megabyte replay archive'
    assert store.get_envelope(sid) == before


@pytest.mark.parametrize('review_client', ['batch-large'], indirect=True)
def test_batch_pages_keep_every_candidate_and_the_existing_form_pin(review_client):
    console, client, sid = review_client
    candidates = {o['object_id'] for o in console.snapshot_objects(sid)
                  if (o.get('metadata') or {}).get('semantic_passage', {}).get('spans')}
    before = console.objects_revision(sid)
    seen = set()
    for page in (1, 2, 3):
        response = client.get('/review', params={'document': sid, 'task': 'batch', 'queue_page': page})
        assert response.status_code == 200
        ids = set(re.findall(r'name="object_ids" value="([^"]+)"', response.text))
        assert ids and len(ids) <= 25
        assert not seen & ids
        seen.update(ids)
        assert f'pagina {page} van 3' in response.text
        assert f'name="snapshot_revision" value="{before}"' in response.text
    assert seen == candidates


@pytest.mark.parametrize('review_client', ['batch-large'], indirect=True)
def test_stale_second_batch_keeps_retry_selection_visible(review_client):
    console, client, sid = review_client
    page = client.get('/review', params={'document': sid, 'task': 'batch', 'queue_page': 2})
    ids = re.findall(r'name="object_ids" value="([^"]+)"', page.text)
    pin = re.search(r'name="snapshot_revision" value="([^"]+)"', page.text)[1]
    assert len(ids) == 20
    changed = deepcopy(console._load_objects(sid))
    changed[0]['concurrent_read_test_marker'] = 'another commit'
    console._save_objects(sid, changed)
    before = deepcopy(console.snapshot_objects(sid))
    events = console.workflow_review_store.read_events()
    response = client.post('/review/normal-risk/batch-confirm', data={
        'snapshot_id': sid, 'object_ids': ids, 'snapshot_revision': pin}, follow_redirects=False)
    assert response.status_code == 409
    checked = set(re.findall(r'name="object_ids" value="([^"]+)" checked', response.text))
    assert checked == set(ids)
    assert 'pagina 2 van 3' in response.text
    assert console.snapshot_objects(sid) == before
    assert console.workflow_review_store.read_events() == events


@pytest.mark.parametrize('review_client', ['large'], indirect=True)
def test_queue_navigation_keeps_document_return_filters(review_client):
    from html import unescape
    from urllib.parse import parse_qs, urlsplit
    _console, client, sid = review_client
    page = client.get('/review', params={'document': sid, 'task': 'individual',
        'q': 'zorg & huid', 'page': 2, 'theme': 'huid'})
    assert page.status_code == 200
    next_link = re.search(r'href="([^"]+)">Volgende</a>', page.text)[1]
    query = parse_qs(urlsplit(unescape(next_link)).query)
    assert query['q'] == ['zorg & huid'] and query['page'] == ['2'] and query['theme'] == ['huid']
    next_page = client.get(unescape(next_link))
    assert next_page.status_code == 200
    back = re.search(r'href="([^"]+)">Terug naar documenten</a>', next_page.text)[1]
    query = parse_qs(urlsplit(unescape(back)).query)
    assert query['q'] == ['zorg & huid'] and query['page'] == ['2'] and query['theme'] == ['huid']


@pytest.mark.parametrize('task', ['individual', 'inventory', 'batch'])
def test_open_document_keeps_full_formation_warning(tmp_path, production_console, monkeypatch, task):
    import src.vorming.knowledge_materialisation_v1 as materialisation
    from fastapi.testclient import TestClient
    from tests.test_review_formation_problems import received, execute
    from tests.test_availability_repair import login

    console, sid, author, _reviewer, _calls, _mode, _provider = received(
        tmp_path, production_console, monkeypatch)
    execute(console, sid, author, 'read-cost-partial')
    before = deepcopy(console.snapshot_objects(sid)), deepcopy(console._envelope(sid))
    assert console.processing_status(sid)['formation_incomplete']
    calls, comparisons = [], []
    original = console.processing_status
    equality = materialisation._SourceNumber.__eq__

    def status(*args, **kwargs):
        from src.vorming.prepared_source_views_v1 import SourceFragments
        assert isinstance(kwargs.get('formation_fragments'), SourceFragments)
        calls.append(1)
        return original(*args, **kwargs)

    def compare(self, other):
        comparisons.append(1)
        return equality(self, other)

    monkeypatch.setattr(console, 'processing_status', status)
    monkeypatch.setattr(materialisation._SourceNumber, '__eq__', compare)
    with TestClient(console._metis_test_application) as client:
        login(client, 'reviewer')
        page = client.get('/review', params={'document': sid, 'task': task})
    assert page.status_code == 200
    assert 'data-formation-incomplete' in page.text and 'Vormingsproblemen behandelen' in page.text
    assert calls == [1] and not comparisons
    assert (console.snapshot_objects(sid), console._envelope(sid)) == before


def test_document_capture_keeps_objectset_pin_when_a_writer_commits(review_client, monkeypatch):
    from src.review.review_passage_read_v1 import read_review_document
    from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore

    console, _client, sid = review_client
    store = console.workflow_document_store
    other = PostgresConcurrentWorkflowDocumentStore(store.config)
    old = deepcopy(store.list_document_objects(sid))
    envelope = other.get_envelope(sid)
    changed = deepcopy(old)
    changed[-1]['read_race_marker'] = 'new-committed-state'
    old_pin = store.revision_for_rows(old)
    original = store.review_document_input
    captured = []

    def capture(snapshot_id):
        result = original(snapshot_id)
        if not captured:
            captured.append(1)
            other.write_bundle(envelope=envelope, objects=changed, expected_revision=old_pin)
        return result

    monkeypatch.setattr(store, 'review_document_input', capture)
    actor = {'account_id': envelope['named_reviewers'][0], 'roles': ['reviewer']}
    with console.document_read_operation():
        inputs = read_review_document(console, actor, sid)
    assert inputs.revision == old_pin
    assert all(o.get('read_race_marker') is None for o in inputs.objects)
    assert store.revision_for_rows(other.list_document_objects(sid)) != inputs.revision
    with console.document_read_operation():
        fresh = read_review_document(console, actor, sid)
    assert any(o.get('read_race_marker') == 'new-committed-state' for o in fresh.objects)
