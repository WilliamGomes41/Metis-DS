"""Native independent guards for bounded historical validation inputs.

# release-control-evidence: scope/belofte opslag concurrent stale recovery
# release-control-evidence: toegang kwaliteit slop releasebewijs
"""
from copy import deepcopy

import pytest

from src.review.revision_window_v1 import RevisionWindow
from src.review.revision_workflow import current_revisions, with_current_revision
from src.workflows import revision_frontiers_postgres_v1 as frontiers
from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
from tests.test_review_command_storage_v1 import seed, object_storage, document_counters


def certificates(store, sid):
    with store._connect() as con:
        return con.execute('SELECT * FROM workflow.object_revision_frontiers '
                           'WHERE snapshot_id=%s ORDER BY object_id', (sid,)).fetchall()


def test_window_changes_only_current_rows_and_preserves_first_object_order(complete_postgres):
    store, _, sid, _ = seed(complete_postgres)
    before = store.review_command_window(sid, ['delta-a', 'delta-b'])
    assert isinstance(before, RevisionWindow)
    assert [obj['object_id'] for obj in current_revisions(before)] == ['delta-a', 'delta-b']
    assert before.frontiers['delta-a']['history_count'] == 2
    physical = object_storage(store, sid)
    after = deepcopy(before)
    after[0]['text'] = 'Current governance-compatible payload'
    after = with_current_revision(after, {**after[0], 'object_version': '1.2'})
    envelope = store.get_envelope(sid)
    store.apply_review_changes(sid, before, after, envelope, envelope)
    actual = object_storage(store, sid)
    assert actual[0] == physical[0]  # hidden historical prefix remains physical
    assert actual[1] == physical[1]  # independent object remains physical
    captured = store.review_command_window(sid, ['delta-a', 'delta-b'])
    assert [obj['object_id'] for obj in current_revisions(captured)] == ['delta-a', 'delta-b']
    assert captured.frontiers['delta-a']['history_count'] == 3
    assert [row['object_version'] for row in store.review_command_histories(sid, ['delta-a'])] == ['1.0', '1.1', '1.2']


@pytest.mark.parametrize('kind', ['head', 'historical', 'identity', 'delete', 'truncate'])
def test_every_native_legacy_change_invalidates_the_frontier(complete_postgres, kind):
    store, _, sid, _ = seed(complete_postgres)
    before = store.review_command_window(sid, ['delta-a'])
    counters = document_counters(store, sid)
    with store._connect() as con:
        if kind in {'head', 'historical'}:
            version = '1.1' if kind == 'head' else '1.0'
            assert con.execute("UPDATE workflow.document_objects SET payload=jsonb_set(payload,'{text}',"
                "'\"Independent raw write\"'::jsonb) WHERE snapshot_id=%s AND object_id='delta-a' "
                'AND object_version=%s', (sid, version)).rowcount == 1
        elif kind == 'identity':
            con.execute("UPDATE workflow.document_objects SET object_id='renamed' WHERE snapshot_id=%s "
                        "AND object_id='delta-a' AND object_version='1.0'", (sid,))
        elif kind == 'delete':
            con.execute("DELETE FROM workflow.document_objects WHERE snapshot_id=%s AND object_id='delta-a' "
                        "AND object_version='1.0'", (sid,))
        else:
            con.execute('TRUNCATE workflow.document_objects')
    assert document_counters(store, sid) == counters  # legacy021 does not cover these writes
    assert store.review_command_window(sid, ['delta-a']) is None
    winner = object_storage(store, sid), certificates(store, sid)
    env = store.get_envelope(sid)
    with pytest.raises(WorkflowDocumentStoreError, match='snapshot_object_write_conflict'):
        store.apply_review_changes(sid, before, before, env, env)
    assert (object_storage(store, sid), certificates(store, sid)) == winner


