"""Actual source HTTP command: history, unrelated data and protected-work costs.

# release-control-evidence: scope/belofte opslag concurrent stale recovery
# release-control-evidence: toegang kwaliteit metrics slop releasebewijs
"""
from contextlib import contextmanager
from copy import deepcopy
import json
from threading import local
from time import monotonic

from fastapi.testclient import TestClient

from src.review.revision_workflow import revise_object
from src.workflows.workflow_transaction_v1 import workflow_transaction_active
from tests.test_source_context_review_v1 import _system
from tests.test_source_context_review_ui_v1 import _link_form, _payload
from tests.test_workflow_postgres_concurrency import _envelope, _authorization


def test_source_command_cost_is_independent_of_retained_history_and_other_documents(
    tmp_path, production_console, production_app, monkeypatch,
):
    state, author, reviewer, source, target, command = _system(tmp_path, production_console=production_console)
    sid = command['snapshot_id']
    documents, reviews = state.workflow_document_store, state.workflow_review_store
    state.review_object(actor_id=reviewer['account_id'], snapshot_id=sid,
        object_id=target['object_id'], decision='approve', confirmed_object_type='definition')
    assert state.object_review_bindings(sid)
    original_lock, original_reader = state._store_write_lock, state._open_original_reader
    depth, holds = local(), []

    @contextmanager
    def timed_lock():
        with original_lock():
            outer = not getattr(depth, 'value', 0)
            depth.value = getattr(depth, 'value', 0) + 1
            started = monotonic()
            try:
                yield
            finally:
                depth.value -= 1
                if outer:
                    holds.append(monotonic() - started)

    @contextmanager
    def outside_original(*args, **kwargs):
        assert not workflow_transaction_active()
        assert not getattr(depth, 'value', 0)
        with original_reader(*args, **kwargs) as reader:
            yield reader
    monkeypatch.setattr(state, '_store_write_lock', timed_lock)
    monkeypatch.setattr(state, '_open_original_reader', outside_original)
    timings = []

    with TestClient(production_app(state)) as client:
        assert client.post('/login', data={'username': 'bert', 'password': 'bert-secret'},
                           follow_redirects=False).status_code == 303

        def decide(label):
            page = client.get('/source-selection', params={'document': sid,
                'object': source['object_id'], 'context_target': target['object_id']})
            assert page.status_code == 200
            payload = _payload(_link_form(page))
            assert payload['snapshot_revision'].startswith('review-generation-v1:')
            with monkeypatch.context() as guard:
                def forbidden(*args, **kwargs):
                    raise AssertionError('source command used an unbounded or extract path')
                for method in ('review_command_histories', 'list_document_objects', 'objects_revision', 'write_bundle'):
                    guard.setattr(documents, method, forbidden)
                guard.setattr(reviews, 'read_events', forbidden)
                guard.setattr(state, '_extract', forbidden)
                bindings = reviews.read_bindings
                def scoped(snapshot_ids=None, *, object_ids=None):
                    assert snapshot_ids == [sid] and object_ids is not None
                    return bindings(snapshot_ids, object_ids=object_ids)
                guard.setattr(reviews, 'read_bindings', scoped)
                holds.clear()
                started = monotonic()
                result = client.post('/review/source-context', data=payload, follow_redirects=False)
                elapsed = monotonic() - started
            assert result.status_code == 303, result.text
            assert len(holds) == 1
            timings.append({'workload': label, 'post_seconds': elapsed, 'outer_lock_seconds': holds[0]})
            assert elapsed <= 3, timings
            assert holds[0] <= .25, timings

        decide('small')
        rows = state._load_objects(sid)
        previous = next(obj for obj in state.snapshot_objects(sid) if obj['object_id'] == target['object_id'])
        for _ in range(1500 - len(rows)):
            previous = revise_object(previous, deepcopy(previous), snapshot_id=sid,
                reason='Retained synthetic human history', actor=reviewer['account_id'], force=True)
            rows.append(previous)
        state._save_objects(sid, rows, expected_revision=state.objects_revision(sid))
        assert len(documents.list_document_objects(sid)) == 1500
        decide('1500-retained-revisions')

        # Independent metadata/events/bindings, not an alternative candidate creator.
        for number in range(24):
            other = f'independent-document-{number}'
            documents.write_bundle(envelope=_envelope(other, author['account_id'], reviewer['account_id']))
        with reviews.buffered():
            for number in range(1000):
                reviews.append_event(event_type='independent-audit', object_id='independent-object',
                    object_version='1.0', actor='fixture', details={
                        'snapshot_id': 'independent-document-0', 'command_id': f'other-{number}'})
        reviews.replace_snapshot_bindings('independent-document-0', [
            _authorization('independent-document-0', f'independent-{number}', reviewer['account_id'])
            for number in range(1000)])
        before = reviews.read_bindings(['independent-document-0'])
        decide('1500-revisions-and-independent-documents-events-bindings')
        assert reviews.read_bindings(['independent-document-0']) == before

    current = next(obj for obj in state.snapshot_objects(sid) if obj['object_id'] == target['object_id'])
    assert current['metadata']['confirmed_source_context'][0]['text'] == 'DOEN'
    assert not any(binding.get('valid') for binding in state.object_review_bindings(sid)
                   if binding['object_id'] == target['object_id'])
    print(json.dumps({'proof': 'native_source_command_three_axes', 'timings': timings}))
