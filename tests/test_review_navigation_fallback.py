"""Candidate navigation does not need the document's processing archive.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from src.operations_console_v1 import ConsoleError
from src.review.review_passage_read_v1 import read_review_navigation
from tests.test_review_formation_problems import received, execute, FIRST, SECOND
from tests.test_availability_repair import login

THIRD = 'Gebruik geen zeep.'


@pytest.fixture
def navigation_system(tmp_path, production_console, monkeypatch):
    source = (f'<html><body><h1>A</h1><p>{FIRST}</p><h1>B</h1><p>{SECOND}</p>'
              f'<h1>C</h1><p>{THIRD}</p></body></html>').encode()
    console, sid, author, reviewer, _calls, _mode, _provider = received(
        tmp_path, production_console, monkeypatch, source_html=source)
    execute(console, sid, author, 'navigation-fallback')
    assert console.processing_status(sid)['formation_incomplete']
    current = console.snapshot_objects(sid)
    ids = {o['content']['clean_text']: o['object_id'] for o in current
           if o.get('proposed_object_type') == 'recommendation'}
    assert set(ids) == {FIRST, THIRD}
    store = console.workflow_document_store
    with store._connect() as con:
        con.execute('UPDATE workflow.review_fact_state SET initialized=false WHERE snapshot_id=%s', (sid,))
    with TestClient(console._metis_test_application) as browser:
        login(browser, 'reviewer')
        yield console, sid, reviewer, ids, browser


def _durable(console, sid):
    from src.review.review_ledger import read_events
    return deepcopy((console.workflow_document_store.list_document_objects(sid),
                     console.object_review_bindings(sid), read_events(console._ledger_path),
                     console.workflow_document_store.get_envelope(sid)))


@pytest.mark.parametrize('missing_schema', [False, True])
@pytest.mark.parametrize('missing_frontier', [False, True])
def test_navigation_fallback_preserves_candidates_without_processing_archive(navigation_system, monkeypatch, missing_schema, missing_frontier):
    from src.review.review_cockpit_v1 import ordinary_review_queue
    from src.review.review_passage_read_v1 import read_review_document
    from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
    console, sid, reviewer, ids, _browser = navigation_system
    account = console._account(reviewer)
    before = _durable(console, sid)
    with console.document_read_operation():
        baseline = read_review_document(console, account, sid, current_only=True)
    expected = ordinary_review_queue(baseline.objects, review_path='richtlijn',
                                    bindings=baseline.bindings, fragments=baseline.fragments)
    assert {o['object_id'] for o in expected} == set(ids.values())

    def forbidden(*args, **kwargs):
        raise AssertionError('navigation expanded the document processing archive')

    if missing_schema:
        def unavailable(*args, **kwargs):
            raise WorkflowDocumentStoreError('review_card_schema_unprepared')
        monkeypatch.setattr('src.workflows.review_card_inputs_postgres_v1.capture_review_cards', unavailable)
    if missing_frontier:
        monkeypatch.setattr(console.workflow_document_store, 'review_document_window', lambda sid: None)
    with monkeypatch.context() as patch:
        for name in ('formation_input', 'processing_command_input', 'get_envelope'):
            patch.setattr(console.workflow_document_store, name, forbidden)
        with console.document_read_operation():
            actual = read_review_navigation(console, account, sid)
        queue = ordinary_review_queue(actual.objects, review_path='richtlijn',
                                     bindings=actual.bindings, fragments=actual.fragments)
        assert [o['object_id'] for o in queue] == [o['object_id'] for o in expected]
        assert actual.objects == baseline.objects
        assert actual.bindings == baseline.bindings
    assert _durable(console, sid) == before


def test_http_next_passage_uses_unprepared_cards_without_document_assessment(navigation_system, monkeypatch):
    console, sid, _reviewer, ids, browser = navigation_system
    before = _durable(console, sid)

    def forbidden(*args, **kwargs):
        raise AssertionError('next passage assessed the complete document')

    with monkeypatch.context() as patch:
        patch.setattr('src.review.review_passage_read_v1.read_review_document', forbidden)
        response = browser.get('/review', params={'document': sid, 'after': ids[FIRST]},
                               follow_redirects=False)
    assert response.status_code == 200, response.text
    assert f'name="object_id" value="{ids[THIRD]}"' in response.text
    assert f'name="object_id" value="{ids[FIRST]}"' not in response.text
    assert 'data-document-assessment="not_evaluated"' in response.text
    assert _durable(console, sid) == before


@pytest.mark.parametrize('end_of_queue', [False, True])
def test_http_navigation_omits_archive_bytes_and_keeps_the_same_passage(navigation_system, monkeypatch, tmp_path, end_of_queue):
    import hashlib
    import json
    import os
    from pathlib import Path
    import src.review.review_passage_read_v1 as reads
    from src.request_diagnostics_v1 import RequestDiagnostics
    console, sid, _reviewer, ids, browser = navigation_system
    before = _durable(console, sid)
    captured = []

    def emit(_self, payload):
        if payload.get('event') == 'request_finished' and payload.get('route') == '/review':
            captured.append({key: payload[key] for key in ('status', 'elapsed_ms', 'db') if key in payload})

    def old_fallback(console, account, snapshot_id):
        legacy = reads.read_review_document(console, account, snapshot_id, current_only=True)
        return reads.ReviewNavigationInputs(legacy.envelope, legacy.objects, legacy.bindings, legacy.fragments)

    monkeypatch.setattr(RequestDiagnostics, 'emit', emit)
    for mode in ('old_fallback', 'navigation_capture'):
        with monkeypatch.context() as patch:
            if mode == 'old_fallback':
                patch.setattr(reads, '_read_review_navigation_fallback', old_fallback)
            response = browser.get('/review', params={'document': sid, 'after': ids[THIRD if end_of_queue else FIRST]},
                                   follow_redirects=False)
        assert response.status_code == 200, response.text
        if end_of_queue:
            assert f'data-workboard-document="{sid}"' in response.text
            assert f'name="object_id" value="{ids[THIRD]}"' not in response.text
        else:
            assert f'name="object_id" value="{ids[THIRD]}"' in response.text
        assert f'name="object_id" value="{ids[FIRST]}"' not in response.text
    assert len(captured) == 2
    assert captured[1]['db']['db_json_bytes'] < captured[0]['db']['db_json_bytes']
    assert captured[1]['db']['db_queries'] < captured[0]['db']['db_queries']
    assert _durable(console, sid) == before
    output = Path(os.environ.get('METIS_NAVIGATION_PROOF_OUTPUT', tmp_path / 'navigation-proof.json'))
    if end_of_queue:
        output = output.with_name(output.stem + '-end-of-queue' + output.suffix)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        'fixture': 'three synthetic source recommendations, two admitted, incomplete formation, unprepared cards',
        'runtime': 'authenticated ASGI and native PostgreSQL 16',
        'source_sha256': hashlib.sha256(Path(reads.__file__).read_bytes()).hexdigest(),
        'baseline': 'existing document reader used by the previous navigation fallback',
        'production_replay': False,
        'end_of_queue': end_of_queue,
        'samples': dict(zip(('old_fallback', 'navigation_capture'), captured)),
    }, indent=2) + '\n')


@pytest.mark.parametrize('account', [
    {'account_id': 'outsider', 'roles': ['reviewer']},
    {'account_id': 'outsider', 'roles': ['researcher']},
])
def test_navigation_fallback_authorizes_before_objects_or_source(navigation_system, monkeypatch, account):
    console, sid, _reviewer, _ids, _browser = navigation_system

    def forbidden(*args, **kwargs):
        raise AssertionError('unauthorized navigation read objects or source')

    monkeypatch.setattr(console.workflow_document_store, 'review_document_window', forbidden)
    monkeypatch.setattr(console, 'review_source_fragments', forbidden)
    with pytest.raises(ConsoleError, match='reviewer_not_named_on_snapshot'):
        read_review_navigation(console, account, sid)
