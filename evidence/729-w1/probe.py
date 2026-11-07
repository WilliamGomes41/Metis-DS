"""KO4 actual approval and source-correction saves over native PostgreSQL/HTTPS."""
from copy import deepcopy
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
import hashlib
import json
import os
import socket
import ssl
import subprocess
import sys
import time

import httpx
import psycopg
from psycopg import sql

from fastapi.testclient import TestClient
from src.integrity_kernel import stamp_canonical_hashes
from src.knowledge_relations_v1 import PROPOSED_FIELD, CONFIRMED_FIELD, build_knowledge_relation
from src.review.review_ledger import read_events
from tests.production_support import restart_production
from tests.semantic_fixture_support import bind_fixture_selections, install_fixture_history

ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path(os.environ['W1_TOOLS'])
SAMPLES = 4


class Forms(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form':
            self.current = {'attrs': attrs, 'hidden': {}, 'options': set()}
            self.forms.append(self.current)
        elif self.current is not None and tag == 'input' and attrs.get('type') == 'hidden':
            self.current['hidden'][attrs['name']] = attrs.get('value', '')
        elif self.current is not None and tag == 'option':
            self.current['options'].add(attrs.get('value', ''))

    def handle_endtag(self, tag):
        if tag == 'form':
            self.current = None

    @classmethod
    def from_page(cls, text, action):
        parser = cls()
        parser.feed(text)
        matches = [f for f in parser.forms if f['attrs'].get('action') == action]
        assert len(matches) == 1, (action, len(matches))
        return matches[0]


def file_fingerprint(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file()}


def canonical_fingerprint(dsn):
    """Public canonical tables must not be changed by a working review save."""
    result = {}
    with psycopg.connect(dsn) as con:
        tables = con.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").fetchall()
        for (table,) in tables:
            rows = con.execute(sql.SQL('SELECT to_jsonb(t)::text FROM public.{} t ORDER BY to_jsonb(t)::text').format(sql.Identifier(table))).fetchall()
            result[table] = hashlib.sha256('\n'.join(r[0] for r in rows).encode()).hexdigest()
    return result


def stop_child(child, log):
    forced = False
    if child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=15)
        except subprocess.TimeoutExpired:
            forced = True
            child.kill()
            child.wait(timeout=5)
    log.close()
    return forced


