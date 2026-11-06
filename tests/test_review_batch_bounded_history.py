"""Actual bounded batch invocation must preserve the original member kernels.

# release-control-evidence: scope/belofte opslag concurrent stale recovery
# release-control-evidence: toegang kwaliteit metrics slop releasebewijs
"""

from tests.ko_review_fixture_support import affirmative_assessment
from copy import deepcopy
from contextlib import contextmanager
from time import perf_counter
import gc
import pytest

from src.review.revision_workflow import revise_object
from src.review.review_passage_read_v1 import _revision
from tests.test_a08_heading_batch_atomic import _setup


def test_native_heading_batch_keeps_history_outside_command(tmp_path, production_console, monkeypatch):
    console, accounts, sid, ids = _setup(tmp_path, production_console=production_console)
    current = console.snapshot_objects(sid)
    other = next(obj for obj in current if obj.get('proposed_object_type') not in {None,'document','heading','path'})
    previous = other
    rows = console._load_objects(sid)
    while len(rows) < 1500:
        previous = revise_object(previous, deepcopy(previous), snapshot_id=sid,
            reason='Native retained-history batch proof', actor='synthetic-fixture', force=True)
        rows.append(previous)
    console._save_objects(sid, rows, expected_revision=console.objects_revision(sid))
    store, reviews = console.workflow_document_store, console.workflow_review_store
    _, generation = store.review_document_input(sid)
    source = console._verified_source_bytes
    def outside_lock(*args, **kwargs):
        # Scoped source access may borrow verified bytes; actual original I/O
        # is prepared before the outer command. Forbid the unscoped old path.
        from src.review.review_command_state_v1 import active_review_command
        assert active_review_command(console) is not None or not console._store_lock_depth
        return source(*args, **kwargs)
    def no_full(*args, **kwargs):
        raise AssertionError('batch loaded complete retained history/global state')
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
                    holds.append(perf_counter()-started)
    with monkeypatch.context() as patch:
        patch.setattr(console, '_store_write_lock', measured_lock)
        patch.setattr(store, 'list_document_objects', no_full)
        patch.setattr(store, 'write_bundle', no_full)
        patch.setattr(reviews, 'read_events', no_full)
        patch.setattr(console, '_verified_source_bytes', outside_lock)
        started = perf_counter()
        result = console.batch_confirm_headings(actor_id=accounts['reviewer']['account_id'],
            snapshot_id=sid, object_ids=ids, expected_revision=_revision(sid, generation))
        elapsed = perf_counter() - started
    assert {obj['object_id'] for obj in result} == set(ids)
    assert elapsed <= 3, elapsed
    assert max(holds) <= .250, holds
    print({'heading_batch_history':1500,'seconds':elapsed,'outer_hold_seconds':max(holds)})
    final = console.snapshot_objects(sid)
    assert next(obj for obj in final if obj['object_id'] == previous['object_id']) == previous
    assert all(obj['governance']['validation_status'] == 'approved' for obj in final if obj['object_id'] in ids)


from tests.test_v233_review_audit_regressions import review_system  # noqa: F401


def test_native_normal_batch_is_one_bounded_command_and_returns_only_selected(review_system, monkeypatch):
    console, _client, sid, actor, ids = review_system
    store = console.workflow_document_store
    _, generation = store.review_document_input(sid)
    def no_full(*args, **kwargs):
        raise AssertionError('normal batch loaded whole-history/global state')
    with monkeypatch.context() as patch:
        patch.setattr(store, 'list_document_objects', no_full)
        patch.setattr(store, 'write_bundle', no_full)
        result = console.batch_review_normal_risk(actor_id=actor, snapshot_id=sid,
            object_ids=ids, expected_revision=_revision(sid, generation), assessment=affirmative_assessment(), evidence_not_applicable=True)
    assert {obj['object_id'] for obj in result} == set(ids)
    assert len(result) == len(ids)
    assert all(obj['governance']['validation_status'] == 'approved' for obj in result)


