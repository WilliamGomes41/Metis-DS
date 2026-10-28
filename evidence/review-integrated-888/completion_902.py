"""Native WP5 completion probes; no replacement production rules or writers."""
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import runpy
from time import monotonic, sleep

from fastapi.testclient import TestClient


BASE = runpy.run_path(str(Path(__file__).with_name('benchmark.py')))
durable = BASE['durable']


def record(case, **values):
    path = Path(os.environ['REVIEW_PROOF_OUTPUT'])
    rows = json.loads(path.read_text()) if path.exists() else []
    rows.append({'case': case, 'commit': BASE['git']('rev-parse', 'HEAD'), **values})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2) + '\n')


def task_system(tmp_path, production_console, monkeypatch):
    from tests.test_review_formation_problems import received, execute, FIRST
    console, sid, author, reviewer, _, mode, _ = received(tmp_path, production_console, monkeypatch)
    mode['broken'] = False
    execute(console, sid, author, 'completion-fixture')
    objects = console.snapshot_objects(sid)
    focal = next(o for o in objects if o.get('proposed_object_type') == 'recommendation'
                 and o['content']['clean_text'] == FIRST)
    return console, sid, reviewer, focal


def page_form(client, sid, focal):
    page = client.get('/review', params={'document': sid, 'object': focal['object_id']})
    assert page.status_code == 200
    token = re.search(r'name="snapshot_revision" value="([^"]+)"', page.text).group(1)
    return {'snapshot_id': sid, 'object_id': focal['object_id'], 'snapshot_revision': token,
        'suitability': 'ja', 'documentpositie_action': 'dit_klopt', 'type_action': 'dit_klopt',
        'confirmed_object_type': focal.get('confirmed_object_type') or focal.get('proposed_object_type') or 'definition',
        'eindoordeel': 'goedkeuren', 'decision': 'approve', 'recommendation_direction': 'against',
        'recommendation_strength_level': 'not_stated', 'relation_review_ack': '1',
        'comment': 'Synthetic completion probe.'}


def login(console, production_app):
    client = TestClient(production_app(console), base_url='https://testserver')
    assert client.post('/login', data={'username': 'reviewer', 'password': 'fixture-only'},
                       follow_redirects=False).status_code == 303
    return client


def binding_only(tmp_path, production_console, production_app, monkeypatch, storage):
    from src.publication.publish_authorization_v1 import still_matches
    from tests.production_support import restart_production
    if storage == 'task-v1':
        console, sid, reviewer, focal = task_system(tmp_path, production_console, monkeypatch)
    else:
        from tests.semantic_fixture_support import bind_fixture_selections
        console = production_console(root=tmp_path, processing_binder=lambda _: None)
        author = console.create_account(username='author', password='fixture-only', roles=('researcher',))
        reviewer = console.create_account(username='reviewer', password='fixture-only', roles=('reviewer',))['account_id']
        text = 'Een observatie is een systematische waarneming van gedrag.'
        bind_fixture_selections(console, [(text, 'definition')])
        sid = console.ingest(actor_id=author['account_id'], filename='binding.html',
            content_type='text/html', data=f'<html><body><h1>Begrippen</h1><p>{text}</p></body></html>'.encode(),
            ingest_kind='new', title='Synthetic binding-only', version='1', date='2026-10-28',
            live_url='', class_='richtlijn', family='fixture', named_reviewers=[reviewer])['snapshot_id']
        focal = next(o for o in console.snapshot_objects(sid) if o.get('proposed_object_type') == 'definition')
    with login(console, production_app) as client:
        assert client.post('/review', data=page_form(client, sid, focal), follow_redirects=False).status_code == 303
        data = page_form(client, sid, focal)
        with console.workflow_document_store._connect() as con:
            before = dict(con.execute('SELECT revision,object_generation,processing_storage_version FROM workflow.documents WHERE snapshot_id=%s', (sid,)).fetchone())
        assert (before['processing_storage_version'] == 1) == (storage == 'task-v1')
        rows = console.workflow_review_store.read_bindings([sid])[sid]
        assert any(b['object_id'] == focal['object_id'] and b['valid'] for b in rows)
        for row in rows:
            if row['object_id'] == focal['object_id']:
                row['valid'] = False
        # Existing store API: actual binding-only writer, no object mutation.
        console.workflow_review_store.replace_snapshot_bindings(sid, rows)
        with console.workflow_document_store._connect() as con:
            after = dict(con.execute('SELECT revision,object_generation,processing_storage_version FROM workflow.documents WHERE snapshot_id=%s', (sid,)).fetchone())
        assert after == before
        assert not any(b['valid'] for b in console.object_review_bindings(sid) if b['object_id'] == focal['object_id'])
        # A fresh explicit approval may renew a withdrawn exact authorization.
        # Binding-only change is NOT a universal stale-token/409 contract.
        renewed = client.post('/review', data=data, follow_redirects=False)
        assert renewed.status_code == 303
        current = next(o for o in console.snapshot_objects(sid) if o['object_id'] == focal['object_id'])
        assert any(still_matches(b, current) for b in console.object_review_bindings(sid)
                   if b['object_id'] == focal['object_id'])
        assert durable(restart_production(console), [sid]) == durable(console, [sid])
    record('binding_only', storage=storage, counters_before=before, counters_after_binding=after,
           explicit_renewal_status=renewed.status_code, restart_preserves_state=True)


