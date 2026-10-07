from test_t4_single_knowledge_path_invariants import _allowed_source
"""Passive measurement contract and lifecycle regression evidence.
# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: metrics teller noemer score-must-drop
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Lock

import pytest
from fastapi.testclient import TestClient

from src.integrity_kernel import stable_hash
from src.operations_console_app import create_console_app
from src.quality_evidence_v1 import record_processing, review_evidence, route_of
from src.quality_metrics_v1 import build_report
from src.quality_metrics_store_v1 import QualityReportStore, QualityStoreError
from src.quality_metrics_app_v1 import capture
from test_d5_4_review_interaction_evidence import _system, PASSWORD

NOW = '2026-09-27T12:00:00+00:00'


def fixture():
    obj = {'object_id': 'o', 'object_version': '1.0', 'object_type': 'definition',
           'content': {'clean_text': 'Een definitie.'}, 'metadata': {
               'passage_formation': {'strategy': 'deterministic', 'policy_version': '1'}},
           'governance': {'validation_status': 'needs_review'}}
    env = {'snapshot_id': 's', 'sha256': 'source', 'acquired_at': NOW, 'title': 'Bron'}
    record_processing(env, [obj], fragments=[], replay=None, started_at=NOW)
    event = {'event_type': 'clinical_review_approve', 'object_id': 'o', 'object_version': '1.0',
             'occurred_at': NOW, 'details': {'snapshot_id': 's', 'quality_evidence': review_evidence(env, obj, obj)}}
    return {'envelope': env, 'objects': [obj], 'events': [event]}


def test_teller_noemer_score_must_drop_and_unknown_is_not_zero():
    doc = fixture()
    first = build_report([doc], as_of=NOW)['routes']['deterministic']
    assert first['direct_rate'] == 1 and first['first_decisions'] == 1
    doc['events'].append(deepcopy(doc['events'][0]))
    assert build_report([doc], as_of=NOW)['routes']['deterministic']['first_decisions'] == 1
    obj = doc['objects'][0]
    modified = deepcopy(obj)
    modified['content']['clean_text'] = 'Herstelde definitie.'
    doc['events'] = [deepcopy(doc['events'][0])]
    doc['events'][0]['details']['quality_evidence'] = review_evidence(doc['envelope'], obj, modified)
    assert build_report([doc], as_of=NOW)['routes']['deterministic']['direct_rate'] == 0
    doc['events'][0]['details'].pop('quality_evidence')
    unknown = build_report([doc], as_of=NOW)['routes']['unknown']
    assert unknown['direct_rate'] is None and unknown['first_decisions'] == 1


def test_routes_remainder_mixed_and_stale_candidate_version():
    doc = fixture()
    obj = deepcopy(doc['objects'][0])
    obj['metadata']['passage_formation']['strategy'] = 'semantic'
    obj['metadata']['semantic_passage'] = {'selection_origin': 'coverage_remainder'}
    assert route_of(obj)['route'] == 'remainder'
    obj['metadata']['semantic_passage']['selection_origin'] = 'proposal_selected'
    assert route_of(obj)['route'] == 'semantic'
    obj['object_version'] = '1.1'
    assert review_evidence(doc['envelope'], obj, obj)['unchanged_proposal'] is False
    doc['events'][0]['object_version'] = '9.0'
    assert build_report([doc], as_of=NOW)['routes']['unknown']['direct_rate'] is None


def test_failed_retry_interrupted_restart_and_concurrent_single_calculation(tmp_path):
    store = QualityReportStore(tmp_path)
    inputs = {'documents': [], 'filters': {}}
    with pytest.raises(QualityStoreError):
        store.calculate(owner='a', inputs=inputs, build=lambda _: 1 / 0)
    calls = []
    lock = Lock()
    def build(_):
        with lock:
            calls.append(1)
        return {'scope': []}
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(lambda _: QualityReportStore(tmp_path).calculate(owner='a', inputs=inputs, build=build), range(4)))
    assert len(calls) == 1
    assert all(r == rows[0] for r in rows)
    assert [a['status'] for a in rows[0]['attempts']] == ['failed', 'available']
    record = deepcopy(rows[0])
    record['status'] = 'running'
    record['attempts'][-1]['status'] = 'running'
    store._write(record)
    restarted = store.calculate(owner='a', inputs=inputs, build=build)
    assert [a['status'] for a in restarted['attempts']] == ['failed', 'interrupted', 'available']
    assert not store.history(owner='other', allowed_scope=set())


def test_history_scope_revocation_and_immutable_data_boundary(tmp_path):
    store = QualityReportStore(tmp_path)
    inputs = {'documents': [{'envelope': {'snapshot_id': 'private'}}], 'observed_at': NOW}
    old = store.calculate(owner='a', inputs=inputs, build=lambda _: {'scope': ['private']})
    inputs['observed_at'] = '2026-09-27T13:00:00+00:00'
    same = store.calculate(owner='a', inputs=inputs, build=lambda _: pytest.fail('must reuse frozen report'))
    assert old == same
    assert store.history(owner='a', allowed_scope=set()) == []
    assert len(store.history(owner='a', allowed_scope={'private'})) == 1


def test_settings_and_capture_do_not_expand_document_access(tmp_path):
    console, users, sid, oid = _system(tmp_path)
    own = capture(console, users['researcher'])
    assert [d['envelope']['snapshot_id'] for d in own['documents']] == [sid]
    outsider = console.create_account(username='outsider', password=PASSWORD, roles=('researcher',))
    assert capture(console, outsider)['documents'] == []
    client = TestClient(create_console_app(console))
    assert client.get('/settings/quality').status_code == 401
    response = client.post('/login', data={'username': users['researcher']['username'], 'password': PASSWORD})
    assert response.status_code == 200
    response = client.get('/settings/quality')
    assert 'href="/settings/technical"' in response.text
    assert 'href="/settings/quality/compare"' not in response.text
    assert response.status_code == 200, response.text
    assert 'Kwaliteit &amp; werkproces' in response.text
    assert 'Niet volledig meetbaar' in response.text
    assert client.get('/settings/quality?from=invalid').status_code == 400


def test_real_review_carries_evidence_atomically_and_reading_does_not_change_authority(tmp_path):
    from src.review_interaction_v1 import build_review_interaction_evidence
    from src.review_ledger import read_events
    console, users, sid, oid = _system(tmp_path)
    objects = console.snapshot_objects(sid)
    focal = next(o for o in objects if o['object_id'] == oid)
    interaction = build_review_interaction_evidence(
        interaction_id='ri_quality', interaction_kind='contextual',
        reviewer_account_id=users['reviewer_a']['account_id'], snapshot_id=sid,
        review_stage='first_review', focal=focal, objects=objects, review_path='richtlijn')
    console.review_object(actor_id=users['reviewer_a']['account_id'], snapshot_id=sid,
        object_id=oid, decision='approve', confirmed_object_type='definition',
        expected_revision=console.objects_revision(sid), interaction_evidence=interaction)
    event = next(e for e in reversed(read_events(console._ledger_path)) if e['event_type'] == 'clinical_review_approve')
    assert event['details']['quality_evidence']['run_id']
    before = stable_hash(console.snapshot_objects(sid))
    frozen = capture(console, users['reviewer_a'])
    report = build_report(frozen['documents'], as_of=frozen['observed_at'])
    assert report['burden']['review_interactions'] == 1
    assert stable_hash(console.snapshot_objects(sid)) == before


def test_postgres_concurrent_reports_restart_retry_and_no_local_fallback(tmp_path):
    import os
    import uuid
    from pathlib import Path
    import psycopg
    from psycopg.rows import dict_row
    dsn = os.getenv('METIS_TEST_POSTGRES_DSN')
    if not dsn:
        pytest.skip('METIS_TEST_POSTGRES_DSN required')
    connect = lambda: psycopg.connect(dsn, row_factory=dict_row)
    with connect() as con:
        con.execute('CREATE SCHEMA IF NOT EXISTS workflow')
        con.execute((Path(__file__).resolve().parents[1] / 'db/migrations/013_quality_measurements.sql').read_text())
    owner = 'quality-test-' + uuid.uuid4().hex
    store = QualityReportStore(tmp_path, connect=connect)
    try:
        with pytest.raises(QualityStoreError):
            store.calculate(owner=owner, inputs={}, build=lambda _: 1 / 0)
        with ThreadPoolExecutor(max_workers=3) as pool:
            rows = list(pool.map(lambda _: QualityReportStore(tmp_path, connect=connect).calculate(
                owner=owner, inputs={}, build=lambda _: {'scope': []}), range(3)))
        assert all(r == rows[0] for r in rows)
        assert [a['status'] for a in rows[0]['attempts']] == ['failed', 'available']
        assert not list(tmp_path.glob('*.json'))
        assert store.history(owner=owner, allowed_scope=set())[0]['calculation_id'] == rows[0]['calculation_id']
    finally:
        with connect() as con:
            con.execute('DELETE FROM workflow.quality_measurements WHERE owner_account_id=%s', (owner,))


def test_final_context_stays_closed_but_second_review_remains_open():
    from tests.review_authority_fixture_support import materialised_row, source_fragments, approved_bindings
    doc = fixture()
    obj = doc["objects"][0]
    obj["metadata"]["admission"] = {"gate_result": "allowed"}
    obj = materialised_row(obj)
    doc["objects"] = [obj]
    doc["fragments"] = source_fragments()
    obj["metadata"]["passage_register"] = {"status": "used_as_context", "source": "extract"}
    assert build_report([doc], as_of=NOW)["open_passages"] == 0
    obj["metadata"]["passage_register"]["status"] = "selected_as_candidate"
    obj["governance"] = {"validation_status": "approved", "second_review": {"required": True, "status": "pending"}}
    obj["confirmed_object_type"] = "definition"
    obj["risk"] = {"risk_level": "high", "requires_second_review": True}
    doc["bindings"] = approved_bindings([obj], "reviewer-a")
    assert build_report([doc], as_of=NOW)["open_passages"] == 1
    obj["governance"]["second_review"]["status"] = "approved"
    # A compatibility flag alone is insufficient; the exact independent binding closes review.
    assert build_report([doc], as_of=NOW)["open_passages"] == 1
    doc["bindings"] += approved_bindings([obj], "reviewer-b")
    assert build_report([doc], as_of=NOW)["open_passages"] == 0
