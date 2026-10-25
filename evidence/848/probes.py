"""Supplemental #848 adversarial probes; run explicitly with -p tests.conftest.

Synthetic sources only. Not a replacement for the complete standard collection.
"""
from copy import deepcopy
import json
import pytest
from src.operations_console_v1 import ConsoleError
from src.workflows.formation_task_store_v1 import FormationTaskStore
from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
from tests.test_review_formation_problems import received, execute


def test_activation_proof_fences_current_revision_without_changing_preparation(tmp_path, production_console, monkeypatch):
    console, sid, author, _, _, mode, _ = received(tmp_path, production_console, monkeypatch)
    execute(console, sid, author, 'partial')
    first = deepcopy(console._envelope(sid))
    mode['broken'] = False
    execute(console, sid, author, 'recover')
    envelope = console._envelope(sid)
    latest = envelope['processing_attempts'][-1]
    reference = latest['diagnostic']['validator_input_ref']
    assert reference == first['processing_attempts'][-1]['diagnostic']['validator_input_ref']
    saved = deepcopy(console.snapshot_objects(sid))
    store = FormationTaskStore(console.workflow_document_store)
    class RollBackProbe(Exception): pass
    with store.documents._connect() as connection:
        store.assert_activation(connection, envelope)
        original = connection.execute('SELECT final_validation FROM workflow.formation_contexts WHERE context_id=%s',
            (reference['context_id'],)).fetchone()['final_validation']
        forged = deepcopy(original)
        forged['activation_revision'] = 'stale-object-revision'
        bad = deepcopy(envelope)
        bad['processing_attempts'][-1]['diagnostic']['final_validation'] = forged
        try:
            with connection.transaction():
                connection.execute('UPDATE workflow.formation_contexts SET final_validation=%s::jsonb WHERE context_id=%s',
                    (json.dumps(forged), reference['context_id']))
                with pytest.raises(WorkflowDocumentStoreError, match='formation_final_validation_required'):
                    store.assert_activation(connection, bad)
                raise RollBackProbe()
        except RollBackProbe:
            pass
        assert connection.execute('SELECT final_validation FROM workflow.formation_contexts WHERE context_id=%s',
            (reference['context_id'],)).fetchone()['final_validation'] == original
        store.assert_activation(connection, envelope)
    assert console.snapshot_objects(sid) == saved


def test_every_current_problem_remains_reachable_beyond_report_limits(tmp_path, production_console, monkeypatch):
    import re
    from fastapi.testclient import TestClient
    from tests.test_availability_repair import bind, login
    from tests.test_recommendation_context_v3 import response_for
    from tests.production_support import restart_production
    console, _, author, reviewer, _, _, _ = received(tmp_path, production_console, monkeypatch)
    console = restart_production(console)
    sentences=[f'Controleer{i:03d} huidgebied{i:03d}.' for i in range(270)]
    def provider(_url, _headers, payload, _timeout):
        objects=[]
        for sentence in sentences:
            row=response_for(payload,sentence)['objects'][0]
            row['field_evidence']['recommended_action']['span']['literal']='verzonnen bewijs'
            objects.append(row)
        return {'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(
            {'objects':objects,'relations':[],'abstain_reason':None})}]}]}
    bind(console,provider)
    sid=console.receive_source(actor_id=author,filename='many.html',content_type='text/html',
        data=('<html><body><p>'+' '.join(sentences)+'</p></body></html>').encode(),
        ingest_kind='new',title='Veel afzonderlijke bevindingen',version='1',date='2026-10-25',
        live_url='',class_='richtlijn',family='fixture',named_reviewers=[reviewer])['snapshot_id']
    with pytest.raises(ConsoleError,match='source_formation_incomplete'):
        execute(console,sid,author,'many-findings')
    from src.formation_problems_v1 import collect
    report=collect(console,actor_id=author,snapshot_id=sid)
    literal=[r for r in report['problems'] if r['code']=='semantic_evidence_literal_not_found']
    assert len(literal)==270
    client=TestClient(console._metis_test_application);login(client)
    visible=[]
    for offset in range(0,len(report['problems']),100):
        response=client.get('/formation-problems',params={'document':sid,'offset':offset})
        assert response.status_code==200
        visible+=re.findall(r'id="problem-([0-9a-f]{64})"',response.text)
    assert len(visible)==len(set(visible))==len(report['problems'])
    assert {r['problem_id'] for r in literal} <= set(visible)
