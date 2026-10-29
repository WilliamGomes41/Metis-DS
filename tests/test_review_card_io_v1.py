"""Native HTTP byte/row budgets: current facts, never source/history payloads.

# release-control-evidence: scope/belofte opslag concurrent stale recovery
# release-control-evidence: toegang kwaliteit metrics teller noemer score-must-drop slop releasebewijs
"""
from copy import deepcopy
import json
import re

from fastapi.testclient import TestClient
import psycopg
import pytest

from src.review.revision_workflow import revise_object
from src.workflows.review_card_inputs_postgres_v1 import prepare_review_cards
from tests.test_d5_4_review_interaction_evidence import _system, PASSWORD, HTML
from tests.semantic_fixture_support import bind_fixture_selections


def monitor_reads(monkeypatch):
    execute=psycopg.Connection.execute
    measurements=[]
    class Cursor:
        def __init__(self,cursor,query,params):
            self.cursor,self.query,self.params=cursor,query,params
        def __getattr__(self,key):
            return getattr(self.cursor,key)
        def record(self,rows):
            if rows:
                encoded=json.dumps(rows,default=str)
                assert 'card-history-canary' not in encoded
                measurements.append((self.query,self.params,len(rows),len(encoded)))
            return rows
        def fetchone(self):
            row=self.cursor.fetchone()
            self.record([] if row is None else [row])
            return row
        def fetchall(self):
            return self.record(self.cursor.fetchall())
    def checked(connection,query,params=None,**kwargs):
        sql=str(query)
        assert not sql.lstrip().upper().startswith(('INSERT','UPDATE','DELETE','CREATE','ALTER','TRUNCATE'))
        assert 'workflow.document_objects' not in sql
        assert 'workflow.source_read_' not in sql and 'workflow.prepared_extraction_versions' not in sql
        return Cursor(execute(connection,query,params,**kwargs),sql,params)
    monkeypatch.setattr(psycopg.Connection,'execute',checked)
    return measurements


@pytest.mark.parametrize('history_size',[32,128])
def test_http_io_is_independent_of_heavy_object_history(tmp_path,production_console,production_app,monkeypatch,history_size):
    console,users,sid,oid=_system(tmp_path,production_console=lambda **options:production_console(
        environment={'CONSOLE_REVIEW_CARD_READS':'compact'},**options))
    prepare_review_cards(console.workflow_document_store,sid)
    store=console.workflow_document_store
    histories=store.list_document_objects(sid)
    current=next(o for o in console.snapshot_objects(sid) if o['object_id']==oid)
    for index in range(history_size):
        proposed=deepcopy(current)
        proposed['metadata']['history_archive']='card-history-canary-'+str(index)+('x'*65536)
        current=revise_object(current,proposed,snapshot_id=sid,actor='reviewer fixture',reason='explicit revision')
        histories.append(current)
    store.write_bundle(envelope=store.get_envelope(sid),objects=histories,expected_revision=store.objects_revision(sid))
    client=TestClient(production_app(console),base_url='https://testserver')
    assert client.post('/login',data={'username':users['reviewer_a']['username'],'password':PASSWORD},follow_redirects=False).status_code==303
    measurements=monitor_reads(monkeypatch)
    def forbidden(*args,**kwargs):
        pytest.fail('Compact HTTP recomputed a full object hash or source')
    monkeypatch.setattr('src.review.review_card_facts_v1.exact_review_snapshot_hash',forbidden)
    monkeypatch.setattr(console,'review_source_fragments',forbidden)
    monkeypatch.setattr(console,'_verified_source_bytes',forbidden)
    page=client.get('/review')
    assert page.status_code==200 and 'data-personal-open>1<' in page.text
    facts=[row for row in measurements if 'FROM workflow.review_object_facts WHERE' in row[0]]
    assert len(facts)==1 and facts[0][2]==3 and facts[0][3]<20000
    print(json.dumps({'history_versions':history_size,'fact_rows':facts[0][2],'fact_bytes':facts[0][3],
                      'all_json_bytes':sum(row[3] for row in measurements)}))


def test_native_pagination_bounds_fact_rows_as_assigned_documents_grow(tmp_path,production_console,production_app,monkeypatch):
    console=production_console(root=tmp_path,processing_binder=bind_fixture_selections,
        environment={'CONSOLE_REVIEW_CARD_READS':'compact'})
    owner=console.create_account(username='card-page-owner',password=PASSWORD,roles=('researcher','reviewer'))
    peer=console.create_account(username='card-page-peer',password=PASSWORD,roles=('reviewer',))
    bind_fixture_selections(console,[('Interventie A is een behandeling.','definition')])
    client=TestClient(production_app(console),base_url='https://testserver')
    assert client.post('/login',data={'username':owner['username'],'password':PASSWORD},follow_redirects=False).status_code==303
    next_index=0
    for total in (26,51):
        for index in range(next_index,total):
            console.ingest(actor_id=owner['account_id'],filename='page.html',data=HTML,content_type='text/html',
                ingest_kind='new',title=f'Card {index:03}',version='1.0',date='2026-09-25',class_='richtlijn',
                family='test',live_url=None,named_reviewers=[owner['account_id'],peer['account_id']])
        next_index=total
        with monkeypatch.context() as patch:
            measurements=monitor_reads(patch)
            page=client.get('/review')
            assert page.status_code==200
            visible=re.findall(r'data-workboard-document="([^"]+)"',page.text)
            assert len(visible)==25
            facts=[row for row in measurements if 'FROM workflow.review_object_facts WHERE' in row[0]]
            assert len(facts)==1 and set(facts[0][1][0])==set(visible)
            assert facts[0][2]==75 and facts[0][3]<400000
            print(json.dumps({'assigned_documents':total,'visible_documents':len(visible),
                              'fact_rows':facts[0][2],'fact_bytes':facts[0][3]}))
            measurements.clear()
            last=client.get('/review',params={'page':(total+24)//25})
            assert last.status_code==200
            visible_last=re.findall(r'data-workboard-document="([^"]+)"',last.text)
            assert len(visible_last)==1
            facts=[row for row in measurements if 'FROM workflow.review_object_facts WHERE' in row[0]]
            assert len(facts)==1 and set(facts[0][1][0])==set(visible_last) and facts[0][2]==3
