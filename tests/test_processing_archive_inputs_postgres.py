"""Owner-derived input membership is neither new closure nor activation authority.

# release-control-evidence: scope/belofte opslag concurrent stale recovery
# release-control-evidence: toegang beschikbaarheid kwaliteit slop releasebewijs
"""
from copy import deepcopy
import json
from pathlib import Path

import psycopg
import pytest

from tests.test_processing_archives_postgres import archived_system  # noqa: F401
from src.workflows.processing_archives_v1 import digest, encoded
from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError


@pytest.fixture
def indexed_system(archived_system):
    console, store, envelope = archived_system
    with store.documents._connect() as con:
        con.execute(Path('db/migrations/030_operational_document_inputs.sql').read_text())
    return console, store, envelope


def retained(store, envelope, *, kind, key, payload):
    ref = store.retain_processing_archive(store.prepare_processing_archive(envelope,
        kind=kind, record_key=key, observed_revision='indexed-input-test', payload=payload))
    store.prepare_archive_inputs(ref, envelope=envelope)
    return ref


def test_original_replay_and_unknown_findings_survive_indexing(indexed_system):
    _, store, envelope = indexed_system
    replay = deepcopy(envelope['semantic_replay'])
    replay['provider_evidence']['pending_rejections'] = [
        {'kind':'formation','reason_code':'previously_unknown_finding','spans':[]}]
    replay['provider_evidence']['formation_incomplete'] = True
    replay['provider_evidence']['formation_progress'] = {'raw_progress':'retained'}
    replay['provider_evidence']['raw_provider_payload'] = 'x' * 3_000_000
    ref = retained(store,envelope,kind='semantic_replay',key='indexed-replay',payload=replay)
    store.prepare_archive_inputs(ref,envelope=envelope)  # Same owner idempotency.
    compact = {**envelope,'_document_inputs':{'layout':1,'formation_variant':'semantic','replay':ref}}
    assessment = store.formation_assessment_input(compact)
    assert assessment.replay['proposal'] == replay['proposal']
    assert assessment.replay['provider_evidence']['pending_rejections'] == replay['provider_evidence']['pending_rejections']
    assert 'raw_provider_payload' not in assessment.replay['provider_evidence']
    assert len(encoded(assessment.replay)) < 100_000
    assert store.read_processing_archive(ref,envelope=envelope) == replay
    with pytest.raises(Exception,match='immutable'):
        assessment.replay['provider_evidence']['pending_rejections'].clear()


def test_quality_candidate_selection_keeps_original_order_duplicates_and_hashes(indexed_system):
    _, store, envelope = indexed_system
    payload = {'run_id':'latest','candidates':[
        {'object_id':'wanted','fingerprint':'first','value':1e20},
        {'object_id':'other','raw':'x'*2_000_000},
        {'object_id':'wanted','fingerprint':'second'}],
        'source_fragments':[{'raw':'x'*2_000_000}]}
    ref = retained(store,envelope,kind='quality_processing_run',key='indexed-quality',payload=payload)
    parts = store.read_archive_inputs(ref,envelope=envelope,roles=('meta','candidate'),object_ids=['wanted'])
    assert [p[2]['fingerprint'] for p in parts if p[0]=='candidate'] == ['first','second']
    assert len(encoded(parts)) < 1000
    assert encoded([p[2] for p in parts if p[0]=='candidate']) == encoded([payload['candidates'][0],payload['candidates'][2]])
    assert store.read_processing_archive(ref,envelope=envelope) == payload
    with pytest.raises(WorkflowDocumentStoreError,match='reference_invalid'):
        store.read_archive_inputs({**ref,'record_key':'forged'},envelope=envelope,roles=('meta',))


def test_self_consistent_substitution_of_original_pending_findings_is_refused(indexed_system):
    _, store, envelope = indexed_system
    replay = deepcopy(envelope['semantic_replay'])
    replay['provider_evidence'].update(formation_incomplete=True,pending_rejections=[{'reason_code':'unknown_original'}])
    ref = store.retain_processing_archive(store.prepare_processing_archive(envelope,kind='semantic_replay',
        record_key='substituted',observed_revision='original',payload=replay))
    from src.workflows.processing_archive_inputs_v1 import _parts
    records = sorted((r,k,o,digest(encoded(v)),encoded(v)) for r,k,o,v in _parts('semantic_replay',replay))
    changed=[]
    for role,key,oid,hash_,text in records:
        if role=='provider':
            value=json.loads(text)
            value['pending_rejections']=[]
            text=encoded(value)
            hash_=digest(text)
        changed.append((role,key,oid,hash_,text))
    from src.workflows.processing_archives_v1 import source_binding
    header={'layout':1,'archive_id':ref['archive_id'],'payload_hash':ref['payload_hash'],
        'source':source_binding(envelope),'kind':'semantic_replay','manifest':[[r,k,o,h] for r,k,o,h,_ in changed],
        'notice':{'provider_evidence':{'formation_incomplete':True}}}
    with pytest.raises(psycopg.Error,match='processing_input_original_projection_changed'):
        with store.documents._connect() as con:
            con.execute('INSERT INTO workflow.processing_archive_inputs(archive_id,header,header_hash) VALUES(%s,%s::jsonb,%s)',
                (ref['archive_id'],encoded(header),digest(encoded(header))))
            for r,k,o,h,t in changed:
                con.execute('INSERT INTO workflow.processing_archive_input_members VALUES(%s,%s,%s,%s,%s,%s)',
                    (ref['archive_id'],r,k,o,h,t))
            con.execute('UPDATE workflow.processing_archive_inputs SET sealed=true WHERE archive_id=%s',(ref['archive_id'],))
    with store.documents._connect() as con:
        assert con.execute('SELECT 1 FROM workflow.processing_archive_inputs WHERE archive_id=%s',(ref['archive_id'],)).fetchone() is None


