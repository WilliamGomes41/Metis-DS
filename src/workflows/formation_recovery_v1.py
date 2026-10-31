"""Exact formation state inside the existing offline workflow backup transaction.

No independent backup authority, migration, reconstruction or activation. Import
uses existing immutable root seal guards and validates the retained proof again.
"""
import json

from src.publication.publication_chain_recovery_v1 import PublicationChainRecoveryError, _json_safe

# Dependency order; these identifiers never come from the archive.
TABLES = (
    'processing_attempts', 'processing_document_summaries', 'processing_checkpoints',
    'prepared_extraction_versions', 'formation_inputs', 'formation_contexts',
    'formation_task_results', 'formation_task_findings', 'formation_task_result_history',
    'formation_task_plans', 'formation_source_views', 'source_read_roots',
    'source_read_fragments', 'source_read_blocks', 'source_read_block_fragments',
    'processing_archives', 'formation_evidence_roots', 'formation_evidence_members',
)
FACT_TABLES = ('review_fact_state', 'review_object_facts')
DOCUMENT_COLUMNS = ('snapshot_id', 'processing_storage_version', 'object_generation',
                    'review_source_ref', 'formation_evidence_id', 'review_read_envelope', 'review_card_envelope')
ROOTS = {'source_read_roots':'views_id', 'formation_evidence_roots':'proof_id'}
ORDER = {
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
    'review_fact_state':'snapshot_id', 'review_object_facts':'snapshot_id,object_id',
}


def fail(reason):
    raise PublicationChainRecoveryError('workflow_formation_backup_' + reason)


def available(con):
    return con.execute("SELECT to_regclass('workflow.formation_evidence_roots') AS name").fetchone()['name'] is not None


def validate(state):
    section = state.get('formation_recovery')
    if section is None:
        if any((d.get('envelope_payload') or {}).get('processing_storage') == 'task-v1'
               for d in (state.get('workflow_tables') or {}).get('documents', [])):
            fail('missing_reexport_required')
        return None
    if (not isinstance(section, dict) or section.get('version') != 1
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
    return {'version':1,
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
        if table in FACT_TABLES:
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
            task_store.read_formation_evidence({'layout':1,'proof_id':root['proof_id']},
                envelope=envelopes[root['snapshot_id']])
    except WorkflowDocumentStoreError as error:
        raise PublicationChainRecoveryError('workflow_formation_backup_integrity_failed') from error
