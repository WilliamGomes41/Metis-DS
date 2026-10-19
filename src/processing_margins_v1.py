"""Read-only timing evidence over processing_trace's bounded, whitelisted rows.

No queue discovery, logs, workflow mutations, retry policy or forecasts. Stored
state is retained verbatim; elapsed deadlines do not expire an attempt here.
"""
from collections import Counter
from datetime import datetime
from statistics import median

TERMINAL = frozenset({'succeeded', 'failed', 'interrupted', 'incomplete_budget'})
MIN_REFERENCE = 3


def _time(value):
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return result if result.tzinfo is not None else None
    except ValueError:
        return None


def _seconds(later, earlier):
    return round((later - earlier).total_seconds(), 3) if later is not None and earlier is not None else None


def _measure(attempt, observed):
    state = attempt['stored_state']
    start, claim, finish, deadline = [_time(attempt.get(k)) for k in
                                     ('started_at', 'claimed_at', 'finished_at', 'expires_at')]
    issues = []
    row = {k: attempt.get(k) for k in ('attempt_id', 'stored_state', 'dispatch_state', 'kind', 'retry_of')}
    row.update(age_seconds=None, queue_wait_seconds=None, execution_seconds=None,
               attempt_duration_seconds=None, deadline_remaining_seconds=None,
               budget_at_claim_seconds=None, checkpoint_age_seconds=None,
               last_checkpoint_phase=None, retry_gap_seconds=None, reference=None,
               signals=[], evidence_issues=issues)
    if start is None or observed is None:
        issues.append('start_or_observation_time_missing')
        return row
    if state not in TERMINAL | {'running'}:
        issues.append('state_not_recorded')
        return row
    if (start > observed or (claim is not None and not start <= claim <= observed)
            or (finish is not None and not start <= finish <= observed)
            or (claim is not None and finish is not None and claim > finish)
            or (deadline is not None and deadline <= start)
            or (deadline is not None and claim is not None and claim >= deadline)
            or (state == 'running' and finish is not None)):
        issues.append('timing_contradiction')
        return row
    end = observed if state == 'running' else finish
    if end is None:
        issues.append('finish_time_missing')
    row['age_seconds'] = _seconds(end, start)
    row['attempt_duration_seconds'] = _seconds(finish, start)
    dispatch = attempt.get('dispatch_state')
    if dispatch == 'pending' and claim is None and state == 'running':
        row['queue_wait_seconds'] = _seconds(observed, start)
    elif dispatch == 'claimed' and claim is not None:
        row['queue_wait_seconds'] = _seconds(claim, start)
        row['execution_seconds'] = _seconds(end, claim)
        row['budget_at_claim_seconds'] = _seconds(deadline, claim)
    else:
        issues.append('claim_evidence_missing_or_inconsistent')
    if state == 'running':
        row['deadline_remaining_seconds'] = _seconds(deadline, observed)
        if deadline is None:
            issues.append('deadline_not_recorded')
        elif deadline <= observed:
            row['signals'].append('stored_deadline_elapsed')
    checkpoints = attempt.get('checkpoints') or []
    checkpoint_times = [_time(c.get('at')) for c in checkpoints]
    if not checkpoints:
        issues.append('checkpoint_not_recorded')
    elif (any(t is None or not start <= t <= (end or observed) for t in checkpoint_times)
          or any(not c.get('phase') for c in checkpoints)):
        issues.append('checkpoint_evidence_invalid')
    else:
        latest = max(zip(checkpoint_times, checkpoints), key=lambda item: item[0])
        row['checkpoint_age_seconds'] = _seconds(end, latest[0])
        row['last_checkpoint_phase'] = latest[1]['phase']
    if attempt.get('omitted_checkpoints') or attempt.get('diagnostic_evidence_omitted'):
        issues.append('checkpoint_evidence_partial')
    return row


