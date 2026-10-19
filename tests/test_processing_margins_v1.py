"""Measured margins over existing processing authority, never a state transition.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
# release-control-evidence: metrics teller/noemer score-must-drop
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from html import escape
from contextlib import contextmanager
import json
import unittest
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from starlette.requests import Request

from src.processing_trace_v1 import processing_trace, clean_trace
from src.insight_v1 import processing_margins_html

CLOCK = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)
SID = 'snap-' + 'a' * 16 + '-' + 'b' * 8
SOURCE = 'a' * 64


def at(seconds):
    return (CLOCK + timedelta(seconds=seconds)).isoformat()


def attempt(index=1, *, start=-100, claim=-80, finish=None, deadline=100,
            state='running', configuration='same', version='abcdef1', retry_of=None):
    return {'attempt_id': f'pa_{index:032x}', 'command_id': 'private-command',
            'source_hash': SOURCE, 'source_version': 'private-version',
            'expected_revision': 'private-revision', 'kind': 'retry',
            'processing_configuration': {'mode': configuration},
            'state': state, 'started_at': at(start), 'expires_at': at(deadline),
            'finished_at': at(finish) if finish is not None else None,
            'retry_of': f'pa_{retry_of:032x}' if retry_of is not None else None,
            'dispatch': {'state': 'claimed' if claim is not None else 'pending',
                         'claimed_at': at(claim) if claim is not None else None,
                         'token': 'private-claim-token'},
            'diagnostic': {'execution_runtime': {'version': version, 'pid': 17},
                           'origin_request_id': 'f' * 32,
                           'checkpoints': [{'phase': 'reserved', 'at': at(start)},
                                           {'phase': 'model_request', 'at': at(claim if claim is not None else start)}],
                           'provider_text': 'private-provider-prose'}}


def envelope(attempts):
    return {'snapshot_id': SID, 'sha256': SOURCE, 'processing_attempts': attempts,
            'source_text': 'private-source-content', 'named_reviewers': ['reviewer']}


def traced(raw):
    with patch('src.processing_trace_v1.datetime') as clock:
        clock.now.return_value = CLOCK
        return processing_trace(raw)


def reference():
    return [attempt(i + 1, start=-600 + i * 100, claim=-590 + i * 100,
                    finish=-540 + i * 100, state='succeeded') for i in range(3)]


def pressured():
    return attempt(4, start=-200, claim=-20, deadline=10, retry_of=3)


class ProcessingMarginsTests(unittest.TestCase):
    def test_pending_wait_and_claimed_execution_are_separate_measurements(self):
        pending = traced(envelope([attempt(claim=None)]))['processing_margins']['attempts'][0]
        self.assertEqual(pending['queue_wait_seconds'], 100)
        self.assertIsNone(pending['execution_seconds'])
        self.assertEqual(pending['deadline_remaining_seconds'], 100)
        claimed = traced(envelope([attempt()]))['processing_margins']['attempts'][0]
        self.assertEqual(claimed['queue_wait_seconds'], 20)
        self.assertEqual(claimed['execution_seconds'], 80)
        self.assertEqual(claimed['budget_at_claim_seconds'], 180)
        self.assertEqual(claimed['checkpoint_age_seconds'], 80)
        self.assertIsNone(claimed['reference'])

    def test_queue_consumed_budget_is_visible_before_expiry_without_writes(self):
        raw = envelope(reference() + [pressured()]); before = deepcopy(raw)
        report = traced(raw)['processing_margins']
        current = report['attempts'][-1]
        self.assertEqual(current['deadline_remaining_seconds'], 10)
        self.assertEqual(current['budget_at_claim_seconds'], 30)
        self.assertEqual(current['reference']['samples'], 3)
        self.assertEqual(current['reference']['execution_p50_seconds'], 50)
        self.assertIn('claim_budget_below_observed_duration', current['signals'])
        self.assertNotIn('stored_deadline_elapsed', current['signals'])
        self.assertEqual(current['retry_gap_seconds'], 140)
        self.assertEqual(raw, before)
        self.assertEqual(report['coverage'], 'not_established')
        self.assertEqual(current['stored_state'], 'running')
        # Chronological observation at claim time already exposes the margin.
        with patch('src.processing_trace_v1.datetime') as clock:
            clock.now.return_value = CLOCK - timedelta(seconds=20)
            earlier = processing_trace(raw)['processing_margins']['attempts'][-1]
        self.assertIn('claim_budget_below_observed_duration', earlier['signals'])
        self.assertEqual(earlier['deadline_remaining_seconds'], 30)
        from src.processing_retry_v1 import status
        self.assertEqual(status(raw, clock=CLOCK-timedelta(seconds=20))['reason_code'], 'processing_attempt_in_progress')

    def test_ordinary_budget_and_new_configuration_or_deploy_do_not_borrow_history(self):
        for change in ({'deadline': 100}, {'configuration': 'changed'}, {'version': '1234567'}):
            rows = reference() + [attempt(4, start=-200, claim=-20, deadline=10, **{k: v for k, v in change.items() if k != 'deadline'})]
            if 'deadline' in change:
                rows[-1]['expires_at'] = at(change['deadline'])
            current = traced(envelope(rows))['processing_margins']['attempts'][-1]
            self.assertNotIn('claim_budget_below_observed_duration', current['signals'])
            if 'deadline' not in change:
                self.assertIsNone(current['reference'])

    def test_different_attempt_kind_cannot_supply_a_duration_reference(self):
        rows = reference() + [pressured()]
        rows[-1]['kind'] = 'resume'
        current = traced(envelope(rows))['processing_margins']['attempts'][-1]
        self.assertIsNone(current['reference'])
        self.assertNotIn('claim_budget_below_observed_duration', current['signals'])

    def test_future_completions_and_storage_order_do_not_change_reference(self):
        rows = reference() + [pressured()]
        first = traced(envelope(rows))['processing_margins']['attempts'][-1]
        after_claim = attempt(5, start=-150, claim=-100, finish=-10, state='succeeded')
        future = attempt(6, start=-150, claim=-100, finish=10, state='succeeded')
        result = traced(envelope(rows + [after_claim, future]))['processing_margins']['attempts'][3]
        self.assertEqual(first, result)
        shuffled = traced(envelope([rows[3], rows[2], rows[0], rows[1]]))['processing_margins']
        self.assertEqual(shuffled['attempts'][0], first)

    def test_elapsed_deadline_preserves_stored_running_state(self):
        raw = envelope([attempt(deadline=-10)]); before = deepcopy(raw)
        row = traced(raw)['processing_margins']['attempts'][0]
        self.assertEqual(row['deadline_remaining_seconds'], -10)
        self.assertEqual(row['stored_state'], 'running')
        self.assertIn('stored_deadline_elapsed', row['signals'])
        self.assertEqual(raw, before)

    def test_legacy_missing_or_contradictory_timing_is_unknown(self):
        legacy = traced(envelope([{'state': 'running'}]))['processing_margins']['attempts'][0]
        self.assertIsNone(legacy['queue_wait_seconds'])
        self.assertIsNone(legacy['deadline_remaining_seconds'])
        for fields in ({'claimed_at': at(-101)}, {'started_at': at(1)},
                       {'claimed_at': at(101)}, {'started_at': '2026-10-19T11:00:00'},
                       {'finished_at': at(-1)}, {'expires_at': at(-101)}):
            raw = attempt()
            for key, value in fields.items():
                if key == 'claimed_at': raw['dispatch'][key] = value
                else: raw[key] = value
            row = traced(envelope([raw]))['processing_margins']['attempts'][0]
            self.assertIsNone(row['queue_wait_seconds'])
            self.assertIsNone(row['reference'])
            self.assertTrue(row['evidence_issues'])
        empty = traced(envelope([]))['processing_margins']
        self.assertEqual(empty['counts']['retained'], 0)
        self.assertIn('geen uitspraak over gezondheid', processing_margins_html(empty))

    def test_missing_checkpoint_and_truncation_block_comparison_not_recorded_state(self):
        for alteration in ('missing', 'invalid', 'partial'):
            rows = reference() + [pressured()]
            diagnostic = rows[-1]['diagnostic']
            if alteration == 'missing': diagnostic['checkpoints'] = []
            if alteration == 'invalid': diagnostic['checkpoints'][-1]['at'] = at(1)
            if alteration == 'partial': diagnostic['omitted_evidence'] = ['omitted']
            row = traced(envelope(rows))['processing_margins']['attempts'][-1]
            self.assertIsNone(row['reference'])
            self.assertEqual(row['stored_state'], 'running')
        rows = reference() + [pressured()]
        # Old omitted attempts are explicit, even if a few peers remain usable.
        rows = [attempt(i+10, state='failed', finish=-10) for i in range(64)] + rows
        report = traced(envelope(rows))['processing_margins']
        self.assertEqual(len(report['attempts']), 64)
        self.assertEqual(report['omitted_attempts'], 4)
        self.assertIsNone(report['attempts'][-1]['reference'])

    def test_retry_links_are_explicit_and_ambiguous_or_missing_parents_are_unknown(self):
        rows = reference() + [pressured()]
        rows[-1]['retry_of'] = 'pa_' + '9' * 32
        report = traced(envelope(rows))['processing_margins']
        self.assertEqual(report['counts']['retry_links_observed'], 1)
        self.assertEqual(report['counts']['retry_gaps_measured'], 0)
        self.assertIsNone(report['attempts'][-1]['retry_gap_seconds'])
        duplicate = reference() + [deepcopy(reference()[-1]), pressured()]
        row = traced(envelope(duplicate))['processing_margins']['attempts'][-1]
        self.assertIsNone(row['retry_gap_seconds'])
        self.assertIsNone(row['reference'])

    def test_private_payloads_and_supplied_derived_evidence_are_not_trusted(self):
        raw = envelope(reference() + [pressured()]); raw['processing_margins'] = {'evil': 'private-forgery'}
        trace = traced(raw)
        text = json.dumps(trace)
        for private in ('private-command', 'private-claim-token', 'private-source-content',
                        'private-provider-prose', 'private-version', 'private-revision', 'private-forgery'):
            self.assertNotIn(private, text)
        supplied = clean_trace(trace)
        self.assertNotIn('processing_margins', supplied)
        self.assertEqual(supplied['authority'], 'supplied_workflow_projection_not_authenticated_by_exporter')

    def test_rendered_advice_is_visible_and_unsafe_text_is_escaped(self):
        report = traced(envelope(reference() + [pressured()]))['processing_margins']
        report['attempts'][-1]['attempt_id'] = '<script>alert(1)</script>'
        html = processing_margins_html(report)
        self.assertIn('<details open>', html)
        self.assertIn('minder pogingstijd over', html)
        self.assertIn('3 technisch geslaagde pogingen', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>', html)
        self.assertNotIn('<form', html)


class ProcessingMarginsRouteTests(unittest.TestCase):
    def test_existing_trace_handler_preserves_actual_authorization_and_read_only_scope(self):
        from src.source_selection_ui_v1 import install
        from src.operations_console_v1 import ConsoleError
        class Store:
            def __init__(self):
                self.raw = envelope(reference() + [pressured()])
                self.accounts = {'researcher': {'account_id': 'researcher', 'roles': ['researcher']},
                                 'reviewer': {'account_id': 'reviewer', 'roles': ['reviewer']},
                                 'outsider': {'account_id': 'outsider', 'roles': ['reviewer']},
                                 'publisher': {'account_id': 'publisher', 'roles': ['publisher']}}
                self.reads = 0
            @contextmanager
            def source_selection_read_scope(self):
                yield
            def _account(self, actor_id, **kwargs): return self.accounts[actor_id]
            def _envelope(self, document):
                self.reads += 1
                if document != SID: raise ConsoleError('unknown_document')
                return self.raw
            def __getattr__(self, name):
                raise AssertionError('unexpected store operation: ' + name)
        store = Store(); app = FastAPI()
        def require(request):
            actor = request.headers.get('x-test-account')
            if actor is None: raise HTTPException(401)
            return store.accounts[actor]
        # Startup/lifespan is outside a direct handler check. CI also exercises
        # the installed app and real store through authenticated HTTP.
        with patch('src.source_processing_dispatch_v1.install_dispatcher'):
            install(app, store, require, lambda *args, **kwargs: '', lambda *args: '', escape)
        handler = next(r.endpoint for r in app.routes if r.path == '/inzicht/document/verwerkingsspoor')
        def request(actor):
            return Request({'type': 'http', 'headers': [(b'x-test-account', actor.encode())] if actor else [], 'query_string': b''})
        before = deepcopy(store.raw)
        with self.assertRaises(HTTPException): handler(request(None), SID)
        self.assertEqual(store.reads, 0)
        for denied in ('outsider', 'publisher'):
            with self.assertRaises(ConsoleError): handler(request(denied), SID)
        with patch('src.processing_trace_v1.datetime') as clock:
            clock.now.return_value = CLOCK
            for allowed in ('researcher', 'reviewer'):
                response = handler(request(allowed), SID)
                body = json.loads(response.body)
                self.assertEqual(response.headers['Cache-Control'], 'no-store')
                self.assertIn('claim_budget_below_observed_duration', body['processing_margins']['attempts'][-1]['signals'])
        self.assertEqual(store.raw, before)


if __name__ == '__main__':
    unittest.main()