def decision_retry(tmp_path, production_console, production_app, monkeypatch, decision):
    console, sid, reviewer, focal = task_system(tmp_path, production_console, monkeypatch)
    with login(console, production_app) as client:
        data = page_form(client, sid, focal)
        data.update(decision=decision, eindoordeel={'reject': 'afwijzen',
            'revise': 'goedkeuren_na_correctie', 'later': 'later_beoordelen'}[decision])
        before = durable(console, [sid])
        before_generation = console.workflow_document_store.review_document_input(sid)[1]
        first = client.post('/review', data=data, follow_redirects=False)
        expected = 200 if decision == 'revise' else 303
        assert first.status_code == expected
        winner = durable(console, [sid])
        after_generation = console.workflow_document_store.review_document_input(sid)[1]
        if decision in {'later', 'revise'}:
            assert winner == before
            if decision == 'revise':
                assert 'Correctie specificeren' in first.text
        else:
            current = next(o for o in console.snapshot_objects(sid) if o['object_id'] == focal['object_id'])
            assert current['governance']['validation_status'] == 'rejected'
            assert not any(b['valid'] for b in console.object_review_bindings(sid)
                           if b['object_id'] == focal['object_id'])
        retry = client.post('/review', data=data, follow_redirects=False)
        # Strict passage precondition includes the store's document generation,
        # even when a 'later' bundle preserved the semantic domain state.
        assert retry.status_code == (expected if decision == 'revise' else 409)
        assert durable(console, [sid]) == winner
    record('decision_retry', decision=decision, first_status=first.status_code,
           retry_status=retry.status_code, retry_preserves_state=True,
           first_preserves_state=winner == before,
           generation_changed=after_generation != before_generation,
           boundary='HTTP structured revise is a prewrite specification step; later is this payload only')


def context_retarget(tmp_path, production_console, monkeypatch):
    from src.review.source_context_review_v1 import LINKS_KEY, projection
    from tests.production_support import restart_production
    console, sid, reviewer, focal = task_system(tmp_path, production_console, monkeypatch)
    rows = console.snapshot_objects(sid)
    source = next(o for o in rows if o.get('object_type') == 'heading')
    other = next(o for o in rows if o.get('proposed_object_type') == 'recommendation'
                 and o['object_id'] != focal['object_id'])
    def confirm(target, command):
        return console.confirm_source_context(actor_id=reviewer, snapshot_id=sid,
            source_object_id=source['object_id'], role='context', target_object_ids=[target['object_id']],
            reason='Synthetic retargeting.', command_id=command, expected_revision=console.objects_revision(sid))
    confirm(focal, 'context-before')
    confirm(other, 'context-after')
    rows = console.snapshot_objects(sid)
    old = next(o for o in rows if o['object_id'] == focal['object_id'])
    new = next(o for o in rows if o['object_id'] == other['object_id'])
    current_source = next(o for o in rows if o['object_id'] == source['object_id'])
    assert not old.get('metadata', {}).get(LINKS_KEY)
    assert any(r['source_object_id'] == source['object_id'] for r in new['metadata'][LINKS_KEY])
    assert projection(current_source, rows)['target_object_ids'] == [other['object_id']]
    assert all(o['governance']['validation_status'] == 'needs_review' for o in (old, new))
    assert durable(restart_production(console), [sid]) == durable(console, [sid])
    record('context_retarget', old_target_detached=True, new_target_linked=True,
           both_targets_require_review=True, restart_preserves_state=True)


