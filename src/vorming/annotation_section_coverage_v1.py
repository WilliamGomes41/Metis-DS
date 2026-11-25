"""Section coverage belongs to the confirmed structure of one working revision."""
from datetime import datetime, timezone
import re

from src.integrity_kernel import stable_hash
from src.vorming import confirmed_document_structure_v1 as structure
from src.vorming import human_annotation_v1 as annotations
from src.vorming.semantic_passage_v1 import semantic_source_blocks
from src.workflows.processing_archives_v1 import encoded
from src.workflows.workflow_transaction_v1 import workflow_transaction

KEY = 'section_coverage'


def read(con, snapshot_id):
    if con.execute("SELECT to_regclass('workflow.annotation_section_coverage') AS name").fetchone()['name'] is None:
        return None
    return con.execute('SELECT scope, confirmations FROM workflow.annotation_section_coverage WHERE snapshot_id=%s',
                       (snapshot_id,)).fetchone()


def sections(definition, blocks):
    headings = {row['block_id']: row for row in definition['entries']}
    current, by_block, outline = None, {}, []
    for block in blocks:
        anchor = block['block_id']
        if anchor in headings:
            current = headings[anchor]
            outline.append(current)
        elif current is None:
            current = {'block_id': anchor, 'title': 'Vóór de eerste kop', 'level': 1}
            outline.append(current)
        by_block[anchor] = current['block_id']
    return outline, by_block


def project(definition, blocks, heads, recorded):
    outline, by_block = sections(definition, blocks)
    recorded = recorded or {'scope': 'selection', 'confirmations': {}}
    confirmed = recorded['confirmations']
    fingerprints = {row['block_id']: [] for row in outline}
    for head in heads:
        payload = head['payload']
        if payload['status'] != 'ready' or payload.get('disposition') is not None:
            continue
        for anchor in payload['ranges']:
            if anchor['role'] == 'core':
                section = by_block.get(anchor['block_id'])
                if section is not None:
                    fingerprints[section].append((head['annotation_id'], anchor['block_id'],
                                                  anchor['start'], anchor['end']))
    basis = stable_hash(definition)
    result = []
    for row in outline:
        key = row['block_id']
        fingerprint = stable_hash([basis, key, sorted(fingerprints[key])])
        receipt = confirmed.get(key)
        status = ('checked' if receipt['fingerprint'] == fingerprint else 'stale') if receipt else 'open'
        result.append({**row, 'fingerprint': fingerprint, 'status': status})
    return {'basis': basis, 'scope': recorded['scope'], 'sections': result}


def valid_receipts(definition, blocks, receipts):
    outline, _ = sections(definition, blocks)
    if not isinstance(receipts, dict) or not receipts.keys() <= {row['block_id'] for row in outline}:
        return False
    for entry in receipts.values():
        if (not isinstance(entry, dict) or set(entry) != {'fingerprint', 'actor_id', 'recorded_at'}
                or not all(isinstance(value, str) and value for value in entry.values())
                or not re.fullmatch('[0-9a-f]{64}', entry['fingerprint'])):
            return False
        try:
            if datetime.fromisoformat(entry['recorded_at']).tzinfo is None:
                return False
        except ValueError:
            return False
    return True


def write(console, *, actor_id, snapshot_id, basis, scope=None, section=None, fingerprint=None):
    annotations.authorize(console, actor_id, console._envelope(snapshot_id))
    if scope is not None:
        if scope not in ('selection', 'full') or section is not None or fingerprint is not None:
            annotations.fail('annotation_coverage_invalid')
    elif not section or not fingerprint:
        annotations.fail('annotation_coverage_invalid')
    pinned, fragments = annotations._read_set(console, snapshot_id)
    blocks = semantic_source_blocks(fragments)
    store = console.workflow_document_store
    with console._store_write_lock(), workflow_transaction(store) as con:
        envelope = annotations._locked(console, con, actor_id, snapshot_id)
        active = con.execute('SELECT working_revision_id, extraction_hash FROM workflow.annotation_sets '
                             'WHERE snapshot_id=%s FOR UPDATE', (snapshot_id,)).fetchone()
        definition = structure.read(con, snapshot_id)
        if (not active or active['extraction_hash'] != pinned['extraction_hash']
                or active['working_revision_id'] != envelope['working_revision_id']
                or definition is None or stable_hash(definition) != basis):
            annotations.fail('annotation_coverage_stale')
        recorded = read(con, snapshot_id) or {'scope': 'selection', 'confirmations': {}}
        if scope is not None:
            if scope == recorded['scope']:
                return
            recorded['scope'] = scope
        else:
            if recorded['scope'] != 'full':
                annotations.fail('annotation_coverage_scope_closed')
            view = project(definition, blocks, annotations._annotation_heads(con, snapshot_id)['entries'], recorded)
            target = next((row for row in view['sections'] if row['block_id'] == section), None)
            if target is None or target['fingerprint'] != fingerprint:
                annotations.fail('annotation_coverage_stale')
            if target['status'] == 'checked':
                return
            recorded['confirmations'][section] = {
                'fingerprint': fingerprint, 'actor_id': actor_id, 'recorded_at': datetime.now(timezone.utc).isoformat(),
            }
        con.execute('INSERT INTO workflow.annotation_section_coverage (snapshot_id, scope, confirmations, updated_by) '
                    'VALUES (%s,%s,%s::jsonb,%s) ON CONFLICT (snapshot_id) DO UPDATE SET '
                    'scope=EXCLUDED.scope, confirmations=EXCLUDED.confirmations, updated_by=EXCLUDED.updated_by, '
                    'updated_at=CURRENT_TIMESTAMP',
                    (snapshot_id, recorded['scope'], encoded(recorded['confirmations']), actor_id))
