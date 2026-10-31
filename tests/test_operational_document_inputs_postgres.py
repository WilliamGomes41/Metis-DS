"""Native small-header/cutover contract; source/formation authority stays current.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: toegang beschikbaarheid kwaliteit slop releasebewijs
"""
from copy import deepcopy
import json

import pytest


@pytest.fixture(params=[False, True], ids=['local-source', 'azure-source'])
def incomplete_document(tmp_path, production_console, monkeypatch, request):
    from tests.test_review_formation_problems import received, execute
    def factory(**options):
        return production_console(azure=request.param, **options)
    console, sid, author, reviewer, *_ = received(tmp_path, factory, monkeypatch)
    execute(console, sid, author, 'operational-inputs')
    return console, sid, author, reviewer


def test_explicit_cutover_keeps_formation_and_original_bytes_with_small_metadata(incomplete_document):
    console, sid, _, _ = incomplete_document
    store = console.workflow_document_store
    before = deepcopy(store.get_envelope(sid))
    status_before = console.processing_status(sid)
    assert status_before['formation_incomplete']
    with store._connect() as con:
        original = con.execute('SELECT envelope_payload::text AS body FROM workflow.documents WHERE snapshot_id=%s',
                               (sid,)).fetchone()['body']
    prepared = store.prepare_operational_inputs(sid)
    store.activate_operational_inputs(prepared)
    header = store.get_envelope(sid)
    assert header['_document_inputs']['layout'] == 1
    assert not {'semantic_replay','quality_processing_runs','processing_attempts'} & set(header)
    assert not {'fragments','docling_record'} & set(header.get('prepared_source_extraction') or {})
    assert len(json.dumps(header,ensure_ascii=False).encode()) < 16000
    assert console.processing_status(sid) == status_before
    assert store.processing_history_input(sid) == before
    changed = deepcopy(header)
    changed['title'] = 'Current metadata'
    store.write_bundle(envelope=changed)
    assert store.get_envelope(sid)['title'] == 'Current metadata'
    with store._connect() as con:
        assert con.execute('SELECT envelope_payload::text AS body FROM workflow.documents WHERE snapshot_id=%s',
                           (sid,)).fetchone()['body'] == original
