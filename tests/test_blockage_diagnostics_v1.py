"""#618: explain recorded blockages without becoming their authority.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale interrupt retry version-compat recovery
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from src.blockage_diagnostics_v1 import blockage_report, collect_blockage, read_blockage_zip
from src.operations_console_app import create_console_app
from src.processing_evidence_export_v1 import _csv
from tests.test_source_dispatch_hardening import console
from tests.test_workflow_transaction_v1 import workflow_postgres
from tests.test_processing_trace_v1 import restart
from tests.test_recoverable_formation_v1 import system


FIXTURE = Path(__file__).parent / 'fixtures/diagnostics/slice3-v12-anonymized.json'


def login(client, username='author'):
    assert client.post('/login', data={'username':username,'password':'strong-test-password'}, follow_redirects=False).status_code == 303


def incident():
    return json.loads(FIXTURE.read_text())


def write_zip(path, tables):
    revision = tables['revision'][0]['objects_revision']
    compact = 'sha256:' + hashlib.sha256(revision.encode()).hexdigest()
    with ZipFile(path, 'w') as archive:
        for name, rows in tables.items():
            fields = list(dict.fromkeys(key for row in rows for key in row))
            if name != 'revision':
                fields = [key for key in fields if key != 'objects_revision'] + ['revision_id']
                rows = [{**{k:v for k,v in row.items() if k != 'objects_revision'}, 'revision_id':compact} for row in rows]
            archive.writestr(name+'.csv', _csv(tuple(fields), rows))


def test_v12_incident_explains_open_work_and_keeps_history_and_unknowns(tmp_path):
    path = tmp_path/'incident.zip'; write_zip(path, incident())
    report = blockage_report(read_blockage_zip(path))
    assert report['attempt_state_counts'] == {'succeeded':2}
    assert report['formation_progress']['pending_task_count'] == 45
    assert report['finding_counts']['pending'] == 13
    assert report['finding_counts']['historical'] == 4
    assert report['next_blocking_stage'] == 'source_formation'
    assert report['blockers'][0]['code'] == 'source_formation_incomplete'
    assert report['selected_attempt_id'] is None
    assert 'origin_request_not_recorded' in report['missing_evidence']
    assert not report['identity_conflicts']
    assert all(row['observed_conditions_met'] is None for row in report['follow_up'])
    assert all(row['cause'] == 'not_established' for row in report['findings'])
    assert all(row['currentness'] == 'not_established' for row in report['call_error_history'])
    encoded = json.dumps(report)
    assert 'private-' not in encoded and 'must-not-appear' not in encoded
    assert all(row['evidence_refs'][0]['row'] > 0 for row in report['findings'])
    result = subprocess.run([sys.executable, 'scripts/export_section_incident.py', '--evidence', str(path),
        '--output',str(tmp_path/'output')], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    output = json.loads((tmp_path/'output/incident.json').read_text())
    assert output['blockage']['finding_counts'] == report['finding_counts']
    assert output['input_sha256']['evidence'] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert 'Open verwerkingstaken: 45' in (tmp_path/'output/summary.txt').read_text()


def test_identity_conflict_never_enables_an_action_or_selects_a_different_incident():
    tables = incident()
    root = tables['revision'][0]
    checks = {'consistent':True, 'snapshot_id':root['snapshot_id'],
        'revision_sha256':hashlib.sha256(root['objects_revision'].encode()).hexdigest(), 'source_hash':'d'*64,
        'processing':{'resume_allowed':True}, 'observed_at':'2026-10-14T10:00:00Z'}
    tables['formation_findings'][0]['objects_revision'] = 'other-document-revision'
    report = blockage_report(tables, checks=checks)
    assert report['next_blocking_stage'] == 'identity_verification'
    assert 'row_identity_mismatch:formation_findings' in report['identity_conflicts']
    assert all(row['observed_conditions_met'] is None for row in report['follow_up'])
    tables = incident(); tables['processing_attempts'][0]['source_hash'] = 'f'*64
    report = blockage_report(tables, checks=checks)
    assert 'source_hash_disagrees' in report['identity_conflicts']
    assert not any(row['observed_conditions_met'] for row in report['follow_up'])


def test_recovered_and_unknown_findings_are_not_invented_current_blockers():
    tables = incident()
    tables['formation_progress'][0].update(formation_state='complete', pending_task_count=0)
    for row in tables['formation_findings']:
        row['state'] = 'historical'
    tables['formation_findings'][0]['reason_code'] = 'new_unrecognized_rule'
    report = blockage_report(tables, selected_attempt=tables['processing_attempts'][0]['attempt_id'])
    assert report['selected_attempt_state'] == 'succeeded'
    assert report['blockers'] == []
    assert report['next_blocking_stage'] == 'not_established'
    assert report['findings'][0]['explanation_status'] == 'unexplained_code'
    assert report['findings'][0]['expected_condition'] is None
    assert report['findings'][0]['scope'] == 'historical'
    assert 'attempt_id' not in report['findings'][0]  # current saved proposal isn't silently the selected old attempt
    with pytest.raises(ValueError):
        blockage_report(tables, selected_attempt='private-invalid')


def test_bounded_report_and_unavailable_current_checks_are_honest():
    tables = incident()
    tables['formation_findings'] *= 100
    report = blockage_report(tables)
    assert len(report['findings']) == 256
    assert report['omitted_findings'] > 0
    assert sum(report['finding_counts'].values()) == len(report['findings']) + report['omitted_findings']
    report = blockage_report({})
    assert report['blockers'] == []
    assert report['context']['source_hash'] is None
    assert 'revision_context_missing_or_ambiguous' in report['missing_evidence']


def test_zip_reader_bounds_duplicates_and_invalid_rows(tmp_path, monkeypatch):
    import src.blockage_diagnostics_v1 as module
    path = tmp_path/'input.zip'; write_zip(path, incident())
    monkeypatch.setattr(module, 'MAX_UNPACKED_BYTES', 10)
    with pytest.raises(ValueError, match='exceeds_limit'):
        read_blockage_zip(path)
    monkeypatch.setattr(module, 'MAX_UNPACKED_BYTES',64*1024*1024)
    with ZipFile(path,'w') as archive:
        archive.writestr('revision.csv','a,b\n1,2\n')
        with pytest.warns(UserWarning):
            archive.writestr('revision.csv','a,b\n3,4\n')
    with pytest.raises(ValueError, match='duplicate'):
        read_blockage_zip(path)
    with ZipFile(path,'w') as archive:
        archive.writestr('revision.csv','a,b\n1,2,3\n')
    with pytest.raises(ValueError, match='invalid_evidence_csv_row'):
        read_blockage_zip(path)


def partial(console):
    return system(console.root, make_console=lambda: restart(console))


def test_independent_http_report_survives_broken_worklist_without_processing(console, monkeypatch):
    state, sid, actor, reviewer, calls, mode, make, bind = partial(console)
    before = deepcopy(state._envelope(sid)), state.snapshot_objects(sid), state.objects_revision(sid)
    def forbidden(*args, **kwargs):
        raise AssertionError('stored diagnostic read touched processing, objects or the worklist')
    for name in ('list_envelopes','snapshot_objects','snapshot_objects_and_revision','_extract',
                 '_read_source_fragments','_fragments_and_spec','processing_status','publication_readiness',
                 'reserve_source_selection','execute_source_selection'):
        monkeypatch.setattr(state,name,forbidden)
    # Exercise ASGI reads independently of the unrelated periodic dispatcher scan.
    client = TestClient(create_console_app(state), base_url='https://testserver')
    try:
        login(client)
        page = client.get('/source-selection/blockage', params={'document':sid})
        assert page.status_code == 200 and 'Blokkade en bewijs' in page.text
        response = client.get('/source-selection/blockage', params={'document':sid,'download':1})
        assert response.status_code == 200
        assert response.headers['cache-control'] == 'no-store'
        report = response.json()
        assert report['next_blocking_stage'] == 'source_formation'
        assert report['finding_counts']['pending'] > 0
    finally:
        client.close()
    fresh = make()
    assert (fresh._envelope(sid),fresh.snapshot_objects(sid),fresh.objects_revision(sid)) == before
    assert len(calls) == 2


def test_actual_kernel_conditions_and_configuration_guard_are_reused(console, monkeypatch):
    state, sid, actor, reviewer, calls, mode, make, bind = partial(console)
    before = deepcopy(state._envelope(sid)), state.snapshot_objects(sid)
    report = collect_blockage(state, actor_id=actor, snapshot_id=sid, current_checks=True)
    assert report['current_checks']['context_matches']
    assert report['follow_up'][0]['observed_conditions_met'] is True
    assert report['follow_up'][0]['execution_authorized'] is False
    assert 'source_formation_incomplete' in report['current_checks']['readiness']['blockers']
    assert len(calls) == 2
    assert (make()._envelope(sid),make().snapshot_objects(sid)) == before
    monkeypatch.setattr(state,'_processing_configuration_reader', lambda:{'mode':'semantic-source-bound-v3','model':'other-model'})
    report = collect_blockage(state, actor_id=actor, snapshot_id=sid, current_checks=True)
    assert report['follow_up'][0]['observed_conditions_met'] is False
    assert report['current_checks']['errors']['resume_configuration'] == 'processing_resume_configuration_incompatible'


def test_changed_revision_and_partial_check_failure_leave_recorded_evidence_available(console, monkeypatch):
    state, sid, actor, reviewer, calls, mode, make, bind = partial(console)
    original = state.publication_readiness
    def broken(*args, **kwargs):
        raise OSError('private dependency failure')
    monkeypatch.setattr(state,'publication_readiness',broken)
    report = collect_blockage(state, actor_id=actor, snapshot_id=sid, current_checks=True)
    assert report['finding_counts']['pending'] > 0
    assert report['current_checks']['errors']['readiness'] == 'check_unavailable'
    assert 'private dependency failure' not in json.dumps(report)
    monkeypatch.setattr(state,'publication_readiness',original)
    revision = state.objects_revision
    calls_read = []
    def changing(snapshot_id):
        calls_read.append(snapshot_id)
        return revision(snapshot_id) if len(calls_read) == 1 else 'concurrently-changed'
    monkeypatch.setattr(state,'objects_revision',changing)
    report = collect_blockage(state, actor_id=actor, snapshot_id=sid, current_checks=True)
    assert 'current_check_context_changed_or_mismatched' in report['identity_conflicts']
    assert all(a['observed_conditions_met'] is None for a in report['follow_up'])


def test_http_access_denial_never_discloses_report(console):
    state, sid, actor, reviewer, calls, mode, make, bind = partial(console)
    state.create_account(username='outsider',password='strong-test-password',roles=('reviewer',))
    before = deepcopy(state._envelope(sid))
    with TestClient(create_console_app(state), base_url='https://testserver') as client:
        for params in ({'document':sid},{'document':sid,'download':1,'checks':1}):
            response = client.get('/source-selection/blockage',params=params,follow_redirects=False)
            assert response.status_code in (303,401)
        login(client,'outsider')
        response = client.get('/source-selection/blockage',params={'document':sid,'download':1,'checks':1})
        assert response.status_code == 400
        assert 'blockage-report-v1' not in response.text
    assert make()._envelope(sid) == before


def test_zip_report_matches_recorded_state_and_never_runs_current_checks(console, tmp_path, monkeypatch):
    from src.processing_evidence_export_v1 import processing_evidence_zip
    state, sid, actor, reviewer, calls, mode, make, bind = partial(console)
    objects, revision = state.snapshot_objects_and_revision(sid)
    def forbidden(*args, **kwargs):
        raise AssertionError('ZIP export reran a gate or processing')
    monkeypatch.setattr(state,'processing_status',forbidden)
    monkeypatch.setattr(state,'publication_readiness',forbidden)
    payload = processing_evidence_zip(snapshot_id=sid,revision=revision,envelope=state._envelope(sid),objects=objects)
    path=tmp_path/'recorded.zip'; path.write_bytes(payload)
    report=blockage_report(read_blockage_zip(path))
    assert report['next_blocking_stage'] == 'source_formation'
    with ZipFile(io.BytesIO(payload)) as archive:
        assert b'blockage_report' in archive.read('manifest.csv')
        assert b'Bronverwerking' in archive.read('blockage_summary.txt')
    assert all(a['observed_conditions_met'] is None for a in report['follow_up'])
    assert len(calls) == 2


def test_actual_recovery_moves_diagnosis_to_review_and_keeps_old_findings_historical(console, monkeypatch):
    state, sid, actor, reviewer, calls, mode, make, bind = partial(console)
    before = collect_blockage(state,actor_id=actor,snapshot_id=sid,current_checks=True)
    assert before['next_blocking_stage'] == 'source_formation'
    assert not any(a['action'] == 'review_obligations' for a in before['follow_up'])
    complete = next(o for o in state.snapshot_objects(sid) if o.get('metadata',{}).get('admission',{}).get('gate_result') == 'allowed')
    mode['broken'] = False
    def forbidden(*args, **kwargs):
        raise AssertionError('recovery reconstructed accepted extraction')
    monkeypatch.setattr(state,'_extract',forbidden)
    state.resume_formation(actor_id=actor,snapshot_id=sid,command_id='diagnostic-recovery',expected_revision=state.objects_revision(sid))
    fresh=make(); bind(fresh)
    after=collect_blockage(fresh,actor_id=actor,snapshot_id=sid,current_checks=True)
    assert after['next_blocking_stage'] == 'publication_conditions'
    assert not any(b['code'] == 'source_formation_incomplete' for b in after['blockers'])
    assert after['finding_counts'].get('pending',0) == 0
    assert after['finding_counts'].get('historical',0) > 0
    assert any(a['action'] == 'review_obligations' for a in after['follow_up'])
    assert next(o for o in fresh.snapshot_objects(sid) if o['object_id']==complete['object_id']) == complete
    assert len(calls) == 3


def test_access_revoked_during_current_checks_is_denied_not_exported(console, monkeypatch):
    from src.operations_console_v1 import ConsoleError
    state, sid, actor, reviewer, calls, mode, make, bind = partial(console)
    original=state.publication_readiness
    def revoke(snapshot_id):
        result=original(snapshot_id)
        with state._reprocessing_transaction(snapshot_id):
            current=deepcopy(state._envelope(snapshot_id))
            current['named_reviewers']=[value for value in current['named_reviewers'] if value!=reviewer]
            state._commit_prepared_store(envelopes={snapshot_id:current},snapshot_id=snapshot_id)
        return result
    monkeypatch.setattr(state,'publication_readiness',revoke)
    with pytest.raises(ConsoleError,match='reviewer_not_named_on_snapshot'):
        collect_blockage(state,actor_id=reviewer,snapshot_id=sid,current_checks=True)


def test_current_readiness_does_not_fall_back_to_native_extraction(console, monkeypatch):
    from tests.test_source_dispatch_hardening import receive
    from tests.test_availability_repair import accounts
    actor, reviewer=accounts(console)
    sid=receive(console,actor,reviewer,'no-accepted-extraction')
    before=deepcopy(console._envelope(sid))
    invoked=[]
    def forbidden(*args,**kwargs):
        invoked.append(True)
        raise AssertionError('read-only diagnostic invoked extraction-capable readiness')
    monkeypatch.setattr(console,'publication_readiness',forbidden)
    monkeypatch.setattr(console,'_extract',forbidden)
    report=collect_blockage(console,actor_id=actor,snapshot_id=sid,current_checks=True)
    assert invoked == []
    assert report['context']['source_hash'] == before['sha256']
    assert report['current_checks']['errors']['readiness'] == 'retained_source_not_recorded'
    assert not report['current_checks']['readiness']
    assert console._envelope(sid) == before


def test_current_checks_stay_retained_only_if_source_metadata_changes_during_check(console, monkeypatch):
    state, sid, actor, reviewer, calls, mode, make, bind = partial(console)
    original=state.publication_readiness
    invoked=[]
    def forbidden(*args,**kwargs):
        invoked.append(True)
        raise AssertionError('diagnostic fell back to native extraction')
    monkeypatch.setattr(state,'_extract',forbidden)
    def remove_then_check(snapshot_id):
        with state._reprocessing_transaction(snapshot_id):
            current=deepcopy(state._envelope(snapshot_id))
            del current['prepared_source_extraction']
            state._commit_prepared_store(envelopes={snapshot_id:current},snapshot_id=snapshot_id)
        return original(snapshot_id)
    monkeypatch.setattr(state,'publication_readiness',remove_then_check)
    report=collect_blockage(state,actor_id=actor,snapshot_id=sid,current_checks=True)
    assert invoked == []
    assert report['current_checks']['context_matches'] is False
    assert all(a['observed_conditions_met'] is None for a in report['follow_up'])
