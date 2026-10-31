"""Current intrinsic Review inputs under the existing document-store owner.

No approval, closure or personal status is stored. Runtime writers seal their
validated histories in the same transaction; explicit preparation uses CAS.
"""
from collections import defaultdict
from dataclasses import dataclass

from src.integrity_kernel import stable_hash
from src.review.revision_workflow import current_revisions
from src.review.review_card_facts_v1 import (
    CONTRACT, ReviewObjectFacts, ReviewFactSources, producer_contract, source_input,
    prepare_source_proof, prepare_object_facts,
)
from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError, _json_text


@dataclass(frozen=True)
class PreparedCardSource:
    snapshot_id: str
    extraction: dict
    artifact: object
    proofs: dict


def prepare_activation(store, envelope, objects, fragments):
    """Processing preparation before its existing protected activation boundary."""
    extraction = envelope.get('prepared_source_extraction')
    if store is None or not extraction:
        return None
    with store._connect() as con:
        if not available(con):
            return None
    from src.workflows.formation_task_store_v1 import FormationTaskStore
    from src.vorming.prepared_source_views_v1 import prepare, freeze
    root = prepare(fragments)
    artifact = FormationTaskStore(store).prepare_review_source(
        {'snapshot_id': envelope['snapshot_id'], 'extraction_hash': extraction['record_hash']},
        root.payload, extraction=extraction)
    proofs = {obj['object_id']: prepare_source_proof(obj, root.fragments)
              for obj in current_revisions(objects, snapshot_id=envelope['snapshot_id'])}
    return PreparedCardSource(envelope['snapshot_id'], freeze(extraction), artifact, freeze(proofs))


def publish_preparation(store, con, sid, preparation):
    if preparation is None:
        return
    if not isinstance(preparation, PreparedCardSource) or preparation.snapshot_id != sid:
        raise WorkflowDocumentStoreError('review_card_preparation_mismatch')
    envelope = _document(con, sid, preparation=True)
    if envelope.get('prepared_source_extraction', {}).get('record_hash') != preparation.extraction['record_hash']:
        raise WorkflowDocumentStoreError('review_card_preparation_mismatch')
    from src.workflows.formation_task_store_v1 import FormationTaskStore
    task_store = FormationTaskStore(store)
    task_store._immutable(con, 'prepared_extraction_versions', 'record_hash', preparation.extraction['record_hash'],
                          ['snapshot_id'], [sid], preparation.extraction)
    reference = task_store.publish_review_source(preparation.artifact, con=con)
    from src.workflows.formation_evidence_v1 import assert_source_reference
    assert_source_reference(con, sid, reference)
    con.execute('UPDATE workflow.documents SET review_source_ref=%s::jsonb WHERE snapshot_id=%s', (_json_text(reference), sid))


def available(con):
    return con.execute("SELECT to_regclass('workflow.review_fact_state') AS name").fetchone()['name'] is not None


def _document(con, sid, *, preparation=False):
    # Full-envelope fallback is confined to explicit/writer preparation, never GET.
    fallback = """workflow.review_card_envelope_for(d.envelope_payload)
      || jsonb_build_object('snapshot_id',d.snapshot_id,'document_id',d.document_id,
        'source_id',d.source_id,'title',d.title,'class',d.class,'state',d.state,
        'date',to_char(d.source_date,'YYYY-MM-DD'),'version',d.source_version,
        'sha256',d.source_sha256,'content_kind',d.content_kind,
        'publication_eligibility',d.publication_eligibility) || jsonb_build_object(
        '_source_identity',jsonb_build_object('snapshot_id',d.snapshot_id,'source_id',d.source_id,'document_id',d.document_id,
        'sha256',d.source_sha256,'version',d.source_version,'content_kind',d.content_kind,
        'extraction',d.envelope_payload#>'{prepared_source_extraction,record_hash}',
        'extraction_header',workflow.review_card_envelope_for(d.envelope_payload)->'prepared_source_extraction',
        'source_ref',d.review_source_ref))"""
    header = f'COALESCE(d.review_card_envelope,({fallback}))' if preparation else 'd.review_card_envelope'
    row = con.execute(f'SELECT {header} AS envelope FROM workflow.documents d WHERE snapshot_id=%s', (sid,)).fetchone()
    if row is None:
        raise WorkflowDocumentStoreError('unknown_snapshot')
    return row['envelope']


