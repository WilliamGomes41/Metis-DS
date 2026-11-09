"""Exact formation state inside the existing offline workflow backup transaction.

No independent backup authority, migration, reconstruction or activation. Import
uses existing immutable root seal guards and validates the retained proof again.
"""
import json
from copy import deepcopy

from src.publication.publication_chain_recovery_v1 import PublicationChainRecoveryError, _json_safe

# Dependency order; these identifiers never come from the archive.
TABLES = (
    'prepared_extraction_versions', 'annotation_sets','annotation_versions','annotation_heads','annotation_commands',
    'annotation_seals','annotation_build_commands',
    'processing_attempts', 'processing_document_summaries', 'processing_checkpoints', 'formation_inputs', 'formation_contexts',
    'formation_task_results', 'formation_task_findings', 'formation_task_result_history',
    'formation_task_plans', 'formation_source_views', 'source_read_roots',
    'source_read_fragments', 'source_read_blocks', 'source_read_block_fragments',
    'processing_archives', 'formation_evidence_roots', 'formation_evidence_members',
    'processing_archive_inputs','processing_archive_input_members','document_inputs','document_processing_records',
)
FACT_TABLES = ('review_fact_state', 'review_object_facts')
DOCUMENT_COLUMNS = ('snapshot_id', 'processing_storage_version', 'object_generation',
                    'review_source_ref', 'formation_evidence_id', 'review_read_envelope', 'review_card_envelope','document_storage_version')
ROOTS = {'source_read_roots':'views_id', 'formation_evidence_roots':'proof_id','processing_archive_inputs':'archive_id'}
OPERATIONAL_TABLES=('document_processing_records','document_inputs')
NEW_TABLES=('processing_archive_inputs','processing_archive_input_members',*OPERATIONAL_TABLES)
ANNOTATION_TABLES=('annotation_sets','annotation_versions','annotation_heads','annotation_commands')
BUILD_TABLES=('annotation_seals','annotation_build_commands')
ORDER = {
    'annotation_seals':'seal_id', 'annotation_build_commands':'snapshot_id,command_id',
    'processing_attempts':'attempt_id', 'processing_document_summaries':'snapshot_id',
    'processing_checkpoints':'checkpoint_id', 'prepared_extraction_versions':'record_hash',
    'formation_inputs':'artifact_id', 'formation_contexts':'context_id',
    'formation_task_results':'context_id,ranges_hash',
    'formation_task_findings':'context_id,ranges_hash,result_hash',
    'formation_task_result_history':'context_id,ranges_hash,result_hash',
    'formation_task_plans':'context_id', 'formation_source_views':'views_id',
    'source_read_roots':'views_id', 'source_read_fragments':'views_id,fragment_id',
    'source_read_blocks':'views_id,view_name,block_id',
    'source_read_block_fragments':'views_id,view_name,block_id,fragment_id',
    'processing_archives':'archive_id', 'formation_evidence_roots':'proof_id',
    'formation_evidence_members':'proof_id,role,member_key',
    'processing_archive_inputs':'archive_id','processing_archive_input_members':'archive_id,role,member_key',
    'document_inputs':'snapshot_id','document_processing_records':'snapshot_id,kind,ordinal',
    'review_fact_state':'snapshot_id', 'review_object_facts':'snapshot_id,object_id',
    'annotation_sets':'snapshot_id', 'annotation_versions':'snapshot_id,annotation_id,revision',
    'annotation_heads':'snapshot_id,position,annotation_id', 'annotation_commands':'snapshot_id,command_id',
}


def fail(reason):
    raise PublicationChainRecoveryError('workflow_formation_backup_' + reason)


def available(con):
    return con.execute("SELECT to_regclass('workflow.formation_evidence_roots') AS name").fetchone()['name'] is not None


def upgrade_legacy(state):
    """Add only absent storage capabilities to an original v8 backup.

    No proof, task, source input or lifecycle decision is reconstructed.
    The disposable attempt index is rebuilt by its normal row trigger.
    """
    result=deepcopy(state)
    result.setdefault('formation_recovery',None)
    section=result.get('formation_recovery')
    if section is not None and section.get('version')==1:
        if set(section.get('tables') or {}) != set(TABLES+FACT_TABLES)-set(NEW_TABLES)-set(ANNOTATION_TABLES)-set(BUILD_TABLES):
            fail('shape_invalid')
        section['version']=2
        for table in NEW_TABLES:
            section['tables'][table]=[]
        for document in section['documents']:
            document['document_storage_version']=0
    if section is not None and section.get('version')==2:
        if set(section.get('tables') or {}) != set(TABLES+FACT_TABLES)-set(ANNOTATION_TABLES)-set(BUILD_TABLES):
            fail('shape_invalid')
        section['version']=3
        for table in ANNOTATION_TABLES:
            section['tables'][table]=[]
    if section is not None and section.get('version')==3:
        if set(section.get('tables') or {}) != set(TABLES+FACT_TABLES)-set(BUILD_TABLES):
            fail('shape_invalid')
        section['version']=4
        for table in BUILD_TABLES:
            section['tables'][table]=[]
        for row in section['tables']['annotation_sets']:
            row['current_seal_id']=None
        for row in section['tables']['formation_evidence_roots']:
            row['annotation_seal_id']=None
    if section is not None and section.get('version')==4:
        # Only the reader capability changes. No fabricated correction basis,
        # annotation-to-object binding, receipt or review decision is added.
        section['version']=5
    return result


