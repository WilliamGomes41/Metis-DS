"""Pinned document authorization; technical workers never replenish it.

Persistence remains the existing processing_attempt under its document row lock.
Call reservations bound exposure, including uncertain requests. No euro pricing
or exactly-once provider execution is inferred from these limits.
"""
import os
from datetime import datetime, timedelta

DISPATCH_VERSION = 'source-dispatch-v3'
LEASED_VERSIONS = frozenset({'source-dispatch-v2', DISPATCH_VERSION})
VERSION = 'document-processing-budget-v1'
WINDOW_SECONDS = 14400
MAX_OUTPUT_TOKENS = 16384
MAX_INPUT_BYTES = 2_000_000
MAX_WORKER_SECONDS = 1800
CALLS_PER_TASK = 2
ENV = 'METIS_DOCUMENT_PROCESSING_BUDGET'


def error(code):
    from src.operations_console_v1 import ConsoleError
    return ConsoleError(code)


def enabled():
    value = os.environ.get(ENV, '').strip().lower()
    if value in {'', 'off'}:
        return False
    if value != 'v1':
        raise error('processing_document_budget_configuration_invalid')
    return True


def leased(attempt):
    return (attempt.get('dispatch') or {}).get('version') in LEASED_VERSIONS


def document_scoped(attempt):
    return (attempt.get('dispatch') or {}).get('version') == DISPATCH_VERSION


def authorize(attempt):
    """Only called within a new explicit authorized reservation, never recovery."""
    attempt['dispatch']['version'] = DISPATCH_VERSION
    attempt['expires_at'] = (datetime.fromisoformat(attempt['started_at'])+timedelta(seconds=WINDOW_SECONDS)).isoformat()
    attempt['formation_progress_made'] = False
    attempt['document_budget'] = dict(version=VERSION,window_seconds=WINDOW_SECONDS,
        calls_per_task=CALLS_PER_TASK,max_output_tokens=MAX_OUTPUT_TOKENS,max_input_bytes=MAX_INPUT_BYTES,
        max_worker_seconds=MAX_WORKER_SECONDS,
        calls_reserved=0,planned_tasks=None,plan_hash=None,max_model_calls=None)
    attempt.setdefault('diagnostic', {})['document_budget_authorized'] = dict(attempt['document_budget'])


def budget(attempt):
    if not document_scoped(attempt):
        return None
    record = attempt.get('document_budget')
    constants = dict(version=VERSION,window_seconds=WINDOW_SECONDS,calls_per_task=CALLS_PER_TASK,
        max_output_tokens=MAX_OUTPUT_TOKENS,max_input_bytes=MAX_INPUT_BYTES,max_worker_seconds=MAX_WORKER_SECONDS)
    keys = set(constants) | {'calls_reserved','planned_tasks','plan_hash','max_model_calls'}
    if (not isinstance(record,dict) or set(record) != keys
            or any(type(record.get(k)) is not type(v) or record.get(k) != v for k,v in constants.items())
            or type(record.get('calls_reserved')) is not int or record['calls_reserved'] < 0
            or datetime.fromisoformat(attempt['expires_at']) != datetime.fromisoformat(attempt['started_at'])+timedelta(seconds=WINDOW_SECONDS)):
        raise error('processing_document_budget_invalid')
    if record['plan_hash'] is None:
        if record['planned_tasks'] is not None or record['max_model_calls'] is not None or record['calls_reserved']:
            raise error('processing_document_budget_invalid')
    elif (not isinstance(record['plan_hash'],str) or len(record['plan_hash']) != 64
            or type(record['planned_tasks']) is not int or record['planned_tasks'] < 0
            or type(record['max_model_calls']) is not int
            or record['max_model_calls'] != CALLS_PER_TASK*record['planned_tasks']
            or record['calls_reserved'] > record['max_model_calls']):
        raise error('processing_document_budget_invalid')
    return record


def pin_plan(attempt, reference, task_count):
    record = budget(attempt)
    if record is None:
        return
    if record['plan_hash'] is not None:
        if record['plan_hash'] != reference['plan_hash'] or record['planned_tasks'] != task_count:
            raise error('processing_document_budget_plan_conflict')
        return
    record.update(plan_hash=reference['plan_hash'],planned_tasks=task_count,
        max_model_calls=CALLS_PER_TASK*task_count)


def reserve_call(attempt):
    record = budget(attempt)
    if record is None:
        return None
    if record['plan_hash'] is None:
        raise error('processing_document_budget_plan_required')
    if record['calls_reserved'] >= record['max_model_calls']:
        raise error('processing_document_call_budget_exhausted')
    record['calls_reserved'] += 1
    return dict(record)


def worker_expired(attempt, clock):
    return (document_scoped(attempt) and (attempt.get('dispatch') or {}).get('state') == 'claimed'
        and datetime.fromisoformat(attempt['dispatch']['worker_expires_at']) <= clock)


def projection(attempt, clock):
    record = budget(attempt)
    if record is None:
        return {}
    return {'document_budget':dict(window_seconds=record['window_seconds'],expires_at=attempt['expires_at'],
        remaining_seconds=max(0,(datetime.fromisoformat(attempt['expires_at'])-clock).total_seconds()),
        calls_reserved=record['calls_reserved'],max_model_calls=record['max_model_calls'],
        calls_per_task=record['calls_per_task'],worker_limit_seconds=min(record['max_worker_seconds'],attempt['limits']['attempt']))}