def test_missing_member_or_compact_replay_is_never_empty_formation(indexed_system):
    _, store, envelope = indexed_system
    ref = retained(store,envelope,kind='semantic_replay',key='damaged-members',payload=envelope['semantic_replay'])
    for pins, code in [({'formation_variant':'semantic','replay':None},'required_replay_missing'),
                       ({'formation_variant':'tree','replay':ref},'formation_variant_unsupported')]:
        with pytest.raises(WorkflowDocumentStoreError,match=code):
            store.formation_assessment_input({**envelope,'_document_inputs':{'layout':1,**pins}})
    with store.documents._connect() as con:
        con.execute('ALTER TABLE workflow.processing_archive_input_members DISABLE TRIGGER guard_archive_input_member')
        con.execute("DELETE FROM workflow.processing_archive_input_members WHERE archive_id=%s AND role='provider'",(ref['archive_id'],))
        con.execute('ALTER TABLE workflow.processing_archive_input_members ENABLE TRIGGER guard_archive_input_member')
    with pytest.raises(WorkflowDocumentStoreError,match='membership_incomplete'):
        store.formation_assessment_input({**envelope,'_document_inputs':{
            'layout':1,'formation_variant':'semantic','replay':ref}})


from tests.test_formation_evidence_postgres import pending_proof  # noqa: E402, F401


def test_original_and_activation_replay_are_bound_without_conflating_hashes(pending_proof):
    _, _, writer, envelope, proof_ref = pending_proof
    store = writer.store
    with store.documents._connect() as con:
        header = con.execute('SELECT header FROM workflow.formation_evidence_roots WHERE proof_id=%s',
                             (proof_ref['proof_id'],)).fetchone()['header']
    ref = header['capture']['replay_ref']
    store.prepare_archive_inputs(ref,envelope=envelope)
    result = store.formation_assessment_input({**envelope,'_document_inputs':{
        'layout':1,'formation_variant':'semantic','replay':ref,'proof_id':proof_ref['proof_id']}})
    assert result.archive_id == ref['archive_id']
    assert result.payload_hash == ref['payload_hash']
    assert result.replay['proposal'] == store.read_processing_archive(ref,envelope=envelope)['proposal']
    with pytest.raises(WorkflowDocumentStoreError,match='proof_binding_failed'):
        store.formation_assessment_input({**envelope,'_document_inputs':{
            'layout':1,'formation_variant':'semantic','replay':ref,'proof_id':'0'*64}})


@pytest.mark.parametrize('original,substitute', [(1e20,100000000000000000000),(1.0,1),(1,True)])
def test_sql_seal_refuses_self_consistent_numeric_substitution(indexed_system,original,substitute):
    _, store, envelope = indexed_system
    payload={'run_id':'numeric-original','candidates':[{'object_id':'candidate','value':original}]}
    ref=store.retain_processing_archive(store.prepare_processing_archive(envelope,kind='quality_processing_run',
        record_key='numeric-substitute',observed_revision='original',payload=payload))
    from src.workflows.processing_archive_inputs_v1 import _parts
    from src.workflows.processing_archives_v1 import source_binding
    records=[]
    for role,key,oid,value in _parts('quality_processing_run',payload):
        if role=='candidate':
            value={**value,'value':substitute}
        text=encoded(value)
        records.append((role,key,oid,digest(text),text))
    records.sort()
    header={'layout':1,'archive_id':ref['archive_id'],'payload_hash':ref['payload_hash'],
        'source':source_binding(envelope),'kind':'quality_processing_run','manifest':[[r,k,o,h] for r,k,o,h,_ in records]}
    with pytest.raises(psycopg.Error,match='processing_input_original_projection_changed'):
        with store.documents._connect() as con:
            con.execute('INSERT INTO workflow.processing_archive_inputs(archive_id,header,header_hash) VALUES(%s,%s::jsonb,%s)',
                (ref['archive_id'],encoded(header),digest(encoded(header))))
            for r,k,o,h,t in records:
                con.execute('INSERT INTO workflow.processing_archive_input_members VALUES(%s,%s,%s,%s,%s,%s)',
                    (ref['archive_id'],r,k,o,h,t))
            con.execute('UPDATE workflow.processing_archive_inputs SET sealed=true WHERE archive_id=%s',(ref['archive_id'],))
