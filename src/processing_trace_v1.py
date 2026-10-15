"""Bounded projections/observations over existing attempts; never workflow state."""
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone

from src.section_incident_v1 import choice, identifier, number, timestamp

VERSION = 'processing-trace-v1'
MAX_ATTEMPTS = 64
MAX_CHECKPOINTS = 128
MAX_CHECKPOINT_EVENTS = 64
PHASES = frozenset({'reserved', 'source_reconstructed', 'model_request', 'response_received',
    'model_response', 'proposal_parsed', 'proposal_gate_rejected', 'validation_rejected',
    'evidence_resolved', 'proposal_received', 'formation_accounted', 'validation_started',
    'extraction_started', 'extraction_finished', 'extraction_checkpoint', 'extraction_reused'})
_PROCESS_RUNTIME = None
EVENTS = frozenset({'processing_reserved', 'processing_command_reused', 'processing_claimed',
                   'processing_checkpoint', 'processing_finished', 'processing_delivery_stopped'})


def token(value, pattern):
    return value if isinstance(value, str) and re.fullmatch(pattern, value) else None


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest() if isinstance(value, str) else None


def sha(value):
    return token(value, r'[0-9a-f]{64}')


def attempt_id(value):
    return token(value, r'pa_[0-9a-f]{32}')


def runtime_identity():
    global _PROCESS_RUNTIME
    if _PROCESS_RUNTIME is None or _PROCESS_RUNTIME[0] != os.getpid():
        _PROCESS_RUNTIME = (os.getpid(), uuid.uuid4().hex)
    from src.attempt_diagnostics_v1 import deployment_identity
    return {'version': token(os.getenv('METIS_BUILD_COMMIT'), r'[0-9a-f]{7,64}') or deployment_identity(),
            'instance': token(os.getenv('WEBSITE_INSTANCE_ID', 'local'), r'(?:[0-9a-f-]{1,128}|local)'),
            'pid': os.getpid(), 'runtime_id':_PROCESS_RUNTIME[1]}


def clean_runtime(raw):
    raw = raw if isinstance(raw, dict) else {}
    return {'version': token(raw.get('version'), r'[0-9a-f]{7,64}'),
            'instance': token(raw.get('instance'), r'(?:[0-9a-f-]{1,128}|local)'),
            'pid': number(raw.get('pid')), 'runtime_id':identifier(raw.get('runtime_id'))}


def mapping(value):
    return value if isinstance(value, dict) else {}


def project_attempt(attempt):
    attempt = mapping(attempt)
    diagnostic = mapping(attempt.get('diagnostic'))
    dispatch = mapping(attempt.get('dispatch'))
    history = diagnostic.get('checkpoints')
    history = history if isinstance(history, list) else []
    return {
        'attempt_id': attempt_id(attempt.get('attempt_id')),
        'retry_of': attempt_id(attempt.get('retry_of')),
        'command_sha256': digest(attempt.get('command_id')),
        'source_hash': sha(attempt.get('source_hash')),
        'source_version_sha256': digest(attempt.get('source_version')),
        'expected_revision_sha256': digest(attempt.get('expected_revision')),
        'configuration_sha256': digest(json.dumps(attempt['processing_configuration'], sort_keys=True))
            if isinstance(attempt.get('processing_configuration'), dict) else None,
        'origin_request_id': identifier(diagnostic.get('origin_request_id')),
        'origin_runtime': clean_runtime(diagnostic.get('origin_runtime')),
        'execution_runtime': clean_runtime(diagnostic.get('execution_runtime')),
        'kind': choice(attempt.get('kind'), {'ingest', 'retry', 'resume', 'reextract'}),
        'stored_state': choice(attempt.get('state'), {'running', 'succeeded', 'incomplete_budget', 'failed', 'interrupted'}),
        'started_at': timestamp(attempt.get('started_at')), 'expires_at': timestamp(attempt.get('expires_at')),
        'finished_at': timestamp(attempt.get('finished_at')),
        'dispatch_state': choice(dispatch.get('state'), {'pending', 'claimed'}),
        'claimed_at': timestamp(dispatch.get('claimed_at')),
        # Error codes are kernel-bounded; never export exception/provider prose.
        'error_code': token(attempt.get('error_code'), r'[a-z][a-z0-9_]{0,95}'),
        'checkpoints': [{'phase': choice(row.get('phase'), PHASES), 'at': timestamp(row.get('at'))}
                        for row in history[-MAX_CHECKPOINTS:] if isinstance(row, dict)],
        'omitted_checkpoints': max(0, len(history)-MAX_CHECKPOINTS),
        'diagnostic_evidence_omitted': bool(diagnostic.get('omitted_evidence')),
        'extraction_checkpoint_hash': sha(mapping(diagnostic.get('extraction_checkpoint')).get('record_hash')),
        # Absent on legacy attempts: None, never backfilled or inferred.
        'stop_reason': choice(attempt.get('stop_reason'), {'done', 'budget_exhausted', 'error'}),
        'semantic_contract_version': token(attempt.get('semantic_contract_version'), r'[A-Za-z0-9._/-]{1,512}'),
    }