def validate(state):
    section = state.get('formation_recovery')
    if section is None:
        if any((d.get('envelope_payload') or {}).get('processing_storage') == 'task-v1'
               for d in (state.get('workflow_tables') or {}).get('documents', [])):
            fail('missing_reexport_required')
        return None
    if (not isinstance(section, dict) or section.get('version') != 5
            or set(section.get('tables') or {}) != set(TABLES + FACT_TABLES)
            or not isinstance(section.get('documents'), list)):
        fail('shape_invalid')
    documents = {d['snapshot_id'] for d in state['workflow_tables']['documents']}
    if (len(section['documents']) != len(documents)
            or any(not isinstance(d, dict) or set(d) != set(DOCUMENT_COLUMNS) for d in section['documents'])
            or {d['snapshot_id'] for d in section['documents']} != documents):
        fail('documents_invalid')
    for table in TABLES + FACT_TABLES:
        rows = section['tables'][table]
        if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
            fail('table_invalid:' + table)
    return section


def export(con):
    if not available(con):
        return None
    return {'version':5,
            'documents':[_json_safe(dict(r)) for r in con.execute(
                'SELECT '+','.join(DOCUMENT_COLUMNS)+' FROM workflow.documents ORDER BY snapshot_id').fetchall()],
            'tables':{table:[_json_safe(dict(r)) for r in con.execute(
                f'SELECT * FROM workflow.{table} ORDER BY {ORDER[table]}').fetchall()] for table in TABLES + FACT_TABLES}}


def assert_empty(con):
    if not available(con):
        return
    for table in TABLES + FACT_TABLES:
        if con.execute(f'SELECT 1 FROM workflow.{table} LIMIT 1').fetchone():
            fail('target_not_empty:' + table)


