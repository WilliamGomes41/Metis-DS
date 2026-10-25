"""Temporary native worker ownership of the existing authorized attempt.

No new command, retry or budget authority. Locks are document then attempt,
matching TaskCheckpointWriter and activation. A lost provider response may be
retried after lease loss; committed task results are never repeated.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from datetime import datetime, timedelta
import uuid

from src.operations_console_v1 import ConsoleError
from src.processing_retry_v1 import now, finish
from src.source_selection_v1 import authorize_account, configuration
from src.workflows.formation_task_store_v1 import FormationTaskStore
from src.workflows.workflow_documents_postgres_v1 import _json_text

VERSION = 'source-dispatch-v2'
_STOP = ContextVar('source_worker_stop', default=None)


@contextmanager
def worker_execution(stop_event):
    token = _STOP.set(stop_event)
    try:
        yield
    finally:
        _STOP.reset(token)


class WorkerHandover(ConsoleError):
    def __init__(self):
        super().__init__('processing_worker_handover')


@contextmanager
def locked(console, sid, attempt_id):
    from src.workflows.workflow_transaction_v1 import workflow_transaction_active
    if workflow_transaction_active():
        raise ConsoleError("formation_checkpoint_requires_independent_transaction")
    store = FormationTaskStore(console.workflow_document_store)
    with store.documents._connect() as con:
        with con.transaction():
            con.execute("SET LOCAL lock_timeout='5s'")
            document = con.execute('SELECT snapshot_id,source_sha256 AS sha256,source_version AS version,'
                'object_generation,processing_storage_version FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE', (sid,)).fetchone()
            if not document or document['processing_storage_version'] != 1:
                raise ConsoleError('processing_storage_compatible_writer_required')
            row = con.execute('SELECT payload,object_generation FROM workflow.processing_attempts '
                'WHERE snapshot_id=%s AND attempt_id=%s FOR UPDATE', (sid, attempt_id)).fetchone()
            if not row:
                raise ConsoleError('processing_attempt_not_active')
            active = row['payload']
            yield con, document, row, active
            con.execute('UPDATE workflow.processing_attempts SET payload=%s::jsonb,record_version=record_version+1 WHERE attempt_id=%s',
                (_json_text(active), attempt_id))
            store.checkpoint_summary(con, sid, active)


def validate(console, con, document, row, active):
    # Worker leases do not grant authorization and never extend the hard limit.
    if datetime.fromisoformat(active['expires_at']) <= now():
        raise ConsoleError('processing_attempt_expired')
    dispatch = active['dispatch']
    if dispatch.get('budget_expires_at') and datetime.fromisoformat(dispatch['budget_expires_at']) <= now():
        raise ConsoleError('source_task_budget_exhausted')
    if (active['source_hash'] != document['sha256'] or active['source_version'] != document['version']
            or row['object_generation'] != document['object_generation']):
        raise ConsoleError('processing_command_conflict')
    if active.get('processing_configuration') != configuration(console):
        raise ConsoleError('processing_configuration_changed')
    account = con.execute('SELECT account_id,roles,retirement FROM workflow.accounts WHERE account_id=%s FOR SHARE',
        (active['actor_id'],)).fetchone()
    if not account:
        raise ConsoleError('not_authenticated')
    document['named_reviewers'] = [r['account_id'] for r in con.execute(
        'SELECT account_id FROM workflow.document_reviewers WHERE snapshot_id=%s', (document['snapshot_id'],)).fetchall()]
    authorize_account(account, document)
    if console.workflow_document_store._release_history_locked(con, document['snapshot_id']):
        raise ConsoleError('published_objects_must_not_be_rewritten')


def block(active, error):
    finish({'processing_attempts':[active]}, active['attempt_id'], state='failed', error=error)
    active['dispatch'].update(state='blocked', blocked_reason=error.code,
        required_action='Nieuwe geautoriseerde start of herstel na oplossen van de blokkade.')


def native_attempt(console, sid, attempt_id=None):
    with console.workflow_document_store._connect() as con:
        row = con.execute('SELECT a.payload FROM workflow.processing_attempts a JOIN workflow.documents d USING(snapshot_id) '
            'WHERE a.snapshot_id=%s AND d.processing_storage_version=1 '
            + ('AND a.attempt_id=%s ' if attempt_id else '') + 'ORDER BY a.started_at DESC LIMIT 1',
            (sid, attempt_id) if attempt_id else (sid,)).fetchone()
    return row['payload'] if row and (row['payload'].get('dispatch') or {}).get('version') == VERSION else None


def discover(console, sid, attempt):
    """Return a pending v2 command, or persist an explicit real-boundary stop."""
    with locked(console, sid, attempt['attempt_id']) as (con, document, row, active):
        if active['state'] != 'running':
            return None
        try:
            validate(console, con, document, row, active)
        except ConsoleError as error:
            block(active, error)
            return None
        dispatch = active['dispatch']
        if dispatch['state'] == 'claimed' and datetime.fromisoformat(dispatch['lease_expires_at']) <= now():
            dispatch.update(state='pending', token=None, released_at=now().isoformat(), release_reason='lease_expired')
        return deepcopy(active) if dispatch['state'] == 'pending' else None


def claim_native(console, sid, attempt_id, *, actor_id=None, stop_event=None, worker_seconds):
    result = None
    denied = None
    with locked(console, sid, attempt_id) as (con, document, row, active):
        if actor_id is not None and active['actor_id'] != actor_id:
            raise ConsoleError('processing_command_conflict')
        if active['state'] != 'running' or active['dispatch']['state'] != 'pending':
            return None
        if stop_event is not None and stop_event.is_set():
            return None
        try:
            validate(console, con, document, row, active)
        except ConsoleError as error:
            block(active, error)
            denied = error
        else:
            clock = now()
            expires = datetime.fromisoformat(active['expires_at'])
            dispatch = active['dispatch']
            dispatch.update(state='claimed', token=uuid.uuid4().hex, claimed_at=clock.isoformat(),
                claim_number=dispatch.get('claim_number', 0)+1,
                worker_until=(clock+timedelta(seconds=worker_seconds)).isoformat(),
                lease_expires_at=min(expires, clock+timedelta(seconds=worker_seconds+180)).isoformat())
            from src.processing_trace_v1 import runtime_identity
            active.setdefault('diagnostic', {})['execution_runtime'] = runtime_identity()
            FormationTaskStore.checkpoint(con, attempt_id, 'worker_claimed', {
                'worker_claim': {k:dispatch[k] for k in ('claim_number','claimed_at','lease_expires_at','worker_until')}})
            result = deepcopy(active)
    if denied:
        raise denied
    return result


def before_task(writer):
    """Check the current owner and durable budget before each external call.

    A fixed wall-clock allowance is conservative across crashes/downtime and
    preserves the existing elapsed-time budget; switching worker never renews it.
    """
    handover = False
    with writer._locked() as (con, active):
        dispatch = active.get('dispatch') or {}
        if dispatch.get('version') != VERSION:
            return None
        clock = now()
        if 'budget_expires_at' not in dispatch:
            dispatch['budget_expires_at'] = min(datetime.fromisoformat(active['expires_at']),
                clock+timedelta(seconds=active['limits']['total'])).isoformat()
        remaining = (datetime.fromisoformat(dispatch['budget_expires_at'])-clock).total_seconds()
        if remaining <= 0:
            raise ConsoleError('source_task_budget_exhausted')
        stop = _STOP.get()
        if (datetime.fromisoformat(dispatch['worker_until']) <= clock or (stop is not None and stop.is_set())) and getattr(writer, 'committed_this_worker', False):
            dispatch.update(state='pending', token=None, released_at=clock.isoformat(), release_reason='worker_boundary')
            writer.store.checkpoint(con, writer.attempt_id, 'worker_handover', {
                'worker_handover': {'claim_number':dispatch['claim_number'], 'released_at':dispatch['released_at'],
                    'task_plan_ref':writer.plan_reference, 'validator_input_ref':writer.input_reference}})
            handover = True
    if handover:
        raise WorkerHandover()
    return remaining
