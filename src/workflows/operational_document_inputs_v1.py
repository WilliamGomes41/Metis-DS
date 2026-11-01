"""The existing document aggregate's compact representation and explicit inputs.

Preparation is independent; admission is a representation-only CAS on the same
row/identity/lock as every other document command. Reads never migrate data.
"""
from copy import deepcopy
from dataclasses import dataclass
import json

from src.workflows.processing_archives_v1 import encoded, digest, TREE_FIELDS
from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
from src.workflows.workflow_transaction_v1 import workflow_transaction_active

SCALARS = {
    'snapshot_id':'snapshot_id','source_id':'source_id','document_id':'document_id',
    'title':'title','family':'family','topic_id':'topic_id','class':'class','state':'state',
    'publication_eligibility':'publication_eligibility','content_kind':'content_kind',
    'ingest_kind':'ingest_kind','version':'source_version','date':'source_date','sha256':'source_sha256',
    'locator':'source_locator','immutable_storage_locator':'immutable_storage_locator',
    'live_url':'live_url','uploader_account_id':'uploader_account_id','replaces_snapshot_id':'replaces_snapshot_id',
    'object_diff':'object_diff','clinical_rereview_required':'clinical_rereview_required',
    'acquired_at':'acquired_at','console_version':'console_version','logical_document_id':'logical_document_id',
    'working_revision_id':'working_revision_id','working_revision_number':'working_revision_number',
    'processing_storage':'processing_storage_version',
}
HEAVY = {'semantic_replay','quality_processing_runs','processing_attempts','prepared_source_extraction'} | TREE_FIELDS
EPHEMERAL = {'_document_inputs','_review_source_ref','_review_check_formation',
             '_review_formation_notice','_review_has_replay','_processing_counts','_prepared_document_write','_document_header_only','_metadata_header_unprepared','tree_source_route'}
CAPTURE = '''SELECT revision,object_generation,source_sha256,source_version,review_source_ref,
    formation_evidence_id,document_storage_version,processing_storage_version,
    (SELECT md5(COALESCE(string_agg(attempt_id||':'||record_version,',' ORDER BY attempt_id),''))
     FROM workflow.processing_attempts a WHERE a.snapshot_id=d.snapshot_id) AS attempts_token
    FROM workflow.documents d WHERE snapshot_id=%s'''


def fail(reason):
    raise WorkflowDocumentStoreError('document_inputs_' + reason)


def admission_requested(environ=None):
    import os
    settings=os.environ if environ is None else environ
    value=settings.get('METIS_DOCUMENT_INPUT_STORAGE','').strip()
    if value not in {'','legacy','v1'}:
        fail('admission_configuration_invalid')
    if value=='v1' and settings.get('METIS_FORMATION_TASK_STORAGE')!='v1':
        fail('native_task_storage_required')
    return value=='v1'


def metadata(envelope):
    return {k:deepcopy(v) for k,v in envelope.items() if k not in SCALARS.keys() | HEAVY | EPHEMERAL}


@dataclass(frozen=True)
class PreparedOperationalInputs:
    snapshot_id: str
    capture_text: str


@dataclass(frozen=True)
class PreparedOperationalWrite:
    before_refs_text: str
    next_refs_text: str
    extraction_text: str
    notice_text: str
    records_text: str


def replay_reference(envelope):
    prepared=envelope.get('_prepared_document_write')
    refs=json.loads(prepared.next_refs_text) if isinstance(prepared,PreparedOperationalWrite) else envelope.get('_document_inputs')
    return (refs or {}).get('replay')