def test_wrong_owner_and_changed_baseline_cannot_authorize_a_delta(complete_postgres):
    store, _, sid, _ = seed(complete_postgres)
    before = store.review_command_window(sid, ['delta-a'])
    env = store.get_envelope(sid)
    other = PostgresConcurrentWorkflowDocumentStore(complete_postgres)
    with pytest.raises(WorkflowDocumentStoreError, match='revision_window_mismatch'):
        other.apply_review_changes(sid, before, before, env, env)
    forged = deepcopy(before)
    forged[0]['text'] = 'Forged same-identity baseline'
    with pytest.raises(WorkflowDocumentStoreError, match='snapshot_object_write_conflict'):
        store.apply_review_changes(sid, forged, forged, env, env)
    with pytest.raises(WorkflowDocumentStoreError, match='revision_frontier_history_mismatch'):
        with store._connect() as con:
            frontiers.seal_complete(store, con, sid, list(before))


def test_extra_same_connection_history_write_rolls_back_entire_delta(complete_postgres, monkeypatch):
    store, _, sid, _ = seed(complete_postgres)
    before = store.review_command_window(sid, ['delta-a'])
    after = deepcopy(before)
    after[0]['text'] = 'Our intended current change'
    original = frontiers.seal_delta
    observed = []
    def extra_write(store, con, sid, *args):
        assert con.execute("UPDATE workflow.document_objects SET payload=jsonb_set(payload,'{text}',"
            "'\"Hidden historical write\"'::jsonb) WHERE snapshot_id=%s AND object_id='delta-a' "
            "AND object_version='1.0'", (sid,)).rowcount == 1
        observed.append(True)
        return original(store, con, sid, *args)
    monkeypatch.setattr(frontiers, 'seal_delta', extra_write)
    durable = object_storage(store, sid), document_counters(store, sid), certificates(store, sid)
    env = store.get_envelope(sid)
    with pytest.raises(WorkflowDocumentStoreError, match='snapshot_object_write_conflict'):
        store.apply_review_changes(sid, before, after, env, env)
    assert observed
    assert (object_storage(store, sid), document_counters(store, sid), certificates(store, sid)) == durable


def test_explicit_preparation_changes_no_authoritative_history(complete_postgres):
    store, _, sid, _ = seed(complete_postgres)
    with store._connect() as con:
        con.execute('UPDATE workflow.object_revision_frontiers SET certificate=NULL,certificate_hash=NULL '
                    'WHERE snapshot_id=%s', (sid,))
    assert store.review_command_window(sid, ['delta-a']) is None
    durable = object_storage(store, sid), document_counters(store, sid), store.get_envelope(sid)
    assert frontiers.prepare(store, sid)['status'] == 'prepared'
    assert isinstance(store.review_command_window(sid, ['delta-a']), RevisionWindow)
    assert (object_storage(store, sid), document_counters(store, sid), store.get_envelope(sid)) == durable


def test_preparation_refuses_an_independent_change_after_capture(complete_postgres, monkeypatch):
    store, _, sid, _ = seed(complete_postgres)
    original = frontiers._certificate
    written = []
    def stale(*args, **kwargs):
        if not written:
            with store._connect() as con:
                con.execute("UPDATE workflow.document_objects SET payload=jsonb_set(payload,'{text}',"
                    "'\"Preparation winner\"'::jsonb) WHERE snapshot_id=%s AND object_id='delta-a' "
                    "AND object_version='1.1'", (sid,))
            written.append(True)
        return original(*args, **kwargs)
    monkeypatch.setattr(frontiers, '_certificate', stale)
    with pytest.raises(WorkflowDocumentStoreError, match='snapshot_object_write_conflict'):
        frontiers.prepare(store, sid)
    assert written
    assert store.review_command_window(sid, ['delta-a']) is None
    assert store.review_command_histories(sid, ['delta-a'])[-1]['text'] == 'Preparation winner'


def test_corrupt_predecessor_cannot_acquire_a_new_frontier(tmp_path, production_console):
    from tests.test_t9_review_knowledge_authority import _console, _approve
    console, reviewer, sid, focal = _console(tmp_path, production_console=production_console)
    _approve(console, reviewer, sid, focal)  # real strict successor
    store = console.workflow_document_store
    assert store.review_command_window(sid, [focal['object_id']])
    with store._connect() as con:
        con.execute("UPDATE workflow.document_objects SET payload=jsonb_set(payload,'{content,clean_text}',"
            "'\"Corrupt predecessor\"'::jsonb) WHERE snapshot_id=%s AND object_id=%s AND object_version=%s",
            (sid, focal['object_id'], focal['object_version']))
    assert store.review_command_window(sid, [focal['object_id']]) is None
    with pytest.raises(ValueError, match='revision_predecessor_mismatch'):
        frontiers.prepare(store, sid)
    assert store.review_command_window(sid, [focal['object_id']]) is None