def _cohort(attempt):
    key = (attempt.get('source_hash'), attempt.get('configuration_sha256'),
           (attempt.get('execution_runtime') or {}).get('version'), attempt.get('kind'))
    return key if all(key) else None


def processing_margins(trace):
    """Consume only project_attempt output, using the trace's observation time.

    Durations describe retained attempts of one document. Neither these counts
    nor retry links establish remaining retry rights or fleet capacity.
    """
    attempts = trace['attempts']
    observed = _time(trace.get('observed_at'))
    rows = [_measure(a, observed) for a in attempts]
    counts = Counter(a['attempt_id'] for a in attempts if a['attempt_id'])
    indexed = {a['attempt_id']: (a, row) for a, row in zip(attempts, rows)
               if a['attempt_id'] and counts[a['attempt_id']] == 1}
    for attempt, row in zip(attempts, rows):
        aid = attempt.get('attempt_id')
        if not aid or counts[aid] != 1:
            row['evidence_issues'].append('attempt_identity_missing_or_ambiguous')
        parent_id = attempt.get('retry_of')
        if parent_id:
            parent = indexed.get(parent_id)
            if parent is None or not aid or counts[aid] != 1 or parent_id == aid:
                row['evidence_issues'].append('retry_parent_missing_or_ambiguous')
            else:
                previous, previous_row = parent
                before, after = _time(previous.get('finished_at')), _time(attempt.get('started_at'))
                if (previous['stored_state'] in TERMINAL and before is not None
                        and after is not None and before <= after
                        and previous_row['attempt_duration_seconds'] is not None
                        and row['age_seconds'] is not None):
                    row['retry_gap_seconds'] = _seconds(after, before)
                else:
                    row['evidence_issues'].append('retry_timing_not_established')
    for attempt, row in zip(attempts, rows):
        aid = attempt.get('attempt_id')
        if attempt['stored_state'] != 'running' or row['execution_seconds'] is None:
            continue
        cohort = _cohort(attempt)
        claim = _time(attempt.get('claimed_at'))
        reference = []
        if (cohort is not None and not trace.get('omitted_attempts')
                and aid and counts[aid] == 1 and not row['evidence_issues']):
            for peer, measurement in zip(attempts, rows):
                finished = _time(peer.get('finished_at'))
                if (peer['stored_state'] == 'succeeded' and _cohort(peer) == cohort
                        and peer.get('attempt_id') != aid and counts[peer.get('attempt_id')] == 1
                        and finished is not None and finished <= claim
                        and measurement['execution_seconds'] is not None
                        and not measurement['evidence_issues']):
                    reference.append(measurement['execution_seconds'])
        if len(reference) >= MIN_REFERENCE:
            value = median(reference)
            row['reference'] = {'samples': len(reference), 'execution_p50_seconds': value,
                                'scope': 'same_source_configuration_execution_version_kind_before_claim'}
            budget = row['budget_at_claim_seconds']
            if budget is not None and budget > 0 and budget < value:
                row['signals'].append('claim_budget_below_observed_duration')
    return {
        'schema': 'processing-margins-v1', 'observed_at': trace.get('observed_at'),
        'authority': 'derived_from_stored_workflow_envelope', 'scope': 'retained_document_attempts',
        'coverage': 'not_established', 'omitted_attempts': trace.get('omitted_attempts', 0),
        'attempts': rows,
        'counts': {'retained': len(rows),
                   'running_observed': sum(r['stored_state'] == 'running' for r in rows),
                   'retry_links_observed': sum(bool(r['retry_of']) for r in rows),
                   'retry_gaps_measured': sum(r['retry_gap_seconds'] is not None for r in rows)},
        'limitations': ['checkpoint_silence_is_not_worker_failure', 'counts_are_not_retry_budget',
                       'deadline_margin_is_not_guaranteed_action_time',
                       'no_fleet_capacity_or_forecast', 'technical_success_is_not_domain_completion'],
    }
