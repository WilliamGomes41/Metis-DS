"""Native source batches reuse the guarded command; no generic history reseal.

# release-control-evidence: scope/belofte opslag concurrent stale recovery
# release-control-evidence: toegang kwaliteit slop releasebewijs
"""
from fastapi.testclient import TestClient
from tests.test_source_accountability_v1 import system
from src.workflows import revision_frontiers_postgres_v1 as frontiers
import pytest


def test_native_http_source_batch_uses_existing_delta_and_keeps_prepared_frontiers(
    tmp_path,production_console,production_app,monkeypatch,
):
    console,initial,command=system(tmp_path,production_console=production_console)
    sid=command['snapshot_id'];reviews=console.workflow_review_store
    with TestClient(production_app(console)) as client:
        assert client.post('/login',data={'username':'reviewer','password':'long-test-password'},follow_redirects=False).status_code==303
        def forbidden(*args,**kwargs):raise AssertionError('batch used full/global write work')
        with monkeypatch.context() as patch:
            patch.setattr(frontiers,'seal_complete',forbidden)
            patch.setattr(console,'_reload_store_locked',forbidden)
            patch.setattr(reviews,'read_events',forbidden)
            patch.setattr(console.workflow_document_store,'write_bundle',forbidden)
            result=client.post('/review/source-exclusions',data={
                'snapshot_id':sid,'source_object_ids':command['source_object_ids'],'reason':command['reason'],
                'command_id':command['command_id'],'snapshot_revision':command['expected_revision'],'source_checked':'1'},follow_redirects=False)
        assert result.status_code==303,result.text
    window=console.workflow_document_store.review_command_window(sid,[row['object_id'] for row in initial])
    assert window is not None
    for obj in window:
        if obj['object_id'] in command['source_object_ids']:
            assert obj['governance']['validation_status']=='rejected'


@pytest.mark.parametrize('history_count', [6, 1500])
def test_generation_source_batch_keeps_history_outside_command_and_rejects_stale(
    tmp_path, production_console, production_app, monkeypatch, history_count,
):
    from copy import deepcopy
    from contextlib import contextmanager
    from time import perf_counter
    from src.review.revision_workflow import revise_object
    from tests.test_review_command_bounded_http_v1 import bounded_post_only, physical_state
    console, initial, command = system(tmp_path, production_console=production_console)
    sid = command['snapshot_id']
    documents = console.workflow_document_store
    rows = console._load_objects(sid)
    previous = next(obj for obj in initial if obj.get('proposed_object_type') == 'definition')
    while len(rows) < history_count:
        previous = revise_object(previous, deepcopy(previous), snapshot_id=sid,
            reason='Retained-history source command cost proof', actor='synthetic-fixture', force=True)
        rows.append(previous)
    console._save_objects(sid, rows, expected_revision=console.objects_revision(sid))
    data = {'snapshot_id': sid, 'source_object_ids': command['source_object_ids'],
            'reason': command['reason'], 'command_id': command['command_id'],
            'source_checked': '1'}
    holds, depth = [], 0
    lock = console._store_write_lock
    @contextmanager
    def measured_lock():
        nonlocal depth
        with lock():
            outer = depth == 0
            depth += 1
            started = perf_counter()
            try:
                yield
            finally:
                depth -= 1
                if outer:
                    holds.append(perf_counter() - started)
    with TestClient(production_app(console)) as client:
        assert client.post('/login', data={'username':'reviewer', 'password':'long-test-password'},
                           follow_redirects=False).status_code == 303
        from tests.test_source_context_review_ui_v1 import Forms
        with monkeypatch.context() as patch:
            def no_history(*args, **kwargs):
                raise AssertionError('source page loaded complete retained history')
            patch.setattr(documents, 'list_document_objects', no_history)
            page = client.get('/source-selection', params={'document':sid, 'task':'disposition'})
        assert page.status_code == 200, page.text
        form = next(row for row in Forms(page.text).forms
                    if row['attrs'].get('action') == '/review/source-exclusions')
        data['snapshot_revision'] = next(row['value'] for row in form['inputs']
                                         if row.get('name') == 'snapshot_revision')
        assert data['snapshot_revision'].startswith('review-generation-v1:')
        assert len(data['snapshot_revision']) < 512
        with bounded_post_only(console, sid, monkeypatch), monkeypatch.context() as patch:
            patch.setattr(console, '_store_write_lock', measured_lock)
            started = perf_counter()
            response = client.post('/review/source-exclusions', data=data, follow_redirects=False)
            elapsed = perf_counter() - started
        assert response.status_code == 303, response.text
        assert elapsed <= 3, elapsed
        assert max(holds) <= .250, holds
        durable = physical_state(console, sid)
        assert client.post('/review/source-exclusions', data=data, follow_redirects=False).status_code == 409
        assert physical_state(console, sid) == durable
    assert documents.review_command_window(sid, [obj['object_id'] for obj in initial]) is not None
    print({'source_history_rows': len(rows), 'http_seconds': elapsed, 'outer_hold_seconds': max(holds)})


