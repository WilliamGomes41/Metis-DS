"""Bounded shadow evaluation of the existing ETA; no processing authority."""

from datetime import datetime, timezone
from math import isfinite

from src.source_selection_v1 import estimate


MAX_DOCUMENTS = 256
MAX_RECORDS = 128
MAX_ATTEMPTS = 64
HORIZONS = (300, 900, 3600, 21600, 86400)


def _time(value):
    try:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.utcoffset() is not None else None
    except (TypeError, ValueError):
        return None


def _size(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) and value > 0


def _record(envelope, attempt):
    """Do not attribute a later envelope configuration/source to earlier work."""
    configuration = attempt.get('processing_configuration')
    start, finish = _time(attempt.get('started_at')), _time(attempt.get('finished_at'))
    size = (envelope.get('received_source') or {}).get('bytes')
    route = (envelope.get('content_kind'), envelope.get('class'))
    if (not start or not _size(size) or not all(route) or not isinstance(configuration, dict) or not configuration
            or not isinstance(attempt.get('attempt_id'), str) or not attempt['attempt_id'] or not envelope.get('sha256')
            or attempt.get('source_hash') != envelope['sha256']
            or attempt.get('source_version') != envelope.get('version')
            or not envelope.get('version')):
        return None
    state = attempt.get('state')
    if state not in {'running', 'succeeded', 'failed', 'expired', 'interrupted', 'incomplete_budget'}:
        return None
    if state == 'running':
        if attempt.get('finished_at') is not None:
            return None
    elif not finish or (finish - start).total_seconds() < 1:
        return None
    return {'id': attempt['attempt_id'], 'start': start, 'finish': finish, 'state': state,
            'size': size, 'route': route, 'configuration': configuration,
            'deadline': _time(attempt.get('expires_at'))}


def _comparable(left, right):
    return (left['route'] == right['route'] and left['configuration'] == right['configuration']
            and .5 <= left['size'] / right['size'] <= 2)


def _range(target, records):
    """Reservation-time forecast: outcome labels must already have been known."""
    rates, censored, failed = [], 0, 0
    for row in records:
        if row['id'] == target['id'] or row['start'] >= target['start'] or not _comparable(row, target):
            continue
        if row['finish'] is None or row['finish'] > target['start']:
            censored += 1
        elif row['state'] != 'succeeded':
            failed += 1
        else:
            rates.append((row['size'], row['configuration'],
                          (row['finish'] - row['start']).total_seconds() / row['size']))
    # Successful-only timing cannot safely stand in for observed non-completion.
    if censored or failed:
        return None, len(rates), censored, failed
    env = {'received_source': {'bytes': target['size']}, 'content_kind': target['route'][0],
           'class': target['route'][1], 'processing_configuration': target['configuration']}
    result = estimate(env, (), observations={target['route']: rates})
    return result['range_seconds'], result['sample_count'], censored, failed


def _evaluate(records):
    counts = dict(scored=0, abstained=0, below_range=0, above_range=0,
                  deadline_compared=0, false_pressure=0, missed_boundary=0)
    for row in records:
        if row['state'] != 'succeeded':
            continue
        band, _, _, _ = _range(row, records)
        if band is None:
            counts['abstained'] += 1
            continue
        counts['scored'] += 1
        actual = (row['finish'] - row['start']).total_seconds()
        counts['below_range'] += actual < band[0]
        counts['above_range'] += actual > band[1]
        deadline = row['deadline']
        if deadline and deadline > row['start']:
            counts['deadline_compared'] += 1
            budget = (deadline - row['start']).total_seconds()
            pressure, crossed = band[1] >= budget, actual >= budget
            counts['false_pressure'] += pressure and not crossed
            counts['missed_boundary'] += crossed and not pressure
    return counts