def _prepare(store, con, sid, histories, envelope, previous):
    current = current_revisions(histories, snapshot_id=sid)
    reuse, needed = {}, []
    for obj in current:
        old = previous.get(obj['object_id'])
        proof = (old or {}).get('proof')
        if (proof and proof.get('producer') == producer_contract()
                and proof.get('input_hash') == stable_hash(source_input(obj))):
            reuse[obj['object_id']] = proof
        else:
            needed.append(obj)
    fragments = None
    if needed and str(envelope.get('class')) != 'beslisboom':
        from src.workflows.formation_task_store_v1 import FormationTaskStore
        # The existing source reader verifies selected membership/mapping only;
        # it neither opens the original binary nor reconstructs source on GET.
        fragments = FormationTaskStore(store).read_review_source(envelope,
            objects=[source_input(obj) for obj in needed], con=con)
        if fragments is None:
            raise WorkflowDocumentStoreError('review_card_retained_source_unprepared')
    records = {}
    for obj in current:
        proof = reuse.get(obj['object_id'])
        if proof is None:
            proof = prepare_source_proof(obj, fragments)
        records[obj['object_id']] = prepare_object_facts(obj, proof=proof)
    return records


def _previous(con, sid, source_identity, *, object_ids=None):
    state = con.execute('SELECT source_identity FROM workflow.review_fact_state WHERE snapshot_id=%s', (sid,)).fetchone()
    if state is None or state['source_identity'] != source_identity:
        return {}
    scope = ' AND object_id=ANY(%s)' if object_ids is not None else ''
    params = (sid, object_ids) if object_ids is not None else (sid,)
    rows = con.execute("SELECT object_id,record FROM workflow.review_object_facts WHERE snapshot_id=%s "
        "AND record IS NOT NULL AND record_hash=encode(sha256(convert_to(record::text,'UTF8')),'hex')" + scope, params).fetchall()
    return {row['object_id']: row['record'] for row in rows}


def _install(con, sid, records, source_identity, *, complete):
    ids = list(records)
    physical = con.execute('SELECT object_id,min(position) AS first_position,count(*) AS n,'
        'bool_and(position IS NOT NULL) AS positioned FROM workflow.document_objects '
        'WHERE snapshot_id=%s AND object_id=ANY(%s) GROUP BY object_id', (sid, ids)).fetchall() if ids else []
    positions = {row['object_id']: row for row in physical}
    if any(not row['positioned'] for row in physical) or set(positions) != set(records):
        raise WorkflowDocumentStoreError('review_card_history_unprepared')
    for oid, record in records.items():
        record = {**record, 'source_identity': source_identity}
        row = positions[oid]
        con.execute("INSERT INTO workflow.review_object_facts(snapshot_id,object_id,history_count,dirty,"
            "current_version,object_order,record,record_hash) VALUES(%s,%s,%s,false,%s,%s,%s::jsonb,"
            "encode(sha256(convert_to((%s::jsonb)::text,'UTF8')),'hex')) ON CONFLICT(snapshot_id,object_id) "
            "DO UPDATE SET history_count=EXCLUDED.history_count,dirty=false,current_version=EXCLUDED.current_version,"
            "object_order=EXCLUDED.object_order,record=EXCLUDED.record,record_hash=EXCLUDED.record_hash",
            (sid, oid, row['n'], record['fields']['object_version'], row['first_position'], _json_text(record), _json_text(record)))
    if complete:
        con.execute('UPDATE workflow.review_object_facts SET dirty=false,history_count=0,current_version=NULL,'
            'record=NULL,record_hash=NULL WHERE snapshot_id=%s AND NOT(object_id=ANY(%s))', (sid, ids))
        con.execute('INSERT INTO workflow.review_fact_state(snapshot_id,initialized,expected_heads,source_identity) '
            'VALUES(%s,true,%s,%s::jsonb) ON CONFLICT(snapshot_id) DO UPDATE '
            'SET initialized=true,expected_heads=EXCLUDED.expected_heads,source_identity=EXCLUDED.source_identity',
            (sid, len(records), _json_text(source_identity)))
    con.execute('UPDATE workflow.review_fact_state s SET prepared_epoch=input_epoch WHERE snapshot_id=%s '
        'AND initialized AND source_identity=%s::jsonb '
        'AND NOT EXISTS(SELECT 1 FROM workflow.review_object_facts f WHERE f.snapshot_id=s.snapshot_id AND dirty)',
        (sid, _json_text(source_identity)))


