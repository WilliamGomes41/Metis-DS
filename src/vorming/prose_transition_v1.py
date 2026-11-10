"""Explicit per-WorkingRevision retirement of prose execution; never a takeover."""
from copy import deepcopy
import re

from src.integrity_kernel import stable_hash
from src.operations_console_v1 import ConsoleError
from src.vorming.source_selection_v1 import authorize

KEY = 'prose_transitions'
VERSION = 'prose-transition-v1'
STOPPED = 'processing_prose_transition_required'
TRIGGERS = ('guard_prose_transition_document', 'guard_prose_transition_inputs',
            'guard_prose_transition_attempt')


def current(envelope):
    records = envelope.get(KEY, [])
    if not isinstance(records, list):
        raise ConsoleError('prose_transition_corrupt')
    for record in reversed(records):
        if not isinstance(record, dict):
            raise ConsoleError('prose_transition_corrupt')
        if record.get('working_revision_id') == envelope.get('working_revision_id'):
            if (record.get('version') != VERSION or record.get('snapshot_id') != envelope.get('snapshot_id')
                    or record.get('source_hash') != envelope.get('sha256')
                    or record.get('source_version') != envelope.get('version')):
                raise ConsoleError('prose_transition_corrupt')
            return record
    return None


def assert_execution(envelope, *, kind=None):
    if kind not in {'human_annotation_build', 'human_annotation_source'} and current(envelope) is not None:
        raise ConsoleError(STOPPED)


def require_storage(con):
    rows = con.execute("SELECT tgname,tgrelid::regclass::text AS relation FROM pg_trigger "
                       "WHERE tgname=ANY(%s) AND tgenabled IN ('O','A')", (list(TRIGGERS),)).fetchall()
    if {(r['tgname'], r['relation']) for r in rows} != {
            (TRIGGERS[0], 'workflow.documents'), (TRIGGERS[1], 'workflow.document_inputs'),
            (TRIGGERS[2], 'workflow.processing_attempts')}:
        raise ConsoleError('prose_transition_storage_not_ready')


def inventory(console, *, actor_id, snapshot_id):
    envelope = console._processing_command_envelope(snapshot_id)
    authorize(console, actor_id, envelope)
    objects = console._read_current_objects(snapshot_id)
    return {'snapshot_id': snapshot_id, 'working_revision_id': envelope['working_revision_id'],
        'source_hash': envelope['sha256'], 'source_version': envelope['version'],
        'objects_revision': console.objects_revision(snapshot_id), 'object_count': len(objects),
        'published': console.snapshot_is_published(snapshot_id),
        'transition': deepcopy(current(envelope)),
        'attempts': [{k: deepcopy(a.get(k)) for k in ('attempt_id', 'kind', 'state', 'dispatch', 'error_code')}
                     for a in envelope.get('processing_attempts') or []]}


def stop(console, *, actor_id, snapshot_id, attempt_id, command_id, expected_revision, reason):
    if (not isinstance(command_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', command_id)
            or not isinstance(reason, str) or not reason.strip() or len(reason) > 1000
            or any(not isinstance(value, str) or not value or len(value) > 256
                   for value in (snapshot_id, expected_revision, attempt_id))):
        raise ConsoleError('prose_transition_command_invalid')
    with console._reprocessing_transaction(snapshot_id):
        envelope = deepcopy(console._processing_command_envelope(snapshot_id, attempt_id=attempt_id))
        authorize(console, actor_id, envelope)
        console._require_mutable_working_revision(snapshot_id, current=True)
        if envelope['class'] == 'beslisboom':
            raise ConsoleError('prose_transition_prose_required')
        request_hash = stable_hash({'actor_id': actor_id, 'snapshot_id': snapshot_id,
            'working_revision_id': envelope['working_revision_id'], 'source_hash': envelope['sha256'],
            'source_version': envelope['version'], 'attempt_id': attempt_id,
            'expected_revision': expected_revision, 'reason': reason.strip()})
        previous = current(envelope)
        if previous is not None:
            if previous['command_id'] != command_id or previous['request_hash'] != request_hash:
                raise ConsoleError('prose_transition_command_conflict')
            return deepcopy(previous)
        if console.objects_revision(snapshot_id) != expected_revision:
            raise ConsoleError('prose_transition_revision_stale')
        attempts = envelope.get('processing_attempts') or []
        if not attempts or attempts[-1]['attempt_id'] != attempt_id:
            raise ConsoleError('prose_transition_attempt_stale')
        if attempts[-1].get('kind') == 'human_annotation_build':
            raise ConsoleError('prose_transition_prose_required')
        if attempts[-1]['state'] == 'succeeded':
            raise ConsoleError('prose_transition_no_open_attempt')
        from src.vorming.processing_retry_v1 import finish, now
        record = {'version': VERSION, 'command_id': command_id, 'request_hash': request_hash,
            'snapshot_id': snapshot_id, 'working_revision_id': envelope['working_revision_id'],
            'source_hash': envelope['sha256'], 'source_version': envelope['version'],
            'actor_id': actor_id, 'attempt_id': attempt_id, 'reason': reason.strip(),
            'objects_revision': expected_revision, 'recorded_at': now().isoformat(),
            'external_cancellation': 'not_guaranteed', 'stopped_attempt_ids': []}
        for attempt in attempts:
            if attempt['state'] == 'running':
                if attempt.get('kind') == 'human_annotation_build':
                    raise ConsoleError('prose_transition_prose_required')
                finish(envelope, attempt['attempt_id'], state='failed', error=ConsoleError(STOPPED))
                if attempt.get('dispatch'):
                    attempt['dispatch'].update(state='blocked', token=None, blocked_reason=STOPPED)
                record['stopped_attempt_ids'].append(attempt['attempt_id'])
        envelope.setdefault(KEY, []).append(record)
        # Save native attempt stops before the metadata fence in the same
        # existing transaction. Legacy inline attempts are one document write.
        with console.workflow_document_store._connect() as con:
            require_storage(con)
            if envelope.get('processing_storage') == 'task-v1':
                con.execute("SELECT set_config('metis.document_storage_writer','v1',true)")
                from src.workflows.formation_task_store_v1 import FormationTaskStore
                FormationTaskStore.save_attempts(con, snapshot_id, attempts)
            console._commit_prepared_store(envelopes={snapshot_id: envelope}, snapshot_id=snapshot_id)
        return deepcopy(record)