def serve_and_measure(config, operation, tasks, out, prefix, request):
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    sock.close()
    metadata = out / f'{prefix}-{operation}-worker.json'
    cfg = out / f'{prefix}-{operation}-config.json'
    cfg.write_text(json.dumps({**config, 'metadata': str(metadata)}))
    log_path = out / f'{prefix}-{operation}-server.log'
    log = log_path.open('w')
    env = {**os.environ, 'KO4_SERVER_CONFIG': str(cfg),
           'PYTHONPATH': str(TOOLS) + ':' + str(ROOT)}
    assert not env.get('GUNICORN_CMD_ARGS'), 'Do not override the production default timeout'
    child = subprocess.Popen([sys.executable, '-m', 'gunicorn', '-w', '1',
        '-k', 'uvicorn.workers.UvicornWorker', 'server:app', '--bind', f'127.0.0.1:{port}',
        '--certfile', str(TOOLS / 'server.crt'), '--keyfile', str(TOOLS / 'server.key'),
        '--log-level', 'warning'], cwd=ROOT, env=env, stdout=log, stderr=log)
    request.addfinalizer(lambda: stop_child(child, log) if not log.closed else None)
    deadline = time.monotonic() + 40
    while True:
        assert child.poll() is None, log_path.read_text()[-2000:]
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=.2):
                break
        except OSError:
            assert time.monotonic() < deadline
            time.sleep(.05)
    base = f'https://127.0.0.1:{port}'
    client = httpx.Client(base_url=base, verify=ssl.create_default_context(cafile=str(TOOLS / 'server.crt')),
                         timeout=35, trust_env=False, follow_redirects=False)
    request.addfinalizer(client.close)
    assert client.post('/login', data={'username': 'reviewer', 'password': 'fixture-only'},
                       headers={'Origin': base}).status_code == 303
    observations = []
    for sample, task in enumerate(tasks, 1):
        action_started = time.perf_counter()
        if operation == 'approve':
            page = client.get('/review', params={'document': config['snapshot'], 'object': task['object_id']})
            assert page.status_code == 200
            form = Forms.from_page(page.text, '/review')
            assert 'data-ko-assessment-form' in form['attrs']
            payload = {**form['hidden'], 'review_action': 'approve',
                       'applicable': 'yes', 'complete': 'yes', 'placed_correctly': 'yes'}
            path = '/review'
        else:
            page = client.get('/source-selection', params={'document': config['snapshot'],
                'object': task['object_id'], 'task': 'repair', 'repair_kind': 'source_units'})
            assert page.status_code == 200
            form = Forms.from_page(page.text, '/review/resolve')
            assert task['unit_id'] in form['options']
            payload = {**form['hidden'], 'source_unit_ids': [task['unit_id']],
                       'comment': 'Gebruik deze exacte bronzin als nieuw voorstel.'}
            path = '/review/resolve'
        form_get_ms = (time.perf_counter() - action_started) * 1000
        started = time.perf_counter()
        try:
            response = client.post(path, data=payload, headers={'Origin': base})
        except Exception as exc:
            failed = {'sample': sample, 'object_id': task['object_id'],
                'wall_ms': (time.perf_counter() - started) * 1000, 'error': repr(exc)}
            (out / f'{prefix}-{operation}-failed-observation.json').write_text(json.dumps(failed))
            raise
        observations.append({'sample': sample, 'object_id': task['object_id'],
            'wall_ms': (time.perf_counter() - started) * 1000,
            'status': response.status_code, 'location': response.headers.get('location', ''),
            'request_id': response.headers.get('x-metis-request-id', ''),
            'response_bytes': len(response.content)})
        if response.status_code != 303:
            (out / f'{prefix}-{operation}-failed-response.html').write_text(response.text)
            (out / f'{prefix}-{operation}-failed-observation.json').write_text(json.dumps(observations))
            raise AssertionError((operation, response.status_code, response.text[-500:]))
        if operation == 'correct':
            next_started = time.perf_counter()
            next_page = client.get(response.headers['location'])
            assert next_page.status_code == 200
            next_ms = (time.perf_counter() - next_started) * 1000
            reopen_started = time.perf_counter()
            reopened_page = client.get('/source-selection', params={'document': config['snapshot'],
                'object': task['object_id'], 'task': 'repair', 'repair_kind': 'source_units'})
            assert reopened_page.status_code == 200
            observations[-1].update(form_get_ms=form_get_ms, redirect_get_ms=next_ms,
                reopen_get_ms=(time.perf_counter() - reopen_started) * 1000,
                complete_action_ms=(time.perf_counter() - action_started) * 1000)
    client.close()
    forced = stop_child(child, log)
    return {'operation': operation, 'observations': observations, 'log_path': str(log_path),
            'metadata_path': str(metadata), 'exit_code': child.returncode, 'forced_reap': forced}


