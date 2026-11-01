"""MET-43: real protected Review after another runtime wins preparation.

# release-control-evidence: scope/belofte opslag concurrent stale recovery
# release-control-evidence: toegang kwaliteit slop releasebewijs
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
from threading import Event

import pytest

from src.operations_console_v1 import ConsoleError
from src.integrity_kernel import compute_canonical_object_hash
from src.review.review_policy_v1 import missing_reviewers, object_policy
from src.review.review_duty_v1 import exact_current_approver_ids
from src.review.review_passage_read_v1 import _revision
from src.workflows.account_retirement_v1 import retire_account
from tests.production_support import restart_production
from tests.semantic_fixture_support import bind_fixture_selections
from tests.test_explicit_review_policy import policy


@pytest.fixture
def system(tmp_path, production_console):
    a = production_console(root=tmp_path, runtime=tmp_path / 'runtime-a',
                           processing_binder=bind_fixture_selections)
    accounts = {name: a.create_account(username=name, password='fixture-only', roles=roles)
                for name, roles in [('researcher', ('researcher', 'reviewer')),
                                    ('reviewer', ('reviewer',)), ('publisher', ('publisher',))]}
    bind_fixture_selections(a, [('Oedeem is een ophoping van vocht.', 'definition')])
    sid = a.ingest(actor_id=accounts['researcher']['account_id'], filename='source.html',
        content_type='text/html',
        data=b'<html><body><h1>Begrippen</h1><p>Oedeem is een ophoping van vocht.</p></body></html>',
        ingest_kind='new', title='Native dependency handoff', version='1.0', date='2026-11-01',
        live_url='', class_='richtlijn', family='test', named_reviewers=[],
        review_policy=policy(accounts, 'optional'))['snapshot_id']
    focal = next(o for o in a.snapshot_objects(sid) if o.get('proposed_object_type') == 'definition')
    b = production_console(root=tmp_path, runtime=tmp_path / 'runtime-b',
        source_store=a.source_store, immutable_source_store=a.immutable_source_store,
        processing_binder=bind_fixture_selections)
    assert a.runtime != b.runtime
    return a, b, accounts, sid, focal


def durable(console, sid):
    """Logical durable truth, including facts/counters, independent of local maps."""
    with console.workflow_document_store._connect() as con:
        document = con.execute('SELECT revision,object_generation,envelope_payload '
            'FROM workflow.documents WHERE snapshot_id=%s', (sid,)).fetchone()
        objects = con.execute('SELECT object_id,object_version,position,payload '
            'FROM workflow.document_objects WHERE snapshot_id=%s ORDER BY position', (sid,)).fetchall()
        bindings = con.execute('SELECT authorization_id,position,authorization_payload '
            'FROM workflow.publish_authorizations WHERE snapshot_id=%s '
            'ORDER BY position NULLS LAST,authorization_id', (sid,)).fetchall()
        facts = con.execute('SELECT * FROM workflow.review_object_facts WHERE snapshot_id=%s '
            'ORDER BY object_id', (sid,)).fetchall()
        fact_state = con.execute('SELECT * FROM workflow.review_fact_state WHERE snapshot_id=%s',
                                 (sid,)).fetchall()
    return dict(document=document, objects=objects, bindings=bindings, facts=facts,
                fact_state=fact_state, events=console.workflow_review_store.read_events())


def approve(console, accounts, sid, focal, **extra):
    return console.review_object(actor_id=accounts['researcher']['account_id'], snapshot_id=sid,
        object_id=focal['object_id'], decision='approve', confirmed_object_type='definition', **extra)


@contextmanager
def prepared_handoff(console, monkeypatch):
    """Pause precisely after actual source preparation, before the first write lock.

    Thread contextvars and native connections are independent. Timeouts only
    detect a broken test; Events establish order without sleeps/file locks.
    """
    prepared, resume = Event(), Event()
    original = console._store_write_lock
    original_source = console._read_source_fragments
    entered = []
    source_reads = []

    def read_source(*args, **kwargs):
        value = original_source(*args, **kwargs)
        source_reads.append(True)
        return value

    @contextmanager
    def paused():
        if not entered:
            from src.workflows.workflow_transaction_v1 import workflow_transaction_active
            assert source_reads, 'handoff occurred before actual source preparation'
            assert not workflow_transaction_active(), 'handoff still owns an outer SQL transaction'
            entered.append(True)
            prepared.set()
            assert resume.wait(15), 'test failed to release prepared command'
        with original():
            yield

    monkeypatch.setattr(console, '_store_write_lock', paused)
    monkeypatch.setattr(console, '_read_source_fragments', read_source)
    with ThreadPoolExecutor(max_workers=1) as executor:
        try:
            yield executor, prepared, resume
        finally:
            resume.set()
    assert entered, 'test did not reach external-preparation handoff'


def participation(console, accounts, sid, action, reviewer_id):
    return console.manage_review_participation(actor_id=accounts['publisher']['account_id'],
        snapshot_id=sid, command_id='handoff-' + action, expected_revision=console.objects_revision(sid),
        reason='Synthetic dependency race', action=action, reviewer_id=reviewer_id)


def test_actor_retirement_after_preparation_refuses_without_review_delta(system, monkeypatch):
    a, b, accounts, sid, focal = system
    with prepared_handoff(a, monkeypatch) as (pool, prepared, resume):
        future = pool.submit(approve, a, accounts, sid, focal)
        assert prepared.wait(15)
        with b.workflow_identity_store._connect() as con:
            retire_account(con, account_id=accounts['researcher']['account_id'],
                actor_id=accounts['publisher']['account_id'], reason='Synthetic retirement', apply=True)
        winner = durable(b, sid)
        resume.set()
        with pytest.raises(ConsoleError, match='not_authenticated'):
            future.result(timeout=15)
    assert durable(restart_production(b), sid) == winner


def test_archived_participant_after_preparation_is_currently_denied(system, monkeypatch):
    a, b, accounts, sid, focal = system
    def deferred():
        # None is intentional: refusal must come from the roster, not a token.
        return a.review_object(actor_id=accounts['reviewer']['account_id'], snapshot_id=sid,
                               object_id=focal['object_id'], decision='later')
    with prepared_handoff(a, monkeypatch) as (pool, prepared, resume):
        future = pool.submit(deferred)
        assert prepared.wait(15)
        participation(b, accounts, sid, 'archive', accounts['reviewer']['account_id'])
        winner = durable(b, sid)
        resume.set()
        with pytest.raises(ConsoleError, match='reviewer_not_named_on_snapshot'):
            future.result(timeout=15)
    assert durable(restart_production(b), sid) == winner


def test_policy_added_after_preparation_cannot_be_satisfied_by_old_roster(system, monkeypatch):
    a, b, accounts, sid, focal = system
    extra = b.create_account(username='new-required', password='fixture-only', roles=('reviewer',))
    with prepared_handoff(a, monkeypatch) as (pool, prepared, resume):
        future = pool.submit(approve, a, accounts, sid, focal)
        assert prepared.wait(15)
        participation(b, accounts, sid, 'add_required', extra['account_id'])
        current_policy = deepcopy(b._envelope(sid)['review_policy'])
        resume.set()
        future.result(timeout=15)
    fresh = restart_production(b)
    current = next(o for o in fresh.snapshot_objects(sid) if o['object_id'] == focal['object_id'])
    assert object_policy(current) == current_policy
    assert missing_reviewers(current, fresh.object_review_bindings(sid)) == {extra['account_id']}
    readiness = fresh.consider_publish(actor_id=accounts['publisher']['account_id'], snapshot_id=sid)
    assert 'required_policy_review_missing' in readiness['blockers']
    assert fresh.canonical_publication_store.release_for_snapshot(sid) is None


def test_equivalent_source_repreparation_does_not_invent_a_conflict(system, monkeypatch):
    a, b, accounts, sid, focal = system
    documents = b.workflow_document_store
    with documents._connect() as con:
        before_pin = con.execute('SELECT review_source_ref FROM workflow.documents '
            'WHERE snapshot_id=%s', (sid,)).fetchone()['review_source_ref']
    assert before_pin
    with prepared_handoff(a, monkeypatch) as (pool, prepared, resume):
        future = pool.submit(approve, a, accounts, sid, focal)
        assert prepared.wait(15)
        reference = b.prepare_review_source_views(actor_id=accounts['researcher']['account_id'],
            snapshot_id=sid, expected_revision=b.objects_revision(sid))
        assert reference == before_pin
        resume.set()
        future.result(timeout=15)
    fresh = restart_production(b)
    current = next(o for o in fresh.snapshot_objects(sid) if o['object_id'] == focal['object_id'])
    assert current['governance']['validation_status'] == 'approved'
    assert fresh.object_review_bindings(sid)
    with documents._connect() as con:
        assert con.execute('SELECT review_source_ref FROM workflow.documents '
            'WHERE snapshot_id=%s', (sid,)).fetchone()['review_source_ref'] == before_pin


@pytest.mark.parametrize('variant', ['generation', 'm2', 'unconditional'])
def test_same_version_binding_winner_preserves_each_public_precondition(system, monkeypatch, variant):
    a, b, accounts, sid, focal = system
    participation(b, accounts, sid, 'archive', accounts['reviewer']['account_id'])
    participation(b, accounts, sid, 'add_required', accounts['reviewer']['account_id'])
    # Establish primary approval first. The required colleague's racing second
    # review changes governance/bindings without replacing the canonical version.
    approve(a, accounts, sid, focal)
    focal = next(o for o in a.snapshot_objects(sid) if o['object_id'] == focal['object_id'])
    token = None
    if variant == 'm2':
        token = a.objects_revision(sid)
    elif variant == 'generation':
        _, counters = a.workflow_document_store.review_document_input(sid, command=True)
        token = _revision(sid, counters)
    before_version = focal['object_version']
    bindings_before = deepcopy(b.object_review_bindings(sid))
    with prepared_handoff(a, monkeypatch) as (pool, prepared, resume):
        future = pool.submit(approve, a, accounts, sid, focal, expected_revision=token)
        assert prepared.wait(15)
        b.approve_second_review(actor_id=accounts['reviewer']['account_id'],
                                snapshot_id=sid, object_id=focal['object_id'])
        after = next(o for o in b.snapshot_objects(sid) if o['object_id'] == focal['object_id'])
        assert after['object_version'] == before_version  # governance/binding-only race
        assert compute_canonical_object_hash(after) == compute_canonical_object_hash(focal)
        bindings_after = b.object_review_bindings(sid)
        assert bindings_after != bindings_before
        assert set(exact_current_approver_ids(after, bindings_after)) == {
            accounts['researcher']['account_id'], accounts['reviewer']['account_id']}
        winner = durable(b, sid)
        assert winner['bindings']
        resume.set()
        if variant == 'unconditional':
            future.result(timeout=15)  # existing semantic duplicate, no extra evidence
        else:
            with pytest.raises(ConsoleError, match='snapshot_object_write_conflict'):
                future.result(timeout=15)
    assert durable(restart_production(b), sid) == winner


def test_composed_review_final_event_failure_rolls_back_all_participants(system, monkeypatch):
    a, b, accounts, sid, focal = system
    before = durable(b, sid)
    observed = []
    reviews = a.workflow_review_store
    original = reviews._flush_buffer
    def fail_final_flush(events):
        staged = durable(a, sid)  # bound to the actual open command connection
        assert staged['objects'] != before['objects']
        assert staged['bindings'] != before['bindings']
        assert staged['document']['revision'] > before['document']['revision']
        observed.append(True)
        raise RuntimeError('controlled final audit failure')
    monkeypatch.setattr(reviews, '_flush_buffer', fail_final_flush)
    with pytest.raises(RuntimeError, match='controlled final audit failure'):
        approve(a, accounts, sid, focal)
    assert observed
    assert durable(restart_production(b), sid) == before
    monkeypatch.setattr(reviews, '_flush_buffer', original)
    approve(b, accounts, sid, focal)
    after = durable(restart_production(b), sid)
    assert after['objects'] != before['objects']
    assert after['bindings'] and after['events'] != before['events']