def test_strict_anchor_retains_the_original_self_hash_check(tmp_path, production_console):
    from src.review.revision_workflow import validate_revision_write
    from tests.test_t9_review_knowledge_authority import _console, _approve
    console, reviewer, sid, focal = _console(tmp_path, production_console=production_console)
    _approve(console, reviewer, sid, focal)
    store = console.workflow_document_store
    before = store.review_command_window(sid, [focal['object_id']])
    after = deepcopy(before)
    after[0]['provenance']['canonical_object_hash'] = '0' * 64
    full = store.review_command_histories(sid, [focal['object_id']])
    changed_full = [*full[:-1], after[0]]
    with pytest.raises(ValueError, match='revision_evidence_invalid'):
        current_revisions(changed_full, snapshot_id=sid)
    with pytest.raises(ValueError, match='revision_evidence_invalid'):
        validate_revision_write(before, after, snapshot_id=sid)
    env = store.get_envelope(sid)
    durable = object_storage(store, sid), certificates(store, sid)
    with pytest.raises(WorkflowDocumentStoreError):
        store.apply_review_changes(sid, before, after, env, env)
    assert (object_storage(store, sid), certificates(store, sid)) == durable


@pytest.mark.parametrize('column,value', [('object_id', 'different-physical-id'), ('object_version', '9.0')])
def test_preparation_refuses_physical_payload_identity_disagreement(complete_postgres, column, value):
    from psycopg import sql
    store, _, sid, _ = seed(complete_postgres)
    with store._connect() as con:
        con.execute(sql.SQL("UPDATE workflow.document_objects SET {}=%s WHERE snapshot_id=%s "
                            "AND object_id='delta-a' AND object_version='1.0'").format(sql.Identifier(column)),
                    (value, sid))
    with pytest.raises(WorkflowDocumentStoreError, match='revision_frontier_identity_mismatch'):
        frontiers.prepare(store, sid)


def test_hidden_history_retains_protection_and_publication_inputs(complete_postgres):
    from src.review.revision_workflow import validate_revision_write
    store, _, sid, _ = seed(complete_postgres)
    rows = store.list_document_objects(sid)
    rows[0]['metadata'] = {'semantic_passage': {'selection_origin': 'proposal_selected'}}
    rows[0]['governance'] = {'publication_status': 'published'}
    from psycopg.types.json import Jsonb
    # Explicit retained legacy state; ordinary writers correctly forbid this
    # historical edit. Preparation must preserve the full validator's inputs.
    with store._connect() as con:
        con.execute("UPDATE workflow.document_objects SET payload=%s WHERE snapshot_id=%s "
                    "AND object_id='delta-a' AND object_version='1.0'", (Jsonb(rows[0]), sid))
    frontiers.prepare(store, sid)
    before = store.review_command_window(sid, ['delta-a'])
    assert before.frontiers['delta-a']['historical_has_knowledge']
    assert before.frontiers['delta-a']['historical_has_publication']
    changed = deepcopy(before)
    changed[0]['content'] = {'clean_text': 'Forbidden in-place meaning change'}
    with pytest.raises(ValueError, match='revision_content_changed_in_place'):
        validate_revision_write(before, changed, snapshot_id=sid)
    proposed = deepcopy(before)
    proposed.append({**deepcopy(before[0]), 'object_version': '1.2',
        'metadata': {'semantic_passage': {'selection_origin': 'proposal_selected'}}})
    with pytest.raises(ValueError, match='published_working_revision_immutable'):
        validate_revision_write(before, proposed, snapshot_id=sid)


def test_current_publication_mirror_is_not_sticky_hidden_history(complete_postgres):
    store, _, sid, _ = seed(complete_postgres)
    before = store.review_command_window(sid, ['delta-a'])
    env = store.get_envelope(sid)
    published = deepcopy(before)
    published[0]['governance'] = {'publication_status': 'published'}
    store.apply_review_changes(sid, before, published, env, env)
    current = store.review_command_window(sid, ['delta-a'])
    assert not current.frontiers['delta-a']['historical_has_publication']
    opened = deepcopy(current)
    opened[0]['governance']['publication_status'] = 'unpublished'
    store.apply_review_changes(sid, current, opened, env, env)
    assert not store.review_command_window(sid, ['delta-a']).frontiers['delta-a']['historical_has_publication']


