"""Passage observations do not claim an evaluated document outcome.

# release-control-evidence: scope/belofte kwaliteit toegang releasebewijs
"""
from tests.test_operational_document_inputs_postgres import incomplete_document  # noqa: F401


def selected(console, sid):
    return next(o for o in console.snapshot_objects(sid) if o.get('proposed_object_type') == 'recommendation')


def test_passage_notice_never_reloads_archives_or_evaluates_global_status(incomplete_document, monkeypatch):
    from src.review.review_passage_read_v1 import read_review_passage
    from src.operations_console_app import _review_formation_notice
    console, sid, _, reviewer = incomplete_document
    obj = selected(console, sid)
    expected = console.processing_status(sid)
    before = console.snapshot_objects(sid)
    with console.document_read_operation():
        inputs = read_review_passage(console, {'account_id': reviewer, 'roles': ['reviewer']}, sid, obj['object_id'])
        with monkeypatch.context() as forbidden:
            def unrelated_document_work(*args, **kwargs):
                raise AssertionError('A passage observation must not reload/evaluate the document')
            forbidden.setattr(console, 'processing_status', unrelated_document_work)
            forbidden.setattr(console.workflow_document_store, 'get_envelope', unrelated_document_work)
            forbidden.setattr(console.workflow_document_store, 'processing_history_input', unrelated_document_work)
            notice = _review_formation_notice(console, sid, inputs)
        assert 'data-document-assessment="not_evaluated"' in notice
        assert 'publicatie is geblokkeerd' not in notice
        assert inputs.document_assessment == 'not_evaluated'
    assert console.snapshot_objects(sid) == before
    assert console.processing_status(sid) == expected


def test_explicit_document_notice_keeps_complete_formation_owner(incomplete_document, monkeypatch):
    from src.review.review_passage_read_v1 import read_review_document, ReviewPassageInputs
    from src.operations_console_app import _review_formation_notice
    console, sid, _, reviewer = incomplete_document
    expected = console.processing_status(sid)
    assert expected['formation_incomplete']
    calls = []
    original = console.processing_status
    def measured(*args, **kwargs):
        result = original(*args, **kwargs)
        calls.append(result)
        return result
    with console.document_read_operation():
        inputs = read_review_document(console, {'account_id': reviewer, 'roles': ['reviewer']}, sid)
        assert not isinstance(inputs, ReviewPassageInputs)
        from src.vorming.prepared_source_views_v1 import SourceFragments
        import pytest
        from src.operations_console_v1 import ConsoleError
        assert isinstance(inputs.fragments, SourceFragments)
        with pytest.raises(ConsoleError, match='source_views_carrier_immutable'):
            inputs.fragments[0]['clean_text'] = 'forbidden'
        monkeypatch.setattr(console, 'processing_status', measured)
        notice = _review_formation_notice(console, sid, inputs, document_source=inputs.fragments)
    assert 'data-formation-incomplete' in notice
    assert calls == [expected]


def test_http_partial_formation_does_not_reload_25mb_processing_history(incomplete_document, monkeypatch):
    from copy import deepcopy
    from fastapi.testclient import TestClient
    from tests.test_availability_repair import login
    console, sid, _, _ = incomplete_document
    store = console.workflow_document_store
    obj = selected(console, sid)
    envelope = store.get_envelope(sid)
    runs = deepcopy(envelope['quality_processing_runs'])
    retained = {**deepcopy(runs[0]), 'run_id': 'retained-fixture-history',
                'raw_processing_evidence': 'synthetic retained evidence ' * 1000000}
    envelope['quality_processing_runs'] = [retained, *runs]
    store.write_bundle(envelope=envelope)
    with store._connect() as con:
        size = con.execute('SELECT octet_length(envelope_payload::text) AS n FROM workflow.documents WHERE snapshot_id=%s', (sid,)).fetchone()['n']
    assert size > 25000000
    before = deepcopy(console.snapshot_objects(sid))
    status_before = console.processing_status(sid)
    with TestClient(console._metis_test_application, base_url='https://console.example.test', headers={'Origin':'https://console.example.test'}) as client:
        login(client, 'reviewer')
        with monkeypatch.context() as forbidden:
            def no_full_document_work(*args, **kwargs):
                raise AssertionError('Ordinary passage GET must not read/evaluate global processing history')
            forbidden.setattr(store, 'get_envelope', no_full_document_work)
            forbidden.setattr(store, 'processing_history_input', no_full_document_work)
            forbidden.setattr(console, 'processing_status', no_full_document_work)
            response = client.get('/review', params={'document': sid, 'object': obj['object_id'], 'task': 'contextual'})
        assert response.status_code == 200
        assert 'data-document-assessment="not_evaluated"' in response.text
    assert console.snapshot_objects(sid) == before
    assert console.processing_status(sid) == status_before


def test_compact_document_assessment_uses_captured_immutable_inputs_without_full_envelope(incomplete_document, monkeypatch):
    from src.review.review_passage_read_v1 import read_review_document
    from src.operations_console_app import _review_formation_notice
    console, sid, _, reviewer = incomplete_document
    store = console.workflow_document_store
    expected = console.processing_status(sid)
    store.activate_operational_inputs(store.prepare_operational_inputs(sid))
    with console.document_read_operation(), monkeypatch.context() as forbidden:
        def no_archive_reload(*args, **kwargs):
            raise AssertionError('Prepared document scope reads its captured immutable inputs')
        forbidden.setattr(store, 'get_envelope', no_archive_reload)
        forbidden.setattr(store, 'processing_history_input', no_archive_reload)
        inputs = read_review_document(console, {'account_id': reviewer, 'roles': ['reviewer']}, sid)
        assert inputs.scope == 'document'
        assert 'semantic_replay' in inputs.envelope
        notice = _review_formation_notice(console, sid, inputs, document_source=inputs.fragments)
        assert 'data-formation-incomplete' in notice
    assert console.processing_status(sid) == expected


def test_complete_document_attempts_remain_bound_to_captured_snapshot(incomplete_document, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from src.review.review_passage_read_v1 import read_review_document
    from src.operations_console_app import _review_formation_notice
    console, sid, author, reviewer = incomplete_document
    store = console.workflow_document_store
    store.activate_operational_inputs(store.prepare_operational_inputs(sid))
    expected = console.processing_status(sid)
    native = store.formation_input
    changed = []
    def concurrent_reservation(envelope):
        if not changed:
            changed.append(True)
            from src.workflows.workflow_transaction_v1 import workflow_transaction_active
            assert not workflow_transaction_active()
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(console.reserve_source_selection, actor_id=author, snapshot_id=sid,
                    command_id='after-document-capture', expected_revision=console.objects_revision(sid))
                attempt, fresh = future.result(timeout=15)
            assert fresh
            changed.append(attempt['attempt_id'])
        return native(envelope)
    with console.document_read_operation(), monkeypatch.context() as patch:
        patch.setattr(store, 'formation_input', concurrent_reservation)
        inputs = read_review_document(console, {'account_id': reviewer, 'roles': ['reviewer']}, sid)
        assert changed[1] not in {a['attempt_id'] for a in inputs.envelope['processing_attempts']}
        assert console.processing_status(sid) == expected
        assert 'data-formation-incomplete' in _review_formation_notice(console, sid, inputs, document_source=inputs.fragments)
    assert changed[1] in {a['attempt_id'] for a in console._processing_envelope(sid)['processing_attempts']}