def _validate_annotations(con):
    """Reject partial imports, including history that is not the current head.

    Runs inside the existing offline restore transaction with exclusive locks.
    Command hashes are checked against their original immutable entry version;
    no author, generation or idempotent outcome is manufactured during restore.
    """
    from uuid import UUID
    from src.integrity_kernel import stable_hash
    from src.vorming.human_annotation_v1 import NORMALIZATION, validate_stored_selection, _relationship_history, require_input_storage
    from src.vorming.source_preparation_context_v1 import stored_extraction
    for source in con.execute('SELECT s.*,e.payload AS extraction,d.source_id,d.document_id,'
        'd.source_sha256,d.source_version,d.content_kind,d.working_revision_id AS current_working_revision '
        'FROM workflow.annotation_sets s JOIN workflow.documents d USING(snapshot_id) '
        'JOIN workflow.prepared_extraction_versions e ON e.record_hash=s.extraction_hash').fetchall():
        sid = source['snapshot_id']
        identity = {key:source[column] for key,column in (
            ('snapshot_id','snapshot_id'),('source_id','source_id'),('document_id','document_id'),
            ('sha256','source_sha256'),('version','source_version'),('content_kind','content_kind'))}
        if (identity != source['source_identity'] or source['working_revision_id'] != source['current_working_revision']
                or source['normalization'] != NORMALIZATION or source['extraction_hash'] != source['extraction']['record_hash']):
            fail('annotation_source_mismatch')
        fragments = stored_extraction({**identity,'prepared_source_extraction':source['extraction']})
        if fragments is None:
            fail('annotation_source_mismatch')
        versions = con.execute('SELECT * FROM workflow.annotation_versions WHERE snapshot_id=%s '
                              'ORDER BY annotation_id,revision',(sid,)).fetchall()
        if any(row['payload'].get('selection_version') for row in versions):
            require_input_storage(con)
        heads = con.execute('SELECT * FROM workflow.annotation_heads WHERE snapshot_id=%s',(sid,)).fetchall()
        commands = con.execute('SELECT * FROM workflow.annotation_commands WHERE snapshot_id=%s',(sid,)).fetchall()
        if len(versions) != source['generation'] or len(commands) < source['generation']:
            fail('annotation_history_incomplete')
        latest, history = {}, {}
        for row in versions:
            key = row['annotation_id']
            if (str(UUID(key)) != key or row['revision'] != latest.get(key,0)+1
                    or row['status'] != row['payload']['status'] or stable_hash(row['payload']) != row['payload_hash']):
                fail('annotation_history_invalid')
            validate_stored_selection(row['payload'],fragments=fragments,annotation_id=row['annotation_id'])
            previous = history.get((key,row['revision']-1))
            if previous and previous['payload'].get('selection_version') and not row['payload'].get('selection_version'):
                fail('annotation_client_contract_stale')
            if row['payload'].get('selection_version'):
                _relationship_history(previous['payload'] if previous else None,deepcopy(row['payload']),key)
            latest[key] = row['revision']
            history[key,row['revision']] = row
        if len(heads) != len(latest) or {h['annotation_id']:h['revision'] for h in heads} != latest:
            fail('annotation_heads_invalid')
        generations, seen, first = set(), set(), {}
        for row in commands:
            result = row['result']
            required = {'annotation_id','revision','generation','status'}
            if not required <= set(result) or set(result) - required - {'input_precondition','objects_revision','unchanged'}:
                fail('annotation_command_invalid')
            key, revision, generation = result['annotation_id'],result['revision'],result['generation']
            if type(revision) is not int or type(generation) is not int:
                fail('annotation_command_invalid')
            version = history.get((key,revision))
            unchanged = result.get('unchanged', False)
            if type(unchanged) is not bool or (unchanged and 'input_precondition' not in result):
                fail('annotation_command_invalid')
            if (version is None or (not unchanged and row['actor_id'] != version['author_id']) or result['status'] != version['status']
                    or (not unchanged and (generation in generations or (key,revision) in seen))):
                fail('annotation_command_invalid')
            precondition = result.get('input_precondition')
            expected_revision = revision if unchanged else revision-1
            expected_generation = generation if unchanged else generation-1
            if precondition is not None and (not isinstance(precondition, dict)
                    or set(precondition) != {'entry_revision','generation','objects_revision'}
                    or precondition['entry_revision'] != expected_revision
                    or precondition['generation'] != expected_generation
                    or not isinstance(precondition['objects_revision'], str)):
                fail('annotation_command_invalid')
            expected = stable_hash({'actor_id':row['actor_id'],'annotation_id':key,'expected_revision':revision-1,
                'expected_generation':generation-1,'extraction_hash':source['extraction_hash'],
                'normalization':source['normalization'],'selection':version['payload']})
            if precondition is not None:
                expected = stable_hash({'request':stable_hash({'actor_id':row['actor_id'],'annotation_id':key,
                    'expected_revision':expected_revision,'expected_generation':expected_generation,
                    'extraction_hash':source['extraction_hash'],'normalization':source['normalization'],
                    'selection':version['payload']}), 'objects_revision':precondition['objects_revision']})
            if row['request_hash'] != expected:
                fail('annotation_command_invalid')
            if unchanged:
                continue
            generations.add(generation)
            seen.add((key,revision))
            first[key] = min(first.get(key,generation),generation)
        if generations != set(range(1,source['generation']+1)) or any(h['position'] != first[h['annotation_id']] for h in heads):
            fail('annotation_history_invalid')

        from src.vorming.human_annotation_preview_v1 import inspect_document
        from src.workflows.processing_archives_v1 import encoded
        seals=con.execute('SELECT * FROM workflow.annotation_seals WHERE snapshot_id=%s', (sid,)).fetchall()
        if seals:
            from src.vorming.human_annotation_build_v1 import require_storage
            require_storage(con)
        for seal in seals:
            body=seal['payload']
            if (stable_hash(body)!=seal['seal_id'] or encoded(body)!=seal['payload_text']
                    or stable_hash({k:v for k,v in body.items() if k!='overview_hash'})!=seal['overview_hash']):
                fail('annotation_seal_invalid')
            entries=[]
            for ref in body['entries']:
                entry=history.get((ref['annotation_id'],ref['revision']))
                if not entry or entry['payload_hash']!=ref['payload_hash']:
                    fail('annotation_seal_invalid')
                entries.append(entry)
            if inspect_document(entries,fragments=fragments)['findings']:
                fail('annotation_seal_incomplete')
            if source['current_seal_id']==seal['seal_id'] and seal['generation']!=source['generation']:
                fail('annotation_seal_stale')
        for command in con.execute('SELECT c.*,s.payload AS seal FROM workflow.annotation_build_commands c '
                'JOIN workflow.annotation_seals s USING(seal_id) WHERE c.snapshot_id=%s',(sid,)).fetchall():
            body=command['seal']
            expected=stable_hash({'actor_id':command['actor_id'],'overview_hash':body['overview_hash'],
                'generation':body['generation'],'objects_revision':body['objects_revision']})
            if command['request_hash']!=expected:
                fail('annotation_build_command_invalid')