@pytest.mark.parametrize('carrier', ['raw', 'window'])
def test_final_transition_requires_exact_json_not_python_numeric_equality(complete_postgres, carrier):
    """A validated unchanged transition cannot authorize a different final value."""
    from psycopg.types.json import Jsonb
    from src.review.revision_workflow import validate_revision_write

    store, _, sid, _ = seed(complete_postgres)
    # Retained legacy input, with no strict edge: make the current object a
    # protected KnowledgeObject before capturing its actual validated baseline.
    rows = store.review_command_histories(sid, ['delta-a'])
    rows[-1]['metadata'] = {
        'semantic_passage': {'selection_origin': 'proposal_selected'},
        'measurement': 1,
    }
    with store._connect() as con:
        assert con.execute('UPDATE workflow.document_objects SET payload=%s '
            'WHERE snapshot_id=%s AND object_id=%s AND object_version=%s',
            (Jsonb(rows[-1]), sid, rows[-1]['object_id'], rows[-1]['object_version'])).rowcount == 1
    frontiers.prepare(store, sid)
    before = (store.review_command_window(sid, ['delta-a']) if carrier == 'window'
              else store.review_command_histories(sid, ['delta-a']))
    after = deepcopy(before)
    after[-1]['metadata']['measurement'] = 1.0
    assert after == before  # Python equality is insufficient for stored JSON.
    with pytest.raises(ValueError, match='revision_content_changed_in_place'):
        validate_revision_write(before, after, snapshot_id=sid)
    env = store.get_envelope(sid)
    durable = object_storage(store, sid), document_counters(store, sid), certificates(store, sid)
    with pytest.raises(WorkflowDocumentStoreError, match='workflow_review_transition_chain_invalid'):
        store.apply_review_changes(sid, before, after, env, env,
            transitions=[deepcopy(before)])
    assert (object_storage(store, sid), document_counters(store, sid), certificates(store, sid)) == durable


@pytest.mark.parametrize('bounded', [False, True])
def test_zero_commit_cannot_hide_a_numerically_equal_raw_delta(complete_postgres, bounded):
    store, _, sid, _ = seed(complete_postgres)
    before = store.review_command_histories(sid, ['delta-a'])
    env = store.get_envelope(sid)
    seeded = deepcopy(before)
    seeded[-1]['numeric_fixture'] = 1
    store.apply_review_changes(sid, before, seeded, env, env)
    before = store.review_command_window(sid, ['delta-a']) if bounded else seeded
    after = deepcopy(before)
    after[-1]['numeric_fixture'] = 1.0
    assert before == after  # Python equality cannot enforce exact JSON identity.
    durable = object_storage(store, sid), document_counters(store, sid), certificates(store, sid)
    with pytest.raises(WorkflowDocumentStoreError, match='workflow_review_commit_count_invalid'):
        store.apply_review_changes(sid, before, after, env, env, commit_count=0)
    assert (object_storage(store, sid), document_counters(store, sid), certificates(store, sid)) == durable