class OperationalDocumentInputs:
    def admit_new_document_locked(self,con,snapshot_id):
        """Atomic new, unformed receipt only; never migrate an existing row."""
        row=con.execute('SELECT d.snapshot_id,d.topic_id,d.envelope_payload,t.display_name '
            'FROM workflow.documents d LEFT JOIN workflow.topics t ON t.topic_id=d.topic_id '
            'WHERE d.snapshot_id=%s',(snapshot_id,)).fetchone()
        envelope=self._envelope_from_row(con,row)
        if any(envelope.get(key) for key in HEAVY):
            fail('new_document_must_be_unformed')
        capture=con.execute(CAPTURE,(snapshot_id,)).fetchone()
        refs={'layout':1,'acquired_at_z':str(envelope.get('acquired_at') or '').endswith('Z'),
            'fields':sorted((set(envelope)&SCALARS.keys()) | {'processing_storage'}),
            'shapes':{k:('absent' if k not in envelope else 'null' if envelope[k] is None else 'value') for k in HEAVY},
            'formation_variant':'absent','replay':None,'quality':None,'extraction_hash':None,'tree':None,'tree_route':False}
        con.execute('INSERT INTO workflow.document_inputs(snapshot_id,metadata,refs,extraction_header,notice,'
            "prepared_capture,prepared_quality_count,prepared_has_replay) VALUES(%s,%s::jsonb,%s::jsonb,'null'::jsonb,'{}'::jsonb,%s::jsonb,0,false)",
            (snapshot_id,encoded(metadata(envelope)),encoded(refs),encoded(capture)))
        con.execute("SELECT set_config('metis.document_storage_writer','v1',true)")
        con.execute('UPDATE workflow.documents SET document_storage_version=1,revision=revision+1 WHERE snapshot_id=%s',(snapshot_id,))

    def prepare_operational_inputs(self, snapshot_id):
        if workflow_transaction_active():
            fail('requires_independent_transaction')
        from src.workflows.formation_task_store_v1 import FormationTaskStore
        tasks = FormationTaskStore(self)
        with self._connect() as con:
            con.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            capture = con.execute(CAPTURE,(snapshot_id,)).fetchone()
            if capture is None:
                fail('document_missing')
            if capture['document_storage_version'] != 0:
                fail('already_admitted')
            row = con.execute('SELECT d.snapshot_id,d.topic_id,d.envelope_payload,t.display_name '
                'FROM workflow.documents d LEFT JOIN workflow.topics t ON t.topic_id=d.topic_id '
                'WHERE snapshot_id=%s',(snapshot_id,)).fetchone()
            envelope = self._envelope_from_row(con,row)
        attempts=envelope.get('processing_attempts') or []
        if any(a.get('state')=='running' for a in attempts):
            fail('processing_in_progress')
        if envelope.get('processing_storage')!='task-v1' and attempts:
            from datetime import datetime
            try:
                ordered=sorted(attempts,key=lambda a:(datetime.fromisoformat(a['started_at'].replace('Z','+00:00')),a['attempt_id']))
            except (KeyError,TypeError,ValueError) as error:
                raise WorkflowDocumentStoreError('document_inputs_legacy_attempt_incompatible') from error
            if [a['attempt_id'] for a in ordered]!=[a['attempt_id'] for a in attempts]:
                fail('legacy_attempt_order_incompatible')
            # Inactive, exact copies. The old inline owner stays authoritative
            # until the same row CAS selects format v1; no old attempt is run.
            with self._connect() as con:
                conflict=con.execute("SELECT 1 FROM workflow.documents d CROSS JOIN LATERAL jsonb_array_elements(COALESCE(d.envelope_payload->'processing_attempts','[]'::jsonb)) a JOIN workflow.processing_attempts existing ON existing.attempt_id=a->>'attempt_id' WHERE d.snapshot_id=%s AND (existing.snapshot_id<>d.snapshot_id OR existing.command_id IS DISTINCT FROM a->>'command_id') LIMIT 1",(snapshot_id,)).fetchone()
                if conflict:
                    fail('legacy_attempt_owner_conflict')
                con.execute("INSERT INTO workflow.processing_attempts(attempt_id,snapshot_id,command_id,started_at,object_generation,payload) "
                    "SELECT a->>'attempt_id',d.snapshot_id,a->>'command_id',(a->>'started_at')::timestamptz,d.object_generation,a "
                    "FROM workflow.documents d CROSS JOIN LATERAL jsonb_array_elements(COALESCE(d.envelope_payload->'processing_attempts','[]'::jsonb)) a "
                    "WHERE d.snapshot_id=%s AND COALESCE(d.processing_storage_version,0)=0 "
                    "ON CONFLICT(attempt_id) DO UPDATE SET payload=EXCLUDED.payload,record_version="
                    "workflow.processing_attempts.record_version+CASE WHEN workflow.processing_attempts.payload=EXCLUDED.payload THEN 0 ELSE 1 END WHERE workflow.processing_attempts.snapshot_id=EXCLUDED.snapshot_id AND workflow.processing_attempts.command_id=EXCLUDED.command_id",
                    (snapshot_id,))
                after=con.execute(CAPTURE,(snapshot_id,)).fetchone()
            if {k:v for k,v in after.items() if k!='attempts_token'}!={k:v for k,v in capture.items() if k!='attempts_token'}:
                fail('stale_preparation')
            capture=after
        with self._connect() as con:
            con.execute('INSERT INTO workflow.processing_attempt_inputs '
                '(attempt_id,snapshot_id,command_id,started_at,record_version,state,kind,progress_made,payload) '
                "SELECT attempt_id,snapshot_id,command_id,started_at,record_version,payload->>'state',payload->>'kind',"
                "payload->'formation_progress_made'='true'::jsonb,workflow.processing_attempt_input_for(payload) "
                'FROM workflow.processing_attempts WHERE snapshot_id=%s ON CONFLICT(attempt_id) DO NOTHING',(snapshot_id,))
        latest=next(reversed(envelope.get('processing_attempts') or []),{})
        if (capture['formation_evidence_id'] is None and (latest.get('diagnostic') or {}).get('validator_input_ref')
                and envelope.get('semantic_replay')):
            fail('legacy_formation_preparation_required')
        refs = {'layout':1,'acquired_at_z':str(envelope.get('acquired_at') or '').endswith('Z'),'fields':sorted((set(envelope)&SCALARS.keys()) | {'processing_storage'}),
                'shapes':{k:('absent' if k not in envelope else 'null' if envelope[k] is None else 'value') for k in HEAVY},
                'formation_variant':'semantic' if envelope.get('semantic_replay') else
                    'tree' if envelope.get('decision_graph') else 'absent',
                'replay':None,'quality':None,'extraction_hash':None,'tree':None,'tree_route':False}
        records=[]
        replay=envelope.get('semantic_replay')
        if replay:
            prepared=tasks.prepare_processing_archive(envelope,kind='semantic_replay',
                record_key='operation-'+digest(encoded(capture))[:16]+'-'+digest(encoded(replay)),observed_revision=encoded(capture),payload=replay)
            refs['replay']=tasks.retain_processing_archive(prepared)
            tasks.prepare_archive_inputs(refs['replay'],envelope=envelope)
            records.append(('semantic_replay',0,refs['replay']))
        for ordinal,run in enumerate(envelope.get('quality_processing_runs') or []):
            prepared=tasks.prepare_processing_archive(envelope,kind='quality_processing_run',
                record_key='operation-'+digest(encoded(capture))[:16]+'-'+str(ordinal)+'-'+digest(encoded(run)),observed_revision=encoded(capture),payload=run)
            ref=tasks.retain_processing_archive(prepared)
            tasks.prepare_archive_inputs(ref,envelope=envelope)
            records.append(('quality_processing_run',ordinal,ref))
            refs['quality']=ref
        tree={k:envelope[k] for k in TREE_FIELDS if k in envelope}
        if tree:
            ref=tasks.retain_processing_archive(tasks.prepare_processing_archive(envelope,kind='tree_formation',
                record_key='operation-tree-'+digest(encoded(capture))[:16]+'-'+digest(encoded(tree)),observed_revision=encoded(capture),payload=tree))
            tasks.prepare_archive_inputs(ref,envelope=envelope)
            refs['tree']=ref
            refs['tree_route']=bool(tree.get('decision_tree_formation'))
            if refs['replay'] is None:
                refs['formation_variant']='tree'
            records.append(('tree_formation',0,ref))
        extraction=envelope.get('prepared_source_extraction')
        extraction_header=None
        if extraction:
            from src.vorming.source_preparation_context_v1 import stored_extraction
            if stored_extraction(envelope) is None:
                fail('extraction_incompatible')
            with self._connect() as con:
                tasks._immutable(con,'prepared_extraction_versions','record_hash',extraction['record_hash'],
                    ['snapshot_id'],[snapshot_id],extraction)
            refs['extraction_hash']=extraction['record_hash']
            extraction_header={k:deepcopy(v) for k,v in extraction.items() if k not in {'fragments','docling_record'}}
        notice=({'provider_evidence':{'formation_incomplete':
            (replay.get('provider_evidence') or {}).get('formation_incomplete')}} if replay else {})
        # Persist only owner-verified metadata/indexes before taking the
        # document command lock. An altered carrier can never replace this plan.
        with self._connect() as con:
            con.execute('DELETE FROM workflow.document_processing_records WHERE snapshot_id=%s',(snapshot_id,))
            for kind,ordinal,ref in records:
                con.execute('INSERT INTO workflow.document_processing_records(snapshot_id,kind,ordinal,archive_id,reference) '
                    'VALUES(%s,%s,%s,%s,%s::jsonb)',(snapshot_id,kind,ordinal,ref['archive_id'],encoded(ref)))
        with self._connect() as con:
            con.execute('INSERT INTO workflow.document_inputs(snapshot_id,metadata,refs,extraction_header,notice,'
                'prepared_capture,prepared_quality_count,prepared_has_replay,prepared_has_tree) '
                'VALUES(%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s) '
                'ON CONFLICT(snapshot_id) DO UPDATE SET metadata=EXCLUDED.metadata,refs=EXCLUDED.refs,'
                'extraction_header=EXCLUDED.extraction_header,notice=EXCLUDED.notice,prepared_capture=EXCLUDED.prepared_capture,'
                'prepared_quality_count=EXCLUDED.prepared_quality_count,prepared_has_replay=EXCLUDED.prepared_has_replay,prepared_has_tree=EXCLUDED.prepared_has_tree',
                (snapshot_id,encoded(metadata(envelope)),encoded(refs),encoded(extraction_header),encoded(notice),encoded(capture),
                 len(envelope.get('quality_processing_runs') or []),bool(replay),bool(tree)))
        return PreparedOperationalInputs(snapshot_id,encoded(capture))

    def activate_operational_inputs(self, prepared):
        if not isinstance(prepared,PreparedOperationalInputs):
            fail('preparation_invalid')
        with self._connect() as con:
            with con.transaction():
                con.execute('SELECT snapshot_id FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE',
                            (prepared.snapshot_id,)).fetchone()
                row=con.execute(CAPTURE,(prepared.snapshot_id,)).fetchone()
                if row is None or encoded(row)!=prepared.capture_text:
                    fail('stale_preparation')
                stored=con.execute('SELECT metadata,refs,extraction_header,notice,prepared_capture,prepared_quality_count,prepared_has_replay,prepared_has_tree '
                    'FROM workflow.document_inputs WHERE snapshot_id=%s',(prepared.snapshot_id,)).fetchone()
                if stored is None or encoded(stored['prepared_capture'])!=prepared.capture_text:
                    fail('preparation_changed')
                counts=con.execute("SELECT count(*) FILTER(WHERE kind='quality_processing_run') AS quality,"
                    "count(*) FILTER(WHERE kind='semantic_replay') AS replay,count(*) FILTER(WHERE kind='tree_formation') AS tree FROM workflow.document_processing_records "
                    "WHERE snapshot_id=%s",(prepared.snapshot_id,)).fetchone()
                if counts['quality']!=stored['prepared_quality_count'] or counts['replay']!=int(stored['prepared_has_replay']) or counts['tree']!=int(stored['prepared_has_tree']):
                    fail('membership_incomplete')
                con.execute('UPDATE workflow.documents SET document_storage_version=1,processing_storage_version=1,revision=revision+1,'
                    'formation_evidence_id=formation_evidence_id WHERE snapshot_id=%s',(prepared.snapshot_id,))

    def formation_input(self, envelope):
        """Explicit current intrinsic inputs, never historical provider bodies."""
        if '_document_inputs' not in envelope:
            return envelope
        from src.workflows.formation_task_store_v1 import FormationTaskStore
        result=deepcopy(envelope)
        pins=envelope['_document_inputs']
        if bool(pins.get('replay')) != (pins.get('formation_variant')=='semantic'):
            fail('formation_variant_inconsistent')
        if pins.get('formation_variant') == 'semantic':
            result['semantic_replay']=deepcopy(FormationTaskStore(self).formation_assessment_input(envelope).replay)
        elif pins.get('formation_variant') not in {'tree','absent'}:
            fail('formation_variant_unsupported')
        return result

    def tree_input(self,envelope, *, fields=('decision_graph_evidence',)):
        if '_document_inputs' not in envelope:
            return envelope
        ref=envelope['_document_inputs'].get('tree')
        if ref is None:
            if envelope.get('decision_graph'):
                fail('tree_source_missing')
            return envelope
        from src.workflows.formation_task_store_v1 import FormationTaskStore
        parts=FormationTaskStore(self).read_archive_inputs(ref,envelope=envelope,roles=fields)
        result=deepcopy(envelope)
        result.update({role:value for role,_,value in parts})
        return result

    def source_input(self, envelope):
        if '_document_inputs' not in envelope:
            return envelope
        from src.workflows.formation_task_store_v1 import FormationTaskStore
        tasks=FormationTaskStore(self)
        result=deepcopy(envelope)
        refs=envelope['_document_inputs']
        if refs['extraction_hash'] is not None:
            result['prepared_source_extraction']=tasks.retained_extraction(envelope,refs['extraction_hash'])
        elif refs['quality'] is not None:
            # Preserve the existing Docling oracle: latest accepted extraction,
            # skipping later failed/classification events. Only indexed source
            # parts are read; candidate/provider payloads stay in the archive.
            with self._connect() as con:
                chosen=con.execute("SELECT r.reference FROM workflow.document_processing_records r "
                    "JOIN workflow.processing_archive_inputs root USING(archive_id) "
                    "JOIN workflow.processing_archive_input_members m ON m.archive_id=r.archive_id AND m.role='meta' AND m.member_key='0' "
                    "WHERE r.snapshot_id=%s AND r.kind='quality_processing_run' AND r.ordinal<=(SELECT p.ordinal FROM workflow.document_processing_records p WHERE p.snapshot_id=r.snapshot_id AND p.kind=r.kind AND p.archive_id=%s) AND m.payload_text::jsonb->>'outcome'='succeeded' "
                    "AND (COALESCE(jsonb_array_length(m.payload_text::jsonb->'extractor_versions'),0)>0 "
                    "OR (root.header->>'source_fragment_count')::bigint>0 OR EXISTS(SELECT 1 FROM workflow.processing_archive_input_members x "
                    "WHERE x.archive_id=r.archive_id AND x.role='document_extraction')) ORDER BY r.ordinal DESC LIMIT 1",
                    (envelope['snapshot_id'],refs['quality']['archive_id'])).fetchone()
            if chosen:
                parts=tasks.read_archive_inputs(chosen['reference'],envelope=envelope,
                    roles=('meta','source_fragments','document_extraction'))
                run=next(value for role,_,value in parts if role=='meta')
                run.update({role:value for role,_,value in parts if role!='meta'})
                result['quality_processing_runs']=[run]
        return result

    def processing_execution_input(self, envelope):
        if workflow_transaction_active():
            fail('requires_independent_transaction')
        if '_document_inputs' not in envelope:
            return envelope
        from src.workflows.formation_task_store_v1 import FormationTaskStore
        result=self.source_input(self.processing_command_input(envelope))
        if envelope['_document_inputs']['replay'] is not None:
            result['semantic_replay']=FormationTaskStore(self).read_processing_archive(
                envelope['_document_inputs']['replay'],envelope=envelope)
        return result

    def prepare_producer_inputs(self, envelope):
        if '_document_inputs' not in envelope:
            return envelope
        if workflow_transaction_active():
            fail('requires_independent_transaction')
        from src.workflows.formation_task_store_v1 import FormationTaskStore
        tasks=FormationTaskStore(self)
        before=envelope['_document_inputs']
        refs=deepcopy(before)
        refs.pop('proof_id',None)
        records=[]
        if envelope.get('semantic_replay'):
            replay=envelope['semantic_replay']
            if envelope.get('processing_storage')=='task-v1':
                from src.workflows.formation_evidence_v1 import activation_replay
                replay=activation_replay(replay)
            prepared=tasks.prepare_processing_archive(envelope,kind='semantic_replay',
                record_key='operation-'+digest(encoded(before))[:16]+'-'+digest(encoded(replay)),observed_revision=encoded(before),payload=replay)
            refs['replay']=tasks.retain_processing_archive(prepared)
            tasks.prepare_archive_inputs(refs['replay'],envelope=envelope)
            refs['formation_variant']='semantic'
            refs['shapes']['semantic_replay']='value'
        with self._connect() as con:
            ordinal=con.execute("SELECT COALESCE(max(ordinal),-1)+1 AS n FROM workflow.document_processing_records "
                "WHERE snapshot_id=%s AND kind='quality_processing_run'",(envelope['snapshot_id'],)).fetchone()['n']
        for run in envelope.get('quality_processing_runs') or []:
            if before['quality'] is not None and digest(encoded(run))==before['quality']['payload_hash']:
                continue
            ref=tasks.retain_processing_archive(tasks.prepare_processing_archive(envelope,kind='quality_processing_run',
                record_key='operation-'+str(ordinal)+'-'+digest(encoded(run)),observed_revision=encoded(before),payload=run))
            tasks.prepare_archive_inputs(ref,envelope=envelope)
            records.append(('quality_processing_run',ordinal,ref))
            ordinal+=1
            refs['quality']=ref
            refs['shapes']['quality_processing_runs']='value'
        tree={k:envelope[k] for k in TREE_FIELDS if k in envelope}
        if tree:
            ref=tasks.retain_processing_archive(tasks.prepare_processing_archive(envelope,kind='tree_formation',
                record_key='operation-tree-'+digest(encoded(before))[:16]+'-'+digest(encoded(tree)),observed_revision=encoded(before),payload=tree))
            tasks.prepare_archive_inputs(ref,envelope=envelope)
            refs['tree']=ref
            refs['tree_route']=bool(tree.get('decision_tree_formation'))
            if refs['replay'] is None:
                refs['formation_variant']='tree'
            for key in tree:
                refs['shapes'][key]='value' if tree[key] is not None else 'null'
        extraction=envelope.get('prepared_source_extraction')
        if extraction and 'fragments' in extraction:
            from src.vorming.source_preparation_context_v1 import stored_extraction
            stored_extraction(envelope)
            with self._connect() as con:
                tasks._immutable(con,'prepared_extraction_versions','record_hash',extraction['record_hash'],
                    ['snapshot_id'],[envelope['snapshot_id']],extraction)
            refs['extraction_hash']=extraction['record_hash']
            refs['shapes']['prepared_source_extraction']='value'
            extraction={k:v for k,v in extraction.items() if k not in {'fragments','docling_record'}}
        with self._connect() as con:
            notice=(con.execute("SELECT header->'notice' AS notice FROM workflow.processing_archive_inputs WHERE archive_id=%s",
                (refs['replay']['archive_id'],)).fetchone()['notice'] if refs['replay'] else {})
        prepared=PreparedOperationalWrite(encoded(before),encoded(refs),encoded(extraction),encoded(notice),encoded(records))
        result={k:deepcopy(v) for k,v in envelope.items() if k not in HEAVY-{'processing_attempts'}}
        if extraction is not None:
            result['prepared_source_extraction']=extraction
        result['_prepared_document_write']=prepared
        return result

    def processing_command_input(self, envelope, *, command_id=None, attempt_id=None):
        """Latest/running/requested command plus scalar cap counts, never history."""
        if '_document_inputs' not in envelope:
            return envelope
        snapshot_id=envelope['snapshot_id']
        with self._connect() as con:
            missing=con.execute('SELECT 1 FROM workflow.processing_attempts a LEFT JOIN workflow.processing_attempt_inputs i '
                'ON i.attempt_id=a.attempt_id WHERE a.snapshot_id=%s AND '
                '(i.attempt_id IS NULL OR i.record_version<>a.record_version) LIMIT 1',(snapshot_id,)).fetchone()
            if missing:
                fail('attempt_index_incomplete')
            counts=con.execute("SELECT count(*) AS total,count(*) FILTER (WHERE NOT ("
                "COALESCE(progress_made AND (state='incomplete_budget' OR (kind='resume' AND state='succeeded')),false))) AS used "
                "FROM workflow.processing_attempt_inputs WHERE snapshot_id=%s",(snapshot_id,)).fetchone()
            rows=con.execute("WITH latest AS (SELECT attempt_id FROM workflow.processing_attempt_inputs WHERE snapshot_id=%s "
                "ORDER BY started_at DESC,attempt_id DESC LIMIT 1) SELECT i.payload,i.record_version "
                "FROM workflow.processing_attempt_inputs i WHERE snapshot_id=%s AND (attempt_id IN(SELECT attempt_id FROM latest) "
                "OR state='running' OR command_id=%s OR attempt_id=%s) ORDER BY started_at,attempt_id",
                (snapshot_id,snapshot_id,command_id,attempt_id)).fetchall()
        result=deepcopy(envelope)
        result['processing_attempts']=[{**r['payload'],'_record_version':r['record_version'],'_input_projection':True} for r in rows]
        result['_processing_counts']={'total':counts['total'],'used':counts['used'],
            'selected_total':len(rows),'selected_used':sum(1 for r in rows if not (
                r['payload'].get('formation_progress_made') is True and (r['payload'].get('state')=='incomplete_budget'
                or (r['payload'].get('kind')=='resume' and r['payload'].get('state')=='succeeded'))))}
        return result

    def processing_history_input(self, snapshot_id):
        envelope=self.get_envelope(snapshot_id)
        if envelope is None or '_document_inputs' not in envelope:
            return envelope
        from src.workflows.formation_task_store_v1 import FormationTaskStore
        tasks=FormationTaskStore(self)
        refs=envelope.pop('_document_inputs')
        with self._connect() as con:
            records=con.execute('SELECT kind,reference FROM workflow.document_processing_records '
                'WHERE snapshot_id=%s ORDER BY kind,ordinal',(snapshot_id,)).fetchall()
            original_storage=con.execute("SELECT envelope_payload->>'processing_storage' AS storage FROM workflow.documents WHERE snapshot_id=%s",(snapshot_id,)).fetchone()['storage']
            attempts=tasks.attempts(con,snapshot_id,include_versions=original_storage=='task-v1')
        envelope.pop('tree_source_route',None)
        if original_storage is None:
            envelope.pop('processing_storage',None)
        for key,shape in refs['shapes'].items():
            if shape=='null':
                envelope[key]=None
            elif shape=='absent':
                envelope.pop(key,None)
        if refs['replay'] is not None:
            envelope['semantic_replay']=tasks.read_processing_archive(refs['replay'],envelope=envelope)
        if refs['shapes']['quality_processing_runs']=='value':
            envelope['quality_processing_runs']=[tasks.read_processing_archive(r['reference'],envelope=envelope)
                for r in records if r['kind']=='quality_processing_run']
        if refs['extraction_hash'] is not None:
            envelope['prepared_source_extraction']=tasks.retained_extraction(envelope,refs['extraction_hash'])
        if attempts or refs['shapes']['processing_attempts']=='value':
            envelope['processing_attempts']=attempts
        if refs.get('tree') is not None:
            envelope.update(tasks.read_processing_archive(refs['tree'],envelope=envelope))
        return envelope

    def _write_operational_envelope_locked(self,con,envelope):
        row=con.execute('SELECT document_storage_version FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE',
                        (envelope['snapshot_id'],)).fetchone()
        if row is None or row['document_storage_version']==0:
            return False
        con.execute("SELECT set_config('metis.document_storage_writer','v1',true)")
        current=con.execute('SELECT workflow.current_document_envelope(d) AS envelope FROM workflow.documents d '
                            'WHERE snapshot_id=%s',(envelope['snapshot_id'],)).fetchone()['envelope']
        prepared=envelope.get('_prepared_document_write')
        submitted_refs=deepcopy(envelope.get('_document_inputs'))
        current_refs=deepcopy(current['_document_inputs'])
        if isinstance(prepared,PreparedOperationalWrite):
            expected=json.loads(prepared.before_refs_text)
            expected.pop('proof_id',None)
            current_refs.pop('proof_id',None)
            if expected!=current_refs or submitted_refs!=json.loads(prepared.before_refs_text):
                fail('stale_producer_preparation')
            refs=json.loads(prepared.next_refs_text)
            extraction=json.loads(prepared.extraction_text)
            notice=json.loads(prepared.notice_text)
            for kind,ordinal,ref in json.loads(prepared.records_text):
                con.execute('INSERT INTO workflow.document_processing_records(snapshot_id,kind,ordinal,archive_id,reference) '
                    'VALUES(%s,%s,%s,%s,%s::jsonb)',(envelope['snapshot_id'],kind,ordinal,ref['archive_id'],encoded(ref)))
        else:
            if submitted_refs!=current_refs:
                fail('producer_preparation_required')
            refs={k:v for k,v in current_refs.items() if k!='proof_id'}
            extraction=current.get('prepared_source_extraction')
            notice=con.execute('SELECT notice FROM workflow.document_inputs WHERE snapshot_id=%s',
                (envelope['snapshot_id'],)).fetchone()['notice']
            if envelope.get('prepared_source_extraction')!=extraction:
                fail('source_preparation_required')
        if set(envelope) & ({'semantic_replay','quality_processing_runs'} | TREE_FIELDS):
            fail('producer_preparation_required')
        if envelope.get('processing_storage')!='task-v1':
            fail('compatible_writer_required')
        values=self._document_values(envelope)
        # Reviewer authority remains the existing relational rows; refresh them
        # before aggregate projections inspect the new compact representation.
        if sorted(set(envelope.get('named_reviewers') or [])) != self._reviewers(con,envelope['snapshot_id']):
            con.execute('DELETE FROM workflow.document_reviewers WHERE snapshot_id=%s',(envelope['snapshot_id'],))
            for actor in sorted(set(envelope.get('named_reviewers') or [])):
                con.execute('INSERT INTO workflow.document_reviewers(snapshot_id,account_id) VALUES(%s,%s)',
                            (envelope['snapshot_id'],actor))
        topic=self._resolve_topic_locked(con,envelope['family'])
        next_metadata=metadata(envelope)
        con.execute('UPDATE workflow.document_inputs SET metadata=%s::jsonb,refs=%s::jsonb,extraction_header=%s::jsonb,notice=%s::jsonb '
            'WHERE snapshot_id=%s AND (metadata,refs,extraction_header,notice) IS DISTINCT FROM (%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb)',
            (encoded(next_metadata),encoded(refs),encoded(extraction),encoded(notice),envelope['snapshot_id'],
             encoded(next_metadata),encoded(refs),encoded(extraction),encoded(notice)))
        columns=['source_id','document_id','title','family','class','state','publication_eligibility','content_kind',
            'ingest_kind','source_version','source_date','source_sha256','source_locator','immutable_storage_locator',
            'live_url','uploader_account_id','replaces_snapshot_id','object_diff','clinical_rereview_required',
            'acquired_at','console_version']
        con.execute('UPDATE workflow.documents SET '+','.join(c+'=%s'+('::jsonb' if c=='object_diff' else '') for c in columns)
            +',topic_id=%s,revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE snapshot_id=%s',
            (*values[1:],topic['topic_id'],envelope['snapshot_id']))
        if 'processing_attempts' in envelope:
            from src.workflows.formation_task_store_v1 import FormationTaskStore
            FormationTaskStore.save_attempts(con,envelope['snapshot_id'],envelope['processing_attempts'])
        return True
