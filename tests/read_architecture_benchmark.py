"""Reproducible synthetic PG read benchmark, invoked explicitly (not a timing gate).

PGBIN=... python -m pytest -q -s tests/read_architecture_benchmark.py
Run this exact file against the comparison checkout and the recovery checkout.
"""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import cProfile
import json
import subprocess
import time

from tests.test_d5_4_review_interaction_evidence import _system
from tests.test_insight_v1 import _login


def test_read_benchmark(tmp_path, production_console, production_app, monkeypatch):
    import src.request_diagnostics_v1 as diagnostics
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    store = console.workflow_document_store
    env = store.get_envelope(sid)
    env.setdefault('semantic_replay', {}).setdefault('provider_evidence', {})['large_fixture'] = [
        {'index': i, 'spans': [{'start': i, 'end': i+20}], 'text': 'synthetic evidence'} for i in range(4000)]
    store.write_bundle(envelope=env)
    # Sizes are measured during setup, never by a timed request/telemetry hook.
    sizes = {'get_envelope': len(json.dumps(env).encode()),
             'list_envelopes': len(json.dumps([env]).encode()),
             'list_document_objects': len(json.dumps(store.list_document_objects(sid)).encode())}
    from psycopg.types.json import _JsonLoader, set_json_loads
    native_loads = _JsonLoader._loads
    json_volume = [0]
    def measured_json(data):
        json_volume[0] += len(data)
        return native_loads(data)
    set_json_loads(measured_json)
    profile = cProfile.Profile()
    endpoint = next(r for r in production_app(console).routes if getattr(r, 'path', '') == '/inzicht/api/documents')
    original_call = endpoint.dependant.call
    endpoint.dependant.call = lambda *a, **kw: profile.runcall(original_call, *a, **kw)
    full_names = set(sizes)
    # Compact sizes are sampled once in setup. This is decoded JSON size, not
    # PostgreSQL wire bytes or TOAST/storage bytes.
    for name, args in [('list_document_summaries', ()), ('document_processing_inputs', ([sid],)),
                       ('document_diagnostic_inputs', ([sid],)), ('list_document_cards', ()), ('list_source_selection_summaries', ())]:
        method = getattr(store, name, None)
        if method is not None:
            sizes[name] = len(json.dumps(method(*args)).encode())
    calls, metrics = Counter(), []
    for name in sizes:
        original = getattr(store, name)
        def counted(*args, _name=name, _original=original, **kwargs):
            calls[_name] += 1
            return _original(*args, **kwargs)
        monkeypatch.setattr(store, name, counted)
    original_metrics = diagnostics.note_request_metrics
    def capture(**values):
        metrics.append(values)
        return original_metrics(**values)
    monkeypatch.setattr(diagnostics, 'note_request_metrics', capture)
    console.workflow_identity_store.update_roles(users['reviewer_a']['account_id'], ['researcher', 'reviewer', 'publisher'])
    clients = [_login(console, users[role]['username'], production_app=production_app)
               for role in ['researcher', 'reviewer_a']]
    records = []
    try:
        for sample in range(5):
            calls.clear(); metrics.clear(); profile.clear(); json_volume[0] = 0
            started = time.perf_counter()
            response = clients[0].get('/inzicht/api/documents')
            assert response.status_code == 200
            copy = [e for e in profile.getstats() if getattr(e.code, 'co_name', '') == 'deepcopy']
            records.append({'sample': sample, 'mode': 'first' if sample == 0 else 'repeat',
                'seconds': round(time.perf_counter()-started, 6), 'full_reads': {k:v for k,v in calls.items() if k in full_names},
                'store_reads': dict(calls),
                'native_json_bytes': json_volume[0],
                'full_payload_bytes': sum(calls[name]*sizes[name] for name in full_names),
                'decoded_payload_bytes': sum(calls[name]*sizes[name] for name in sizes),
                'deepcopy_calls': sum(e.callcount for e in copy),
                'deepcopy_seconds': round(sum(e.totaltime for e in copy), 6),
                'db': metrics[-1]})
        # Profilers are thread-specific; concurrency observes wall time and DB only.
        endpoint.dependant.call = original_call
        calls.clear(); metrics.clear(); json_volume[0] = 0
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda c: c.get('/inzicht/api/documents'), clients))
        assert all(r.status_code == 200 for r in responses)
        records.append({'mode': 'two_readers', 'seconds': round(time.perf_counter()-started, 6),
                        'full_reads': {k:v for k,v in calls.items() if k in full_names},
                'store_reads': dict(calls), 'db': metrics})
        route_records = []
        for route, params in [('/', {}), ('/ingest', {}), ('/source-selection', {}),
                ('/review', {}), ('/publish', {}), ('/tree', {}), ('/settings', {}), ('/inzicht', {}),
                ('/inzicht/api/documents', {}), ('/inzicht/api/quality', {}),
                ('/inzicht/document', {'document': sid}),
                ('/review', {'document': sid, 'task': 'individual'}),
                ('/publish', {'document': sid}), ('/source-selection', {'document': sid})]:
            calls.clear(); metrics.clear(); json_volume[0] = 0
            started = time.perf_counter()
            response = clients[1].get(route, params=params)
            elapsed = time.perf_counter()-started
            assert response.status_code == 200, (route, response.status_code)
            route_records.append({'route': route, 'detail': bool(params), 'seconds': round(elapsed, 6),
                                  'full_reads': {k:v for k,v in calls.items() if k in full_names},
                                  'store_reads': dict(calls), 'native_json_bytes': json_volume[0], 'db': metrics[-1]})
        print('READ_ARCHITECTURE_ROUTES', json.dumps(route_records, sort_keys=True))
        from tests.production_support import restart_production
        from tests.test_d5_4_review_interaction_evidence import HTML
        from threading import Barrier
        producer = restart_production(console)
        barrier = Barrier(3)
        def read_during_formation(client):
            barrier.wait(timeout=5)
            return client.get('/inzicht/api/documents').status_code
        def form():
            barrier.wait(timeout=5)
            return producer.ingest(actor_id=users['researcher']['account_id'], filename='parallel.html',
                data=HTML, content_type='text/html', ingest_kind='new', title='Concurrent benchmark',
                version='1.0', date='2026-09-25', live_url='', class_='richtlijn', family='test',
                named_reviewers=[users['reviewer_a']['account_id'], users['reviewer_b']['account_id']])
        calls.clear(); metrics.clear(); json_volume[0] = 0
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=3) as pool:
            first, second, forming = pool.submit(read_during_formation, clients[0]), pool.submit(read_during_formation, clients[1]), pool.submit(form)
            assert first.result() == second.result() == 200
            assert forming.result()['snapshot_id']
        records.append({'mode': 'formation_with_two_readers', 'seconds': round(time.perf_counter()-started, 6),
                        'full_reads': {k:v for k,v in calls.items() if k in full_names}, 'db': metrics})
        if hasattr(store, 'list_document_summaries'):
            import ast
            from pathlib import Path
            module = ast.parse(Path('src/workflows/workflow_documents_cutover_v1.py').read_text())
            plans = {}
            for name, params in [('document_processing_inputs', ([sid],)), ('document_diagnostic_inputs', ([sid],))]:
                method = next(n for n in ast.walk(module) if isinstance(n, ast.FunctionDef) and n.name == name)
                query = next(n.args[0].value for n in ast.walk(method) if isinstance(n, ast.Call)
                             and isinstance(n.func, ast.Attribute) and n.func.attr == 'execute'
                             and n.args and isinstance(n.args[0], ast.Constant)
                             and ('WITH latest' in n.args[0].value if name == 'document_diagnostic_inputs'
                                  else 'FROM workflow.documents d' in n.args[0].value))
                with store._connect() as con:
                    plan = con.execute('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ' + query, params).fetchone()['QUERY PLAN'][0]
                plans[name] = {'execution_ms': plan['Execution Time'], 'planning_ms': plan['Planning Time'],
                               'shared_hit_blocks': plan['Plan'].get('Shared Hit Blocks'),
                               'shared_read_blocks': plan['Plan'].get('Shared Read Blocks')}
            print('READ_ARCHITECTURE_QUERY_PLANS', json.dumps(plans, sort_keys=True))
        print('READ_ARCHITECTURE_BENCHMARK', json.dumps({'revision': subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip(), 'fixture': {'documents': 1,
            'replay_records': 4000, 'envelope_bytes': sizes['get_envelope'],
            'source': 'synthetic HTML', 'database': 'PostgreSQL16', 'roles': ['researcher','assigned_reviewer']},
            'samples': records}, sort_keys=True))
    finally:
        set_json_loads(native_loads)
        endpoint.dependant.call = original_call