def processing_trace(envelope):
    """Reads stored metadata only; does not validate, reconstruct, claim or expire."""
    attempts = envelope.get('processing_attempts')
    attempts = attempts if isinstance(attempts, list) else []
    extraction = mapping(envelope.get('prepared_source_extraction'))
    replay = mapping(envelope.get('semantic_replay'))
    provider = mapping(replay.get('provider_evidence'))
    progress = mapping(provider.get('formation_progress'))
    return {'schema': VERSION,
        'snapshot_id': token(envelope.get('snapshot_id'), r'snap-[0-9a-f]{16}-[0-9a-f]{8}'),
        'source_hash': sha(envelope.get('sha256')),
        'observed_at': datetime.now(timezone.utc).isoformat(),
        'authority': 'stored_workflow_envelope', 'domain_completion': 'not_assessed',
        'attempts': [project_attempt(a) for a in attempts[-MAX_ATTEMPTS:]],
        'omitted_attempts': max(0, len(attempts)-MAX_ATTEMPTS),
        'artifacts': {'extraction_record_hash': sha(extraction.get('record_hash')),
            'extraction_fragment_count': len(extraction['fragments']) if isinstance(extraction.get('fragments'), list) else None,
            'semantic_identity_hash': sha(mapping(replay.get('identity')).get('hash')),
            'semantic_validation': choice(replay.get('validation'), {'passed'}),
            'formation_incomplete':provider.get('formation_incomplete') if type(provider.get('formation_incomplete')) is bool else None,
            'formation_progress': {key:number(progress.get(key)) for key in ('task_count', 'terminal_task_count', 'pending_task_count', 'failed_task_count')},
            'verification': 'not_revalidated_by_trace'},
        'limitations': ['diagnostic_checkpoints_do_not_authorize_resume',
            'checkpoint_payload_history_not_retained', 'formation_and_publication_not_assessed',
            'logs_are_not_commit_proof']}


