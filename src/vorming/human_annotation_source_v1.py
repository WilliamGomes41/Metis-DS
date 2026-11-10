"""Durable source preparation over the existing attempt/claim/checkpoint kernel."""
from copy import deepcopy
from datetime import datetime
import re

from src.operations_console_v1 import ConsoleError
from src.vorming import human_annotation_v1 as annotations
from src.vorming.processing_retry_v1 import reserve as reserve_attempt, now, assert_active, finish
from src.workflows.formation_task_store_v1 import FormationTaskStore
from src.workflows.workflow_documents_postgres_v1 import _json_text

KIND = 'human_annotation_source'
MODE = 'human-annotation-source-v1'


def configuration(console, envelope):
    from src.vorming.docling_pdf_v1 import enabled
    return {'mode': MODE, 'docling': envelope['content_kind'] == 'pdf' and enabled(),
            'extractor_contract': annotations.extractor_contract(envelope['content_kind']),
            'source_identity': annotations._identity(envelope),
            'working_revision_id': envelope['working_revision_id'],
            'logical_document_id': envelope['logical_document_id'], 'class': envelope['class']}


def require_storage(con):
    ready = con.execute("SELECT EXISTS(SELECT 1 FROM pg_trigger "
        "WHERE tgrelid='workflow.processing_attempts'::regclass "
        "AND tgname='guard_annotation_source_attempt' AND tgenabled IN ('O','A')) AS ready").fetchone()['ready']
    if not ready:
        raise ConsoleError('annotation_source_storage_not_ready')