def test_perf(tmp_path, production_console, request):
    os.environ.setdefault('METIS_AUDIT_HMAC_KEY', 'ko4-performance-test-only')
    side = os.environ['KO4_SIDE']
    round_id = int(os.environ['KO4_ROUND'])
    out = Path(os.environ['KO4_OUT'])
    prefix = f'{side}-{round_id}'
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    console = production_console(root=tmp_path, processing_binder=bind_fixture_selections)
    author = console.create_account(username='author', password='fixture-only', roles=('researcher',))
    reviewer = console.create_account(username='reviewer', password='fixture-only', roles=('reviewer',))
    texts = [f'Begrip {i} is een beschrijving van een afzonderlijke waarneming in de zorg. '
             f'De verpleegkundige legt waarneming {i} vast.' for i in range(923)]
    selected = texts[::10][:92]
    bind_fixture_selections(console, [(text, 'definition') for text in selected])
    sid = console.ingest(actor_id=author['account_id'], filename='source.html', content_type='text/html',
        data=('<html><body><h1>Richtlijn</h1>' + ''.join(f'<p>{t}</p>' for t in texts) + '</body></html>').encode(),
        ingest_kind='new', title='KO4 performance synthetic', version='1.0', date='2026-11-06',
        live_url='', class_='richtlijn', family='ko4-perf', named_reviewers=[reviewer['account_id']])['snapshot_id']
    rows = console.snapshot_objects(sid, include_blocked=True)
    by_text = {str((o.get('content') or {}).get('clean_text') or ''): o for o in rows}
    candidates = [by_text[t] for t in selected]
    assert len(candidates) == 92 and len(console.review_source_fragments(sid)) == 924
    approvals = []
    history = console._load_objects(sid)
    for i in range(SAMPLES):
        support, claim = candidates[2*i], candidates[2*i + 1]
        row = next(o for o in history if o['object_id'] == claim['object_id']
                   and o['object_version'] == claim['object_version'])
        relation = build_knowledge_relation(source_object_id=claim['object_id'],
            source_object_version=claim['object_version'], relation_type='supported_by',
            target_object_id=support['object_id'], target_object_version=support['object_version'])
        row[PROPOSED_FIELD] = [relation]
        row['relations'] = [{'relation_type': 'supported_by', 'target_object_id': support['object_id'],
            'target_object_version': support['object_version'], 'confirmed': False}]
        stamp_canonical_hashes(row)
        approvals.append({'object_id': claim['object_id']})
    # Synthetic model proposals are fixture inputs. Confirmation and reopening
    # are real existing commands, outside every measured request.
    install_fixture_history(console, sid, history)
    with TestClient(console._metis_test_application, base_url='https://testserver') as setup:
        assert setup.post('/login', data={'username': 'reviewer', 'password': 'fixture-only'},
                          follow_redirects=False).status_code == 303
        for task in approvals:
            page = setup.get('/review', params={'document': sid, 'object': task['object_id']})
            form = Forms.from_page(page.text, '/review')
            response = setup.post('/review', data={**form['hidden'], 'review_action': 'approve',
                'applicable': 'yes', 'complete': 'yes', 'placed_correctly': 'yes'},
                follow_redirects=False)
            assert response.status_code == 303, response.text[-1000:]
            console.confirm_object_type(actor_id=reviewer['account_id'], snapshot_id=sid,
                object_id=task['object_id'], confirmed_object_type='explanation',
                expected_revision=console.objects_revision(sid))
            claim = console._current_object(sid, task['object_id'])
            assert claim['governance']['validation_status'] == 'needs_review'
            assert any(r['relation_type'] == 'supported_by' for r in claim[CONFIRMED_FIELD])
    corrections = []
    for obj in candidates[8:12]:
        own = {str(ref.get('raw_object_id') or '') for ref in obj['provenance']['source_fragments']}
        units = [u for u in console.source_units(snapshot_id=sid, object_id=obj['object_id'])
                 if u['fragment_id'] in own]
        assert len(units) >= 2
        corrections.append({'object_id': obj['object_id'], 'unit_id': units[0]['unit_id'],
                            'expected_text': units[0]['text']})
    before = {o['object_id']: deepcopy(o) for o in console.snapshot_objects(sid, include_blocked=True)}
    before_source = file_fingerprint(Path(console.source_store))
    before_canonical = canonical_fingerprint(console.workflow_document_store.config.dsn)
    before_events = read_events(console._ledger_path)
    config = {'checkout': str(ROOT), 'sha': sha, 'root': str(console.root),
        'runtime': str(console.runtime), 'source_store': str(console.source_store),
        'dsn': console.workflow_document_store.config.dsn, 'snapshot': sid}
    runs = []
    for operation, tasks in [('approve', approvals), ('correct', corrections)]:
        runs.append(serve_and_measure(config, operation, tasks, out, prefix, request))
    # All proof reads and log parsing follow both complete timed paths.
    reopened = restart_production(console)
    after = {o['object_id']: o for o in reopened.snapshot_objects(sid, include_blocked=True)}
    mutated = {t['object_id'] for t in approvals + corrections}
    assert {k: v for k, v in before.items() if k not in mutated} == {k: v for k, v in after.items() if k not in mutated}
    assert file_fingerprint(Path(console.source_store)) == before_source
    assert canonical_fingerprint(console.workflow_document_store.config.dsn) == before_canonical
    bindings = reopened.object_review_bindings(sid)
    approval_bindings = [b for b in bindings if b.get('valid') and b.get('decision') == 'approve']
    assert len(approval_bindings) == SAMPLES
    assert {b['object_id'] for b in approval_bindings} == {t['object_id'] for t in approvals}
    for task in approvals:
        obj = after[task['object_id']]
        assert obj['governance']['validation_status'] == 'approved'
        assert len([b for b in approval_bindings if b['object_id'] == task['object_id']]) == 1
    for task in corrections:
        obj = after[task['object_id']]
        assert obj['object_version'] != before[task['object_id']]['object_version']
        assert obj['governance']['validation_status'] == 'needs_review'
        assert obj['content']['clean_text'] == task['expected_text']
        assert not any(b.get('valid') and b['object_id'] == task['object_id'] for b in bindings)
    assert not any(o.get('governance', {}).get('validation_status') == 'revise' for o in after.values())
    events = read_events(reopened._ledger_path)
    assert events[:len(before_events)] == before_events
    new_events = events[len(before_events):]
    approved_events = [e for e in new_events if e['event_type'].endswith('_review_approve')]
    assert len(approved_events) == SAMPLES
    for event in approved_events:
        assessment = event['details']['review_interaction']['assessment']
        assert all(assessment.get(k) == 'yes' for k in ['applicable', 'complete', 'placed_correctly'])
    all_metrics = {}
    for run in runs:
        assert not run['forced_reap']
        meta = json.loads(Path(run['metadata_path']).read_text())
        assert meta['sha'] == sha and meta['gc_enabled'] and meta['gunicorn_default_timeout_seconds'] == 30
        records = {}
        for line in Path(run['log_path']).read_text().splitlines():
            if line.startswith('metis_diagnostic '):
                row = json.loads(line[len('metis_diagnostic '):])
                if row.get('event') == 'request_finished':
                    assert row['request_id'] not in records
                    records[row['request_id']] = row
        operation = run['operation']
        for metric in run['observations']:
            row = records[metric['request_id']]
            assert row['status'] == 303 and row['outcome'] == 'completed' and not row.get('error')
            metric.update(server_ms=row['elapsed_ms'], db_queries=row.get('db', {}).get('db_queries', 0),
                db_json_bytes=row.get('db', {}).get('db_json_bytes', 0),
                physical_connections=row.get('db', {}).get('db_connections', 0))
            metric.update(outer_lock_ms=row.get('phases', {}).get('store_lock_hold', {}).get('inclusive_ms', 0),
                transaction_ms=row.get('phases', {}).get('store_transaction', {}).get('inclusive_ms', 0))
            query = parse_qs(urlparse(metric['location']).query)
            assert query.get('document') == [sid]
            if operation == 'approve':
                assert query.get('receipt_interaction')
                assert any(e['details']['review_interaction']['interaction_id'] == query['receipt_interaction'][0]
                           for e in approved_events)
            else:
                assert query.get('repair_saved') == ['yes']
        all_metrics[operation] = run['observations']
    outcome = {'version': 1, 'sha': sha, 'side': side, 'round': round_id,
        'fixture': {'paragraphs': 923, 'raw_source_fragments': 924, 'candidates': 92,
                    'approval_tasks_with_real_support': 4, 'correction_tasks': 4},
        'metrics': all_metrics, 'workers': [json.loads(Path(r['metadata_path']).read_text()) for r in runs],
        'proofs': {'approved_exact_bindings': 4, 'new_open_corrections': 4,
            'three_yes_recorded': True, 'untargeted_objects_unchanged': True,
            'source_files_unchanged': True, 'canonical_store_unchanged': True,
            'persisted_after_restart': True, 'no_persisted_revise': True},
        'measurement_scope': 'POST response separately; correction also measures form GET, redirect GET and reopen GET without user think time',
        'observer_scope': 'All business proofs and finalized log parsing after both timed paths; no forced GC.'}
    (out / f'{prefix}.json').write_text(json.dumps(outcome, indent=2))