def clean_trace(raw):
    """Whitelist an offline/exported projection as strictly as the live one."""
    if not isinstance(raw, dict) or raw.get('schema') != VERSION:
        raise ValueError('invalid_processing_trace')
    rows = raw.get('attempts')
    if not isinstance(rows, list):
        raise ValueError('invalid_processing_attempts')
    # Reuse the same field/shape projector, translating only hashed identities.
    attempts = []
    for row in rows[-MAX_ATTEMPTS:]:
        if not isinstance(row, dict):
            continue
        proxy = dict(attempt_id=row.get('attempt_id'), retry_of=row.get('retry_of'),
            state=row.get('stored_state'), kind=row.get('kind'), source_hash=row.get('source_hash'),
            started_at=row.get('started_at'), expires_at=row.get('expires_at'), finished_at=row.get('finished_at'),
            error_code=row.get('error_code'), stop_reason=row.get('stop_reason'),
            semantic_contract_version=row.get('semantic_contract_version'), dispatch={'state':row.get('dispatch_state'), 'claimed_at':row.get('claimed_at')},
            diagnostic={'origin_request_id':row.get('origin_request_id'), 'origin_runtime':row.get('origin_runtime'),
                'execution_runtime':row.get('execution_runtime'), 'checkpoints':row.get('checkpoints') if isinstance(row.get('checkpoints'), list) else [],
                'omitted_evidence':['omitted'] if row.get('diagnostic_evidence_omitted') is True else [],
                'extraction_checkpoint':{'record_hash':row.get('extraction_checkpoint_hash')}})
        clean = project_attempt(proxy)
        for key in ('command_sha256', 'source_version_sha256', 'expected_revision_sha256', 'configuration_sha256'):
            clean[key] = sha(row.get(key))
        clean['omitted_checkpoints'] += number(row.get('omitted_checkpoints')) or 0
        attempts.append(clean)
    artifacts = raw.get('artifacts') if isinstance(raw.get('artifacts'), dict) else {}
    return {'schema': VERSION, 'snapshot_id': token(raw.get('snapshot_id'), r'snap-[0-9a-f]{16}-[0-9a-f]{8}'),
        'source_hash': sha(raw.get('source_hash')), 'observed_at': timestamp(raw.get('observed_at')),
        'authority': 'supplied_workflow_projection_not_authenticated_by_exporter',
        'domain_completion': 'not_assessed', 'attempts': attempts,
        'omitted_attempts': max(0, len(rows)-MAX_ATTEMPTS)+(number(raw.get('omitted_attempts')) or 0),
        'artifacts': {'extraction_record_hash':sha(artifacts.get('extraction_record_hash')),
            'extraction_fragment_count':number(artifacts.get('extraction_fragment_count')),
            'semantic_identity_hash':sha(artifacts.get('semantic_identity_hash')),
            'semantic_validation':choice(artifacts.get('semantic_validation'), {'passed'}),
            'formation_incomplete':artifacts.get('formation_incomplete') if type(artifacts.get('formation_incomplete')) is bool else None,
            'formation_progress': {key:number(mapping(artifacts.get('formation_progress')).get(key)) for key in ('task_count', 'terminal_task_count', 'pending_task_count', 'failed_task_count')},
            'verification':'not_revalidated_by_trace'}}


def observe(event, snapshot_id, attempt, *, phase=None):
    """Best effort console evidence; operation return is NOT a durable commit proof."""
    try:
        from src.request_diagnostics_v1 import _LOGGER, current_request_id
        if event not in EVENTS:
            return
        if event == 'processing_checkpoint' and len((attempt.get('diagnostic') or {}).get('checkpoints') or []) > MAX_CHECKPOINT_EVENTS:
            return
        row = project_attempt(attempt)
        payload = {**runtime_identity(), 'event':event, 'timestamp':datetime.now(timezone.utc).isoformat(),
            'snapshot_id': token(snapshot_id, r'snap-[0-9a-f]{16}-[0-9a-f]{8}'),
            'request_id':row['origin_request_id'], 'observed_request_id':current_request_id(),
            'attempt_id':row['attempt_id'], 'command_sha256':row['command_sha256'],
            'source_hash':row['source_hash'], 'phase':choice(phase, PHASES),
            'observation_kind':'non_authoritative_operation_return'}
        _LOGGER.info('metis_diagnostic %s', json.dumps(payload, separators=(',', ':')))
    except Exception:
        pass