def restore(con, state, store):
    section = validate(state)
    if section is None:
        return
    if not available(con):
        fail('schema_required')
    for table in TABLES + FACT_TABLES:
        # Reject unknown/missing columns; jsonb_populate_record performs native
        # casts for arrays, timestamps and JSON. No archive-provided SQL names.
        columns = {r['column_name'] for r in con.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_schema='workflow' AND table_name=%s",
            (table,)).fetchall()}
        rows = section['tables'][table]
        if any(set(row) != columns for row in rows):
            fail('columns_invalid:' + table)
        if table in FACT_TABLES or table in OPERATIONAL_TABLES:
            # Existing document/object triggers create disposable dirty facts.
            # Restore exact committed facts after all document pin updates below.
            continue
        for row in rows:
            value = {**row, 'sealed':False} if table in ROOTS else row
            con.execute(f'INSERT INTO workflow.{table} OVERRIDING SYSTEM VALUE '
                        f'SELECT * FROM jsonb_populate_record(NULL::workflow.{table},%s::jsonb)',
                        (json.dumps(value, ensure_ascii=False),))
    for table, key in ROOTS.items():
        for root in section['tables'][table]:
            if not root['sealed']:
                fail('unsealed_root')
            con.execute(f'UPDATE workflow.{table} SET sealed=true WHERE {key}=%s', (root[key],))
    for table in OPERATIONAL_TABLES:
        for row in section['tables'][table]:
            con.execute(f'INSERT INTO workflow.{table} SELECT * FROM jsonb_populate_record(NULL::workflow.{table},%s::jsonb)',
                        (json.dumps(row,ensure_ascii=False),))
    for document in section['documents']:
        # Generation was advanced by the ordinary object insertion triggers.
        # Restore the captured allocator/pins, never derive a fresh identity.
        assignments = [c+'=%s'+('::jsonb' if c in {'review_source_ref','review_read_envelope','review_card_envelope'} else '')
                       for c in DOCUMENT_COLUMNS[1:]]
        values = [json.dumps(document[c]) if c in {'review_source_ref','review_read_envelope','review_card_envelope'}
                  and document[c] is not None else document[c] for c in DOCUMENT_COLUMNS[1:]]
        con.execute('UPDATE workflow.documents SET '+','.join(assignments)+' WHERE snapshot_id=%s',
                    (*values, document['snapshot_id']))
    for table in reversed(FACT_TABLES):
        con.execute(f'DELETE FROM workflow.{table}')
    for table in FACT_TABLES:
        for row in section['tables'][table]:
            con.execute(f'INSERT INTO workflow.{table} SELECT * FROM jsonb_populate_record(NULL::workflow.{table},%s::jsonb)',
                        (json.dumps(row, ensure_ascii=False),))
    checkpoint = con.execute('SELECT max(checkpoint_id) AS n FROM workflow.processing_checkpoints').fetchone()['n']
    if checkpoint is not None:
        con.execute("SELECT setval(pg_get_serial_sequence('workflow.processing_checkpoints','checkpoint_id'),%s,true)", (checkpoint,))
    # Integrity is checked using the existing owner/read contract, not counts or
    # trusting a recomputed archive checksum as an authorization oracle.
    from src.workflows.formation_task_store_v1 import FormationTaskStore
    from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
    from contextlib import nullcontext
    from types import SimpleNamespace
    task_store = FormationTaskStore(SimpleNamespace(config=store.config, _connect=lambda:nullcontext(con)))
    envelopes = {r['snapshot_id']:r['envelope_payload'] for r in state['workflow_tables']['documents']}
    try:
        for root in section['tables']['formation_evidence_roots']:
            task_store.read_formation_evidence({'layout':root['header']['layout'],'proof_id':root['proof_id']},
                envelope=envelopes[root['snapshot_id']])
        _validate_annotations(con)
    except WorkflowDocumentStoreError as error:
        raise PublicationChainRecoveryError('workflow_formation_backup_integrity_failed') from error
    except (ValueError, KeyError, TypeError, IndexError) as error:
        raise PublicationChainRecoveryError('workflow_formation_backup_annotation_integrity_failed') from error