@pytest.mark.parametrize('kind', ['heading', 'normal'])
def test_batch_rejects_foreign_snapshot_interaction_identity(
    tmp_path, production_console, review_system, kind,
):
    from src.operations_console_v1 import ConsoleError
    from src.review.review_interaction_v1 import build_review_interaction_evidence, new_review_interaction_id
    from tests.test_review_command_bounded_http_v1 import physical_state
    if kind == 'heading':
        console, accounts, sid, ids = _setup(tmp_path / 'headings', production_console=production_console)
        actor = accounts['reviewer']['account_id']
        operation, interaction_kind = console.batch_confirm_headings, 'structure'
    else:
        console, _client, sid, actor, ids = review_system
        operation, interaction_kind = console.batch_review_normal_risk, 'batch'
    store, reviews = console.workflow_document_store, console.workflow_review_store
    members = store.review_command_current_heads(sid, ids)
    evidence = build_review_interaction_evidence(interaction_id=new_review_interaction_id(),
        interaction_kind=interaction_kind, reviewer_account_id=actor, snapshot_id=sid,
        review_stage='first_review', members=members)
    foreign = {**deepcopy(evidence), 'snapshot_id':'another-snapshot'}
    reviews.append_event(event_type='review_object', object_id='foreign-object', object_version='1.0',
        actor='synthetic-fixture', details={'snapshot_id':'another-snapshot', 'review_interaction':foreign})
    _, generation = store.review_document_input(sid)
    before, events = physical_state(console, sid), reviews.read_events()
    with pytest.raises(ConsoleError, match='review_interaction_identity_conflict'):
        operation(actor_id=actor, snapshot_id=sid, object_ids=ids,
            expected_revision=_revision(sid, generation), interaction_evidence=evidence)
    assert physical_state(console, sid) == before
    assert reviews.read_events() == events


from tests.test_review_render_source_reuse import review_client  # noqa: F401


@pytest.mark.parametrize('review_client', ['batch-large'], indirect=True)
def test_twenty_member_batch_uses_actual_compact_http_form(review_client, monkeypatch):
    from tests.test_source_context_review_ui_v1 import Forms
    console, client, sid = review_client
    # Collect unreachable ASGI/console cycles from preceding fixtures before
    # the normal GET/POST flow; automatic GC and command budgets stay unchanged.
    gc.collect()
    page = client.get('/review', params={'document':sid, 'task':'batch'})
    assert page.status_code == 200
    form = next(row for row in Forms(page.text).forms
                if row['attrs'].get('action') == '/review/normal-risk/batch-confirm')
    data = {row['name']:row.get('value','') for row in form['inputs'] if row.get('type') == 'hidden'}
    ids = [row['value'] for row in form['inputs'] if row.get('name') == 'object_ids']
    assert len(ids) == 20
    assert data['snapshot_revision'].startswith('review-generation-v1:')
    before = {row['object_id']:row for row in console.snapshot_objects(sid) if row['object_id'] not in ids}
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
                    holds.append(perf_counter()-started)
    from tests.test_review_command_bounded_http_v1 import bounded_post_only
    source_reader = console._prepared_review_source
    from src.review import review_command_v1 as commands
    transaction = commands.workflow_transaction
    writes = []
    @contextmanager
    def measured_transaction(owner):
        started = perf_counter()
        try:
            with transaction(owner) as connection:
                yield connection
        finally:
            writes.append(perf_counter()-started)
    def source_before_write_lock(*args, **kwargs):
        assert not console._store_lock_depth, 'batch member reopened source inputs under the write lock'
        return source_reader(*args, **kwargs)
    with bounded_post_only(console, sid, monkeypatch), monkeypatch.context() as patch:
        patch.setattr(console, '_store_write_lock', measured_lock)
        patch.setattr(console, '_prepared_review_source', source_before_write_lock)
        patch.setattr(commands, 'workflow_transaction', measured_transaction)
        started = perf_counter()
        result = client.post('/review/normal-risk/batch-confirm', data={**data,'object_ids':ids}, follow_redirects=False)
        elapsed = perf_counter()-started
    print({'normal_batch_members':20,'http_seconds':elapsed,'outer_hold_seconds':max(holds),
           'write_transaction_seconds':max(writes)})
    assert result.status_code == 303, result.text
    assert elapsed <= 3, elapsed
    assert max(holds) <= .250, holds
    assert len(writes) == 1 and max(writes) <= .500, writes
    final = {row['object_id']:row for row in console.snapshot_objects(sid)}
    assert all(final[oid] == row for oid,row in before.items())
    assert all(final[oid]['governance']['validation_status'] == 'approved' for oid in ids)
