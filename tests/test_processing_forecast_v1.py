"""Chronological synthetic proof, not incident prediction accuracy.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
# release-control-evidence: metrics teller/noemer score-must-drop
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from html import escape
import json
import unittest
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from starlette.requests import Request

from src.processing_forecast_v1 import deadline_forecast, LOOKBACK_SECONDS, MAX_DOCUMENTS, MAX_RECORDS, MAX_ATTEMPTS
from src.source_selection_ui_v1 import deadline_forecast_html, install
from src.source_selection_v1 import estimate, authorize
from src.operations_console_v1 import ConsoleError

CLOCK = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)
CONFIG = {'mode': 'fixture', 'model': 'private-model', 'deployment': 'same'}


def at(seconds):
    return (CLOCK + timedelta(seconds=seconds)).isoformat()


def document(index, *, start=-100, duration=None, budget=80, size=1000, state=None):
    return {'snapshot_id': f'snapshot-{index}', 'sha256': 'private-source-hash', 'version': '1',
            'title': 'Fixture', 'binary_path': 'source.html', 'named_reviewers': ['reviewer'],
            'received_source': {'bytes': size, 'filename': 'source.html'},
            'content_kind': 'html', 'class': 'richtlijn', 'processing_configuration': CONFIG,
            'source_text': 'private-source-prose',
            'processing_attempts': [{'attempt_id': f'pa_{index:032x}', 'kind': 'ingest',
                'source_hash': 'private-source-hash', 'source_version': '1',
                'processing_configuration': deepcopy(CONFIG), 'started_at': at(start),
                'finished_at': at(start + duration) if duration is not None else None,
                'expires_at': at(start + budget), 'state': state or ('succeeded' if duration is not None else 'running'),
                'dispatch': {'state': 'pending'}, 'diagnostic': {'phase': 'reserved'}}]}


def history(durations=(100,) * 6, budget=300):
    return [document(i + 1, start=-3000 + i * 300, duration=d, budget=budget) for i, d in enumerate(durations)]


def forecast(current=None, rows=None):
    current = current or document(100, start=0, budget=80)
    rows = history() if rows is None else rows
    return deadline_forecast(current, rows + [current], observed_at=at(0))


class ForecastTests(unittest.TestCase):
    def test_existing_estimator_is_reused_and_pressure_is_visible_before_stored_boundary(self):
        current = document(100, start=0, budget=80); docs = history() + [current]
        before = deepcopy(docs)
        report = deadline_forecast(current, docs, observed_at=at(0))
        self.assertEqual(report['status'], 'shadow_only')
        self.assertEqual(report['range_seconds'], [50, 200])
        self.assertEqual(report['range_seconds'], estimate(current, docs)['range_seconds'])
        self.assertTrue(report['pressure'])
        self.assertEqual(report['deadline_remaining_seconds'], 80)
        self.assertEqual(report['sample_count'], 6)
        self.assertEqual(report['evaluation'], dict(scored=3, abstained=3, below_range=0,
            above_range=0, deadline_compared=3, false_pressure=0, missed_boundary=0))
        self.assertEqual(report['actionable_lead'], 'not_established')
        self.assertEqual(docs, before)
        self.assertFalse(report['automatic_action'])

    def test_normal_control_does_not_report_pressure_or_claim_safety(self):
        report = forecast(document(100, start=0, budget=400))
        self.assertFalse(report['pressure'])
        self.assertIn('dit bewijst geen veiligheid', deadline_forecast_html(report, escape))

    def test_future_and_storage_order_cannot_supply_completed_training_labels(self):
        rows = history()
        rows.append(document(20, start=10, duration=10000))
        self.assertEqual(forecast(rows=rows), forecast(rows=list(reversed(rows))))
        self.assertEqual(forecast(rows=rows), forecast())
        rows.append(document(21, start=-10, duration=20))
        report = forecast(rows=rows)
        self.assertEqual(report['reason'], 'noncompletion_bias')
        self.assertEqual(report['evidence']['censored'], 1)
        self.assertIsNone(report['range_seconds'])

    def test_chronological_backtest_catches_underestimation_and_missed_boundary(self):
        report = forecast(rows=history((100, 100, 100, 250, 100, 100), budget=220))
        self.assertEqual(report['evaluation']['above_range'], 1)
        self.assertEqual(report['evaluation']['missed_boundary'], 1)
        self.assertEqual(report['evaluation']['scored'], 3)
        # A retrospective all-data fit would incorrectly include the 250s label.
        self.assertEqual(report['range_seconds'], [50, 250])

    def test_outcome_known_now_but_not_at_reservation_remains_censored(self):
        current = document(100, start=0, budget=500)
        rows = history() + [document(20, start=-10, duration=20), current]
        report = deadline_forecast(current, rows, observed_at=at(100))
        self.assertEqual(report['reason'], 'noncompletion_bias')
        self.assertEqual(report['evidence']['censored'], 1)
        self.assertIsNone(report['range_seconds'])

    def test_false_pressure_and_overestimation_have_explicit_denominators(self):
        report = forecast(rows=history((100, 100, 100, 10, 100, 100), budget=150))
        self.assertEqual(report['evaluation']['below_range'], 1)
        self.assertEqual(report['evaluation']['false_pressure'], 3)
        self.assertEqual(report['evaluation']['deadline_compared'], 3)

    def test_failed_and_unfinished_comparable_work_prevents_success_only_confidence(self):
        for row in (document(20, start=-600, duration=100, state='failed'), document(20, start=-600)):
            report = forecast(rows=history() + [row])
            self.assertEqual(report['reason'], 'noncompletion_bias')
            self.assertIsNone(report['pressure'])

    def test_forecast_requires_both_history_and_held_out_evaluations(self):
        self.assertEqual(forecast(rows=history()[:2])['reason'], 'insufficient_comparable_history')
        self.assertEqual(forecast(rows=history()[:5])['reason'], 'insufficient_chronological_evaluation')

    def test_attempt_configuration_and_source_identity_cannot_be_reconstructed_from_envelope(self):
        for field in ('processing_configuration', 'source_hash', 'source_version'):
            rows = history(); rows[0]['processing_attempts'][0].pop(field)
            self.assertEqual(forecast(rows=rows)['reason'], 'invalid_history')
        rows = history()
        for row in rows:
            row['processing_configuration'] = {'mode': 'later-envelope-config'}
        self.assertEqual(forecast(rows=rows)['status'], 'shadow_only')

    def test_different_route_size_configuration_and_kind_do_not_supply_history(self):
        for field, value in (('content_kind', 'pdf'), ('class', 'other'), ('bytes', 3000),
                             ('configuration', {'mode': 'other'}), ('kind', 'resume')):
            rows = history()
            for row in rows:
                if field == 'bytes': row['received_source']['bytes'] = value
                elif field == 'configuration': row['processing_attempts'][0]['processing_configuration'] = value
                elif field == 'kind': row['processing_attempts'][0]['kind'] = value
                else: row[field] = value
            self.assertEqual(forecast(rows=rows)['reason'], 'insufficient_comparable_history')

    def test_missing_contradictory_naive_and_nonfinite_evidence_is_unknown(self):
        for field, value in (('started_at', None), ('started_at', '2026-10-19T12:00:00'),
                             ('finished_at', at(-4000)), ('finished_at', None)):
            rows = history(); rows[0]['processing_attempts'][0][field] = value
            self.assertEqual(forecast(rows=rows)['reason'], 'invalid_history')
        for size in (0, -1, True, float('nan'), float('inf')):
            current = document(100, start=0, size=size)
            self.assertEqual(forecast(current)['reason'], 'invalid_current_evidence')

    def test_duplicate_identity_and_limits_fail_closed(self):
        rows = history(); rows.append(deepcopy(rows[0]))
        self.assertEqual(forecast(rows=rows)['reason'], 'ambiguous_attempt_identity')
        limited = forecast(rows=history() * MAX_DOCUMENTS)
        self.assertEqual(limited['reason'], 'document_limit')
        self.assertEqual(limited['evidence']['over_document_limit'], 6 * MAX_DOCUMENTS + 1 - MAX_DOCUMENTS)
        current = document(100, start=0)
        current['processing_attempts'] *= MAX_ATTEMPTS + 1
        self.assertEqual(forecast(current)['reason'], 'missing_or_limited_current_attempt')
        rows = [document(i + 1, start=-100000 + i * 300, duration=100) for i in range(MAX_RECORDS + 1)]
        self.assertEqual(forecast(rows=rows)['reason'], 'record_limit')

    def test_unrelated_legacy_and_large_stores_do_not_hold_every_forecast(self):
        legacy = document(200, start=-50000, duration=100, budget=300)
        legacy['content_kind'] = 'pdf'
        del legacy['processing_attempts'][0]['processing_configuration']
        report = forecast(rows=history() + [legacy])
        self.assertEqual(report['status'], 'shadow_only')
        self.assertEqual(report['evidence']['invalid'], 0)
        self.assertEqual(report['evidence']['other_route_or_size'], 1)
        others = []
        for i in range(MAX_RECORDS + 2):
            other = document(1000 + i, start=-90000 + i * 10, duration=100, budget=300)
            other['content_kind'] = 'pdf'
            others.append(other)
        report = forecast(rows=history() + others)
        self.assertEqual(report['status'], 'shadow_only')
        self.assertEqual(report['evidence']['other_route_or_size'], MAX_RECORDS + 2)
        rows = history()
        for row in rows[:3]:
            row['processing_attempts'][0]['processing_configuration'] = {'mode': 'other'}
        report = forecast(rows=rows)
        self.assertEqual(report['evidence']['other_configuration'], 3)
        self.assertEqual(report['evidence']['invalid'], 0)

    def test_comparable_invalid_or_failed_work_still_holds_inside_lookback_only(self):
        old = -LOOKBACK_SECONDS - 3600
        failed = document(300, start=old, duration=100, budget=300, state='failed')
        legacy = document(301, start=old - 600, duration=100, budget=300)
        del legacy['processing_attempts'][0]['processing_configuration']
        report = forecast(rows=history() + [failed, legacy])
        self.assertEqual(report['status'], 'shadow_only')
        self.assertEqual(report['evidence']['outside_lookback'], 2)
        recent_failed = document(302, start=-5000, duration=100, budget=300, state='failed')
        self.assertEqual(forecast(rows=history() + [recent_failed])['reason'], 'noncompletion_bias')
        recent_legacy = document(303, start=-5000, duration=100, budget=300)
        del recent_legacy['processing_attempts'][0]['processing_configuration']
        self.assertEqual(forecast(rows=history() + [recent_legacy])['reason'], 'invalid_history')

    def test_expired_boundary_and_exhausted_range_do_not_become_zero_eta(self):
        current = document(100, start=-100, budget=80)
        report = forecast(current)
        self.assertEqual(report['reason'], 'stored_deadline_elapsed')
        self.assertEqual(report['deadline_remaining_seconds'], -20)
        self.assertEqual(forecast(document(100, start=-220, budget=500))['reason'], 'observed_range_exhausted')

    def test_horizons_are_research_categories_and_never_claim_validated_accuracy(self):
        report = forecast()
        self.assertEqual(set(report['horizons']), {'300', '900', '3600', '21600', '86400'})
        for horizon in report['horizons'].values():
            self.assertEqual(horizon['predictive_accuracy'], 'not_established')

    def test_projection_and_html_do_not_expose_source_configuration_or_action_controls(self):
        report = forecast()
        text = json.dumps(report) + deadline_forecast_html(report, escape)
        for private in ('private-source-hash', 'private-source-prose', 'private-model', 'snapshot-', 'pa_'):
            self.assertNotIn(private, text)
        self.assertNotIn('<form', text)
        self.assertIn('Besluit- en interventietijd zijn onbekend', text)


class ForecastSelectionTests(unittest.TestCase):
    def test_registered_selection_handler_uses_only_visible_loaded_documents_without_writes(self):
        class Store:
            def __init__(self):
                self._envelopes = {row['snapshot_id']: row for row in history() + [document(100, start=0)]}
                for row in self._envelopes.values(): row['named_reviewers'] = []
                self._envelopes['snapshot-100']['named_reviewers'] = ['reviewer']
                self._processing_configuration_reader = lambda: CONFIG
                self.reads = 0
            @contextmanager
            def source_selection_read_scope(self): yield
            def _account(self, actor_id, **kwargs):
                return {'account_id': actor_id, 'roles': ['researcher' if actor_id == 'researcher' else 'reviewer']}
            def _envelope(self, sid): self.reads += 1; return self._envelopes[sid]
            def list_snapshot_ids(self): return list(self._envelopes)
            def processing_status(self, sid, *, actor_id, **kwargs):
                authorize(self, actor_id, self._envelopes[sid])
                return {'state': 'running', 'formation_incomplete': True, 'retry_allowed': False, 'resume_allowed': False}
            def snapshot_objects(self, sid): return []
            def _overview_rows(self, sid): return []
            def objects_revision(self, sid): return 'fixture'
            def __getattr__(self, name): raise AssertionError('unexpected operation: ' + name)
        store = Store(); app = FastAPI()
        def require(request):
            actor = request.headers.get('x-test-account')
            if not actor: raise HTTPException(401)
            return store._account(actor)
        with patch('src.source_processing_dispatch_v1.install_dispatcher'):
            install(app, store, require, lambda html: html, lambda *args: '', lambda x: escape(str(x)))
        handler = next(r.endpoint for r in app.routes if r.path == '/source-selection')
        def request(actor):
            return Request({'type': 'http', 'query_string': b'',
                'headers': [(b'x-test-account', actor.encode())] if actor else []})
        def page(response):
            self.assertEqual(response.headers['cache-control'], 'no-store')
            return response.body.decode()
        before = deepcopy(store._envelopes)
        with self.assertRaises(HTTPException): handler(request(None), 'snapshot-100')
        self.assertEqual(store.reads, 0)
        with self.assertRaises(ConsoleError): handler(request('outsider'), 'snapshot-100')
        with patch('src.processing_forecast_v1.datetime', wraps=datetime) as clock:
            clock.now.return_value = CLOCK
            text = page(handler(request('researcher'), 'snapshot-100'))
            self.assertIn('op basis van 6 eerdere vergelijkbare pogingen', text)
            text = page(handler(request('reviewer'), 'snapshot-100'))
            self.assertIn('Te weinig vergelijkbare metingen', text)
            self.assertNotIn('op basis van 6 eerdere', text)
            self.assertNotIn('id="deadline-schaduwprognose"', page(handler(request('researcher'), '')))
        self.assertEqual(store._envelopes, before)


if __name__ == '__main__':
    unittest.main()