def deadline_forecast(envelope, documents, *, observed_at=None):
    """Caller supplies authorized envelopes from the existing read scope only.

    No source/configuration values or identities leave this projection. The
    range concerns technical attempt duration including waiting, not formation
    completeness or the probability of an incident. Limits fail closed.
    """
    clock = _time(observed_at) if observed_at is not None else datetime.now(timezone.utc)
    report = {'schema': 'processing-deadline-shadow-v1', 'status': 'hold', 'reason': None,
              'coverage': 'not_established', 'range_seconds': None, 'sample_count': 0,
              'evidence': dict(retained=0, invalid=0, ignored_kind=0, censored=0, failed=0,
                               over_document_limit=0, over_attempt_limit=0, unexamined_at_least=0),
              'evaluation': None, 'deadline_remaining_seconds': None, 'pressure': None,
              'horizons': {str(h): {'stored_boundary_within_horizon': None,
                                   'predictive_accuracy': 'not_established'} for h in HORIZONS},
              'actionable_lead': 'not_established', 'automatic_action': False}

    def hold(reason):
        report['reason'] = reason
        return report

    if not clock:
        return hold('invalid_observation_time')
    if len(documents) > MAX_DOCUMENTS:
        report['evidence']['over_document_limit'] = len(documents) - MAX_DOCUMENTS
        return hold('document_limit')
    attempts = envelope.get('processing_attempts') or []
    if not attempts or len(attempts) > MAX_ATTEMPTS:
        report['evidence']['over_attempt_limit'] = max(0, len(attempts) - MAX_ATTEMPTS)
        return hold('missing_or_limited_current_attempt')
    attempt = attempts[-1]  # Same persisted latest-attempt selection as projection.
    if attempt.get('kind') != 'ingest' or attempt.get('state') != 'running':
        return hold('no_running_ingest')
    current = _record(envelope, attempt)
    if not current or current['start'] > clock:
        return hold('invalid_current_evidence')
    deadline = current['deadline']
    if not deadline or deadline <= current['start']:
        return hold('invalid_stored_deadline')
    remaining = (deadline - clock).total_seconds()
    report['deadline_remaining_seconds'] = remaining
    for h in HORIZONS:
        report['horizons'][str(h)]['stored_boundary_within_horizon'] = 0 < remaining <= h
    if remaining <= 0:
        return hold('stored_deadline_elapsed')
    records, identities = [], set()
    for document in documents:
        rows = document.get('processing_attempts') or []
        if len(rows) > MAX_ATTEMPTS:
            report['evidence']['over_attempt_limit'] = len(rows) - MAX_ATTEMPTS
            return hold('attempt_limit')
        for raw in rows:
            if raw.get('kind') != 'ingest':
                report['evidence']['ignored_kind'] += 1
                continue
            row = _record(document, raw)
            if not row:
                report['evidence']['invalid'] += 1
                continue
            if row['start'] > clock:
                continue
            if row['id'] in identities:
                return hold('ambiguous_attempt_identity')
            identities.add(row['id'])
            # A future terminal label must not be visible to the evaluator.
            if row['finish'] and row['finish'] > clock:
                row = {**row, 'finish': None, 'state': 'running'}
            records.append(row)
            if len(records) > MAX_RECORDS:
                report['evidence']['retained'] = MAX_RECORDS
                report['evidence']['unexamined_at_least'] = 1
                return hold('record_limit')
    report['evidence']['retained'] = len(records)
    if report['evidence']['invalid']:
        return hold('invalid_history')
    relevant = [row for row in records if _comparable(row, current)]
    report['evaluation'] = _evaluate(relevant)
    band, count, censored, failed = _range(current, records)
    report['sample_count'] = count
    report['evidence'].update(censored=censored, failed=failed)
    if censored or failed:
        return hold('noncompletion_bias')
    if band is None:
        return hold('insufficient_comparable_history')
    if report['evaluation']['scored'] < 3:
        return hold('insufficient_chronological_evaluation')
    elapsed = (clock - current['start']).total_seconds()
    if elapsed >= band[1]:
        return hold('observed_range_exhausted')
    report.update(status='shadow_only', reason='uncalibrated_empirical_range',
                  range_seconds=band,
                  pressure=band[1] >= (deadline - current['start']).total_seconds())
    # A known deadline within a horizon is not evidence of predictive skill at
    # that horizon. In particular it cannot establish a 24-hour forecast.
    return report
