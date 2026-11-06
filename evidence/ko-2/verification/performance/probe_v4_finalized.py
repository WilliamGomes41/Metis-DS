"""KO2 v3 diagnostic: actual compact head form, standalone receipt and continuation cost.

The earlier frozen probes remain evidence for the rejected a16 implementation.
This adapter changes public form/navigation inputs after the user's new-page GO;
it retains the fixture sizes, durable-work checks and unchanged10% budget.
"""
from contextlib import contextmanager
from html.parser import HTMLParser
from pathlib import Path
import json
import logging
import os
import subprocess
import time

import httpx
import socket
import sys
from tests.semantic_fixture_support import bind_fixture_selections

ROOT = Path(__file__).resolve().parents[1]
OBSERVER_PHASE = "setup"


class PublicForm(HTMLParser):
    def __init__(self, marker):
        super().__init__()
        self.marker = marker
        self.active = False
        self.hidden = {}
        self.action = ''

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form' and self.marker in attrs:
            self.active = True
            self.action = attrs.get('action', '')
        if self.active and tag == 'input' and attrs.get('type') == 'hidden':
            self.hidden[attrs.get('name', '')] = attrs.get('value', '')

    def handle_endtag(self, tag):
        if tag == 'form':
            self.active = False


class PublicLink(HTMLParser):
    def __init__(self, marker):
        super().__init__()
        self.marker = marker
        self.href = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and self.marker in attrs:
            if self.href is not None:
                raise AssertionError('Ambiguous continuation link')
            self.href = attrs.get('href')


def measure(send):
    started = time.perf_counter()
    response = send()
    wall_ms = (time.perf_counter() - started) * 1000
    assert response.status_code == 200, (response.status_code, response.text[:300])
    ids = [r.headers['x-metis-request-id'] for r in [*response.history, response]]
    return response, {
        'status': response.status_code,
        'redirect_statuses': [r.status_code for r in response.history],
        'wall_ms': wall_ms,
        'request_ids': ids,
        'response_bytes': len(response.content),
        'final_url': str(response.url),
        'history_locations': [r.headers.get('location') for r in response.history],
    }


def attach_server_evidence(metric, records):
    if metric is None:
        return
    rows = [records[request_id] for request_id in metric['request_ids']]
    assert all(row['outcome'] == 'completed' and row['status'] < 400 and not row.get('error') for row in rows), rows
    metric.update(requests=rows,
        server_ms=sum(row['elapsed_ms'] for row in rows),
        db_json_bytes=sum((row.get('db') or {}).get('db_json_bytes', 0) for row in rows),
        db_queries=sum((row.get('db') or {}).get('db_queries', 0) for row in rows))


def combined(first, continuation):
    if continuation is None:
        return {**first, 'continuation_required': False}
    return {
        **first,
        **{key: first[key] + continuation[key] for key in
           ('wall_ms', 'response_bytes')},
        'request_ids': [*first['request_ids'], *continuation['request_ids']],
        'continuation_required': True,
        'continuation_redirect_statuses': continuation['redirect_statuses'],
    }


