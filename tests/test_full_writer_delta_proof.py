"""Actual generic writes keep prepared lineage without a second prefix read.

# release-control-evidence: scope/belofte opslag concurrent stale recovery
# release-control-evidence: toegang kwaliteit slop releasebewijs
"""
from copy import deepcopy
import pytest
from src.workflows import revision_frontiers_postgres_v1 as frontiers
from tests.test_review_command_storage_v1 import seed,object_storage,document_counters


def test_full_writer_does_not_reread_history_to_seal_already_validated_delta(complete_postgres,monkeypatch):
    store,_,sid,_=seed(complete_postgres)
    rows=store.list_document_objects(sid)
    rows[-1]['text']='A current governance-compatible legacy edit'
    def forbidden(*args,**kwargs):raise AssertionError('second full history seal')
    monkeypatch.setattr(frontiers,'seal_complete',forbidden)
    store.write_bundle(envelope=store.get_envelope(sid),objects=rows)
    window=store.review_command_window(sid,['delta-a','delta-b'])
    assert window is not None
    assert window[0]['text']==rows[-1]['text']
    assert window.frontiers['delta-a']['history_count']==2


@pytest.mark.parametrize('fault', ['rewrite', 'suppress', 'position', 'after', 'extra', 'delete', 'insert_extra'])
def test_full_writer_refuses_physical_sql_fault_and_rolls_back(complete_postgres, monkeypatch, fault):
    """Actual native SQL, not a mocked writer or a caller-supplied certificate."""
    from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
    from src.workflows import review_card_inputs_postgres_v1 as cards
    store, _, sid, _ = seed(complete_postgres)
    before = object_storage(store, sid), document_counters(store, sid)
    rows = store.list_document_objects(sid)
    rows[-1]['text'] = 'An intended current change'
    if fault == 'delete':
        rows = [obj for obj in rows if obj['object_id'] != 'delta-b']
    if fault == 'extra':
        maintain = cards.maintain
        def change_hidden(store, con, snapshot_id, *args, **kwargs):
            maintain(store, con, snapshot_id, *args, **kwargs)
            con.execute("UPDATE workflow.document_objects SET payload=jsonb_set(payload,'{text}',"
                "'\"Unexpected hidden edit\"') WHERE snapshot_id=%s AND object_id='delta-a' "
                "AND object_version='1.0'", (snapshot_id,))
        monkeypatch.setattr(cards, 'maintain', change_hidden)
    else:
        operation = 'DELETE' if fault == 'delete' else 'UPDATE'
        timing = 'AFTER' if fault in {'after', 'insert_extra'} else 'BEFORE'
        action = {
            'rewrite': "NEW.payload=jsonb_set(NEW.payload,'{text}','\"Rewritten by SQL\"'); RETURN NEW;",
            'suppress': 'RETURN NULL;',
            'position': 'NEW.position=NEW.position+100; RETURN NEW;',
            'after': "IF NEW.object_version='1.1' THEN UPDATE workflow.document_objects "
                     "SET payload=jsonb_set(payload,'{text}','\"Unexpected hidden edit\"') "
                     "WHERE snapshot_id=NEW.snapshot_id AND object_id=NEW.object_id AND object_version='1.0'; "
                     "END IF; RETURN NEW;",
            'delete': 'RETURN NULL;',
            'insert_extra': "INSERT INTO workflow.document_objects(snapshot_id,object_id,object_version,position,payload) "
                            "VALUES(NEW.snapshot_id,'unplanned','1.0',99,"
                            "jsonb_build_object('object_id','unplanned','object_version','1.0','text','Unexpected')); RETURN NEW;",
        }[fault]
        with store._connect() as con:
            con.execute('CREATE FUNCTION workflow.test_full_delta_fault() RETURNS trigger LANGUAGE plpgsql AS $$ '
                        'BEGIN ' + action + ' END $$')
            con.execute(f'CREATE TRIGGER test_full_delta_fault {timing} {operation} ON workflow.document_objects '
                        'FOR EACH ROW EXECUTE FUNCTION workflow.test_full_delta_fault()')
    with pytest.raises(WorkflowDocumentStoreError, match='snapshot_object_write_conflict'):
        store.write_bundle(envelope=store.get_envelope(sid), objects=rows)
    assert (object_storage(store, sid), document_counters(store, sid)) == before
    assert store.review_command_window(sid, ['delta-a', 'delta-b']) is not None


def test_full_writer_retains_legacy_schema_and_metadata_only_contracts(complete_postgres):
    store, _, sid, _ = seed(complete_postgres)
    physical = object_storage(store, sid)
    envelope = store.get_envelope(sid)
    revision = store.objects_revision(sid)
    assert store.write_bundle(envelope={**envelope, 'title':'Metadata only'}, expected_revision=revision) == revision
    assert object_storage(store, sid) == physical
    with store._connect() as con:
        con.execute('DROP TRIGGER zz_object_revision_frontier_change ON workflow.document_objects')
        con.execute('DROP TRIGGER zz_object_revision_frontier_truncate ON workflow.document_objects')
        con.execute('ALTER TABLE workflow.document_objects DROP CONSTRAINT workflow_object_revision_frontier_fk')
        con.execute('DROP TABLE workflow.object_revision_frontiers')
    store._revision_frontier_schema = False
    rows = store.list_document_objects(sid)
    rows[-1]['text'] = 'Legacy schema write is still supported'
    store.write_bundle(envelope=store.get_envelope(sid), objects=rows)
    assert store.list_document_objects(sid) == rows
    assert store.review_command_window(sid, ['delta-a']) is None


def test_full_writer_checks_returned_insert_and_connection_binding(complete_postgres):
    from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
    store, _, sid, _ = seed(complete_postgres)
    rows = store.list_document_objects(sid)
    with store._connect() as con:
        con.execute('SELECT snapshot_id FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE', (sid,))
        captured = store._objects_locked(con, sid)
    with store._connect() as con:
        with pytest.raises(WorkflowDocumentStoreError, match='snapshot_object_write_conflict'):
            store._write_objects_locked(con, sid, captured, rows)
    before = object_storage(store, sid), document_counters(store, sid)
    rows.append({**deepcopy(rows[-1]), 'object_version': '1.2'})
    with store._connect() as con:
        con.execute("CREATE FUNCTION workflow.test_full_insert_fault() RETURNS trigger LANGUAGE plpgsql AS $$ "
                    "BEGIN NEW.payload=jsonb_set(NEW.payload,'{text}','\"Unexpected inserted value\"'); RETURN NEW; END $$")
        con.execute('CREATE TRIGGER test_full_insert_fault BEFORE INSERT ON workflow.document_objects '
                    'FOR EACH ROW EXECUTE FUNCTION workflow.test_full_insert_fault()')
    with pytest.raises(WorkflowDocumentStoreError, match='snapshot_object_write_conflict'):
        store.write_bundle(envelope=store.get_envelope(sid), objects=rows)
    assert (object_storage(store, sid), document_counters(store, sid)) == before