def test_group_capture_includes_nonadjacent_automatic_context_target(complete_postgres):
    """The current group oracle consumes block-span links without an OID edge."""
    from copy import deepcopy
    from types import SimpleNamespace
    from src.integrity_kernel import stamp_canonical_hashes
    from src.review.review_command_v1 import capture_histories
    from src.review.source_context_review_v1 import source_group_candidates
    from src.vorming.source_containers_v1 import partition
    from src.workflows.workflow_transaction_v1 import workflow_transaction
    from tests.test_review_command_storage_v1 import seed
    from tests.test_source_containers_v1 import context_story
    store, _, sid, _ = seed(complete_postgres)
    rows = context_story()
    knowledge = partition(rows)['knowledge'][0]
    source = next(row['record'] for row in partition(rows)['source'] if row['usage']['kind'] == 'linked_context')
    # Place unrelated structural heads on either side of the shown source;
    # nearest-neighbour discovery cannot accidentally supply the distant target.
    source['structure']['sequence'] = 10
    knowledge['structure']['sequence'] = 1000
    for obj in rows:
        stamp_canonical_hashes(obj)
    rows += [{'object_id': 'unrelated-heading-' + str(seq), 'object_version':'1.0',
              'object_type':'heading', 'structure': {'sequence':seq}, 'text':'Synthetic unrelated heading'}
             for seq in (9, 11, 999)]
    oid = source['object_id']
    assert oid not in {obj['object_id'] for group in source_group_candidates(rows).values() for obj in group}
    assert oid in {obj['object_id'] for group in source_group_candidates([source]).values() for obj in group}
    store.write_bundle(envelope=store.get_envelope(sid), objects=rows)
    with workflow_transaction(store):
        histories = capture_histories(SimpleNamespace(workflow_document_store=store), sid, oid,
            {'_dependency_ids':[oid]}, admission_context=True)
    assert knowledge['object_id'] in {obj['object_id'] for obj in histories}
    assert oid not in {obj['object_id'] for group in source_group_candidates(histories).values() for obj in group}


def test_source_batch_final_audit_failure_rolls_back_all_native_state(tmp_path, production_console):
    from src.review.source_context_review_v1 import confirm_source_exclusions
    from tests.test_review_command_bounded_http_v1 import physical_state
    console, initial, command = system(tmp_path, production_console=production_console)
    store = console.workflow_document_store
    sid = command['snapshot_id']
    before = physical_state(console, sid)
    window = store.review_command_window(sid, [obj['object_id'] for obj in initial])
    events = console.workflow_review_store.read_events()
    with store._connect() as con:
        con.execute("CREATE FUNCTION workflow.test_batch_audit_failure() RETURNS trigger LANGUAGE plpgsql AS $$ "
                    "BEGIN RAISE EXCEPTION 'late_source_audit_failure'; END $$")
        con.execute('CREATE CONSTRAINT TRIGGER test_batch_audit_failure AFTER INSERT ON workflow.review_events '
                    'DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION workflow.test_batch_audit_failure()')
    with pytest.raises(Exception, match='late_source_audit_failure'):
        confirm_source_exclusions(console, **command)
    assert physical_state(console, sid) == before
    assert store.review_command_window(sid, [obj['object_id'] for obj in initial]).frontiers == window.frontiers
    assert console.workflow_review_store.read_events() == events


def test_group_reset_requires_original_source_fragments(tmp_path, production_console, monkeypatch):
    from src.operations_console_v1 import ConsoleError
    from src.review.source_context_review_v1 import confirm_source_group, reset_source_group
    from tests.test_b6_source_group_command import _document, _by_text, _command, FIRST
    from tests.test_review_command_bounded_http_v1 import physical_state
    console, sid, reviewer = _document(tmp_path, production_console=production_console)
    member = _by_text(console, sid, FIRST)
    confirm_source_group(console, **_command(console, sid, reviewer, ids=[member['object_id']]))
    revision = console.objects_revision(sid)
    before = physical_state(console, sid)
    def unavailable(*args, **kwargs):
        raise ConsoleError('source_read_fragments_unavailable')
    monkeypatch.setattr(console, '_read_source_fragments', unavailable)
    with pytest.raises(ConsoleError, match='source_read_fragments_unavailable'):
        reset_source_group(console, actor_id=reviewer, snapshot_id=sid, group_command_id='group-1',
                           reason='Recheck original source', command_id='reset-failure', expected_revision=revision)
    assert physical_state(console, sid) == before


def test_group_validates_changed_unchecked_member_with_fresh_generation(tmp_path, production_console):
    from src.operations_console_v1 import ConsoleError
    from src.review.review_passage_read_v1 import _revision
    from src.review.source_context_review_v1 import confirm_source_group, confirm_source_context
    from tests.test_b6_source_group_command import _document, _by_text, _command, FIRST, SECOND
    from tests.test_review_command_bounded_http_v1 import physical_state
    console, sid, reviewer = _document(tmp_path, production_console=production_console)
    selected, unchecked = _by_text(console, sid, FIRST), _by_text(console, sid, SECOND)
    command = _command(console, sid, reviewer, ids=[selected['object_id']])
    confirm_source_context(console, actor_id=reviewer, snapshot_id=sid,
        source_object_id=unchecked['object_id'], role='excluded', target_object_ids=[],
        reason='Independent source decision', command_id='changed-unchecked', expected_revision=console.objects_revision(sid))
    _, generation = console.workflow_document_store.review_document_input(sid)
    before = physical_state(console, sid)
    events = console.workflow_review_store.read_events()
    with pytest.raises(ConsoleError, match='source_group_members_changed'):
        confirm_source_group(console, **{**command, 'expected_revision':_revision(sid, generation)})
    assert physical_state(console, sid) == before
    assert console.workflow_review_store.read_events() == events
