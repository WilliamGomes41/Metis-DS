"""Retained extraction survives real preparation and restart, never approval.
# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale interrupt retry version-compat
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
from threading import Event
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from src.operations_console_v1 import ConsoleError
from src.source_preparation_context_v1 import KEY, stored_extraction, build_formation_context
from tests.test_recoverable_formation_v1 import system
from tests.test_recommendation_coverage_v1 import FIRST
from tests.test_availability_repair import accounts, state, bind, provider, installed_app, login, start, drain, upload
from tests.test_workflow_transaction_v1 import workflow_postgres  # noqa: F401


@pytest.fixture(params=['local', 'postgres'])
def factory(request, tmp_path):
    if request.param == 'postgres':
        from tests.test_review_batch_atomic_postgres import _console
        config = request.getfixturevalue('workflow_postgres')
        return lambda: _console(tmp_path, config)
    return lambda: state(tmp_path)


def test_resume_after_restart_reuses_extraction_and_preserves_completed_object(tmp_path, monkeypatch, factory):
    first, sid, actor, _, calls, mode, make, bind = system(tmp_path, make_console=factory)
    retained = deepcopy(next(o for o in first.snapshot_objects(sid) if o['content']['clean_text'] == FIRST))
    restarted = make(); bind(restarted); mode['broken'] = False
    def forbidden(*a, **kw):
        raise AssertionError('RESTART_RESUME_EXTRACTED_AGAIN')
    monkeypatch.setattr(restarted, '_extract', forbidden)
    previous = len(calls)
    attempt, fresh = restarted.reserve_source_selection(actor_id=actor, snapshot_id=sid,
        command_id='context-resume', expected_revision=restarted.objects_revision(sid))
    assert fresh
    restarted.execute_source_selection(actor_id=actor, snapshot_id=sid, attempt=attempt)
    assert len(calls) == previous + 1
    assert next(o for o in restarted.snapshot_objects(sid) if o['object_id'] == retained['object_id']) == retained
    assert restarted._envelope(sid)['processing_attempts'][-1]['state'] == 'succeeded'
    final = make()
    monkeypatch.setattr(final, '_extract', forbidden)
    assert final.review_source_fragments(sid)
    assert final.review_source_fragments(sid)


def test_http_extraction_checkpoint_survives_provider_failure_and_restart(factory, monkeypatch):
    first = factory(); actor, reviewer = accounts(first)
    extracted = []
    original = first._extract
    def extract(*a, **kw):
        extracted.append(1)
        from src.workflows.workflow_transaction_v1 import workflow_transaction_active
        assert not first._store_thread_lock._is_owned() and not workflow_transaction_active()
        return original(*a, **kw)
    monkeypatch.setattr(first, '_extract', extract)
    def fail(*a):
        assert stored_extraction(first._envelope(sid))
        raise ConsoleError('pre_review_llm_connection_failed')
    bind(first, fail)
    app = installed_app(first)
    with TestClient(app, base_url='https://testserver') as client:
        login(client)
        assert upload(client, reviewer).status_code == 303
        sid = first.list_envelopes()[0]['snapshot_id']
        assert extracted == []
        assert start(client, first, sid).status_code == 303
        drain(client, app)
    assert extracted == [1]
    assert first.snapshot_objects(sid) == []
    assert first._envelope(sid)['processing_attempts'][-1]['state'] == 'failed'
    restarted = factory(); bind(restarted, provider)
    def forbidden(*a, **kw):
        raise AssertionError('RETRY_EXTRACTED_AGAIN')
    monkeypatch.setattr(restarted, '_extract', forbidden)
    app = installed_app(restarted)
    with TestClient(app, base_url='https://testserver') as client:
        login(client)
        assert start(client, restarted, sid, command='retry-after-checkpoint').status_code == 303
        drain(client, app)
    final = factory()
    assert final.snapshot_objects(sid)
    assert final._envelope(sid)['processing_attempts'][-1]['state'] == 'succeeded'


@pytest.mark.parametrize('change', ['fragments', 'source', 'contract'])
def test_corrupt_or_incompatible_extraction_cannot_fallback_or_replace_work(factory, tmp_path, monkeypatch, change):
    first, sid, actor, _, _, mode, make, attach = system(tmp_path, make_console=factory)
    before = deepcopy(first.snapshot_objects(sid))
    envelope = deepcopy(first._envelope(sid))
    record = envelope[KEY]
    if change == 'fragments':
        record['fragments'][0]['raw_text'] = 'changed'
    else:
        from src.integrity_kernel import stable_hash
        if change == 'source':
            record['source']['document_id'] = 'wrong-document'
        else:
            record['extractor_contract'] = 'incompatible-parser'
        record['record_hash'] = stable_hash({k: v for k, v in record.items() if k != 'record_hash'})
    first._commit_prepared_store(envelopes={sid: envelope}, snapshot_id=sid)
    restarted = make(); attach(restarted); mode['broken'] = False
    def forbidden(*a, **kw):
        raise AssertionError('CORRUPTION_TRIGGERED_EXTRACTION_FALLBACK')
    monkeypatch.setattr(restarted, '_extract', forbidden)
    with pytest.raises(ConsoleError, match='source_extraction_'):
        restarted.resume_formation(actor_id=actor, snapshot_id=sid, command_id='corrupt-resume',
            expected_revision=restarted.objects_revision(sid))
    assert restarted.snapshot_objects(sid) == before


def test_checkpoint_commit_failure_does_not_create_durable_extraction(factory, monkeypatch):
    console = factory(); actor, reviewer = accounts(console); bind(console, provider)
    receipt = console.receive_source(actor_id=actor, filename='test.html',
        data=b'<html><body><p>Gebruik geen zalf.</p></body></html>', content_type='text/html',
        ingest_kind='new', title='Test', version='1', date='2026-10-09', live_url='',
        class_='richtlijn', family='test', named_reviewers=[reviewer])
    sid = receipt['snapshot_id']
    attempt, _ = console.reserve_source_selection(actor_id=actor, snapshot_id=sid,
        command_id='failed-checkpoint', expected_revision=console.objects_revision(sid))
    commit = console._commit_prepared_store
    def fail(**kw):
        if KEY in (kw.get('envelopes') or {}).get(sid, {}):
            raise ConsoleError('workflow_document_write_failed')
        return commit(**kw)
    monkeypatch.setattr(console, '_commit_prepared_store', fail)
    with pytest.raises(ConsoleError, match='workflow_document_write_failed'):
        console.execute_source_selection(actor_id=actor, snapshot_id=sid, attempt=attempt)
    assert KEY not in factory()._envelope(sid)
    assert factory().snapshot_objects(sid) == []


def test_revision_changed_during_extraction_rejects_checkpoint(factory, monkeypatch):
    console = factory(); actor, reviewer = accounts(console); bind(console, provider)
    receipt = console.receive_source(actor_id=actor, filename='test.html',
        data=b'<html><body><p>Gebruik geen zalf.</p></body></html>', content_type='text/html',
        ingest_kind='new', title='Test', version='1', date='2026-10-09', live_url='',
        class_='richtlijn', family='test', named_reviewers=[reviewer])
    sid = receipt['snapshot_id']
    attempt, _ = console.reserve_source_selection(actor_id=actor, snapshot_id=sid,
        command_id='concurrent-checkpoint', expected_revision=console.objects_revision(sid))
    entered, release = Event(), Event()
    original = console._extract
    def paused(*a, **kw):
        entered.set(); assert release.wait(5)
        return original(*a, **kw)
    monkeypatch.setattr(console, '_extract', paused)
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(console.execute_source_selection, actor_id=actor, snapshot_id=sid, attempt=attempt)
        try:
            assert entered.wait(3)
            with console._reprocessing_transaction(sid):
                changed = deepcopy(console._envelope(sid)); changed['title'] = 'Concurrent winner'
                console._commit_prepared_store(envelopes={sid: changed}, snapshot_id=sid)
        finally:
            release.set()
        with pytest.raises(ConsoleError, match='snapshot_object_write_conflict'):
            future.result(timeout=5)
    final = factory()
    assert final._envelope(sid)['title'] == 'Concurrent winner'
    assert KEY not in final._envelope(sid) and final.snapshot_objects(sid) == []


def test_context_rejects_missing_identity_and_wrong_actor_before_work(tmp_path):
    console, sid, actor, _, _, _, _, _ = system(tmp_path)
    envelope = deepcopy(console._envelope(sid))
    attempt = envelope['processing_attempts'][-1]
    with pytest.raises(ConsoleError, match='processing_command_conflict'):
        build_formation_context(console, envelope=envelope, actor_id='another-actor',
            expected_revision=attempt['expected_revision'], attempt=attempt, deadline=1)
    envelope.pop('source_id')
    with pytest.raises(ConsoleError, match='source_preparation_context_required'):
        build_formation_context(console, envelope=envelope, actor_id=actor, expected_revision=None)


def test_explicit_reextraction_is_fresh_and_legacy_native_read_still_extracts(tmp_path, monkeypatch):
    console, sid, actor, _, _, _, _, _ = system(tmp_path, broken=False)
    original = console._extract
    calls = []
    def counted(*a, **kw):
        calls.append(1)
        return original(*a, **kw)
    monkeypatch.setattr(console, '_extract', counted)
    console.reextract_unpublished(actor_id=actor, snapshot_id=sid)
    assert calls == [1]
    envelope = deepcopy(console._envelope(sid)); envelope.pop(KEY)
    path, _ = console._verified_source_bytes(envelope)
    assert console._read_source_fragments(envelope, path)
    assert calls == [1, 1]


def test_docling_adapter_keeps_complete_record_and_isolated_return_values():
    from tests.test_docling_contract_v1 import rows
    from src.source_preparation_context_v1 import extraction_record
    fragments = rows()
    envelope = {'snapshot_id': 'snap', 'source_id': 'src', 'document_id': 'doc',
                'sha256': 'a' * 64, 'version': '1', 'content_kind': 'pdf'}
    envelope[KEY] = extraction_record(envelope, fragments, 'pinned-docling')
    loaded = stored_extraction(envelope, required_contract='pinned-docling')
    assert loaded == fragments and loaded.extraction_record == fragments.extraction_record
    loaded[0]['raw_text'] = 'caller mutation'
    assert stored_extraction(envelope) == fragments
