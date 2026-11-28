"""The database admits only a class-bound, current decision-tree seal.

# release-control-evidence: opslag concurrent stale recovery
"""
from uuid import uuid4

import psycopg
import pytest

from src.integrity_kernel import stable_hash
from src.vorming import human_annotation_v1 as annotations
from src.vorming.decision_tree_construction_v1 import proposal_inputs
from src.vorming.human_annotation_decision_tree_v1 import INPUT_CONTRACT, proposal_from_entries
from src.workflows.processing_archives_v1 import encoded
from tests.test_annotation_source_background_postgres import received
from tests.test_v225_beslisboom_path import _boom_freeze_bytes


def test_tree_seal_requires_matching_route_and_generation(tmp_path, production_console):
    console, uploader, reviewer, _ = received(production_console, tmp_path)
    actor = uploader['account_id']
    sid = console.receive_source(
        actor_id=actor, filename='tree.json', data=_boom_freeze_bytes(), content_type='application/json',
        ingest_kind='new', title='Beslisboom', version='1.0', date='2026-11-10', live_url='',
        class_='beslisboom', family='test', named_reviewers=[reviewer['account_id']],
    )['snapshot_id']
    envelope = console._envelope(sid)
    record = annotations.source_record(console, envelope)
    annotations.pin_source(console, actor_id=actor, snapshot_id=sid, expected_revision=console.objects_revision(sid),
                           envelope=envelope, record=record)
    row, fragments = annotations._read_set(console, sid)
    block = proposal_inputs(fragments)[0]
    payload = {
        'contract': INPUT_CONTRACT, 'units': [{'ref': 'a', 'entry': True, 'selection': None,
            'role': 'action', 'spans': [{'block_id': block['block_id'], 'start': 0, 'end': len(block['text'])}]}],
        'connections': [], 'result_bundles': [], 'context_bindings': [], 'unresolved': [],
    }
    assert proposal_from_entries(payload, fragments=fragments, inventory={'items': {}})['units'][0]['quoted_text'] == block['text']
    aid = str(uuid4())
    with console.workflow_document_store._connect() as con:
        con.execute('INSERT INTO workflow.annotation_versions(snapshot_id,annotation_id,revision,status,'
                    'author_id,payload,payload_hash) VALUES (%s,%s,1,\'ready\',%s,%s,%s)',
                    (sid, aid, actor, encoded(payload), stable_hash(payload)))
        con.execute('INSERT INTO workflow.annotation_heads VALUES (%s,%s,1,1)', (sid, aid))
        con.execute('INSERT INTO workflow.annotation_commands(snapshot_id,command_id,actor_id,request_hash,result) '
                    'VALUES (%s,%s,%s,%s,%s)', (sid, str(uuid4()), actor, 'test-request',
                    encoded({'annotation_id': aid, 'revision': 1, 'generation': 1})))
        con.execute('UPDATE workflow.annotation_sets SET generation=1 WHERE snapshot_id=%s', (sid,))
        context = con.execute('SELECT workflow.annotation_materialization_context(d) AS context '
                              'FROM workflow.documents d WHERE snapshot_id=%s', (sid,)).fetchone()['context']
        basis = {key: row[key] for key in ('snapshot_id', 'working_revision_id', 'extraction_hash',
                                          'source_identity', 'objects_revision', 'normalization')}
        basis.update(version='human-annotation-v1', generation=1, context=context,
                     entries=[{'annotation_id': aid, 'revision': 1, 'payload_hash': stable_hash(payload)}])

        def insert_seal(fields):
            seal = {**fields, 'overview_hash': stable_hash(fields)}
            identity = stable_hash(seal)
            con.execute('INSERT INTO workflow.annotation_seals(seal_id,snapshot_id,extraction_hash,generation,'
                        'overview_hash,payload,payload_text,created_by) VALUES (%s,%s,%s,1,%s,%s,%s,%s)',
                        (identity, sid, row['extraction_hash'], seal['overview_hash'], encoded(seal), encoded(seal), actor))
            return identity

        with pytest.raises(psycopg.Error, match='annotation_seal_input_changed'), con.transaction():
            insert_seal(basis)
        tree = {**basis, 'route': 'decision-tree-annotation-v1'}
        with pytest.raises(psycopg.Error, match='annotation_seal_input_changed'), con.transaction():
            insert_seal({**tree, 'entries': []})
        identity = insert_seal(tree)
        con.execute('UPDATE workflow.annotation_sets SET current_seal_id=%s WHERE snapshot_id=%s', (identity, sid))
        current = 'SELECT workflow.annotation_seal_current(%s,%s) AS ok'
        assert con.execute(current, (sid, identity)).fetchone()['ok']
        con.execute('UPDATE workflow.annotation_sets SET generation=2,current_seal_id=NULL WHERE snapshot_id=%s', (sid,))
        assert not con.execute(current, (sid, identity)).fetchone()['ok']
        with pytest.raises(psycopg.Error, match='annotation_seal_stale'), con.transaction():
            con.execute('UPDATE workflow.annotation_sets SET current_seal_id=%s WHERE snapshot_id=%s', (identity, sid))