def maintain(store, con, sid, histories, *, complete=False, preparation=None):
    """Seal only intrinsic inputs of already validated changed histories.

    Old/unprepared schema or retained-source records remain explicitly unavailable
    until controlled preparation; they never trigger a hidden reader rebuild.
    """
    if not available(con):
        return
    envelope = _document(con, sid, preparation=True)
    identity = envelope['_source_identity']
    try:
        previous = _previous(con, sid, identity, object_ids=sorted({obj['object_id'] for obj in histories}))
        if preparation is not None:
            if (not isinstance(preparation, PreparedCardSource) or preparation.snapshot_id != sid
                    or preparation.extraction['record_hash'] != identity.get('extraction')):
                raise WorkflowDocumentStoreError('review_card_preparation_mismatch')
            previous.update({oid: {'proof': proof} for oid, proof in preparation.proofs.items()})
        records = _prepare(store, con, sid, histories, envelope, previous)
    except WorkflowDocumentStoreError as error:
        if str(error).startswith(('source_read_', 'review_card_retained_source_')):
            con.execute('UPDATE workflow.review_fact_state SET initialized=false WHERE snapshot_id=%s', (sid,))
            return
        raise
    _install(con, sid, records, identity, complete=complete)


def prepare_review_cards(store, sid):
    """Explicit preparation: read/verify outside protected writes, install with CAS."""
    with store._connect() as con:
        if not available(con):
            raise WorkflowDocumentStoreError('review_card_schema_unprepared')
        con.execute('INSERT INTO workflow.review_fact_state(snapshot_id) VALUES(%s) ON CONFLICT DO NOTHING', (sid,))
        envelope = _document(con, sid, preparation=True)
        epoch = con.execute('SELECT input_epoch FROM workflow.review_fact_state WHERE snapshot_id=%s', (sid,)).fetchone()['input_epoch']
        rows = con.execute('SELECT position,payload FROM workflow.document_objects WHERE snapshot_id=%s ORDER BY position', (sid,)).fetchall()
        if any(row['position'] is None for row in rows):
            raise WorkflowDocumentStoreError('review_card_history_unprepared')
        histories = [row['payload'] for row in rows]
        previous = _previous(con, sid, envelope['_source_identity'])
    preparation = None
    try:
        records = _prepare(store, None, sid, histories, envelope, previous)
    except WorkflowDocumentStoreError as error:
        if str(error) != 'review_card_retained_source_unprepared':
            raise
        # Explicit legacy preparation may create missing indexed views from
        # the existing verified retained extraction, never from original bytes.
        extraction_header = envelope.get('prepared_source_extraction') or {}
        if not extraction_header.get('record_hash'):
            raise
        extraction = store.review_source_extraction(sid, extraction_header['record_hash'])
        from src.vorming.source_preparation_context_v1 import stored_extraction
        raw = stored_extraction({**extraction['source'], 'prepared_source_extraction': extraction})
        preparation = prepare_activation(store, {**envelope, 'prepared_source_extraction': extraction}, histories, raw)
        records = _prepare(store, None, sid, histories, envelope,
                           {oid: {'proof': proof} for oid, proof in preparation.proofs.items()})
    with store._connect() as con:
        with con.transaction():
            con.execute('SELECT snapshot_id FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE', (sid,))
            state = con.execute('SELECT input_epoch FROM workflow.review_fact_state WHERE snapshot_id=%s FOR UPDATE', (sid,)).fetchone()
            latest = _document(con, sid, preparation=True)
            if state['input_epoch'] != epoch or latest['_source_identity'] != envelope['_source_identity']:
                raise WorkflowDocumentStoreError('review_card_preparation_conflict')
            # Existing legacy rows acquire compact envelope through its owner trigger.
            con.execute('UPDATE workflow.documents SET review_card_envelope=review_card_envelope WHERE snapshot_id=%s', (sid,))
            publish_preparation(store, con, sid, preparation)
            identity = _document(con, sid)['_source_identity']
            _install(con, sid, records, identity, complete=True)
            committed_epoch = con.execute('SELECT input_epoch FROM workflow.review_fact_state WHERE snapshot_id=%s', (sid,)).fetchone()['input_epoch']
    return {'snapshot_id': sid, 'objects': len(records), 'input_epoch': committed_epoch}