@pytest.mark.parametrize('fault', ['rewrite', 'suppress'])
def test_before_trigger_cannot_change_or_skip_the_former_head_in_a_successor_delta(
    tmp_path, production_console, fault,
):
    """Every written row matters, including a head becoming hidden history."""
    from psycopg import sql
    from src.review.revision_workflow import revise_object, validate_revision_write
    from tests.test_t9_review_knowledge_authority import _console, _approve

    console, reviewer, sid, focal = _console(tmp_path, production_console=production_console)
    _approve(console, reviewer, sid, focal)
    store = console.workflow_document_store
    before = store.review_command_window(sid, [focal['object_id']])
    governed = deepcopy(before)
    governed[0]['governance']['validation_status'] = 'revise'
    successor = revise_object(governed[0], governed[0], snapshot_id=sid,
        reason='Valid governance then successor transition', actor=reviewer['account_id'], force=True)
    after = governed + [successor]
    # The actual domain transitions are valid before the database fault: a
    # rejection must come from independent physical-delta verification.
    validate_revision_write(before, governed, snapshot_id=sid)
    validate_revision_write(governed, after, snapshot_id=sid)
    assert governed[0]['governance'] != before[0]['governance']
    env = store.get_envelope(sid)
    durable = object_storage(store, sid), document_counters(store, sid), certificates(store, sid)
    body = ("NEW.payload := jsonb_set(NEW.payload,'{content,clean_text}',"
            "'\"Rewritten predecessor content\"'::jsonb); RETURN NEW;"
            if fault == 'rewrite' else 'RETURN NULL;')
    with store._connect() as con:
        con.execute('CREATE FUNCTION workflow.met36_before_delta_fault() RETURNS trigger '
            'LANGUAGE plpgsql AS $$ BEGIN ' + body + ' END $$')
        con.execute(sql.SQL('CREATE TRIGGER met36_before_delta_fault BEFORE UPDATE '
            'ON workflow.document_objects FOR EACH ROW '
            'WHEN (OLD.snapshot_id={} AND OLD.object_id={} AND OLD.object_version={}) '
            'EXECUTE FUNCTION workflow.met36_before_delta_fault()').format(
                sql.Literal(sid), sql.Literal(focal['object_id']), sql.Literal(before[0]['object_version'])))
    with pytest.raises(WorkflowDocumentStoreError, match='snapshot_object_write_conflict'):
        store.apply_review_changes(sid, before, after, env, env, commit_count=2,
            transitions=[governed, after])
    assert (object_storage(store, sid), document_counters(store, sid), certificates(store, sid)) == durable


def test_native0_unselected_raw_writer_uses_existing_document_serialization(complete_postgres):
    """An unselected paragraph cannot move while its admission view is protected."""
    import psycopg

    store, _, sid, _ = seed(complete_postgres)
    with store._connect() as con:
        assert con.execute('SELECT processing_storage_version FROM workflow.documents '
            'WHERE snapshot_id=%s', (sid,)).fetchone()['processing_storage_version'] in (None, 0)
    before = object_storage(store, sid), document_counters(store, sid), certificates(store, sid)
    with store._connect() as owner:
        with owner.transaction():
            assert owner.execute('SELECT snapshot_id FROM workflow.documents '
                'WHERE snapshot_id=%s FOR UPDATE', (sid,)).fetchone()
            neighbours = frontiers.admission_neighbors(store, owner, sid, ['delta-a'])
            assert neighbours == ['delta-b']
            # This is an independent native connection, not a nested savepoint
            # on a workflow ContextVar. The raw writer targets an unselected OID.
            with store._connect() as writer:
                with pytest.raises(psycopg.errors.LockNotAvailable) as blocked:
                    with writer.transaction():
                        writer.execute("SET LOCAL lock_timeout='200ms'")
                        writer.execute("UPDATE workflow.document_objects SET payload=jsonb_set("
                            "payload,'{structure}','{\"sequence\":-1}'::jsonb) "
                            "WHERE snapshot_id=%s AND object_id='delta-b'", (sid,))
                assert blocked.value.sqlstate == '55P03'
            assert frontiers.admission_neighbors(store, owner, sid, ['delta-a']) == neighbours
            assert (object_storage(store, sid), document_counters(store, sid), certificates(store, sid)) == before
    # Once the same existing document boundary is released, the identical raw
    # edit commits and invalidates the derived index before it can be reused.
    with store._connect() as writer:
        assert writer.execute("UPDATE workflow.document_objects SET payload=jsonb_set("
            "payload,'{structure}','{\"sequence\":-1}'::jsonb) "
            "WHERE snapshot_id=%s AND object_id='delta-b'", (sid,)).rowcount == 1
    assert store.review_command_window(sid, ['delta-b']) is None
    with store._connect() as reader:
        assert frontiers.admission_neighbors(store, reader, sid, ['delta-a']) is None
    assert document_counters(store, sid) == before[1]
    after = object_storage(store, sid)
    assert [row for row in after if row['object_id'] == 'delta-a'] == [
        row for row in before[0] if row['object_id'] == 'delta-a']
    assert next(row for row in after if row['object_id'] == 'delta-b')['payload']['structure']['sequence'] == -1