def lock_worker(folder, kind):
    """Child process: build the real production composition, then run one command."""
    from contextlib import contextmanager
    import src.workflows.workflow_transaction_v1 as transactions
    import src.workflows.workflow_review_cutover_v1 as review_boundary
    import src.review.source_context_review_v1 as context
    from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalConfig
    from tests.production_support import production_application
    folder = Path(folder)
    inputs = json.loads((folder / 'inputs.json').read_text())
    result = {'committed': False, 'sqlstates': []}
    try:
        console = production_application(folder / kind,
            PostgresCanonicalConfig(dsn=os.environ['METIS_WP5_TEST_DSN']),
            source_store=inputs['source_store'], processing_binder=lambda _: None).state.operations_kernel
        original_transaction = transactions.workflow_transaction
        @contextmanager
        def bounded_transaction(owner):
            with original_transaction(owner) as con:
                con.execute("SET LOCAL statement_timeout='15s'")
                yield con
        transactions.workflow_transaction = bounded_transaction
        review_boundary.workflow_transaction = bounded_transaction
        if kind == 'single':
            original_lock = console.workflow_review_store._lock_authorizations
            def hold_auth(con):
                original_lock(con)
                (folder / 'single.ready').write_text(str(con.info.backend_pid))
                deadline = monotonic() + 15
                while not (folder / 'context.ready').exists():
                    if monotonic() >= deadline:
                        raise TimeoutError('context_row_not_observed')
                    sleep(0.01)
            console.workflow_review_store._lock_authorizations = hold_auth
            console.review_object(actor_id=inputs['reviewer'], snapshot_id=inputs['sid'],
                object_id=inputs['focal'], decision='approve', confirmed_object_type='recommendation',
                recommendation_direction='against', recommendation_strength_level='not_stated',
                relation_review_ack=True, expected_revision=inputs['revision'])
        else:
            original_context = context._confirm_source_context
            def observe_context(owner, **command):
                with owner.workflow_document_store._connect() as con:
                    (folder / 'context.ready').write_text(str(con.info.backend_pid))
                return original_context(owner, **command)
            context._confirm_source_context = observe_context
            console.confirm_source_context(actor_id=inputs['reviewer'], snapshot_id=inputs['sid'],
                source_object_id=inputs['source'], role='context', target_object_ids=[inputs['focal']],
                reason='Synthetic lock-cycle probe.', command_id='context-concurrent',
                expected_revision=inputs['revision'])
        result['committed'] = True
    except BaseException as exc:
        result['error_type'] = type(exc).__name__
        result['error_code'] = getattr(exc, 'code', None)
        seen = set()
        while exc is not None and id(exc) not in seen:
            seen.add(id(exc))
            if getattr(exc, 'sqlstate', None):
                result['sqlstates'].append(exc.sqlstate)
            exc = exc.__cause__
    finally:
        (folder / (kind + '.result')).write_text(json.dumps(result))


