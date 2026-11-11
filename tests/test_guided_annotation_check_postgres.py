"""Current annotation check uses the same native heads and validation owners.

# release-control-evidence: scope/belofte kwaliteit toegang opslag concurrent stale
"""
from uuid import uuid4

import pytest
from starlette.testclient import TestClient

from src.operations_console_v1 import ConsoleError
from src.vorming import human_annotation_v1 as annotations
from tests.test_human_annotation_postgres import source, anchor, command


def test_check_is_authorized_read_only_and_names_exact_saved_basis(production_console, production_app, tmp_path):
    console, actor, reviewer, sid, view, _ = source(production_console, tmp_path)
    request = command(view, ranges=[anchor(view, 'Onderzoek')])
    receipt = annotations.save(console, actor_id=actor, **request)
    before = annotations.overview(console, actor_id=actor, snapshot_id=sid)
    check = annotations.check_current(console, actor_id=actor, snapshot_id=sid, annotation_id=request['annotation_id'])
    assert check['revision'] == receipt['revision']
    assert check['basis']['generation'] == before['generation']
    assert check['basis']['objects_revision'] == before['objects_revision']
    assert check['basis']['extraction_hash'] == before['extraction_hash']
    assert 'annotation_evidence_required' in check['codes']  # Underbouwing is nog niet beantwoord.
    assert 'annotation_not_ready' not in check['codes']
    assert 'annotation_source_unaccounted' not in check['codes']
    client=TestClient(production_app(console),base_url='https://testserver')
    client.post('/login',data={'username':'annotator','password':'annotation-secret'})
    response=client.get('/annotations/check',params={'document':sid,'annotation':request['annotation_id']})
    assert response.status_code==200
    assert response.headers['cache-control']=='no-store'
    assert response.json()['basis']==check['basis']
    assert any(finding['code']=='annotation_evidence_required' and finding['message'] for finding in response.json()['findings'])
    assert annotations.overview(console, actor_id=actor, snapshot_id=sid) == before
    with console.workflow_document_store._connect() as con:
        assert con.execute('SELECT count(*) AS n FROM workflow.annotation_versions WHERE snapshot_id=%s',(sid,)).fetchone()['n']==1
        assert con.execute('SELECT count(*) AS n FROM workflow.annotation_commands WHERE snapshot_id=%s',(sid,)).fetchone()['n']==1
    assert annotations.check_current(console, actor_id=reviewer['account_id'], snapshot_id=sid, annotation_id=request['annotation_id']) == check
    outsider = console.create_account(username='outside',password='annotation-secret',roles=('reviewer',))
    with pytest.raises(ConsoleError, match='reviewer_not_named_on_snapshot'):
        annotations.check_current(console, actor_id=outsider['account_id'], snapshot_id=sid, annotation_id=request['annotation_id'])
    client.post('/logout')
    client.post('/login',data={'username':'outside','password':'annotation-secret'})
    assert client.get('/annotations/check',params={'document':sid,'annotation':request['annotation_id']}).status_code==403
    with pytest.raises(ConsoleError, match='annotation_not_found'):
        annotations.check_current(console, actor_id=actor, snapshot_id=sid, annotation_id=str(uuid4()))
    newer = {**request, 'command_id':str(uuid4()), 'expected_revision':receipt['revision'],
             'expected_generation':receipt['generation']}
    newer['selection'] = {**request['selection'], 'object_type':'explanation'}
    annotations.save(console, actor_id=actor, **newer)
    current = annotations.check_current(console, actor_id=actor, snapshot_id=sid, annotation_id=request['annotation_id'])
    assert current['revision'] != check['revision']
    assert current['basis']['generation'] != check['basis']['generation']
    # A check does not refresh an older writer's preconditions.
    with pytest.raises(ConsoleError, match='annotation_write_conflict'):
        annotations.save(console, actor_id=actor, **{**newer, 'command_id':str(uuid4())})
