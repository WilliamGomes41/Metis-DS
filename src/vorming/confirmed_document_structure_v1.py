"""The human-confirmed section structure belongs to one prepared annotation source."""
import os

from src.integrity_kernel import stamp_canonical_hashes
from src.vorming import human_annotation_v1 as annotations
from src.vorming.semantic_passage_v1 import semantic_source_blocks
from src.workflows.processing_archives_v1 import encoded
from src.workflows.workflow_transaction_v1 import workflow_transaction

KEY = 'confirmed_document_structure'
SECTION_KEY = 'confirmed_section'


def enabled():
    return os.getenv('METIS_ANNOTATION_CONFIRMED_STRUCTURE') == '1'


def in_source_contents(path):
    return bool(path and path[0].casefold() == 'inhoudsopgave')


def heading_level(block, path):
    if block.get('heading') and block['heading'] == block['text']:
        return min(5, max(2, len(path) + 1))
    return None


def proposed(blocks):
    result = []
    for block in blocks:
        path = block.get('section_path') or []
        level = heading_level(block, path)
        if level is not None and not in_source_contents(path):
            result.append({'block_id': block['block_id'], 'title': block['text'], 'level': level - 1})
    return result


def validated(entries, blocks):
    if not isinstance(entries, list) or not entries:
        annotations.fail('annotation_structure_invalid')
    expected = [row['block_id'] for row in proposed(blocks)]
    if len(entries) != len(expected):
        annotations.fail('annotation_structure_stale')
    result = []
    for anchor, row in zip(expected, entries):
        if not isinstance(row, dict) or set(row) != {'block_id', 'title', 'level'} or row['block_id'] != anchor:
            annotations.fail('annotation_structure_stale')
        title, level = row['title'], row['level']
        if (not isinstance(title, str) or not title.strip() or len(title) > 2000
                or any(ord(char) < 32 for char in title)
                or type(level) is not int or not 1 <= level <= 4):
            annotations.fail('annotation_structure_invalid')
        result.append({'block_id': anchor, 'title': title.strip(), 'level': level})
    return result


def read(con, snapshot_id):
    # Legacy processes may open the overview before the additive migration.
    if con.execute("SELECT to_regclass('workflow.annotation_structure_confirmations') AS name").fetchone()['name'] is None:
        return None
    row = con.execute('SELECT definition FROM workflow.annotation_structure_confirmations WHERE snapshot_id=%s',
                      (snapshot_id,)).fetchone()
    return row['definition'] if row else None


def anchors(definition):
    return frozenset(entry['block_id'] for entry in definition['entries']) if definition is not None else frozenset()


def has_seal(con, snapshot_id):
    return con.execute('SELECT 1 FROM workflow.annotation_seals WHERE snapshot_id=%s LIMIT 1',
                       (snapshot_id,)).fetchone() is not None


def confirm(console, *, actor_id, snapshot_id, extraction_hash, entries):
    annotations.authorize(console, actor_id, console._envelope(snapshot_id))
    row, fragments = annotations._read_set(console, snapshot_id)
    if row['extraction_hash'] != extraction_hash:
        annotations.fail('annotation_structure_stale')
    entries = validated(entries, semantic_source_blocks(fragments))
    store = console.workflow_document_store
    with console._store_write_lock(), workflow_transaction(store) as con:
        envelope = annotations._locked(console, con, actor_id, snapshot_id)
        active = con.execute('SELECT working_revision_id, extraction_hash FROM workflow.annotation_sets '
                             'WHERE snapshot_id=%s FOR UPDATE', (snapshot_id,)).fetchone()
        if (not active or active['extraction_hash'] != extraction_hash
                or active['working_revision_id'] != envelope['working_revision_id']):
            annotations.fail('annotation_structure_stale')
        existing = read(con, snapshot_id)
        if existing is not None:
            if existing['entries'] == entries:
                return existing
            annotations.fail('annotation_structure_conflict')
        if has_seal(con, snapshot_id):
            annotations.fail('annotation_structure_already_built')
        definition = {'version': 1, 'entries': entries, 'extraction_hash': extraction_hash,
                      'working_revision_id': active['working_revision_id']}
        con.execute('INSERT INTO workflow.annotation_structure_confirmations '
                    '(snapshot_id, extraction_hash, working_revision_id, actor_id, definition) '
                    'VALUES (%s,%s,%s,%s,%s::jsonb)',
                    (snapshot_id, extraction_hash, active['working_revision_id'], actor_id, encoded(definition)))
        return definition


def project(objects, definition, blocks):
    """Add built section labels without changing exact-source path or identity."""
    entries = {row['block_id']: row for row in validated(definition['entries'], blocks)}
    path_by_anchor, stack = {}, []
    for block in blocks:
        anchor = block['block_id']
        heading = entries.get(anchor)
        if heading:
            while stack and stack[-1]['level'] >= heading['level']:
                stack.pop()
            stack.append(heading)
        path_by_anchor[anchor] = {'anchors': [item['block_id'] for item in stack],
                                 'titles': [item['title'] for item in stack]}
    for obj in objects:
        semantic = (obj.get('metadata') or {}).get('semantic_passage') or {}
        spans = semantic.get('spans') or []
        if spans:
            semantic[SECTION_KEY] = path_by_anchor[spans[0]['block_id']]
            stamp_canonical_hashes(obj)


def confirmed_section(obj):
    return ((obj.get('metadata') or {}).get('semantic_passage') or {}).get(SECTION_KEY)
