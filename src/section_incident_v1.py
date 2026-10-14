"""Offline, bounded diagnostic projection. Never a workflow or cause authority."""
from __future__ import annotations

import math
import re
from datetime import datetime

from src.request_diagnostics_v1 import PHASES, ROUTES

MAX_EVENTS = 1000
EVENTS = frozenset({'request_started', 'phase_started', 'request_running',
                   'response_started', 'response_completed', 'request_finished'})
PLATFORM_EVENTS = frozenset({'startup_failed', 'process_unavailable', 'process_restarted',
                             'gateway_response', 'platform_available'})


def identifier(value):
    return value if isinstance(value, str) and re.fullmatch('[0-9a-f]{32}', value) else None


def timestamp(value):
    if not isinstance(value, str) or len(value) > 32:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.isoformat() if parsed.tzinfo is not None else None
    except ValueError:
        return None


def number(value):
    return value if type(value) in (int, float) and 0 <= value <= 10**12 and math.isfinite(value) else None


def status(value):
    return value if type(value) is int and 100 <= value <= 599 else None


def choice(value, allowed):
    return value if isinstance(value, str) and value in allowed else None


def clean_event(row):
    if not isinstance(row, dict) or choice(row.get('event'), EVENTS) is None:
        return None
    result = dict(event=row['event'], request_id=identifier(row.get('request_id')),
                  attempt_id=identifier(row.get('attempt_id')),
                  route=choice(row.get('route'), ROUTES), timestamp=timestamp(row.get('timestamp')),
                  elapsed_ms=number(row.get('elapsed_ms')), status=status(row.get('status')),
                  outcome=choice(row.get('outcome'), {'completed', 'incomplete', 'cancelled', 'exception'}),
                  phase=choice(row.get('phase'), PHASES | {'request_dispatch'}))
    for name, pattern in [('version', r'(?:[0-9a-f]{7,64}|unknown)'),
                          ('instance', r'(?:[0-9a-f-]{1,128}|local)')]:
        value = row.get(name)
        result[name] = value if isinstance(value, str) and re.fullmatch(pattern, value) else None
    result['pid'] = number(row.get('pid'))
    totals = row.get('phases')
    result['phases'] = {name: {'calls': number(value.get('calls')),
                              'inclusive_ms': number(value.get('inclusive_ms'))}
                        for name, value in totals.items() if name in PHASES and isinstance(value, dict)
                       } if isinstance(totals, dict) else {}
    return result