def capture_review_cards(store, con, snapshot_ids):
    """DB capture only: caller owns one consistent read transaction."""
    if not available(con):
        raise WorkflowDocumentStoreError('review_card_schema_unprepared')
    if not snapshot_ids:
        return {}
    documents = con.execute('SELECT d.snapshot_id,d.review_card_envelope AS envelope,s.input_epoch,s.prepared_epoch,'
        's.initialized,s.expected_heads,s.source_identity,'
        'ARRAY(SELECT r.account_id FROM workflow.document_reviewers r WHERE r.snapshot_id=d.snapshot_id) AS reviewers '
        'FROM workflow.documents d '
        'LEFT JOIN workflow.review_fact_state s USING(snapshot_id) WHERE d.snapshot_id=ANY(%s)', (snapshot_ids,)).fetchall()
    rows = con.execute("SELECT snapshot_id,object_id,current_version,dirty,record,"
        "record_hash=encode(sha256(convert_to(record::text,'UTF8')),'hex') AS intact "
        "FROM workflow.review_object_facts WHERE snapshot_id=ANY(%s) AND history_count>0 "
        "ORDER BY snapshot_id,object_order,object_id", (snapshot_ids,)).fetchall()
    grouped = defaultdict(list)
    for row in rows:
        grouped[row['snapshot_id']].append(row)
    out = {sid: {'unavailable': 'review_card_document_missing'} for sid in snapshot_ids}
    for doc in documents:
        sid = doc['snapshot_id']
        items = grouped[sid]
        envelope = doc['envelope']
        valid = (isinstance(envelope, dict) and doc['initialized'] and doc['prepared_epoch'] == doc['input_epoch']
                 and sorted(envelope.get('named_reviewers') or []) == sorted(doc['reviewers'])
                 and doc['source_identity'] == envelope.get('_source_identity')
                 and len(items) == doc['expected_heads']
                 and all(not row['dirty'] and row['intact'] and isinstance(row['record'], dict)
                         and isinstance(row['record'].get('fields'), dict)
                         and row['record'].get('source_identity') == doc['source_identity']
                         and row['record']['fields'].get('object_id') == row['object_id']
                         and row['record']['fields'].get('object_version') == row['current_version']
                         and row['record']['fields'].get('document_id') == envelope.get('document_id')
                         and isinstance(row['record']['fields'].get('source'), dict)
                         and (row['record']['fields'].get('source') or {}).get('source_id') == envelope.get('source_id')
                         and (row['record']['fields'].get('source') or {}).get('source_checksum') == envelope.get('sha256')
                         and (row['record']['fields'].get('source') or {}).get('version') == envelope.get('version')
                         for row in items))
        if not valid:
            out[sid] = {'unavailable': 'review_card_inputs_unprepared', 'envelope': envelope, 'reviewers': doc['reviewers']}
            continue
        try:
            objects = [ReviewObjectFacts(row['record']) for row in items]
        except (KeyError, TypeError, ValueError):
            out[sid] = {'unavailable': 'review_card_inputs_invalid', 'envelope': envelope, 'reviewers': doc['reviewers']}
            continue
        out[sid] = {'envelope': envelope, 'objects': objects, 'sources': ReviewFactSources(tuple(objects)),
                    'reviewers': doc['reviewers']}
    return out
