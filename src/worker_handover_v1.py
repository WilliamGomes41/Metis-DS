"""Temporary native worker ownership of the existing authorized attempt.

No new command, retry or budget authority. Locks are document then attempt,
matching TaskCheckpointWriter and activation. A lost provider response may be
retried after lease loss; committed task results are never repeated.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from threading import Event, Thread
import logging
from copy import deepcopy
from datetime import datetime, timedelta
import uuid

from src.operations_console_v1 import ConsoleError
from src import processing_retry_v1 as retry_clock
from src.processing_document_budget_v1 import leased, document_scoped, budget as document_budget, worker_expired
from src.source_selection_v1 import authorize_account, configuration
from src.workflows.formation_task_store_v1 import FormationTaskStore
from src.workflows.workflow_documents_postgres_v1 import _json_text

def now():
    return retry_clock.now()


_STOP = ContextVar('source_worker_stop', default=None)
HEARTBEAT_SECONDS = 30
LOG = logging.getLogger(__name__)


@contextmanager
def worker_execution(stop_event, *, console, sid, attempt):
    token = _STOP.set(stop_event)
    ended = Event()
    heartbeat = None
    if leased(attempt):
        def maintain():
            while not ended.wait(HEARTBEAT_SECONDS):
                try:
                    if not renew(console, sid, attempt):
                        return
                except Exception:
                    # Loss of a database connection grants no additional time.
                    # Existing protected writes still reject an expired lease.
                    LOG.warning('source_worker_lease_renewal_stopped')
                    continue
        heartbeat = Thread(target=maintain, daemon=True, name='source-worker-lease')
        heartbeat.start()
    try:
        yield
    finally:
        ended.set()
        if heartbeat is not None:
            heartbeat.join(timeout=6)
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
            before = deepcopy(active)
            yield con, document, row, active
            if active != before:
                con.execute('UPDATE workflow.processing_attempts SET payload=%s::jsonb,record_version=record_version+1 WHERE attempt_id=%s',
                    (_json_text(active), attempt_id))
                store.checkpoint_summary(con, sid, active)


def validate(console, con, document, row, active):
    # Worker leases do not grant authorization and never extend the hard limit.
    if datetime.fromisoformat(active['expires_at']) <= now():
        raise ConsoleError('source_task_budget_exhausted' if document_scoped(active) else 'processing_attempt_expired')
    document_budget(active)
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


def block(con, active, error):
    from src.formation_checkpoint_v1 import finish_task_failure
    finish_task_failure(con, active, error)
    active['dispatch'].update(state='blocked', blocked_reason=error.code,
        required_action='Nieuwe geautoriseerde start of herstel na oplossen van de blokkade.')


def native_attempt(console, sid, attempt_id=None):
    with console.workflow_document_store._connect() as con:
        row = con.execute('SELECT a.payload FROM workflow.processing_attempts a JOIN workflow.documents d USING(snapshot_id) '
            'WHERE a.snapshot_id=%s AND d.processing_storage_version=1 '
            + ('AND a.attempt_id=%s ' if attempt_id else '') + 'ORDER BY a.started_at DESC LIMIT 1',
            (sid, attempt_id) if attempt_id else (sid,)).fetchone()
    return row['payload'] if row and leased(row['payload']) else None


def discover(console, sid, attempt):
    """Return a pending v2 command, or persist an explicit real-boundary stop."""
    with locked(console, sid, attempt['attempt_id']) as (con, document, row, active):
        if active['state'] != 'running':
            return None
        try:
            validate(console, con, document, row, active)
        except ConsoleError as error:
            block(con, active, error)
            return None
        dispatch = active['dispatch']
        if dispatch['state'] == 'claimed' and (datetime.fromisoformat(dispatch['lease_expires_at']) <= now() or worker_expired(active, now())):
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
            block(con, active, error)
            denied = error
        else:
            clock = now()
            expires = datetime.fromisoformat(active['expires_at'])
            dispatch = active['dispatch']
            if document_scoped(active):
                dispatch['worker_expires_at'] = min(expires, clock+timedelta(seconds=min(active['limits']['attempt'],active['document_budget']['max_worker_seconds']))).isoformat()
                expires = datetime.fromisoformat(dispatch['worker_expires_at'])
            dispatch.update(state='claimed', token=uuid.uuid4().hex, claimed_at=clock.isoformat(),
                claim_number=dispatch.get('claim_number', 0)+1,
                worker_until=(clock+timedelta(seconds=worker_seconds)).isoformat(),
                lease_expires_at=min(expires, clock+timedelta(seconds=worker_seconds+180)).isoformat())
            from src.processing_trace_v1 import runtime_identity
            active.setdefault('diagnostic', {})['execution_runtime'] = runtime_identity()
            FormationTaskStore.checkpoint(con, attempt_id, 'worker_claimed', {
                'worker_claim': {k:dispatch[k] for k in ('claim_number','claimed_at','lease_expires_at','worker_until','worker_expires_at') if k in dispatch}})
            result = deepcopy(active)
    if denied:
        raise denied
    return result


def renew(console, sid, claimed):
    """Keep long preparation alive without renewing command authorization.

    The same token is required. Hard expiry and formation budget never move;
    process death stops this disposable timer, leaving a discoverable SQL lease.
    """
    with locked(console, sid, claimed['attempt_id']) as (con, document, row, active):
        dispatch = active.get('dispatch') or {}
        if (active['state'] != 'running' or dispatch.get('state') != 'claimed'
                or dispatch.get('token') != claimed['dispatch']['token']):
            return False
        if datetime.fromisoformat(dispatch['lease_expires_at']) <= now() or worker_expired(active, now()):
            return False  # A worker cannot revive its already lost ownership.
        try:
            validate(console, con, document, row, active)
        except ConsoleError as error:
            block(con, active, error)
            return False
        boundary = datetime.fromisoformat(active['expires_at'])
        if document_scoped(active):
            boundary = min(boundary, datetime.fromisoformat(dispatch['worker_expires_at']))
        if dispatch.get('budget_expires_at'):
            boundary = min(boundary, datetime.fromisoformat(dispatch['budget_expires_at']))
        dispatch['lease_expires_at'] = min(boundary, max(datetime.fromisoformat(dispatch['lease_expires_at']),
            now()+timedelta(seconds=180))).isoformat()
        dispatch['heartbeat_at'] = now().isoformat()
        return True


def before_task(writer):
    """Check the current owner and durable budget before each external call.

    A fixed wall-clock allowance is conservative across crashes/downtime and
    preserves the existing elapsed-time budget; switching worker never renews it.
    """
    handover = False
    with writer._locked() as (con, active):
        dispatch = active.get('dispatch') or {}
        if not leased(active):
            return None
        clock = now()
        if 'budget_expires_at' not in dispatch:
            dispatch['budget_expires_at'] = min(datetime.fromisoformat(active['expires_at']),
                clock+timedelta(seconds=active['document_budget']['window_seconds'] if document_scoped(active) else active['limits']['total'])).isoformat()
        remaining = (datetime.fromisoformat(dispatch['budget_expires_at'])-clock).total_seconds()
        if remaining <= 0:
            raise ConsoleError('source_task_budget_exhausted')
        lease_remaining = (datetime.fromisoformat(dispatch['lease_expires_at'])-clock).total_seconds()-5
        stop = _STOP.get()
        if lease_remaining <= 0 or ((datetime.fromisoformat(dispatch['worker_until']) <= clock or (stop is not None and stop.is_set())) and getattr(writer, 'committed_this_worker', False)):
            dispatch.update(state='pending', token=None, released_at=clock.isoformat(), release_reason='worker_boundary')
            writer.store.checkpoint(con, writer.attempt_id, 'worker_handover', {
                'worker_handover': {'claim_number':dispatch['claim_number'], 'released_at':dispatch['released_at'],
                    'task_plan_ref':writer.plan_reference, 'validator_input_ref':writer.input_reference}})
            handover = True
        elif writer._next_cursor is not None:
            cursor = dispatch.get('formation_cursor')
            if cursor is None or cursor['phase'] != writer._next_cursor['phase']:
                dispatch['formation_cursor'] = {'phase':writer._next_cursor['phase'], 'position':-1}
    if handover:
        raise WorkerHandover()
    return min(remaining, lease_remaining)
