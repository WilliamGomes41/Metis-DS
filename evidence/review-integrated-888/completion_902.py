"""Native WP5 completion probes; no replacement production rules or writers."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import runpy
from threading import Event
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


def context_lock_cycle(tmp_path, production_console, monkeypatch):
    """Diagnose real lock inversion. A proven DB abort is a baseline finding."""
    import src.review.source_context_review_v1 as context
    from src.publication.publish_authorization_v1 import still_matches
    from tests.production_support import restart_production
    single, sid, reviewer, focal = task_system(tmp_path, production_console, monkeypatch)
    contender = production_console(root=tmp_path / 'independent', source_store=single.source_store,
                                   processing_binder=lambda _: None)
    assert contender.runtime != single.runtime
    source = next(o for o in single.snapshot_objects(sid) if o.get('proposed_object_type') == 'recommendation'
                  and o['object_id'] != focal['object_id'])
    revision = single.objects_revision(sid)
    auth_held, document_held = Event(), Event()
    pids = {}
    real_lock = single.workflow_review_store._lock_authorizations
    real_context = context._confirm_source_context

    def hold_auth(con):
        real_lock(con)
        pids['single'] = con.info.backend_pid
        auth_held.set()
        assert document_held.wait(15)

    def observe_context(console, **command):
        if console is contender:
            with console.workflow_document_store._connect() as con:
                pids['context'] = con.info.backend_pid
            document_held.set()  # outer real context boundary already locks the row
        return real_context(console, **command)

    def outcome(fn, **kwargs):
        try:
            fn(**kwargs)
            return {'committed': True, 'sqlstates': []}
        except Exception as exc:
            states, seen = [], set()
            while exc is not None and id(exc) not in seen:
                seen.add(id(exc))
                if getattr(exc, 'sqlstate', None):
                    states.append(exc.sqlstate)
                exc = exc.__cause__
            return {'committed': False, 'sqlstates': states}

    monkeypatch.setattr(single.workflow_review_store, '_lock_authorizations', hold_auth)
    monkeypatch.setattr(context, '_confirm_source_context', observe_context)
    cycle = False
    with ThreadPoolExecutor(max_workers=2) as pool:
        approval = pool.submit(outcome, single.review_object, actor_id=reviewer, snapshot_id=sid,
            object_id=focal['object_id'], decision='approve', confirmed_object_type='recommendation',
            recommendation_direction='against', recommendation_strength_level='not_stated',
            relation_review_ack=True, expected_revision=revision)
        try:
            assert auth_held.wait(15)
            linking = pool.submit(outcome, contender.confirm_source_context, actor_id=reviewer,
                snapshot_id=sid, source_object_id=source['object_id'], role='context',
                target_object_ids=[focal['object_id']], reason='Synthetic lock-cycle probe.',
                command_id='context-concurrent', expected_revision=revision)
            assert document_held.wait(15)
            with single.workflow_document_store._connect() as observer:
                observer.autocommit = True
                deadline = monotonic() + 10
                while monotonic() < deadline and not (approval.done() and linking.done()):
                    rows = observer.execute('SELECT pid,wait_event_type,wait_event,pg_blocking_pids(pid) AS blockers '
                        'FROM pg_stat_activity WHERE pid=ANY(%s)', (list(pids.values()),)).fetchall()
                    waits = {r['pid']: r for r in rows}
                    if all(pid in waits for pid in pids.values()):
                        a, b = pids['single'], pids['context']
                        if b in waits[a]['blockers'] and a in waits[b]['blockers']:
                            assert {waits[a]['wait_event'], waits[b]['wait_event']} == {'advisory', 'transactionid'}
                            cycle = True
                            break
                    sleep(0.01)
        finally:
            document_held.set()
        results = {'single': approval.result(timeout=30), 'context': linking.result(timeout=30)}
    assert cycle, 'must observe the real PostgreSQL wait-for cycle, not just two threads'
    assert sum(r['committed'] for r in results.values()) == 1
    assert any('40P01' in r['sqlstates'] for r in results.values()), results
    fresh = restart_production(single)
    current = next(o for o in fresh.snapshot_objects(sid) if o['object_id'] == focal['object_id'])
    linked = bool(current.get('metadata', {}).get('confirmed_source_context'))
    assert linked == results['context']['committed']
    assert (current['governance']['validation_status'] == 'approved') == results['single']['committed']
    assert any(still_matches(b, current) for b in fresh.object_review_bindings(sid)
               if b['object_id'] == focal['object_id']) == results['single']['committed']
    record('context_lock_cycle', observed_cycle=True, wait_categories=['advisory', 'transactionid'],
           results=results, restart_reads_single_winner=True,
           interpretation='controlled baseline defect; no production incident attribution; no fix in WP5')