def processing_incident(raw, events=(), *, selected_attempt=None, selected_request=None):
    if selected_attempt is not None and attempt_id(selected_attempt) is None:
        raise ValueError('invalid_attempt_selector')
    if selected_request is not None and identifier(selected_request) is None:
        raise ValueError('invalid_request_selector')
    trace = clean_trace(raw)
    candidates = trace['attempts']
    if selected_attempt:
        candidates = [a for a in candidates if a['attempt_id'] == attempt_id(selected_attempt)]
    if selected_request:
        candidates = [a for a in candidates if a['origin_request_id'] == identifier(selected_request)]
    chosen = candidates[0] if len(candidates) == 1 and candidates[0]['attempt_id'] else None
    observations = []
    omitted = 0
    for event in events:
        if not isinstance(event, dict) or choice(event.get('event'), EVENTS) is None or chosen is None:
            continue
        if event.get('attempt_id') != chosen['attempt_id']:
            continue
        if event.get('command_sha256') != chosen['command_sha256'] or event.get('source_hash') != chosen['source_hash']:
            continue
        if len(observations) >= 256:
            omitted += 1
            continue
        observations.append({'event':event['event'], 'timestamp':timestamp(event.get('timestamp')),
            'request_id':identifier(event.get('request_id')), 'phase':choice(event.get('phase'), PHASES),
            'runtime':clean_runtime(event)})
    missing = []
    contradictions = []
    if trace['omitted_attempts']:
        missing.append('attempt_history_truncated')
    if chosen and any(e['request_id'] and e['request_id'] != chosen['origin_request_id'] for e in observations):
        contradictions.append('operational_origin_request_disagrees')
    if chosen and chosen['extraction_checkpoint_hash'] and chosen['extraction_checkpoint_hash'] != trace['artifacts']['extraction_record_hash']:
        missing.append('recorded_extraction_differs_from_current_or_is_missing')
    if chosen is None:
        missing.append('attempt_selection_ambiguous_or_missing')
    else:
        if chosen['origin_request_id'] is None:
            missing.append('origin_request_not_recorded')
        if not chosen['checkpoints']:
            missing.append('diagnostic_checkpoints_not_recorded')
        elif any(c['phase'] is None or c['at'] is None for c in chosen['checkpoints']):
            missing.append('checkpoint_phase_or_time_not_recognized')
        if chosen['omitted_checkpoints'] or chosen['diagnostic_evidence_omitted']:
            missing.append('diagnostic_evidence_partial')
        if chosen['stored_state'] == 'running' and chosen['expires_at']:
            if datetime.fromisoformat(chosen['expires_at']) <= datetime.now(timezone.utc):
                missing.append('attempt_deadline_elapsed_reconcile_existing_authority')
        if chosen['stored_state'] == 'running':
            missing.append('terminal_durable_result_not_recorded')
    if not observations:
        missing.append('matching_operational_events_missing')
    if omitted:
        missing.append('operational_events_truncated')
    next_check = 'Reconcile the stored command/attempt and artifact identity before any authorized retry; logs alone do not establish commit or safe resume.'
    if chosen is None:
        next_check = 'Select an exact attempt ID or original request ID; do not assume the latest attempt is the incident.'
    elif chosen['stored_state'] == 'running' and chosen['dispatch_state'] == 'pending':
        next_check = 'The stored attempt is pending. Check dispatcher availability and execution capacity; this snapshot alone does not establish why it is waiting.'
    elif chosen['stored_state'] == 'running' and chosen['dispatch_state'] == 'claimed':
        next_check = 'Inspect the recorded worker runtime and last checkpoint, then reconcile its deadline and durable result before retry.'
    return {'schema':'processing-incident-v1', 'trace':trace, 'selected_attempt_id':chosen['attempt_id'] if chosen else None,
        'observations':observations, 'omitted_operational_events':omitted, 'missing_evidence':missing,
        'contradictions':contradictions,
        'assessment':{'stored_state':chosen['stored_state'] if chosen else None, 'cause':'unknown',
            'last_recorded_checkpoint':chosen['checkpoints'][-1] if chosen and chosen['checkpoints'] else None,
            'next_check':next_check},
        'domain_completion':'not_assessed'}