def reserve(console, *, actor_id, snapshot_id, command_id, expected_revision):
    if (not isinstance(command_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', command_id)
            or not isinstance(expected_revision, str)):
        raise ConsoleError('annotation_command_invalid')
    with console._reprocessing_transaction(snapshot_id):
        store = console.workflow_document_store
        with store._connect() as con:
            envelope = annotations._locked(console, con, actor_id, snapshot_id)
            require_storage(con)
            if envelope['class'] == 'beslisboom':
                raise ConsoleError('annotation_prose_required')
            if annotations.owns_source(console, snapshot_id):
                return None, False
            if store.objects_revision(snapshot_id) != expected_revision:
                raise ConsoleError('annotation_objects_stale')
            if (store.current_document_objects(snapshot_id) or envelope.get('semantic_replay')
                    or (envelope.get('_document_inputs') or {}).get('replay')):
                raise ConsoleError('annotation_existing_work_requires_takeover')
            envelope = deepcopy(console._processing_command_envelope(snapshot_id, command_id=command_id))
            attempts = envelope.get('processing_attempts') or []
            for prior in attempts:
                if prior['command_id'] == command_id:
                    if (prior.get('kind') != KIND or prior['actor_id'] != actor_id
                            or prior['expected_revision'] != expected_revision):
                        raise ConsoleError('processing_command_conflict')
                    return deepcopy(prior), False
            for prior in attempts:
                if prior['state'] == 'running' and datetime.fromisoformat(prior['expires_at']) > now():
                    if prior.get('kind') == KIND:
                        return deepcopy(prior), False
                    raise ConsoleError('annotation_processing_in_progress')
            FormationTaskStore.save_attempts(con, snapshot_id, attempts)
            envelope['processing_storage'] = 'task-v1'
            attempt, fresh = reserve_attempt(envelope, command_id=command_id, actor_id=actor_id,
                revision=expected_revision, clock=now(), limits=console._processing_limits(), kind=KIND)
            attempt['processing_configuration'] = configuration(console, envelope)
            attempt['dispatch'] = {'version': 'source-dispatch-v2', 'state': 'pending'}
            attempt['phase'] = 'annotation_source_pending'
            attempt['diagnostic']['phase'] = attempt['phase']
            # A previous failed/expired command may already have a complete raw checkpoint.
            for prior in reversed(attempts):
                if (prior.get('kind') == KIND
                        and prior.get('processing_configuration') == attempt['processing_configuration']
                        and (prior.get('diagnostic') or {}).get('staged_extraction_hash')):
                    attempt['diagnostic']['staged_extraction_hash'] = prior['diagnostic']['staged_extraction_hash']
                    break
            console._commit_prepared_store(envelopes={snapshot_id: envelope}, snapshot_id=snapshot_id)
            return deepcopy(attempt), fresh


def validate_configuration(console, document, active):
    envelope = console.workflow_document_store.get_envelope(document['snapshot_id'])
    if active.get('producer_contract') != MODE or active.get('processing_configuration') != configuration(console, envelope):
        raise ConsoleError('processing_configuration_changed')


def _owner(console, con, document, row, active, claimed):
    from src.vorming.worker_handover_v1 import validate
    if (active.get('kind') != KIND or active['actor_id'] != claimed['actor_id']
            or active['command_id'] != claimed['command_id']
            or active.get('processing_configuration') != claimed.get('processing_configuration')
            or (active.get('dispatch') or {}).get('token') != claimed['dispatch']['token']):
        raise ConsoleError('processing_command_conflict')
    assert_active({'processing_attempts': [active]}, active['attempt_id'], now())
    validate(console, con, document, row, active)


def checkpoint(console, snapshot_id, claimed, *, record=None, phase):
    from src.vorming.worker_handover_v1 import locked
    with locked(console, snapshot_id, claimed['attempt_id']) as (con, document, row, active):
        _owner(console, con, document, row, active, claimed)
        active['phase'] = phase
        active.setdefault('diagnostic', {})['phase'] = phase
        if record is not None:
            FormationTaskStore(console.workflow_document_store)._immutable(con, 'prepared_extraction_versions',
                'record_hash', record['record_hash'], ['snapshot_id'], [snapshot_id], record)
            active['diagnostic']['staged_extraction_hash'] = record['record_hash']
        FormationTaskStore.checkpoint(con, active['attempt_id'], phase,
            {'phase':phase, 'staged_extraction_hash':active['diagnostic'].get('staged_extraction_hash')})
    return deepcopy(active)


def finish_preparation(console, con, snapshot_id, claimed):
    con.execute("SELECT set_config('metis.document_storage_writer','v1',true)")
    document = con.execute('SELECT snapshot_id,source_sha256 AS sha256,source_version AS version,object_generation '
                           'FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE', (snapshot_id,)).fetchone()
    row = con.execute('SELECT payload,object_generation FROM workflow.processing_attempts '
                      'WHERE snapshot_id=%s AND attempt_id=%s FOR UPDATE', (snapshot_id,claimed['attempt_id'])).fetchone()
    if row is None:
        raise ConsoleError('processing_attempt_not_active')
    active = row['payload']
    _owner(console, con, document, row, active, claimed)
    finish({'processing_attempts':[active]}, active['attempt_id'], state='succeeded')
    active['phase'] = 'annotation_source_prepared'
    active.setdefault('diagnostic', {})['phase'] = active['phase']
    con.execute('UPDATE workflow.processing_attempts SET payload=%s::jsonb,record_version=record_version+1 '
                'WHERE attempt_id=%s', (_json_text(active),active['attempt_id']))
    FormationTaskStore.checkpoint_summary(con, snapshot_id, active)
    FormationTaskStore.checkpoint(con, active['attempt_id'], active['phase'], {'phase':active['phase']})


def execute(console, *, actor_id, snapshot_id, attempt, deadline):
    envelope = console._envelope(snapshot_id)
    record = None
    reference = (attempt.get('diagnostic') or {}).get('staged_extraction_hash')
    if reference:
        with console.workflow_document_store._connect() as con:
            retained = con.execute('SELECT payload FROM workflow.prepared_extraction_versions '
                'WHERE snapshot_id=%s AND record_hash=%s', (snapshot_id,reference)).fetchone()
        if retained is None or retained['payload'].get('record_hash') != reference:
            raise ConsoleError('source_extraction_integrity_failed')
        record = retained['payload']
        fragments = annotations.stored_extraction({**envelope, 'prepared_source_extraction':record})
        if fragments is None:
            raise ConsoleError('source_extraction_integrity_failed')
        annotations.semantic_source_blocks(fragments)
    else:
        checkpoint(console, snapshot_id, attempt, phase='annotation_source_extract')
        record = annotations.source_record(console, envelope, deadline=deadline)
    checkpoint(console, snapshot_id, attempt, record=record, phase='annotation_source_check')
    annotations.pin_source(console, actor_id=actor_id, snapshot_id=snapshot_id,
        expected_revision=attempt['expected_revision'], envelope=envelope, record=record, attempt=attempt)
    return {'snapshot_id': snapshot_id, 'prepared':True}


def progress(console, *, actor_id, snapshot_id):
    annotations.authorize(console, actor_id, console._envelope(snapshot_id))
    with console.workflow_document_store._connect() as con:
        row = con.execute("SELECT payload->>'state' AS state,payload->>'phase' AS phase,"
            "payload->>'error_code' AS error_code,payload->>'started_at' AS started_at, "
            "EXISTS(SELECT 1 FROM workflow.annotation_sets WHERE snapshot_id=%s) AS ready "
            "FROM workflow.processing_attempts WHERE snapshot_id=%s AND payload->>'kind'=%s "
            'ORDER BY started_at DESC,attempt_id DESC LIMIT 1', (snapshot_id,snapshot_id,KIND)).fetchone()
    if row is None:
        return None
    return {**row, 'elapsed_seconds': max(0, int((now()-datetime.fromisoformat(row['started_at'])).total_seconds()))}