def build_incident(probe, application_events, platform_events=()):
    """Join by explicit IDs only. Input event order is retained, not clock-sorted."""
    if (not isinstance(probe, dict) or probe.get('schema') != 'metis.section-probe.v1'
            or not identifier(probe.get('attempt_id')) or choice(probe.get('route'), ROUTES) is None):
        raise ValueError('invalid_browser_probe')
    browser = {key: probe[key] for key in ('schema', 'attempt_id', 'route')}
    browser.update(started_at=timestamp(probe.get('started_at')), finished_at=timestamp(probe.get('finished_at')),
        response_request_id=identifier(probe.get('response_request_id')), status=status(probe.get('status')),
        navigation=choice(probe.get('navigation'), {'loaded', 'timeout', 'network_error', 'probe_error'}),
        final_location=choice(probe.get('final_location'), {'target', 'login', 'other'}),
        assertion=choice(probe.get('assertion'), {'section-visible-v1'}),
        usability=choice(probe.get('usability'), {'passed', 'failed', 'not_checked'}),
        response_complete=probe.get('response_complete') is True,
        navigation_started=probe.get('navigation_started') is True,
        page_errors=number(probe.get('page_errors')),
        blocked_requests=number(probe.get('blocked_requests')))
    rows, omitted, invalid = [], 0, 0
    for raw in application_events:
        if len(rows) >= MAX_EVENTS:
            omitted += 1
            continue
        row = clean_event(raw)
        if row is None:
            invalid += 1
        else:
            rows.append(row)
    relevant = [r for r in rows if r['route'] == browser['route']]
    rid = browser['response_request_id']
    selected = [r for r in relevant if rid and r['request_id'] == rid]
    correlation = 'response_request_id' if selected else 'none'
    if not selected and not rid:
        candidates = [r for r in relevant if r['attempt_id'] == browser['attempt_id'] and r['request_id']]
        ids = {r['request_id'] for r in candidates}
        if len(ids) == 1:
            selected, correlation = candidates, 'client_attempt_untrusted'
        elif len(ids) > 1:
            correlation = 'ambiguous'
    selected.sort(key=lambda row: row['elapsed_ms'] if row['elapsed_ms'] is not None else float('inf'))
    missing = []
    if not selected:
        missing.append('application_events_missing' if correlation != 'ambiguous' else 'application_correlation_ambiguous')
    if omitted:
        missing.append('application_events_truncated')
    if invalid:
        missing.append('unrecognized_application_events')
    if any(r['timestamp'] is None for r in selected):
        missing.append('application_timestamps_missing')
    if any(r['version'] in (None, 'unknown') for r in selected):
        missing.append('application_version_missing')
    if not browser['started_at'] or not browser['finished_at']:
        missing.append('browser_time_window_missing')
    names = {r['event'] for r in selected}
    finished = [r for r in selected if r['event'] == 'request_finished']
    last = finished[-1] if finished else {}
    app = dict(started=True if 'request_started' in names else None,
               response_started=True if 'response_started' in names else None,
               response_completed=True if 'response_completed' in names or last.get('outcome') == 'completed' else None,
               status=last.get('status'), outcome=last.get('outcome'), events=selected)
    app['last_observed_boundary'] = selected[-1]['event'] if selected else None
    app['last_observed_phase'] = next((r['phase'] for r in reversed(selected) if r['phase']), None)
    if selected and not finished:
        missing.append('application_terminal_event_missing')
    if selected and 'request_started' not in names:
        missing.append('application_start_missing')
    contradictions = []
    if any(r['attempt_id'] and r['attempt_id'] != browser['attempt_id'] for r in selected):
        contradictions.append('response_and_attempt_identity_disagree')
    if len({(r['status'], r['outcome']) for r in finished}) > 1:
        contradictions.append('application_terminal_events_disagree')
    if browser['status'] and app['status'] and browser['status'] != app['status']:
        contradictions.append('browser_and_application_status_differ')
    if browser['usability'] == 'passed' and (browser['navigation'] != 'loaded'
            or browser['final_location'] != 'target' or browser['assertion'] is None
            or browser['status'] != 200 or not browser['response_complete']):
        contradictions.append('browser_usability_evidence_inconsistent')
    platform, omitted_platform = [], 0
    for raw in platform_events:
        if len(platform) >= 100:
            omitted_platform += 1
            continue
        if isinstance(raw, dict) and choice(raw.get('event'), PLATFORM_EVENTS) is not None:
            platform.append(dict(event=raw['event'], timestamp=timestamp(raw.get('timestamp')),
                                 status=status(raw.get('status'))))
    if not platform:
        missing.append('platform_evidence_missing')
    if omitted_platform:
        missing.append('platform_events_truncated')
    # These codes describe observations, never diagnosed infrastructure causes.
    if browser['status'] in (401, 403) or (browser['final_location'] == 'login' and browser['route'] != '/login'):
        code, next_check = 'access_not_granted', 'Check the existing session and role decision for this request.'
    elif browser['status'] and browser['status'] >= 400:
        code, next_check = 'browser_http_failure', 'Compare the matching request with gateway and process evidence; do not infer the emitting layer from HTTP status.'
    elif browser['navigation'] in ('timeout', 'network_error'):
        code, next_check = 'browser_navigation_failed', 'Check whether the same attempt reached the app, then inspect platform evidence in the recorded time window.'
    elif last.get('outcome') in ('exception', 'cancelled', 'incomplete'):
        code, next_check = 'application_incomplete', 'Inspect the last observed phase and the matching runtime; cancellation alone does not explain its cause.'
    elif browser['usability'] == 'failed':
        code, next_check = 'browser_assertion_failed', 'Check the page-specific visible controls, client errors and response completion.'
    elif browser['usability'] == 'passed' and not contradictions:
        code, next_check = 'section_visible', 'Continue with the next critical-path step; no domain action has been tested.'
    else:
        code, next_check = 'insufficient_evidence', 'Repair or rerun the read-only probe and supply matching evidence.'
    boundary = ('browser_section_visible' if code == 'section_visible' else
                'browser_response_complete' if browser['response_complete'] else
                'browser_response_headers' if browser['status'] else
                'browser_attempt' if browser['navigation_started'] else 'probe_setup')
    alternatives = []
    if code != 'section_visible':
        if not selected:
            alternatives.append('request did not reach application, or application evidence is missing')
        if selected and app['response_completed'] is None:
            alternatives.append('application/dependency unfinished, or terminal evidence is missing')
        if code in ('browser_http_failure', 'browser_navigation_failed'):
            alternatives.append('response failed or was interrupted at an unproven boundary')
        if code == 'browser_assertion_failed':
            alternatives.extend(['unexpected or incomplete page', 'client rendering or probe restriction'])
    return dict(schema='metis.section-incident.v1', browser=browser, application=app,
        platform=dict(events=platform, correlation='time_window_only', provenance='operator_supplied'),
        correlation=correlation, missing_evidence=missing, contradictions=contradictions,
        omitted_application_events=omitted, omitted_platform_events=omitted_platform,
        domain_completion='not_assessed',
        assessment=dict(code=code, cause='unknown', last_browser_boundary=boundary,
                        next_check=next_check, expected_next_boundary=(
                            'next_domain_step_not_assessed' if code == 'section_visible' else
                            'browser_section_visible' if browser['response_complete'] else
                            'browser_response_complete' if browser['status'] else 'browser_response_headers'),
                        alternatives=alternatives))


def summary(incident):
    assessment = incident['assessment']
    return '\n'.join(['Metis section incident',
        'Observation: ' + assessment['code'], 'Cause: unknown',
        'Last browser boundary: ' + assessment['last_browser_boundary'],
        'Correlation: ' + incident['correlation'],
        'Last application boundary: ' + (incident['application']['last_observed_boundary'] or 'unknown'),
        'Last observed application phase: ' + (incident['application']['last_observed_phase'] or 'unknown'),
        'Missing evidence: ' + (', '.join(incident['missing_evidence']) or 'none in supplied scope'),
        'Contradictions: ' + (', '.join(incident['contradictions']) or 'none observed'),
        'Next check: ' + assessment['next_check'],
        'Domain completion/publication readiness: not assessed.',
        'ASGI send completion does not prove browser receipt. Platform records are operator-supplied; time proximity is not causality.',
        'Do not retry a domain command based on this report. Reconcile its durable outcome first.', ''])
