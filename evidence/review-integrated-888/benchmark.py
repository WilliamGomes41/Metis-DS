"""Opt-in native PG/ASGI comparison; see README.md for the evidence boundaries.

REVIEW_PROOF_OUTPUT=/tmp/proof.json python -m pytest -q -p tests.conftest \
    evidence/review-integrated-888/benchmark.py
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import re
import subprocess
from time import perf_counter

from fastapi.testclient import TestClient
import pytest

from tests.semantic_fixture_support import bind_fixture_selections


def request_progress(label, action, *, index=None, status=None):
    """Retain started requests too, including if a worker is later interrupted."""
    path = Path(os.environ['REVIEW_PROOF_OUTPUT']).with_suffix('.progress.json')
    rows = json.loads(path.read_text()) if path.exists() else []
    if index is None:
        index = len(rows)
        rows.append({'case': 'request_progress', 'workload': label, 'action': action, 'state': 'started'})
    else:
        rows[index].update(state='finished', http_status=status)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2) + '\n')
    return index


def safe_sql_categories(monkeypatch):
    """Transparent native driver observation; retain only fixed categories/counts."""
    import psycopg
    active, categories, owners = [False], {}, {}
    execute = psycopg.Cursor.execute
    def category(query):
        sql = query.lower() if isinstance(query, str) else ''
        operation = sql.lstrip().split(' ', 1)[0]
        write = operation in {'insert', 'update', 'delete'}
        if 'workflow.publish_authorizations' in sql:
            return 'binding_write' if write else 'binding_read'
        if 'workflow.document_objects' in sql:
            return 'object_write' if write else 'object_read'
        if 'workflow.documents' in sql:
            return 'document_lock' if 'for update' in sql else 'document_write' if write else 'document_read'
        if 'workflow.review_events' in sql:
            return 'review_audit'
        if 'workflow.accounts' in sql or 'workflow.sessions' in sql:
            return 'identity'
        if 'pg_advisory' in sql:
            return 'advisory_lock'
        if 'workflow.formation_' in sql or 'workflow.processing_' in sql:
            return 'formation'
        if 'publication_releases' in sql or 'audit_events' in sql:
            return 'publication'
        return 'other'
    def entry(name):
        return categories.setdefault(name, {'execute_count': 0, 'execute_ms': 0,
            'fetch_count': 0, 'fetch_ms': 0, 'fetched_rows': 0, 'affected_write_rows': 0, 'errors': 0})
    def observed_execute(cursor, query, *args, **kwargs):
        if not active[0]:
            return execute(cursor, query, *args, **kwargs)
        name = category(query)
        owners[id(cursor)] = name
        stats = entry(name)
        stats['execute_count'] += 1
        start = perf_counter()
        try:
            result = execute(cursor, query, *args, **kwargs)
            operation = query.lstrip().split(None, 1)[0].lower() if isinstance(query, str) and query.strip() else ''
            if operation in {'insert', 'update', 'delete'}:
                stats['affected_write_rows'] += max(cursor.rowcount, 0)
            return result
        except BaseException:
            stats['errors'] += 1
            raise
        finally:
            stats['execute_ms'] += (perf_counter() - start) * 1000
    monkeypatch.setattr(psycopg.Cursor, 'execute', observed_execute)
    for method in ('fetchone', 'fetchmany', 'fetchall'):
        original = getattr(psycopg.Cursor, method)
        def observed_fetch(cursor, *args, _original=original, _method=method, **kwargs):
            if not active[0]:
                return _original(cursor, *args, **kwargs)
            stats = entry(owners.get(id(cursor), 'other'))
            stats['fetch_count'] += 1
            start = perf_counter()
            try:
                rows = _original(cursor, *args, **kwargs)
                stats['fetched_rows'] += int(rows is not None) if _method == 'fetchone' else len(rows)
                return rows
            finally:
                stats['fetch_ms'] += (perf_counter() - start) * 1000
        monkeypatch.setattr(psycopg.Cursor, method, observed_fetch)
    return active, categories, owners


CASES = {
    'small': (20, False, 1),
    'continued150': (150, True, 1),
    'continued600': (600, True, 1),
    'occupied_batch': (300, False, 1),
    'complex': (20, False, 1),
    'multiple': (20, False, 3),
}


def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()


def durable(console, ids):
    store = console.workflow_document_store
    return deepcopy({
        'envelopes': [store.get_envelope(sid) for sid in ids],
        'objects': [store.list_document_objects(sid) for sid in ids],
        'bindings': console.workflow_review_store.read_bindings(ids),
        'events': console.workflow_review_store.read_events(),
        'commands': console.workflow_review_store.read_command_events(),
    })


def append_post_fixture_revision(console, sid, oid, actor):
    """Advance the current version; never edit an earlier history occurrence."""
    from src.review.revision_workflow import current_revisions, revise_object, with_current_revision
    rows = console._load_objects(sid)
    previous = next(o for o in current_revisions(rows, snapshot_id=sid) if o['object_id'] == oid)
    successor = revise_object(previous, deepcopy(previous), snapshot_id=sid,
        reason='Synthetic history load', actor=actor, force=True)
    assert successor['object_version'] != previous['object_version']
    console._save_objects(sid, with_current_revision(rows, successor),
                          expected_revision=console.objects_revision(sid))


def seed_post_history(console, sid, candidates, reviewer, depth):
    """Synthetic load via real approvals and validated append-order revisions."""

    def approve(oid):
        candidate = next(o for o in candidates if o['object_id'] == oid)
        kind = candidate.get('proposed_object_type') or 'definition'
        console.review_object(actor_id=reviewer['account_id'], snapshot_id=sid, object_id=oid,
            decision='approve', confirmed_object_type=kind, suitability='ja',
            recommendation_direction=('against' if 'geen' in candidate['content']['clean_text'] else 'for') if kind == 'recommendation' else None,
            recommendation_strength_level='not_stated' if kind == 'recommendation' else None,
            documentpositie_action='dit_klopt', type_action='dit_klopt',
            relation_review_ack=True, expected_revision=console.objects_revision(sid))

    # Keep focal and conflict-control objects untouched. Seed independent objects.
    for number, candidate in enumerate(candidates[2:]):
        oid = candidate['object_id']
        for _ in range(depth):
            approve(oid)
            append_post_fixture_revision(console, sid, oid, reviewer['account_id'])
        if number % 2 == 0:
            approve(oid)


def post_with_native_row_blocker(console, sid, send):
    """Hold a real row lock, observe its waiter, release in every failure path."""
    from time import sleep

    store = console.workflow_document_store
    with store._connect() as blocker, store._connect() as observer:
        observer.autocommit = True
        observer.execute("SET statement_timeout = '2s'")
        assert blocker.execute(
            'SELECT snapshot_id FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE', (sid,)).fetchone()
        blocker_pid = blocker.info.backend_pid
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(send)
            observed = None
            try:
                deadline = perf_counter() + 15
                while perf_counter() < deadline:
                    rows = observer.execute(
                        "SELECT wait_event_type,wait_event,"
                        "CASE WHEN query ILIKE 'SELECT%%FROM workflow.documents%%FOR UPDATE%%' "
                        "THEN 'document_row_lock' ELSE 'other_statement' END AS category "
                        "FROM pg_stat_activity WHERE datname=current_database() "
                        "AND %s=ANY(pg_blocking_pids(pid))", (blocker_pid,)).fetchall()
                    if rows:
                        assert len(rows) == 1
                        observed = dict(rows[0])
                        break
                    assert not future.done(), 'POST completed without reaching the controlled row lock'
                    sleep(0.01)
                assert observed is not None, 'native POST lock wait was not observed before deadline'
                assert observed['wait_event_type'] == 'Lock'
                assert observed['category'] == 'document_row_lock'
                assert not future.done()
            finally:
                blocker.rollback()
            response = future.result(timeout=60)
    # No backend IDs, SQL text, database identity or parameters leave the probe.
    return response, {'controlled': True, 'boundary': 'workflow_document_row',
                      'wait_event_type': observed['wait_event_type'],
                      'wait_event': observed['wait_event'], 'query_category': observed['category'],
                      'waiter_observed': True, 'completed_after_release': True,
                      'production_cause_proven': False}


@pytest.mark.parametrize('case', os.environ.get('REVIEW_PROOF_CASES', ','.join(CASES)).split(','))
def test_native_review_matrix(case, tmp_path, production_console, production_app, monkeypatch):
    import src.vorming.source_reconstruction_v1 as reconstruction
    from src.request_diagnostics_v1 import RequestDiagnostics
    from src.vorming.source_preparation_context_v1 import stored_extraction
    from src.vorming.semantic_passage_v1 import semantic_source_blocks
    import src.console_performance_v1 as performance
    import src.review.review_workboard_v1 as workboard

    assert Path(reconstruction.__file__).resolve().is_relative_to(Path.cwd().resolve()), \
        'pytest imported code from a different checkout; this measurement is invalid'

    repeats = int(os.environ.get('REVIEW_PROOF_REPEATS', '7'))
    assert repeats >= 1
    size, continued, documents = CASES[case]
    console = production_console(root=tmp_path, processing_binder=lambda _: None)
    author = console.create_account(username='author', password='fixture-only', roles=('researcher',))
    reviewer = console.create_account(username='reviewer', password='fixture-only', roles=('reviewer',))
    outsider = console.create_account(username='outsider', password='fixture-only', roles=('reviewer',))
    monkeypatch.setattr(workboard, '_observed_at', lambda: '2026-10-28T09:00:00+00:00')
    # Suppress transport logging, retain original diagnostics and metric accounting.
    monkeypatch.setattr(performance._LOGGER, 'info', lambda *args, **kwargs: None)
    texts = [f'begrip {i:04d} is een beschrijving van een afzonderlijke waarneming' +
             ('' if continued else '.') for i in range(size)]
    source = ('<html><body><h1>Bronindeling</h1>' +
              ''.join(f'<p>{text}</p>' for text in texts) + '</body></html>').encode()
    if case == 'complex':
        source = ('<html><body><h1>Bronindeling</h1><h2>Waarneming</h2>' +
            ''.join(f'<p>{text}</p>' for text in texts[:10]) +
            '<h2>Meetgegevens</h2><table><tr><th>Meetpunt</th><th>Waarde</th></tr>'
            '<tr><td>Rust</td><td>20</td></tr></table>' +
            ''.join(f'<p>{text}</p>' for text in texts[10:]) + '</body></html>').encode()
    # A single complete selection in continuing text, one per paragraph otherwise.
    selections = [(' '.join(texts), 'definition')] if continued else [(s, 'definition') for s in texts]
    bind_fixture_selections(console, selections)
    ids, manifests = [], []
    for number in range(documents):
        sid = console.ingest(actor_id=author['account_id'], filename=f'source-{number}.html',
            content_type='text/html', data=source, ingest_kind='new', title=f'Proof document {number}',
            version='1.0', date='2026-10-28', live_url='', class_='richtlijn', family='fixture',
            named_reviewers=[reviewer['account_id']])['snapshot_id']
        ids.append(sid)
        envelope = console.workflow_document_store.get_envelope(sid)
        fragments = stored_extraction(envelope)
        blocks = semantic_source_blocks(fragments)
        rows = console.snapshot_objects(sid)
        candidates = [o for o in rows if (o.get('metadata') or {}).get('semantic_passage', {}).get('spans')]
        assert candidates
        assert not console.processing_status(sid)['formation_incomplete']
        manifests.append({'source_sha256': sha256(source).hexdigest(), 'source_bytes': len(source),
            'fragments': len(fragments), 'blocks': len(blocks), 'objects': len(rows),
            'candidates': len(candidates), 'bindings': len(console.workflow_review_store.read_bindings([sid])),
            'source_contract': envelope['prepared_source_extraction']['version'],
            'continued': continued})
    sid = ids[0]
    obj = next(o for o in console.snapshot_objects(sid)
               if (o.get('metadata') or {}).get('semantic_passage', {}).get('spans'))
    routes = {
        'overview': {}, 'individual': {'document': sid, 'task': 'individual'},
        'inventory': {'document': sid, 'task': 'inventory'},
        'batch': {'document': sid, 'task': 'batch'},
        'passage': {'document': sid, 'object': obj['object_id']},
    }
    # Only aggregate values are retained: no cookies, actor IDs or request IDs.
    evidence = []
    def emit(_self, payload):
        if payload.get('event') == 'request_finished' and payload.get('route') == '/review':
            evidence.append({key: payload[key] for key in ('elapsed_ms', 'status', 'outcome', 'phases',
                'phase_tree', 'counters', 'db', 'unattributed_lower_bound_ms', 'phase_tree_truncated', 'error')
                if key in payload})
    monkeypatch.setattr(RequestDiagnostics, 'emit', emit)
    result = {'case': case, 'commit': git('rev-parse', 'HEAD'),
        'production_diff': git('diff', 'HEAD', '--', 'src'),
        'harness_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'reconstruction_sha256': sha256(Path(reconstruction.__file__).read_bytes()).hexdigest(),
        'python': platform.python_version(), 'postgres': '16', 'runtime': 'local authenticated ASGI + native PG',
        'deployment': None, 'provider': 'explicit deterministic fixture selections, real candidate creator',
        'configuration': {'web_concurrency': 1, 'stores': 'native disposable PostgreSQL',
            'source': 'local immutable HTML fixture', 'semantic_mode': 'semantic-source-bound-v1'},
        'lifecycle_projection': 'original production composition; no replacement',
        'documents': manifests, 'actor': 'named reviewer', 'repeats': repeats,
        'samples': [], 'concurrent_samples': []}
    app = production_app(console)
    with TestClient(app, base_url='https://testserver') as client:
        assert client.post('/login', data={'username': 'reviewer', 'password': 'fixture-only'},
                           follow_redirects=False).status_code == 303
        for incomplete in (False, True):
            if incomplete:
                # Synthetic retained finding, explicitly not a genuine failed provider run.
                envelope = console.workflow_document_store.get_envelope(sid)
                replay = envelope['semantic_replay']['provider_evidence']
                replay['formation_incomplete'] = True
                replay['pending_rejections'] = [{'kind': 'formation',
                    'reason_code': 'synthetic_open', 'spans': []}]
                console.workflow_document_store.write_bundle(envelope=envelope)
                assert console.processing_status(sid)['formation_incomplete']
            before = durable(console, ids)
            for name, params in routes.items():
                for iteration in range(repeats + 1):
                    start = perf_counter()
                    page = client.get('/review', params=params)
                    elapsed = (perf_counter() - start) * 1000
                    assert page.status_code == 200
                    warning = 'data-formation-incomplete' in page.text
                    if params.get('object'):
                        assert ('data-document-assessment="not_evaluated"' in page.text) == incomplete
                        assert not warning
                    elif name != 'overview':
                        assert warning == incomplete
                    batch_count = len(re.findall(r'name="object_ids" value="([^"]+)"', page.text))
                    if case == 'occupied_batch' and name == 'batch' and not incomplete:
                        assert batch_count == 20, 'benchmark must exercise the occupied 20-item batch page'
                    assert evidence
                    result['samples'].append({'route': name, 'incomplete': incomplete,
                        'temperature': 'first_for_route' if iteration == 0 else 'warm',
                        'wall_ms': elapsed, 'html_bytes': len(page.content),
                        'formation_warning': warning, 'batch_members': batch_count, **evidence.pop()})
            # Two requests share one session, but each retains its real read transaction.
            with ThreadPoolExecutor(max_workers=2) as pool:
                start = perf_counter()
                pages = list(pool.map(lambda _: client.get('/review', params=routes['passage']), range(2)))
                elapsed = (perf_counter() - start) * 1000
            assert all(p.status_code == 200 for p in pages)
            result['concurrent_samples'].append({'incomplete': incomplete, 'requests': 2,
                'wall_ms': elapsed, 'statuses': [p.status_code for p in pages],
                'html_bytes': [len(p.content) for p in pages], 'diagnostics': list(evidence)})
            evidence.clear()
            assert durable(console, ids) == before, 'Review GET mutated durable source/review state'
        # A reviewer not assigned to any document cannot see its passage.
        assert client.post('/login', data={'username': 'outsider', 'password': 'fixture-only'},
                           follow_redirects=False).status_code == 303
        denied = client.get('/review', params=routes['passage'], follow_redirects=False)
        assert denied.status_code in (303, 403, 404)
        result['unauthorized_status'] = denied.status_code
    output = Path(os.environ['REVIEW_PROOF_OUTPUT'])
    output.parent.mkdir(parents=True, exist_ok=True)
    previous = json.loads(output.read_text()) if output.exists() else []
    previous.append(result)
    output.write_text(json.dumps(previous, indent=2) + '\n')


@pytest.mark.parametrize('incomplete', [False, True])
def test_native_task_v1_review(tmp_path, production_console, production_app, monkeypatch, incomplete, fault=None, dependency=None, size=2, history_depth=0, integrated=False):
    """Actual bounded processing activates storage v1 before measured HTTP review."""
    from src.request_diagnostics_v1 import RequestDiagnostics
    import src.console_performance_v1 as performance
    from tests.test_review_formation_problems import received, execute, FIRST
    from src.publication.publish_authorization_v1 import still_matches
    assert fault in {None, 'binding', 'commit'}
    assert dependency in {None, 'role', 'context'}

    source_html = None
    if size > 2:
        from tests.test_review_formation_problems import SECOND
        texts = [FIRST, SECOND, *[f'Gebruik geen middel {i:04d} bij deze synthetische situatie; '
            'bespreek de beschreven waarneming en leg de gemaakte keuze vast volgens deze afzonderlijke passage.'
            for i in range(size - 2)]]
        # Scale independent passages under one shared heading. Context/heading
        # mutations have dedicated probes; do not also scale that dependency set.
        source_html = ('<html><body><h1>Adviezen</h1>' + ''.join(f'<p>{s}</p>'
                       for s in texts) + '</body></html>').encode()
    setup_file = Path(os.environ['REVIEW_PROOF_OUTPUT']).with_suffix('.setup.json')
    def setup_stage(stage):
        setup_file.parent.mkdir(parents=True, exist_ok=True)
        setup_file.write_text(json.dumps([{'case': 'setup_progress', 'size': size, 'stage': stage}]))
    setup_stage('receipt')
    console, sid, author, reviewer, calls, mode, _provider = received(
        tmp_path, production_console, monkeypatch, source_html=source_html, all_blocks=size > 2)
    mode['broken'] = incomplete
    setup_stage('activation')
    execute(console, sid, author, 'native-task-review-proof')
    setup_stage('history')
    assert calls, 'the real bounded processing route must run'
    assert console.processing_status(sid)['formation_incomplete'] == incomplete
    focal = next(o for o in console.snapshot_objects(sid)
                 if o.get('proposed_object_type') == 'recommendation'
                 and o['content']['clean_text'] == FIRST)
    candidates = [o for o in console.snapshot_objects(sid) if o.get('proposed_object_type') == 'recommendation']
    assert len(candidates) == size - int(incomplete)
    # Hold the review-history workload fixed while independent source/object
    # volume grows. The first two candidates remain the HTTP focal/control pair.
    history_candidates = candidates[:4] if size > 2 else candidates
    if history_depth:
        seed_post_history(console, sid, history_candidates, {'account_id': reviewer}, history_depth)
    if integrated and os.environ.get('CONSOLE_REVIEW_CARD_READS') == 'compact':
        # Explicit preparation is fixture setup, never a measured GET or startup.
        from src.workflows.review_card_inputs_postgres_v1 import prepare_review_cards, capture_review_cards
        from src.workflows.workflow_transaction_v1 import workflow_read_transaction
        prepare_review_cards(console.workflow_document_store, sid)
        with workflow_read_transaction(console.workflow_document_store) as con:
            assert 'unavailable' not in capture_review_cards(console.workflow_document_store, con, [sid])[sid]
    setup_stage('measurement')

    def storage_state():
        with console.workflow_document_store._connect() as con:
            return dict(con.execute(
                "SELECT processing_storage_version,object_generation,current_setting('server_version') AS postgres_version "
                'FROM workflow.documents WHERE snapshot_id=%s',
                (sid,)).fetchone())

    initial_storage = storage_state()
    assert initial_storage['processing_storage_version'] == 1
    assert initial_storage['object_generation'] >= 0
    if size > 2:
        from tests.production_support import restart_production
        console = restart_production(console)
    captured = []
    sql_active, sql_categories, sql_owners = safe_sql_categories(monkeypatch)

    def emit(_self, payload):
        if payload.get('event') == 'request_finished' and payload.get('route') == '/review':
            captured.append({key: payload[key] for key in ('elapsed_ms', 'status', 'outcome',
                'phases', 'phase_tree', 'counters', 'db', 'unattributed_lower_bound_ms',
                'phase_tree_truncated') if key in payload})

    monkeypatch.setattr(RequestDiagnostics, 'emit', emit)
    monkeypatch.setattr(performance._LOGGER, 'info', lambda *args, **kwargs: None)
    result = {'case': 'task_v1_review', 'formation_incomplete': incomplete, 'fault_point': fault,
        'dependency': dependency,
        'commit': git('rev-parse', 'HEAD'), 'harness_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'python': platform.python_version(),
        'runtime': 'authenticated ASGI + native disposable PostgreSQL',
        'fixture': f'synthetic {size}-passage bounded-processing provider; production activation',
        'storage_before': initial_storage, 'samples': [],
        'limitations': ['synthetic task-v1 proof, not a production latency or incident replay claim',
                        'provider transport is deterministic; stores and activation are native']}
    if integrated:
        result.update(integrated_acceptance=True, production_diff=git('diff', 'HEAD', '--', 'src', 'db'),
                      review_card_mode=getattr(console, 'review_card_read_mode', 'legacy'))
    rows = console.workflow_document_store.list_document_objects(sid)
    current = {o['object_id']: o for o in console.snapshot_objects(sid)}
    bindings = console.workflow_review_store.read_bindings([sid]).get(sid, [])
    env = console.workflow_document_store.get_envelope(sid)
    from src.vorming.source_preparation_context_v1 import stored_extraction
    from src.vorming.prepared_source_views_v1 import contract as prepared_contract
    result['configuration'] = {'route': '/review', 'task': 'default passage form',
        'actor_role': 'reviewer', 'document_class': env['class'],
        'prepared_view_contract': prepared_contract(), 'field_contract': 'source-bound-fields-v3'}
    result['workload'] = {'candidates': len(candidates), 'history_depth': history_depth,
        'history_candidates': len(history_candidates[2:]) if history_depth else 0,
        'current_objects': len(current), 'stored_versions': len(rows), 'bindings': len(bindings),
        'matching_bindings': sum(still_matches(b, current[b['object_id']]) for b in bindings),
        'source_fragments': len(stored_extraction(env)),
        'source_bytes': len(console._verified_source_bytes(env)[1]),
        'source_sha256': env['sha256'], 'extraction_contract': env['prepared_source_extraction']['version']}
    result['temperature'] = ('fresh production composition for first HTTP, then two repeated GET/400 pairs; '
        'OS and PostgreSQL caches are not flushed') if size > 2 else 'compatibility fixture'

    def request(client, name, method, **kwargs):
        captured.clear()
        sql_categories.clear()
        sql_owners.clear()
        progress = request_progress(f'task-v1/{size}/{incomplete}/{fault}/{dependency}', name)
        sql_active[0] = True
        start = perf_counter()
        try:
            response = getattr(client, method)(kwargs.pop('_path', '/review'), follow_redirects=False, **kwargs)
        finally:
            sql_active[0] = False
        assert len(captured) == 1
        result['samples'].append({'action': name, 'http_status': response.status_code,
            'wall_ms': (perf_counter() - start) * 1000, 'response_bytes': len(response.content),
            'diagnostics': captured.pop(), 'sql_categories': deepcopy(sql_categories)})
        request_progress('', '', index=progress, status=response.status_code)
        return response

    def form(page):
        match = re.search(r'name="snapshot_revision" value="([^"]+)"', page.text)
        assert match and match.group(1).startswith('review-generation-v1:')
        return {'snapshot_id': sid, 'object_id': focal['object_id'], 'snapshot_revision': match.group(1),
            'suitability': 'ja', 'documentpositie_action': 'dit_klopt', 'type_action': 'dit_klopt',
            'confirmed_object_type': 'recommendation', 'eindoordeel': 'goedkeuren', 'decision': 'approve',
            'recommendation_direction': 'against', 'recommendation_strength_level': 'not_stated',
            'relation_review_ack': '1', 'comment': 'synthetic task-v1 draft'}

    with TestClient(production_app(console), base_url='https://testserver', raise_server_exceptions=False) as client:
        assert client.post('/login', data={'username': 'reviewer', 'password': 'fixture-only'},
                           follow_redirects=False).status_code == 303
        params = {'document': sid, 'object': focal['object_id']}
        before = durable(console, [sid])
        if integrated:
            for route, query in {'overview': {}, 'individual': {'document': sid, 'task': 'individual'},
                    'inventory': {'document': sid, 'task': 'inventory'},
                    'batch': {'document': sid, 'task': 'batch'}, 'passage': params}.items():
                for temperature in ('first', *[f'warm_{i}' for i in range(7)]):
                    measured = request(client, f'{route}_{temperature}', 'get', params=query)
                    assert measured.status_code == 200
                    assert 'data-personal-state="unavailable"' not in measured.text
            assert durable(console, [sid]) == before
        page = request(client, 'passage', 'get', params=params)
        assert page.status_code == 200
        assert ('data-document-assessment="not_evaluated"' in page.text) == incomplete
        data = form(page)
        assert durable(console, [sid]) == before
        early = request(client, 'pretransaction_refusal', 'post',
            data={**data, 'decision': 'reject', 'eindoordeel': 'afwijzen', 'comment': ''})
        assert early.status_code == 400
        assert 'store_transaction' not in result['samples'][-1]['diagnostics'].get('phases', {})
        assert durable(console, [sid]) == before
        refused = request(client, 'semantic_refusal', 'post',
                          data={**data, 'source_discrepancy': 'context_ontbreekt'})
        assert refused.status_code == 400 and 'synthetic task-v1 draft' in refused.text
        assert result['samples'][-1]['diagnostics']['phases']['store_transaction']['inclusive_ms'] > 0
        assert durable(console, [sid]) == before
        if size > 2:
            for repeat in range(2):
                warmed = request(client, f'warm_passage_{repeat}', 'get', params=params)
                assert warmed.status_code == 200
                rejected = request(client, f'warm_semantic_refusal_{repeat}', 'post',
                    data={**data, 'source_discrepancy': 'context_ontbreekt'})
                assert rejected.status_code == 400
                assert durable(console, [sid]) == before
        if dependency == 'role':
            # Authority is mutable independently of the document generation.
            console.workflow_identity_store.update_roles(reviewer, ['researcher'])
            try:
                assert storage_state() == initial_storage
                denied = request(client, 'revoked_reviewer', 'post', data=data)
                assert denied.status_code == 403
                assert durable(console, [sid]) == before
                assert storage_state() == initial_storage
            finally:
                console.workflow_identity_store.update_roles(reviewer, ['reviewer'])
            result['authority_probe'] = {'generation_unchanged': True,
                'durable_state_unchanged': True, 'http_status': denied.status_code}
        if fault:
            from tests.production_support import restart_production
            expected_sqlstate = 'P9021' if fault == 'binding' else 'P9022'
            table = 'publish_authorizations' if fault == 'binding' else 'review_events'
            sqlstates = []
            original_review = console.review_object

            def observe_real_review(*args, **kwargs):
                try:
                    return original_review(*args, **kwargs)
                except BaseException as exc:
                    # Observe native causes without substituting the command or fault.
                    seen = set()
                    while exc is not None and id(exc) not in seen:
                        seen.add(id(exc))
                        if getattr(exc, 'sqlstate', None):
                            sqlstates.append(exc.sqlstate)
                        exc = exc.__cause__
                    raise

            monkeypatch.setattr(console, 'review_object', observe_real_review)
            with console.workflow_document_store._connect() as con:
                con.execute("CREATE FUNCTION workflow.met23_review_fault() RETURNS trigger LANGUAGE plpgsql AS $$ "
                            "BEGIN RAISE EXCEPTION 'controlled review fault' USING ERRCODE = '" + expected_sqlstate + "'; END $$")
                if fault == 'binding':
                    con.execute('CREATE TRIGGER met23_review_fault BEFORE INSERT ON workflow.publish_authorizations '
                                'FOR EACH ROW EXECUTE FUNCTION workflow.met23_review_fault()')
                else:
                    con.execute('CREATE CONSTRAINT TRIGGER met23_review_fault AFTER INSERT ON workflow.review_events '
                                'DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION workflow.met23_review_fault()')
            try:
                failed = request(client, 'approve_with_native_database_fault', 'post', data=data)
                assert failed.status_code == (400 if fault == 'binding' else 500)
                assert expected_sqlstate in sqlstates, 'the real PostgreSQL trigger must cause the failure'
            finally:
                with console.workflow_document_store._connect() as con:
                    con.execute('DROP TRIGGER met23_review_fault ON workflow.' + table)
                    con.execute('DROP FUNCTION workflow.met23_review_fault()')
            assert durable(console, [sid]) == before
            assert storage_state() == initial_storage
            restarted = restart_production(console)
            assert durable(restarted, [sid]) == before
            result['native_fault'] = {'sqlstate': expected_sqlstate, 'http_status': failed.status_code,
                'durable_rollback': True, 'generation_rollback': True, 'restart_preserves_state': True}
            # Retry the same form after fault removal; rollback must preserve its precondition.
        approved = request(client, 'approve', 'post', data=data)
        assert approved.status_code == 303
        # The observer must count real audit INSERTs even though their safe
        # category is review_audit rather than a name ending in _write.
        assert result['samples'][-1]['sql_categories']['review_audit']['affected_write_rows'] > 0
        winner = durable(console, [sid])
        if integrated:
            redirected = request(client, 'redirect_after_approve', 'get', _path=approved.headers['location'])
            assert redirected.status_code == 200
            overview = request(client, 'overview_after_approve', 'get')
            assert overview.status_code == 200 and 'data-personal-state="unavailable"' not in overview.text
            assert durable(console, [sid]) == winner
        current = next(o for o in console.snapshot_objects(sid) if o['object_id'] == focal['object_id'])
        assert current['governance']['validation_status'] == 'approved'
        assert any(b['object_id'] == focal['object_id'] and still_matches(b, current)
                   for b in console.object_review_bindings(sid))
        result['storage_after_approval'] = storage_state()
        assert result['storage_after_approval']['processing_storage_version'] == 1
        assert result['storage_after_approval']['object_generation'] > initial_storage['object_generation']
        retry = request(client, 'old_form_retry', 'post', data=data)
        assert retry.status_code == 409 and durable(console, [sid]) == winner
        fresh = request(client, 'fresh_passage', 'get', params=params)
        assert fresh.status_code == 200
        stale_data = form(fresh)
        if dependency == 'context':
            from src.review.source_context_review_v1 import LINKS_KEY, context_issues
            from src.review.review_passage_read_v1 import read_review_passage
            source = next(o for o in console.snapshot_objects(sid)
                          if o.get('proposed_object_type') == 'recommendation'
                          and o['object_id'] != focal['object_id'])
            console.confirm_source_context(actor_id=reviewer, snapshot_id=sid,
                source_object_id=source['object_id'], role='context',
                target_object_ids=[focal['object_id']], reason='Synthetic linked source context.',
                command_id='native-context-dependency', expected_revision=console.objects_revision(sid))
            linked_rows = console.snapshot_objects(sid)
            linked = next(o for o in linked_rows if o['object_id'] == focal['object_id'])
            assert linked['governance']['validation_status'] == 'needs_review'
            assert any(link['source_object_id'] == source['object_id']
                       for link in linked['metadata'][LINKS_KEY])
            assert not context_issues(linked_rows)
            assert not any(b.get('valid') for b in console.object_review_bindings(sid)
                           if b['object_id'] == focal['object_id'])
            after_context = durable(console, [sid])
            context_storage = storage_state()
            assert context_storage['object_generation'] > result['storage_after_approval']['object_generation']
            context_stale = request(client, 'context_stale', 'post', data=stale_data)
            assert context_stale.status_code == 409
            assert durable(console, [sid]) == after_context
            assert storage_state() == context_storage
            package = read_review_passage(console, {'account_id': reviewer, 'roles': ['reviewer']},
                                          sid, focal['object_id'])
            assert source['object_id'] in {o['object_id'] for o in package.objects}
            context_page = request(client, 'context_passage', 'get', params=params)
            assert context_page.status_code == 200
            assert 'Context die bij deze passage is vastgelegd' in context_page.text
            assert durable(console, [sid]) == after_context
            result['context_probe'] = {'storage_after_context': context_storage,
                'approval_reopened': True, 'binding_invalidated': True,
                'dependency_in_read_package': True, 'stale_preserves_winner': True}
            stale_data = form(context_page)
        append_post_fixture_revision(console, sid, focal['object_id'], reviewer)
        concurrent_state = durable(console, [sid])
        result['storage_after_concurrent_revision'] = storage_state()
        assert result['storage_after_concurrent_revision']['processing_storage_version'] == 1
        assert result['storage_after_concurrent_revision']['object_generation'] > result['storage_after_approval']['object_generation']
        stale = request(client, 'concurrent_stale', 'post', data=stale_data)
        assert stale.status_code == 409 and durable(console, [sid]) == concurrent_state
        assert console.processing_status(sid)['formation_incomplete'] == incomplete
    result['engineering_budgets'] = {'post_ms': 3000, 'store_lock_hold_ms': 250,
        'store_transaction_ms': 500, 'role': 'WP6 target, not a WP5 baseline pass condition or production SLO'}
    result['baseline_budget_violations'] = [s['action'] for s in result['samples']
        if s['http_status'] in {303, 400, 409} and (s['wall_ms'] > 3000
        or s['diagnostics'].get('phases', {}).get('store_lock_hold', {}).get('inclusive_ms', 0) > 250
        or s['diagnostics'].get('phases', {}).get('store_transaction', {}).get('inclusive_ms', 0) > 500)]
    output = Path(os.environ['REVIEW_PROOF_OUTPUT'])
    output.parent.mkdir(parents=True, exist_ok=True)
    previous = json.loads(output.read_text()) if output.exists() else []
    previous.append(result)
    output.write_text(json.dumps(previous, indent=2) + '\n')


@pytest.mark.parametrize('size', [int(v) for v in os.environ.get('REVIEW_POST_SIZES', '20').split(',')])
def test_native_review_post_baseline(size, tmp_path, production_console, production_app, monkeypatch):
    """MET-23: full response and durable outcomes, without replacing the kernel."""
    from src.request_diagnostics_v1 import RequestDiagnostics
    import src.console_performance_v1 as performance

    assert size >= 2
    console = production_console(root=tmp_path, processing_binder=lambda _: None)
    author = console.create_account(username='author', password='fixture-only', roles=('researcher',))
    reviewer = console.create_account(username='reviewer', password='fixture-only', roles=('reviewer',))
    texts = [f'begrip {i:04d} is een beschrijving van een afzonderlijke waarneming.' for i in range(size)]
    source = ('<html><body><h1>Bronindeling</h1>' + ''.join(f'<p>{s}</p>' for s in texts) + '</body></html>').encode()
    bind_fixture_selections(console, [(s, 'definition') for s in texts])
    sid = console.ingest(actor_id=author['account_id'], filename='post-fixture.html',
        content_type='text/html', data=source, ingest_kind='new', title='Synthetic POST baseline',
        version='1.0', date='2026-10-28', live_url='', class_='richtlijn', family='fixture',
        named_reviewers=[reviewer['account_id']])['snapshot_id']
    candidates = [o for o in console.snapshot_objects(sid)
                  if (o.get('metadata') or {}).get('semantic_passage', {}).get('spans')]
    assert len(candidates) == size
    assert not console.processing_status(sid)['formation_incomplete']
    focal = candidates[0]
    profile = os.environ.get('REVIEW_POST_PROFILE', 'initial')
    assert profile in {'initial', 'history', 'history_incomplete'}
    depth = int(os.environ.get('REVIEW_POST_HISTORY_DEPTH', '4')) if profile != 'initial' else 0
    if profile != 'initial':
        assert size >= 4 and depth >= 2
        seed_post_history(console, sid, candidates, reviewer, depth)
    incomplete = profile == 'history_incomplete'
    if incomplete:
        # Explicit synthetic retained finding, not a genuine failed provider run.
        envelope = console.workflow_document_store.get_envelope(sid)
        replay = envelope['semantic_replay']['provider_evidence']
        replay['formation_incomplete'] = True
        replay['pending_rejections'] = [{'kind': 'formation', 'reason_code': 'synthetic_open', 'spans': []}]
        console.workflow_document_store.write_bundle(envelope=envelope)
        assert console.processing_status(sid)['formation_incomplete']
    from src.publication.publish_authorization_v1 import still_matches
    from src.review.revision_workflow import current_revisions
    from src.vorming.source_preparation_context_v1 import stored_extraction
    rows = console.workflow_document_store.list_document_objects(sid)
    current = {o['object_id']: o for o in current_revisions(rows, snapshot_id=sid)}
    bindings = console.workflow_review_store.read_bindings([sid]).get(sid, [])
    matching = sum(still_matches(b, current[b['object_id']]) for b in bindings)
    if depth:
        assert len(rows) > len(current)
        assert 0 < matching < len(bindings), 'fixture needs matching and stale exact bindings'
    envelope = console.workflow_document_store.get_envelope(sid)
    with console.workflow_document_store._connect() as version_connection:
        postgres_version = version_connection.execute('SHOW server_version').fetchone()['server_version']
        storage_contract = version_connection.execute(
            'SELECT processing_storage_version,object_generation FROM workflow.documents WHERE snapshot_id=%s',
            (sid,)).fetchone()
    captured = []

    def emit(_self, payload):
        if payload.get('event') == 'request_finished' and payload.get('route') == '/review':
            # Deliberately exclude request IDs, SQL, error details and form values.
            captured.append({key: payload[key] for key in ('elapsed_ms', 'status', 'outcome',
                'phases', 'phase_tree', 'counters', 'db', 'unattributed_lower_bound_ms',
                'phase_tree_truncated') if key in payload})

    monkeypatch.setattr(RequestDiagnostics, 'emit', emit)
    monkeypatch.setattr(performance._LOGGER, 'info', lambda *args, **kwargs: None)
    result = {'case': 'post_baseline', 'profile': profile, 'commit': git('rev-parse', 'HEAD'),
        'harness_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'production_diff': git('diff', 'HEAD', '--', 'src'),
        'python': platform.python_version(), 'postgres': postgres_version,
        'runtime': 'authenticated ASGI + native disposable PostgreSQL',
        'fixture': {'source_sha256': sha256(source).hexdigest(), 'source_bytes': len(source),
            'candidates': size, 'history_depth': depth, 'history_rows': len(rows),
            'current_objects': len(current), 'bindings': len(bindings),
            'matching_bindings': matching, 'stale_bindings': len(bindings) - matching,
            'extraction_contract': envelope['prepared_source_extraction']['version'],
            'source_fragments': len(stored_extraction(envelope)),
            'processing_storage_version': storage_contract['processing_storage_version'],
            'object_generation': storage_contract['object_generation'],
            'relations': 'no additional relation context',
            'formation': 'synthetic incomplete finding' if incomplete else 'complete',
            'provider': 'deterministic fixture selections, production candidate creator'},
        'samples': [], 'limitations': ['synthetic fixture, not incident replay',
            'no relation closure fixture or production SQL attribution yet',
            'one observation per action; no percentile or production SLO claim']}

    def request(client, name, method, **kwargs):
        captured.clear()
        progress = request_progress(f'legacy/{size}/{profile}', name)
        start = perf_counter()
        response = getattr(client, method)('/review', follow_redirects=False, **kwargs)
        wall_ms = (perf_counter() - start) * 1000
        assert len(captured) == 1, 'each completed HTTP request needs its own diagnostic record'
        result['samples'].append({'action': name, 'wall_ms': wall_ms,
            'http_status': response.status_code, 'response_bytes': len(response.content),
            'diagnostics': captured.pop()})
        request_progress('', '', index=progress, status=response.status_code)
        return response

    def form(page):
        match = re.search(r'name="snapshot_revision" value="([^"]+)"', page.text)
        assert match, 'actual rendered form must supply the revision'
        return {'snapshot_id': sid, 'object_id': focal['object_id'], 'snapshot_revision': match.group(1),
            'suitability': 'ja', 'documentpositie_action': 'dit_klopt', 'type_action': 'dit_klopt',
            'confirmed_object_type': 'definition', 'eindoordeel': 'goedkeuren', 'decision': 'approve',
            'relation_review_ack': '1', 'comment': 'synthetic draft retained'}

    with TestClient(production_app(console), base_url='https://testserver') as client:
        assert client.post('/login', data={'username': 'reviewer', 'password': 'fixture-only'},
                           follow_redirects=False).status_code == 303
        params = {'document': sid, 'object': focal['object_id']}
        before = durable(console, [sid])
        page = request(client, 'passage', 'get', params=params)
        assert page.status_code == 200
        assert ('data-document-assessment="not_evaluated"' in page.text) == incomplete
        data = form(page)
        assert durable(console, [sid]) == before
        # Real semantic refusal inside review_object, not an injected exception.
        rejected = request(client, 'semantic_refusal', 'post',
                           data={**data, 'source_discrepancy': 'context_ontbreekt'})
        assert rejected.status_code == 400
        assert 'synthetic draft retained' in rejected.text
        assert durable(console, [sid]) == before
        if profile == 'history':
            # Separate the injected wait from the ordinary focal approval timing.
            control_id = candidates[1]['object_id']
            blocked, result['lock_probe'] = post_with_native_row_blocker(
                console, sid, lambda: request(client, 'control_approve_with_lock', 'post',
                                             data={**data, 'object_id': control_id}))
            assert blocked.status_code == 303
            control = next(o for o in console.snapshot_objects(sid) if o['object_id'] == control_id)
            assert control['governance']['validation_status'] == 'approved'
            assert any(b['valid'] and b['object_id'] == control_id for b in console.object_review_bindings(sid))
            # The independent committed approval invalidates the prior page token.
            page = request(client, 'passage_after_lock_control', 'get', params=params)
            assert page.status_code == 200
            data = form(page)
        approved = request(client, 'approve', 'post', data=data)
        assert approved.status_code == 303
        approved_state = durable(console, [sid])
        assert approved_state != before
        current = next(o for o in console.snapshot_objects(sid) if o['object_id'] == focal['object_id'])
        assert current['governance']['validation_status'] == 'approved'
        assert any(b['valid'] and b['object_id'] == focal['object_id']
                   for b in console.object_review_bindings(sid))
        # Replaying the old form is a stale request, not a universal idempotency key.
        retry = request(client, 'old_form_retry', 'post', data=data)
        assert retry.status_code == 409
        assert durable(console, [sid]) == approved_state
        # Also exercise a separately rendered form invalidated by another object write.
        fresh = request(client, 'fresh_passage', 'get', params=params)
        assert fresh.status_code == 200
        stale_data = form(fresh)
        append_post_fixture_revision(console, sid, candidates[1]['object_id'], reviewer['account_id'])
        concurrent_state = durable(console, [sid])
        stale = request(client, 'concurrent_stale', 'post', data=stale_data)
        assert stale.status_code == 409
        assert durable(console, [sid]) == concurrent_state
    output = Path(os.environ['REVIEW_PROOF_OUTPUT'])
    output.parent.mkdir(parents=True, exist_ok=True)
    previous = json.loads(output.read_text()) if output.exists() else []
    previous.append(result)
    output.write_text(json.dumps(previous, indent=2) + '\n')