def legacy_fixture(console, paragraphs=923, selected=92):
    author = console.create_account(username='author', password='fixture-only', roles=('researcher',))
    reviewer = console.create_account(username='reviewer', password='fixture-only', roles=('reviewer',))
    texts = [f'Begrip {i} is een beschrijving van een afzonderlijke waarneming in de zorg. De verpleegkundige legt waarneming {i} vast.' for i in range(paragraphs)]
    step = max(1, paragraphs // selected)
    bind_fixture_selections(console, [(text, 'definition') for text in texts[::step][:selected]])
    sid = console.ingest(actor_id=author['account_id'], filename='source.html', content_type='text/html',
        data=('<html><body><h1>Richtlijn</h1>' + ''.join(f'<p>{t}</p>' for t in texts) + '</body></html>').encode(),
        ingest_kind='new', title='KO2 performance synthetic', version='1.0', date='2026-11-06', live_url='',
        class_='richtlijn', family='probe', named_reviewers=[reviewer['account_id']])['snapshot_id']
    return sid, 'definition', selected, paragraphs


def native_fixture(console, tmp_path, monkeypatch):
    from tests.test_review_formation_problems import received, execute
    source = ('<html><body><h1>Adviezen</h1>' + ''.join(
        f'<p>Gebruik geen middel {i:04d} bij deze synthetische situatie; bespreek de beschreven waarneming en leg de gemaakte keuze vast volgens deze afzonderlijke passage.</p>'
        for i in range(128)) + '</body></html>').encode()
    def factory(**options):
        return console
    _, sid, author, reviewer, calls, mode, provider = received(
        tmp_path, factory, monkeypatch, source_html=source, all_blocks=True)
    mode['broken'] = False
    execute(console, sid, author, 'native-perf')
    return sid, 'recommendation', 128, 128


def test_perf(tmp_path, production_console, production_app, monkeypatch, request):
    global OBSERVER_PHASE
    head_mode = os.getenv('KO2_EXPECT_RECEIPT') == '1'
    fixture = os.getenv('KO2_FIXTURE', 'legacy')
    assert fixture in {'legacy', 'native'}
    console = production_console(root=tmp_path, processing_binder=bind_fixture_selections)
    sid, kind, selected, paragraphs = (native_fixture(console, tmp_path, monkeypatch)
        if fixture == 'native' else legacy_fixture(console))
    candidates = [o for o in console.snapshot_objects(sid) if o.get('proposed_object_type') == kind]
    assert len(candidates) == selected
    dest = Path(os.environ['KO2_OUT'])
    dest.mkdir(parents=True, exist_ok=True)
    prefix = f"{fixture}-{os.getenv('KO2_LABEL', 'sanity')}-{os.getenv('KO2_ROUND', '0')}"
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    before_objects = console.snapshot_objects(sid)
    before_revision = console.objects_revision(sid)
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    sock.close()
    config = {'root': str(console.root), 'dsn': console.workflow_document_store.config.dsn,
        'runtime': str(console.runtime), 'source_store': str(console.source_store), 'port': port,
        'sha': sha, 'ready_metadata': str(dest / (prefix + '-server.json'))}
    config_path = tmp_path / 'server-config.json'
    config_path.write_text(json.dumps(config))
    server_log_path = dest / (prefix + '-server.log')
    server_log = server_log_path.open('w')
    child = subprocess.Popen([sys.executable, '/tmp/ko2-perf/server_v4.py', str(config_path)],
        cwd=ROOT, env={**os.environ, 'PYTHONPATH': str(ROOT)}, stdout=server_log, stderr=server_log)
    def stop_child():
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
        server_log.close()
    request.addfinalizer(stop_child)
    deadline = time.monotonic() + 30
    while True:
        assert child.poll() is None, server_log_path.read_text()[-8000:]
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=.2):
                break
        except OSError:
            assert time.monotonic() < deadline, server_log_path.read_text()[-8000:]
            time.sleep(.05)
    assert console.snapshot_objects(sid) == before_objects, 'Ordinary restart mutated persisted objects'
    assert console.objects_revision(sid) == before_revision, 'Ordinary restart changed source revision'
    client = httpx.Client(base_url=f'https://127.0.0.1:{port}', verify=__import__('ssl').create_default_context(cafile='/tmp/ko2-perf/server-v4.crt'), timeout=60, follow_redirects=True, trust_env=False)
    request.addfinalizer(client.close)
    assert client.post('/login', data={'username': 'reviewer', 'password': 'fixture-only'}, follow_redirects=False).status_code == 303
    receipt = {
        'probe_version': 4,
        'log_finalize_version': 'v4-after-server-stop',
        'observer_placement': 'Fresh separate HTTP child serves persisted parent-seeded fixture; client parsing and all direct verification outside child; server diagnostics parsed after all HTTP flows; default GC.',
        'head_mode': 'compact-v1-and-standalone-receipt' if head_mode else 'legacy-form-and-existing-next-destination',
        'sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'label': os.getenv('KO2_LABEL', 'sanity'),
        'round': int(os.getenv('KO2_ROUND', '0')),
        'paragraphs': paragraphs, 'candidate_count': selected, 'fixture': fixture,
        'card': [], 'save_to_receipt': [], 'continue': [], 'save': [],
    }
    proofs = []
    for obj in candidates[:int(os.getenv('KO2_SAMPLES', '3'))]:
        OBSERVER_PHASE = 'card'
        get = lambda: client.get('/review', params={'document': sid, 'object': obj['object_id'], 'task': 'contextual'})
        assert get().status_code == 200
        page, card = measure(get)
        assert obj['content']['clean_text'] in page.text
        assert 'data-review-receipt' not in page.text
        receipt['card'].append(card)
        OBSERVER_PHASE = 'form_parse'
        parser = PublicForm('data-ko-assessment-form' if head_mode else 'data-review-form')
        parser.feed(page.text)
        hidden = parser.hidden
        assert parser.action == '/review', parser.action
        assert hidden.get('interaction_id') and hidden.get('snapshot_revision'), sorted(hidden)
        assert hidden.get('snapshot_id') == sid and hidden.get('object_id') == obj['object_id']
        data = {**hidden, 'return_task': 'contextual'}
        if head_mode:
            assert hidden.get('review_ui') == 'compact-v1'
            data.update(applicable='yes', complete='yes', placed_correctly='yes', review_action='approve')
        else:
            data.update(suitability='ja', documentpositie_action='dit_klopt', type_action='dit_klopt',
                confirmed_object_type=kind, relation_review_ack='1', eindoordeel='goedkeuren', decision='approve')
            if kind == 'recommendation':
                data.update(recommendation_direction='against', recommendation_strength_level='not_stated')
        OBSERVER_PHASE = 'save_to_receipt'
        saved, save_to_receipt = measure(lambda: client.post(parser.action, data=data, follow_redirects=True))
        assert save_to_receipt['redirect_statuses'][0] == 303
        continuation_metrics = None
        if head_mode:
            assert 'data-review-receipt' in saved.text and obj['content']['clean_text'] in saved.text
            assert 'data-ko-assessment-form' not in saved.text, 'Receipt is not standalone'
            link = PublicLink('data-ko-next-passage')
            link.feed(saved.text)
            assert link.href, 'Missing actual continuation route'
            assert 'receipt_interaction' not in link.href
            OBSERVER_PHASE = 'continue'
            next_page, continuation_metrics = measure(lambda: client.get(link.href, follow_redirects=True))
            assert 'data-review-receipt' not in next_page.text
            if fixture == 'native':
                assert 'data-ko-assessment-form' in next_page.text, 'Native continuation lost next review card'
        elif fixture == 'native':
            assert 'data-review-form' in saved.text, 'Baseline native save did not continue to next card'
        proofs.append((obj, hidden['interaction_id'], save_to_receipt))
        receipt['save_to_receipt'].append(save_to_receipt)
        receipt['continue'].append(continuation_metrics)
        receipt['save'].append(combined(save_to_receipt, continuation_metrics))
    OBSERVER_PHASE = 'verification'
    for proof_index, (obj, interaction_id, save_to_receipt) in enumerate(proofs):
        bindings = console.object_review_bindings(sid)
        own_bindings = [b for b in bindings if b['object_id'] == obj['object_id'] and b.get('valid')]
        assert len(own_bindings) == 1
        assert own_bindings[0].get('confirmed_object_type') == kind
        events = console.workflow_review_store.read_review_command_events(
            sid, [], interaction_id=interaction_id, include_pending=False)
        exact = [event for event in events if event.get('object_id') == obj['object_id']]
        assert len(exact) == 1
        assert exact[0].get('object_version') == own_bindings[0]['object_version']
        assert exact[0].get('event_type', '').endswith('_review_approve')
        if head_mode:
            assessment = ((exact[0].get('details') or {}).get('review_interaction') or {}).get('assessment')
            assert assessment == {'version': 'review-assessment-v1', 'applicable': 'yes', 'complete': 'yes', 'placed_correctly': 'yes'}, assessment
            save_to_receipt['durable_assessment_verified'] = True
        save_to_receipt['durable_binding_verified'] = True
        save_to_receipt['saved_object_version'] = own_bindings[0]['object_version']
        save_to_receipt['saved_confirmed_type'] = kind
        save_to_receipt['durable_event_verified'] = True
        save_to_receipt['receipt_present'] = head_mode
        receipt['save'][proof_index].update({key: value for key, value in save_to_receipt.items()
            if key.startswith('durable_') or key.startswith('saved_') or key == 'receipt_present'})
    if head_mode:
        OBSERVER_PHASE = 'context_expand'
        obj = candidates[-1]
        expanded, context = measure(lambda: client.get('/review/context-section', params={'document': sid, 'object': obj['object_id']}))
        assert 'data-full-section' in expanded.text
        receipt['context_expand'] = context
    client.close()
    # Persist HTTP timings/IDs and successful durable proofs before child teardown.
    (dest / (prefix + '-http-transcript.json')).write_text(json.dumps(receipt, indent=2))
    # Body delivery may precede request_finished cleanup; join the process first.
    stop_child()
    rows = []
    for line in server_log_path.read_text().splitlines():
        if line.startswith('metis_diagnostic '):
            row = json.loads(line[len('metis_diagnostic '):])
            if row.get('event') == 'request_finished':
                rows.append(row)
    assert len({r['request_id'] for r in rows}) == len(rows), 'Duplicate server completion evidence'
    by_id = {r['request_id']: r for r in rows}
    for key in ('card', 'save_to_receipt', 'continue', 'save'):
        for metric in receipt[key]:
            attach_server_evidence(metric, by_id)
    if head_mode:
        attach_server_evidence(receipt['context_expand'], by_id)
    metadata = json.loads(Path(config['ready_metadata']).read_text())
    assert metadata['pid'] != os.getpid() and metadata['parent_pid'] == os.getpid()
    assert metadata['gc_enabled'] and metadata['gc_threshold'] == list(__import__('gc').get_threshold())
    assert metadata['root'] == str(console.root) and metadata['runtime'] == str(console.runtime)
    assert metadata['source_store'] == str(console.source_store)
    receipt.update(server_process=metadata, parent_pid=os.getpid(), restart_immutability_verified=True,
        server_log=str(server_log_path), matched_server_requests=len(by_id),
        transport='real HTTPS, local trusted test certificate, fresh Uvicorn process; no TestClient',
        http_client='httpx.Client, keepalive defaults, follow_redirects, localhost, trust_env=False')
    result_path = dest / f"{fixture}-{receipt['label']}-{receipt['round']}.json"
    result_path.write_text(json.dumps(receipt, indent=2))
    stop_child()
    receipt['server_exit_code'] = child.returncode
    receipt['server_shutdown_grace_seconds'] = 15
    receipt['server_reaped_after_grace'] = child.returncode == -9
    for obj, interaction_id, metric in proofs:
        exact = [event for event in console.workflow_review_store.read_review_command_events(
            sid, [], interaction_id=interaction_id, include_pending=False)
            if event.get('object_id') == obj['object_id']]
        assert len(exact) == 1 and exact[0]['object_version'] == metric['saved_object_version']
        if head_mode:
            assert ((exact[0].get('details') or {}).get('review_interaction') or {}).get('assessment') == {
                'version': 'review-assessment-v1', 'applicable': 'yes', 'complete': 'yes', 'placed_correctly': 'yes'}
    receipt['durable_events_reverified_after_server_stop'] = True
    result_path.write_text(json.dumps(receipt, indent=2))