def context_lock_cycle(tmp_path, production_console, monkeypatch, with_binding):
    """Two OS processes: real lock owners, hard cleanup and safe DB observation."""
    import subprocess
    import sys
    from src.publication.publish_authorization_v1 import still_matches
    from tests.production_support import restart_production
    console, sid, reviewer, focal = task_system(tmp_path, production_console, monkeypatch)
    if with_binding:
        console.review_object(actor_id=reviewer, snapshot_id=sid, object_id=focal['object_id'],
            decision='approve', confirmed_object_type='recommendation', recommendation_direction='against',
            recommendation_strength_level='not_stated', relation_review_ack=True)
        BASE['append_post_fixture_revision'](console, sid, focal['object_id'], reviewer)
        focal = next(o for o in console.snapshot_objects(sid) if o['object_id'] == focal['object_id'])
        prior = console.workflow_review_store.read_bindings([sid])[sid]
        assert any(b['valid'] and b['object_id'] == focal['object_id'] for b in prior)
        assert not any(still_matches(b, focal) for b in prior)
    source = next(o for o in console.snapshot_objects(sid) if o.get('proposed_object_type') == 'recommendation'
                  and o['object_id'] != focal['object_id'])
    folder = tmp_path / 'lock-probe'
    folder.mkdir()
    (folder / 'inputs.json').write_text(json.dumps({'sid': sid, 'reviewer': reviewer,
        'focal': focal['object_id'], 'source': source['object_id'],
        'revision': console.objects_revision(sid), 'source_store': str(console.source_store)}))
    environment = dict(os.environ, METIS_WP5_TEST_DSN=console.workflow_document_store.config.dsn)
    # DB config remains in environment, never in argv, artifacts or result logs.
    command = [sys.executable, '-c', 'import runpy,sys; runpy.run_path(sys.argv[1])["lock_worker"](sys.argv[2],sys.argv[3])',
               str(Path(__file__).resolve()), str(folder)]
    children = {}
    cycle = False
    try:
        children['single'] = subprocess.Popen([*command, 'single'], env=environment,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = monotonic() + 30
        while not (folder / 'single.ready').exists():
            assert children['single'].poll() is None, 'single process exited before its lock'
            assert monotonic() < deadline, 'single process did not acquire authorization lock'
            sleep(0.01)
        children['context'] = subprocess.Popen([*command, 'context'], env=environment,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = monotonic() + 30
        while not (folder / 'context.ready').exists():
            assert children['context'].poll() is None, 'context process exited before its row lock'
            assert monotonic() < deadline, 'context process did not acquire document lock'
            sleep(0.01)
        a = int((folder / 'single.ready').read_text())
        b = int((folder / 'context.ready').read_text())
        with console.workflow_document_store._connect() as observer:
            observer.autocommit = True
            observer.execute("SET statement_timeout='2s'")
            deadline = monotonic() + 10
            while monotonic() < deadline:
                rows = observer.execute('SELECT pid,wait_event_type,wait_event,pg_blocking_pids(pid) AS blockers '
                    'FROM pg_stat_activity WHERE pid=ANY(%s)', ([a, b],)).fetchall()
                waits = {r['pid']: r for r in rows}
                if a in waits and b in waits and b in waits[a]['blockers'] and a in waits[b]['blockers']:
                    assert {waits[a]['wait_event'], waits[b]['wait_event']} == {'advisory', 'transactionid'}
                    cycle = True
                    break
                if all(p.poll() is not None for p in children.values()):
                    break
                sleep(0.01)
        for child in children.values():
            child.wait(timeout=30)
        results = {name: json.loads((folder / (name + '.result')).read_text()) for name in children}
    finally:
        for child in children.values():
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)
    record('context_lock_cycle_observation', has_prior_binding=with_binding, observed_cycle=cycle, results=results)
    assert cycle == with_binding, results
    assert sum(r['committed'] for r in results.values()) == 1, results
    if with_binding:
        assert any('40P01' in r['sqlstates'] for r in results.values()), results
    else:
        assert results['context']['committed']
        assert results['single']['error_code'] == 'snapshot_object_write_conflict'
        assert not any(r['sqlstates'] for r in results.values())
    fresh = restart_production(console)
    current = next(o for o in fresh.snapshot_objects(sid) if o['object_id'] == focal['object_id'])
    assert bool(current.get('metadata', {}).get('confirmed_source_context')) == results['context']['committed']
    assert (current['governance']['validation_status'] == 'approved') == results['single']['committed']
    assert any(still_matches(b, current) for b in fresh.object_review_bindings(sid)
               if b['object_id'] == focal['object_id']) == results['single']['committed']
    current_source = next(o for o in fresh.snapshot_objects(sid) if o['object_id'] == source['object_id'])
    assert (current_source['object_version'] != source['object_version']) == results['context']['committed']
    events = fresh.workflow_review_store.read_events()
    context_events = [e for e in events if e.get('event_type') == 'source_context_review'
                      and (e.get('details') or {}).get('command_id') == 'context-concurrent']
    assert len(context_events) == int(results['context']['committed'])
    record('context_lock_cycle', has_prior_binding=with_binding, observed_cycle=cycle,
           wait_categories=['advisory', 'transactionid'] if cycle else [],
           results=results, restart_reads_single_winner=True, losing_source_and_context_audit_rolled_back=True,
           interpretation='controlled baseline defect; no production incident attribution; no fix in WP5')
