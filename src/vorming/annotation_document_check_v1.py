"""The annotation round and the input to the existing build seal."""
import os

from src.vorming import annotation_section_coverage_v1 as coverage
from src.vorming import confirmed_document_structure_v1 as structure
from src.vorming import human_annotation_v1 as annotations
from src.vorming.semantic_passage_v1 import semantic_source_blocks
from src.workflows.workflow_transaction_v1 import workflow_transaction

KEY = 'document_check'


def enabled():
    return os.getenv('METIS_ANNOTATION_DOCUMENT_CHECK') == '1'


def storage_available(con):
    return con.execute("SELECT to_regclass('workflow.annotation_round_events') AS name").fetchone()['name'] is not None


def read(con, snapshot_id):
    if not storage_available(con):
        return None
    return con.execute('SELECT revision, phase, generation, actor_id FROM workflow.annotation_round_events '
                       'WHERE snapshot_id=%s ORDER BY revision DESC LIMIT 1', (snapshot_id,)).fetchone()


def transition(console, *, actor_id, snapshot_id, phase, expected_generation, expected_round):
    if phase not in ('annotating', 'checking') or type(expected_generation) is not int or type(expected_round) is not int:
        annotations.fail('annotation_document_round_invalid')
    with console._store_write_lock(), workflow_transaction(console.workflow_document_store) as con:
        annotations._locked(console, con, actor_id, snapshot_id)
        active = con.execute('SELECT generation FROM workflow.annotation_sets WHERE snapshot_id=%s FOR UPDATE',
                             (snapshot_id,)).fetchone()
        if active is None:
            annotations.fail('annotation_source_not_prepared')
        if not storage_available(con):
            annotations.fail('annotation_document_round_unavailable')
        current = read(con, snapshot_id)
        if current is None and (not enabled() or structure.has_seal(con, snapshot_id)):
            annotations.fail('annotation_document_round_unavailable')
        if current is None and structure.enabled() and structure.read(con, snapshot_id) is None:
            annotations.fail('annotation_structure_confirmation_required')
        if current is None and phase != 'checking':
            annotations.fail('annotation_document_round_stale')
        revision = current['revision'] if current else 0
        if active['generation'] != expected_generation:
            annotations.fail('annotation_document_round_stale')
        if current and current['phase'] == phase and expected_round in (revision, revision - 1):
            return current
        if revision != expected_round:
            annotations.fail('annotation_document_round_stale')
        from src.vorming.human_annotation_build_v1 import latest_build
        build = latest_build(con, snapshot_id)
        if build and build['state'] == 'running':
            annotations.fail('processing_attempt_in_progress')
        return con.execute('INSERT INTO workflow.annotation_round_events(snapshot_id,revision,phase,generation,actor_id) '
                           'VALUES(%s,%s,%s,%s,%s) RETURNING revision,phase,generation,actor_id',
                           (snapshot_id, revision + 1, phase, expected_generation, actor_id)).fetchone()


def capture(con, snapshot_id, current):
    recorded = coverage.read(con, snapshot_id) or {'scope': 'selection', 'confirmations': {}}
    return {'version': 1, 'round': current, 'scope': recorded['scope'],
            'confirmations': recorded['confirmations'] if recorded['scope'] == 'full' else {}}


def findings(check, definition, entries, fragments):
    if check['round']['phase'] != 'checking':
        return [{'annotation_id': None, 'code': 'annotation_document_round_required'}]
    if check['scope'] == 'selection':
        return []
    if check['scope'] != 'full' or definition is None:
        return [{'annotation_id': None, 'code': 'annotation_document_coverage_required'}]
    view = coverage.project(definition, semantic_source_blocks(fragments), entries, check)
    return [{'annotation_id': None, 'code': 'annotation_document_coverage_required',
             'section': row['block_id'], 'title': row['title']}
            for row in view['sections'] if row['status'] != 'checked']
