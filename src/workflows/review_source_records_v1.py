"""Selective immutable source records owned by FormationTaskStore.

The publisher validates the complete existing source oracle once. Readers verify
selected membership/content under the same trusted immutable PostgreSQL model;
they never turn a read window into whole-document closure or approval evidence.
"""
from dataclasses import dataclass
import json

from src.integrity_kernel import stable_hash
from src.request_diagnostics_v1 import diagnostic_phase
from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError, _json_text


def fail(code='source_read_integrity_failed'):
    raise WorkflowDocumentStoreError(code)


@dataclass(frozen=True)
class PreparedReadSource:
    views_id: str
    extraction_hash: str
    header: str
    header_hash: str
    fragments: tuple
    blocks: tuple
    members: tuple


def references(value):
    blocks, fragments = set(), set()
    def visit(item):
        if isinstance(item, dict):
            for key, child in item.items():
                if key == 'block_id' and isinstance(child, str):
                    blocks.add(child)
                elif key in {'raw_object_id', 'fragment_id'} and isinstance(child, str):
                    fragments.add(child)
                elif key == 'source_fragment_ids' and isinstance(child, (list, tuple)):
                    fragments.update(v for v in child if isinstance(v, str))
                visit(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                visit(child)
    visit(value)
    return blocks, fragments


def block_fragments(pair):
    _, deps = references(pair)
    deps.update(pair[0]['source_fragment_ids'])
    for span in pair[1].get('_raw_source_mapping', []):
        deps.update(span[k] for k in ('left_fragment_id','right_fragment_id') if k in span)
    return deps


class ReviewSourceRecords:
    @diagnostic_phase('source_views_prepare_records')
    def prepare_review_source(self, input_reference, payload):
        from src.vorming.prepared_source_views_v1 import contract, prepare
        from src.vorming.source_preparation_context_v1 import KEY, stored_extraction
        with self.documents._connect() as con:
            if 'extraction_hash' in input_reference:
                row = con.execute('SELECT record_hash,payload FROM workflow.prepared_extraction_versions '
                    'WHERE record_hash=%s AND snapshot_id=%s',
                    (input_reference['extraction_hash'], input_reference['snapshot_id'])).fetchone()
            else:
                row = con.execute('SELECT e.record_hash,e.payload FROM workflow.formation_inputs i '
                    'JOIN workflow.prepared_extraction_versions e ON e.record_hash=i.extraction_hash '
                    'WHERE i.artifact_id=%s AND i.snapshot_id=%s',
                    (input_reference['artifact_id'], input_reference['snapshot_id'])).fetchone()
        if not row:
            fail('formation_input_missing')
        extraction = row['payload']
        if (extraction.get('record_hash') != row['record_hash']
                or extraction.get('source', {}).get('snapshot_id') != input_reference['snapshot_id']):
            fail('formation_input_source_mismatch')
        raw = stored_extraction({**extraction['source'], KEY: extraction})
        views_id = stable_hash({'extraction_hash': row['record_hash'], 'contract': contract()})
        with self.documents._connect() as con:
            existing = con.execute('SELECT header,header_hash,sealed FROM workflow.source_read_roots WHERE views_id=%s',
                                   (views_id,)).fetchone()
        if existing is not None:
            header = existing['header']
            if (not existing['sealed'] or stable_hash(header) != existing['header_hash']
                    or header.get('views_id') != views_id or header.get('layout') != 1
                    or header.get('extraction_hash') != row['record_hash']
                    or header.get('source') != extraction['source']
                    or header.get('version') != payload.get('version')
                    or header.get('fragments_hash') != extraction['fragments_hash']
                    or header.get('docling_hash') != stable_hash(extraction.get('docling_record'))
                    or header.get('extractor_contract') != extraction['extractor_contract']
                    or header.get('contract') != contract()):
                fail()
            recorded = {**payload, 'extraction_hash': row['record_hash'],
                        'extractor_contract': extraction['extractor_contract']}
            if stable_hash(recorded) != header['payload_hash']:
                fail('source_read_oracle_mismatch')
            # This exact payload already passed the complete source oracle at
            # immutable publication. Reuse its proof on retry, without rebuilding.
            return PreparedReadSource(views_id, row['record_hash'], _json_text(header),
                                      existing['header_hash'], (), (), ())
        # Constructor checks alone establish mapping shape, not that supplied
        # text was actually reconstructed from the recorded raw source. Compare
        # the complete existing oracle before publishing any derived membership.
        # This one-time work happens outside document/claim transactions.
        root = prepare(raw)
        if stable_hash(payload) != stable_hash(root.payload):
            fail('source_read_oracle_mismatch')
        # JSONB dictionary order has no identity meaning. Derive aliases and
        # record order from the canonical oracle, never deserialization order.
        payload = root.payload
        views_id = stable_hash({'extraction_hash': row['record_hash'], 'contract': contract()})
        header = {k: payload[k] for k in ('version', 'contract', 'fragments_hash')}
        record = {**payload, 'extraction_hash': row['record_hash'],
                  'extractor_contract': extraction['extractor_contract']}
        header.update(layout=1, views_id=views_id, extraction_hash=row['record_hash'],
            source=extraction['source'], extractor_contract=extraction['extractor_contract'],
            payload_hash=stable_hash(record), fragment_count=len(raw),
            filters={name: {target: root.filters[(name, target)].name
                if root.filters[(name, target)] is not None else None for target in root.carriers}
                for name in root.carriers}, docling_hash=stable_hash(extraction.get('docling_record')))
        # prepare() already proves that equal raw-index views share exactly the
        # same block pairs. Store/transfer that payload once, retaining all six
        # public views and the original global filter semantics in the header.
        header['aliases'] = {name: root.filters[(name, name)].name for name in root.carriers}
        canonical_views = {name:payload['views'][name] for name in root.carriers
                           if header['aliases'][name] == name}
        fragments, blocks, members = [], [], []
        membership = {name: set(view['fragment_indices']) for name, view in payload['views'].items()}
        block_membership = {r['fragment_id']: {name: [] for name in payload['views']} for r in raw}
        for name, view in canonical_views.items():
            for pair in view['blocks']:
                for fid in block_fragments(pair):
                    if fid not in block_membership:
                        fail()
                    block_membership[fid][name].append(pair[0]['block_id'])
        hashes = {}
        for ordinal, fragment in enumerate(raw):
            views = tuple(name for name, indices in membership.items() if ordinal in indices)
            manifest = block_membership[fragment['fragment_id']]
            hashes[fragment['fragment_id']] = stable_hash({'ordinal': ordinal, 'views': list(views),
                                                         'blocks': manifest, 'payload': fragment})
            fragments.append((views_id, fragment['fragment_id'], ordinal, views, _json_text(manifest),
                              hashes[fragment['fragment_id']], _json_text(fragment)))
        for name, view in canonical_views.items():
            for ordinal, pair in enumerate(view['blocks']):
                public, source = pair
                deps = block_fragments(pair)
                if not deps or not deps <= hashes.keys():
                    fail()
                block_hash = stable_hash({'view_name': name, 'block_id': public['block_id'],
                    'ordinal': ordinal, 'fragment_count': len(deps), 'payload': pair})
                blocks.append((views_id, name, public['block_id'], ordinal, len(deps), block_hash, _json_text(pair)))
                members.extend((views_id, name, public['block_id'], fid, hashes[fid]) for fid in sorted(deps))
        header['block_count'] = len(blocks)
        return PreparedReadSource(views_id, row['record_hash'], _json_text(header), stable_hash(header),
                                  tuple(fragments), tuple(blocks), tuple(members))

    @diagnostic_phase('source_views_publish_records')
    def publish_review_source(self, prepared, *, con=None):
        from src.workflows.workflow_transaction_v1 import workflow_transaction_active
        if con is None:
            if workflow_transaction_active():
                fail('source_read_preparation_requires_independent_transaction')
            with self.documents._connect() as connection:
                return self.publish_review_source(prepared, con=connection)
        con.execute('INSERT INTO workflow.source_read_roots(views_id,extraction_hash,header,header_hash) '
            'VALUES(%s,%s,%s::jsonb,%s) ON CONFLICT DO NOTHING',
            (prepared.views_id, prepared.extraction_hash, prepared.header, prepared.header_hash))
        row = con.execute('SELECT extraction_hash,header_hash,header,sealed FROM workflow.source_read_roots '
                          'WHERE views_id=%s FOR UPDATE', (prepared.views_id,)).fetchone()
        if (row['extraction_hash'] != prepared.extraction_hash or row['header_hash'] != prepared.header_hash
                or row['header'] != json.loads(prepared.header)):
            fail('formation_immutable_record_conflict')
        if not row['sealed']:
            with con.cursor() as cursor:
                cursor.executemany('INSERT INTO workflow.source_read_fragments '
                    '(views_id,fragment_id,ordinal,views,blocks,payload_hash,payload) VALUES(%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb)',
                    [(a,b,c,list(d),e,f,g) for a,b,c,d,e,f,g in prepared.fragments])
                cursor.executemany('INSERT INTO workflow.source_read_blocks '
                    '(views_id,view_name,block_id,ordinal,fragment_count,payload_hash,payload) '
                    'VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb)', prepared.blocks)
                cursor.executemany('INSERT INTO workflow.source_read_block_fragments '
                    '(views_id,view_name,block_id,fragment_id,payload_hash) VALUES(%s,%s,%s,%s,%s)', prepared.members)
            con.execute('UPDATE workflow.source_read_roots SET sealed=true WHERE views_id=%s', (prepared.views_id,))
        return {'layout': 1, 'views_id': prepared.views_id, 'extraction_hash': prepared.extraction_hash,
                'header_hash': prepared.header_hash}

    @diagnostic_phase('source_views_read_records')
    def read_review_source(self, envelope, *, objects=None):
        import psycopg
        try:
            return self._read_review_source(envelope, objects=objects)
        except (KeyError, TypeError, IndexError, ValueError) as error:
            raise WorkflowDocumentStoreError('source_read_integrity_failed') from error
        except psycopg.Error as error:
            raise WorkflowDocumentStoreError('source_read_unavailable') from error

    def _read_review_source(self, envelope, *, objects=None):
        from src.vorming.prepared_source_views_v1 import ReadSource, contract
        from src.vorming.source_preparation_context_v1 import KEY, VERSION, SourceIdentity
        from dataclasses import asdict
        extraction = envelope.get(KEY)
        if not extraction:
            return None
        views_id = stable_hash({'extraction_hash': extraction['record_hash'], 'contract': contract()})
        with self.documents._connect() as con:
            if con.execute("SELECT to_regclass('workflow.source_read_roots') AS table_name").fetchone()['table_name'] is None:
                if envelope.get('_review_source_ref') is not None:
                    fail('source_read_root_missing')
                has_column = con.execute("SELECT 1 FROM information_schema.columns WHERE table_schema='workflow' "
                    "AND table_name='documents' AND column_name='review_source_ref'").fetchone()
                if has_column and con.execute('SELECT review_source_ref FROM workflow.documents WHERE snapshot_id=%s',
                    (envelope['snapshot_id'],)).fetchone()['review_source_ref'] is not None:
                    fail('source_read_root_missing')
                return None
            reference = envelope.get('_review_source_ref')
            if reference is None:
                # One bounded lookup captures both the optional pin and root.
                # A missing root must still expose an existing pin and fail closed.
                row = con.execute('SELECT r.extraction_hash,r.header,r.header_hash,r.sealed,d.review_source_ref '
                    'FROM workflow.documents d LEFT JOIN workflow.source_read_roots r ON r.views_id=%s '
                    'WHERE d.snapshot_id=%s', (views_id, envelope['snapshot_id'])).fetchone()
                reference = row.pop('review_source_ref') if row else None
                if row is not None and row['extraction_hash'] is None:
                    row = None
            else:
                row = con.execute('SELECT extraction_hash,header,header_hash,sealed FROM workflow.source_read_roots '
                                  'WHERE views_id=%s', (views_id,)).fetchone()
            if row is None:
                if reference:
                    fail('source_read_root_missing')
                return None
            header = row['header']
            if (not row['sealed'] or stable_hash(header) != row['header_hash']
                    or extraction.get('version') != VERSION
                    or extraction.get('source') != header.get('source')
                    or row['extraction_hash'] != extraction['record_hash']
                    or header.get('extraction_hash') != extraction['record_hash']
                    or header.get('views_id') != views_id or header.get('layout') != 1
                    or header.get('source') != asdict(SourceIdentity.from_envelope(envelope))
                    or header.get('fragments_hash') != extraction['fragments_hash']
                    or header.get('extractor_contract') != extraction['extractor_contract']
                    or header.get('contract') != contract()):
                fail()
            expected_ref = {'layout': 1, 'views_id': views_id,
                            'extraction_hash': row['extraction_hash'], 'header_hash': row['header_hash']}
            if reference is not None and reference != expected_ref:
                fail('source_read_reference_invalid')
            block_ids, raw_ids = references(objects)
            complete = objects is None or not (block_ids or raw_ids)
            if complete:
                blocks = con.execute('SELECT * FROM workflow.source_read_blocks WHERE views_id=%s '
                                     'ORDER BY view_name,ordinal', (views_id,)).fetchall()
                members = con.execute('SELECT view_name,block_id,fragment_id,payload_hash '
                    'FROM workflow.source_read_block_fragments WHERE views_id=%s', (views_id,)).fetchall()
                fragments = con.execute('SELECT * FROM workflow.source_read_fragments WHERE views_id=%s '
                                        'ORDER BY ordinal', (views_id,)).fetchall()
            else:
                blocks, members, fragments = [], [], []
                pending_blocks, pending_raw = set(block_ids), set(raw_ids)
                seen_blocks, seen_raw = set(), set()
                while pending_blocks or pending_raw:
                    if pending_blocks:
                        requested = sorted(pending_blocks)
                        seen_blocks.update(pending_blocks)
                        pending_blocks.clear()
                        blocks.extend(con.execute('SELECT * FROM workflow.source_read_blocks WHERE views_id=%s '
                            'AND block_id=ANY(%s) ORDER BY view_name,ordinal', (views_id,requested)).fetchall())
                        loaded_members = con.execute('SELECT view_name,block_id,fragment_id,payload_hash '
                            'FROM workflow.source_read_block_fragments WHERE views_id=%s AND block_id=ANY(%s)',
                            (views_id,requested)).fetchall()
                        members.extend(loaded_members)
                        pending_raw.update(m['fragment_id'] for m in loaded_members if m['fragment_id'] not in seen_raw)
                    if pending_raw:
                        requested = sorted(pending_raw)
                        seen_raw.update(pending_raw)
                        pending_raw.clear()
                        loaded_raw = con.execute('SELECT * FROM workflow.source_read_fragments WHERE views_id=%s '
                            'AND fragment_id=ANY(%s) ORDER BY ordinal', (views_id,requested)).fetchall()
                        if {r['fragment_id'] for r in loaded_raw} != set(requested):
                            fail('source_read_fragment_missing')
                        fragments.extend(loaded_raw)
                        pending_blocks.update(bid for row in loaded_raw for ids in row['blocks'].values()
                                              for bid in ids if bid not in seen_blocks)
                if not block_ids <= {r['block_id'] for r in blocks}:
                    fail('source_read_block_missing')
        with diagnostic_phase('source_views_validate'):
            fragments.sort(key=lambda r:r['ordinal'])
            blocks.sort(key=lambda r:(r['view_name'],r['ordinal']))
            expected = {r['fragment_id']: r['payload_hash'] for r in members}
            if complete and (len(fragments) != header['fragment_count'] or len(blocks) != header['block_count']):
                fail()
            by_id = {r['fragment_id']: r for r in fragments}
            if not (raw_ids | expected.keys()) <= by_id.keys():
                fail('source_read_fragment_missing')
            views = {name: {'fragment_indices': [], 'blocks': []} for name in header['filters']}
            for index, fragment in enumerate(fragments):
                if (fragment['payload_hash'] != stable_hash({k:fragment[k] for k in ('ordinal','views','blocks','payload')})
                        or fragment['payload'].get('fragment_id') != fragment['fragment_id']
                        or fragment['fragment_id'] in expected and fragment['payload_hash'] != expected[fragment['fragment_id']]):
                    fail()
                for name in fragment['views']:
                    views[name]['fragment_indices'].append(index)
            dependencies = {}
            actual_membership = set()
            for member in members:
                dependencies.setdefault((member['view_name'], member['block_id']), []).append(member)
                actual_membership.add((member['view_name'],member['block_id'],member['fragment_id']))
                if member['payload_hash'] != by_id[member['fragment_id']]['payload_hash']:
                    fail()
            declared_membership = {(name,bid,row['fragment_id']) for row in fragments
                                   for name, ids in row['blocks'].items() for bid in ids}
            if actual_membership != declared_membership:
                fail('source_read_block_missing')
            for block in blocks:
                deps = dependencies.get((block['view_name'], block['block_id']), [])
                if (block['payload_hash'] != stable_hash({k:block[k] for k in
                        ('view_name','block_id','ordinal','fragment_count','payload')})
                        or block['payload'][0]['block_id'] != block['block_id']
                        or len(deps) != block['fragment_count']):
                    fail()
                required = block_fragments(block['payload'])
                if required != {d['fragment_id'] for d in deps}:
                    fail()
                views[block['view_name']]['blocks'].append(block['payload'])
            for name, original in header['aliases'].items():
                if original not in views or header['aliases'][original] != original:
                    fail()
                views[name]['blocks'] = views[original]['blocks']
            def docling():
                with self.documents._connect() as con:
                    row = con.execute("SELECT payload->'docling_record' AS record FROM workflow.prepared_extraction_versions "
                                      'WHERE record_hash=%s', (extraction['record_hash'],)).fetchone()
                record = row['record'] if row else None
                if stable_hash(record) != header['docling_hash']:
                    fail()
                return record
        with diagnostic_phase('source_views_hydrate'):
            result = ReadSource([r['payload'] for r in fragments], views, header, expected_ref,
                                complete=complete, docling_loader=docling)
        return result.fragments
