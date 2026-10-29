"""WP7 native immutable source reads, independent of Review permissions.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: metrics
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy

import pytest

from src.vorming.prepared_source_views_v1 import prepare
from src.vorming.source_preparation_context_v1 import stored_extraction
from src.workflows.formation_task_store_v1 import FormationTaskStore
from tests.test_formation_task_store_postgres import prepared, checkpoint_context, validator_data


def source_records(tmp_path, production_console):
    console, envelope, data = prepared(tmp_path, production_console)
    # Recreate a pre-WP7 database: original extraction/views remain, no additive
    # read records or read reference. This is privileged test setup only.
    with console.workflow_document_store._connect() as con:
        con.execute('TRUNCATE workflow.source_read_roots CASCADE')
        con.execute('UPDATE workflow.documents SET review_source_ref=NULL')
        con.execute("UPDATE workflow.processing_attempts SET payload=payload #- '{diagnostic,review_source_ref}'")
    writer = checkpoint_context(console, envelope, data)
    root = prepare(stored_extraction(envelope))
    store = writer.store
    artifact = store.prepare_review_source(writer.input_reference, root.payload)
    return console, envelope, store, root, artifact


def test_full_and_selected_reads_preserve_exact_views_after_restart(tmp_path, production_console):
    console, envelope, store, root, artifact = source_records(tmp_path, production_console)
    assert store.read_review_source(envelope) is None  # Explicit legacy absence.
    store.publish_review_source(artifact)
    fresh = FormationTaskStore(console.workflow_document_store)
    full = fresh.read_review_source(envelope)
    assert full.root.complete
    for name, original in root.carriers.items():
        actual = full.root.carriers[name]
        assert list(actual) == list(original)
        assert list(actual.blocks) == list(original.blocks)
        for target in root.carriers:
            if root.filters[(name, target)] is not None:
                assert list(actual.filtered(target).blocks) == list(original.filtered(target).blocks)
    block = root.carriers['content'].blocks[-1][0]
    selected = fresh.read_review_source(envelope, objects=[{'block_id': block['block_id']}])
    assert not selected.root.complete
    assert selected.root.reference['extraction_hash'] == envelope['prepared_source_extraction']['record_hash']
    assert selected.root.carriers['content'].block_index[block['block_id']] == root.carriers['content'].block_index[block['block_id']]
    assert {b['block_id'] for b, _ in selected.root.carriers['content'].blocks} == {block['block_id']}
    assert len(selected) < len(full)


def test_publishing_is_atomic_idempotent_and_seals_membership(tmp_path, production_console):
    from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
    import psycopg

    console, envelope, store, root, artifact = source_records(tmp_path, production_console)
    with pytest.raises(RuntimeError, match='rollback-read-root'):
        with store.documents._connect() as con:
            store.publish_review_source(artifact, con=con)
            raise RuntimeError('rollback-read-root')
    assert store.read_review_source(envelope) is None
    first = store.publish_review_source(artifact)
    assert store.publish_review_source(artifact) == first
    with pytest.raises(psycopg.Error, match='source_read_records_immutable'):
        with store.documents._connect() as con:
            con.execute('DELETE FROM workflow.source_read_blocks WHERE views_id=%s', (first['views_id'],))
    corrupt = deepcopy(root.payload)
    corrupt['views']['full']['blocks'][0][0]['text'] += 'changed'
    with pytest.raises((WorkflowDocumentStoreError, ValueError)):
        store.prepare_review_source({'artifact_id': 'missing', 'snapshot_id': envelope['snapshot_id']}, corrupt)


def test_reordered_json_views_reuse_the_same_published_identity(tmp_path, production_console, monkeypatch):
    console, envelope, store, root, artifact = source_records(tmp_path, production_console)
    first = store.publish_review_source(artifact)
    def no_rebuild(*args, **kwargs):
        raise AssertionError('An exactly published source must reuse its oracle proof')
    monkeypatch.setattr('src.vorming.source_reconstruction_v1._with_status', no_rebuild)
    reordered = deepcopy(root.payload)
    reordered['views'] = dict(reversed(list(reordered['views'].items())))
    same = store.prepare_review_source({'snapshot_id':envelope['snapshot_id'],
        'extraction_hash':envelope['prepared_source_extraction']['record_hash']}, reordered)
    assert (same.views_id, same.extraction_hash, same.header, same.header_hash) == (
        artifact.views_id, artifact.extraction_hash, artifact.header, artifact.header_hash)
    assert store.publish_review_source(same) == first
    retained = store.read_review_source(envelope)
    for name in root.carriers:
        assert list(retained.root.carriers[name].blocks) == list(root.carriers[name].blocks)
    reordered['views']['full']['blocks'][0][0]['text'] = 'forged'
    from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
    with pytest.raises(WorkflowDocumentStoreError, match='source_read_oracle_mismatch'):
        store.prepare_review_source({'snapshot_id':envelope['snapshot_id'],
            'extraction_hash':envelope['prepared_source_extraction']['record_hash']}, reordered)


@pytest.mark.parametrize('damage', ['root_missing','layout_missing','root_hash','source','contract',
    'fragment_payload','fragment_hash','fragment_ordinal','fragment_views',
    'block_payload','block_hash','block_ordinal','membership','single_view_block'])
def test_selected_corruption_fails_closed_without_rebuilding(tmp_path, production_console, damage):
    from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError, _json_text
    console, envelope, store, root, artifact = source_records(tmp_path, production_console)
    reference = store.publish_review_source(artifact)
    block = root.carriers['content'].blocks[-1][0]
    with store.documents._connect() as con:
        con.execute('UPDATE workflow.documents SET review_source_ref=%s::jsonb', (_json_text(reference),))
        # Privileged test corruption bypasses normal immutable writer guards.
        # It does not grant a production writer any alternate mutation route.
        if damage == 'root_missing':
            con.execute('TRUNCATE workflow.source_read_roots CASCADE')
        elif damage == 'layout_missing':
            con.execute('DROP TABLE workflow.source_read_roots CASCADE')
        elif damage in {'root_hash','source','contract'}:
            con.execute('ALTER TABLE workflow.source_read_roots DISABLE TRIGGER USER')
            if damage == 'root_hash':
                con.execute("UPDATE workflow.source_read_roots SET header_hash='bad'")
            else:
                header = con.execute('SELECT header FROM workflow.source_read_roots').fetchone()['header']
                if damage == 'source':
                    header['source']['sha256'] = 'different'
                else:
                    header['contract']['reconstruction'] = 'different'
                from src.integrity_kernel import stable_hash
                con.execute('UPDATE workflow.source_read_roots SET header=%s::jsonb,header_hash=%s',
                            (_json_text(header),stable_hash(header)))
            con.execute('ALTER TABLE workflow.source_read_roots ENABLE TRIGGER USER')
        elif damage.startswith('fragment'):
            con.execute('ALTER TABLE workflow.source_read_fragments DISABLE TRIGGER USER')
            fid = block['source_fragment_ids'][0]
            updates = {'fragment_payload': "payload=payload || '{\"raw_text\":\"changed\"}'::jsonb",
                       'fragment_hash': "payload_hash='bad'",
                       'fragment_ordinal': 'ordinal=ordinal+10000',
                       'fragment_views': "views=ARRAY['headings']::text[]"}
            # A changed referenced hash must still satisfy SQL FK constraints;
            # use a deferred privileged replica write only for this fault.
            if damage == 'fragment_hash':
                con.execute('SET LOCAL session_replication_role=replica')
            con.execute('UPDATE workflow.source_read_fragments SET ' + updates[damage] + ' WHERE fragment_id=%s', (fid,))
            con.execute('ALTER TABLE workflow.source_read_fragments ENABLE TRIGGER USER')
        elif damage == 'single_view_block':
            con.execute('ALTER TABLE workflow.source_read_blocks DISABLE TRIGGER USER')
            con.execute('ALTER TABLE workflow.source_read_block_fragments DISABLE TRIGGER USER')
            con.execute("DELETE FROM workflow.source_read_blocks WHERE view_name='content' AND block_id=%s", (block['block_id'],))
            con.execute('ALTER TABLE workflow.source_read_block_fragments ENABLE TRIGGER USER')
            con.execute('ALTER TABLE workflow.source_read_blocks ENABLE TRIGGER USER')
        elif damage.startswith('block'):
            con.execute('ALTER TABLE workflow.source_read_blocks DISABLE TRIGGER USER')
            updates = {'block_payload': "payload=jsonb_set(payload,'{0,text}','\"changed\"')",
                       'block_hash': "payload_hash='bad'", 'block_ordinal': 'ordinal=ordinal+10000'}
            con.execute('UPDATE workflow.source_read_blocks SET ' + updates[damage] + ' WHERE block_id=%s', (block['block_id'],))
            con.execute('ALTER TABLE workflow.source_read_blocks ENABLE TRIGGER USER')
        else:
            con.execute('ALTER TABLE workflow.source_read_block_fragments DISABLE TRIGGER USER')
            con.execute('DELETE FROM workflow.source_read_block_fragments WHERE block_id=%s', (block['block_id'],))
            con.execute('ALTER TABLE workflow.source_read_block_fragments ENABLE TRIGGER USER')
    with pytest.raises(WorkflowDocumentStoreError, match='source_read_'):
        store.read_review_source(envelope, objects=[{'block_id': block['block_id']}])


def test_explicit_legacy_preparation_preserves_work_and_rejects_stale(tmp_path, production_console):
    from src.operations_console_v1 import ConsoleError
    console, envelope, store, root, artifact = source_records(tmp_path, production_console)
    sid, actor = envelope['snapshot_id'], envelope['uploader_account_id']
    before = deepcopy(console.snapshot_objects(sid))
    revision = console.objects_revision(sid)
    with pytest.raises(ConsoleError, match='snapshot_object_write_conflict'):
        console.prepare_review_source_views(actor_id=actor, snapshot_id=sid, expected_revision='stale')
    assert store.read_review_source(envelope) is None
    ref = console.prepare_review_source_views(actor_id=actor, snapshot_id=sid, expected_revision=revision)
    assert console.prepare_review_source_views(actor_id=actor, snapshot_id=sid, expected_revision=revision) == ref
    assert console.snapshot_objects(sid) == before
    assert console.objects_revision(sid) == revision
    assert store.read_review_source(envelope).root.reference == ref


def test_consistently_rehashed_forged_block_cannot_be_published(tmp_path, production_console):
    from src.vorming.semantic_passage_v1 import _block_id
    from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
    console, envelope, store, root, artifact = source_records(tmp_path, production_console)
    forged = deepcopy(root.payload)
    public, source = forged['views']['content']['blocks'][-1]
    public['text'] = 'X' + public['text'][1:]
    source['clean_text'] = public['text']
    public['block_id'] = _block_id(source, public['text'])
    with pytest.raises(WorkflowDocumentStoreError, match='source_read_oracle_mismatch'):
        store.prepare_review_source({'snapshot_id':envelope['snapshot_id'],
            'extraction_hash':envelope['prepared_source_extraction']['record_hash']}, forged)
    assert store.read_review_source(envelope) is None


def test_concurrent_publishers_return_one_root_and_reject_presealed_insert(tmp_path, production_console):
    from concurrent.futures import ThreadPoolExecutor
    import psycopg
    console, envelope, store, root, artifact = source_records(tmp_path, production_console)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: store.publish_review_source(artifact), range(2)))
    assert results[0] == results[1]
    assert store.read_review_source(envelope).root.complete
    with pytest.raises(psycopg.Error, match='source_read_records_immutable'):
        with store.documents._connect() as con:
            con.execute('INSERT INTO workflow.source_read_roots(views_id,extraction_hash,header,header_hash,sealed) '
                'VALUES(%s,%s,%s::jsonb,%s,true)',
                ('forged',artifact.extraction_hash,artifact.header,artifact.header_hash))


def test_preparation_releases_document_lock_and_stale_pin_preserves_authority(
    tmp_path, production_console, monkeypatch,
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from src.operations_console_v1 import ConsoleError
    console, envelope, store, root, artifact = source_records(tmp_path, production_console)
    writer = checkpoint_context(console, envelope, validator_data(envelope))
    previous_objects = deepcopy(console.snapshot_objects(envelope['snapshot_id']))
    entered, release = Event(), Event()
    original = writer.store.prepare_review_source
    def paused(*args, **kwargs):
        value = original(*args, **kwargs)
        entered.set()
        assert release.wait(15)
        return value
    monkeypatch.setattr(writer.store, 'prepare_review_source', paused)
    with ThreadPoolExecutor(max_workers=1) as pool:
        task = pool.submit(writer.retain_source_views, root.payload)
        assert entered.wait(15)
        try:
            with store.documents._connect() as con:
                # An independent writer obtains the actual native row lock
                # while full source preparation is paused, then wins generation.
                con.execute('SELECT 1 FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE NOWAIT',
                            (envelope['snapshot_id'],))
                con.execute('UPDATE workflow.documents SET object_generation=object_generation+1 WHERE snapshot_id=%s',
                            (envelope['snapshot_id'],))
        finally:
            release.set()
        with pytest.raises(ConsoleError, match='processing_command_conflict'):
            task.result()
    with store.documents._connect() as con:
        row = con.execute('SELECT review_source_ref FROM workflow.documents WHERE snapshot_id=%s',
                          (envelope['snapshot_id'],)).fetchone()
        assert row['review_source_ref'] is None
    # A valid unused derivation may remain; it never pins/activates stale work.
    assert store.read_review_source(envelope).root.complete
    assert console.snapshot_objects(envelope['snapshot_id']) == previous_objects


@pytest.mark.parametrize('field', ['version','source'])
def test_request_cache_preserves_source_header_validation(tmp_path, production_console, field):
    from src.console_read_snapshot_v1 import CURRENT_READ, ConsoleReadSnapshot
    from src.operations_console_v1 import ConsoleError
    console, envelope, store, root, artifact = source_records(tmp_path, production_console)
    store.publish_review_source(artifact)
    token = CURRENT_READ.set(ConsoleReadSnapshot(console))
    try:
        assert console._prepared_review_source(envelope) is not None
        invalid = deepcopy(envelope)
        invalid['prepared_source_extraction'][field] = 'unsupported'
        with pytest.raises(ConsoleError, match='source_read_integrity_failed'):
            console._prepared_review_source(invalid)
    finally:
        CURRENT_READ.reset(token)


def test_retained_docling_mapping_and_record_survive_selective_native_read(
    tmp_path, production_console, monkeypatch,
):
    from tests.test_docling_contract_v1 import result
    from src.vorming.docling_contract_v1 import translate
    from src.vorming.source_preparation_context_v1 import extraction_record, extractor_contract
    import fitz
    console, envelope, store, root, artifact = source_records(tmp_path, production_console)
    monkeypatch.setenv('METIS_PDF_EXTRACTOR', 'docling')
    with fitz.open() as pdf:
        pdf.new_page(width=600,height=800).insert_text((10,40),'een advies')
        binary = pdf.tobytes()
    actor = envelope['uploader_account_id']
    sid = console.receive_source(actor_id=actor, filename='mapping.pdf', content_type='application/pdf',
        data=binary, ingest_kind='new',title='Mapping',version='1',date='2026-10-25',live_url='',
        class_='richtlijn',family='fixture',named_reviewers=envelope['named_reviewers'])['snapshot_id']
    target = console._envelope(sid)
    payload = result()
    payload['source_sha256'] = target['sha256']
    translated = translate(payload, document_id=target['document_id'], source_id=target['source_id'],
                           source_sha256=target['sha256'])
    target['prepared_source_extraction'] = extraction_record(target, translated, extractor_contract('pdf'))
    console.workflow_document_store.write_bundle(envelope=target)
    reference = console.prepare_review_source_views(actor_id=actor, snapshot_id=sid,
                                                   expected_revision=console.objects_revision(sid))
    oracle = prepare(translated)
    block = oracle.fragments.blocks[0][0]
    selected = store.read_review_source(target, objects=[{'block_id':block['block_id']}])
    assert selected.root.reference == reference
    assert selected.blocks == oracle.fragments.blocks
    assert selected.fragment_index == oracle.fragments.fragment_index
    assert selected.extraction_record == translated.extraction_record


def test_compact_capture_is_atomic_and_does_not_evaluate_legacy_archive(tmp_path, production_console):
    from src.workflows.workflow_documents_postgres_v1 import _json_text
    console, envelope, store, root, artifact = source_records(tmp_path, production_console)
    sid = envelope['snapshot_id']
    with store.documents._connect() as con:
        assert con.execute('SELECT review_read_envelope=workflow.review_read_envelope_for(envelope_payload) AS valid FROM workflow.documents WHERE snapshot_id=%s',(sid,)).fetchone()['valid']
    expected, generation = store.documents.review_document_input(sid)
    assert 'fragments' not in expected['prepared_source_extraction']
    with store.documents._connect() as con:
        # A direct cache write cannot invent different policy; the existing-row
        # trigger always derives it from that row's actual envelope.
        con.execute("UPDATE workflow.documents SET review_read_envelope='{}'::jsonb WHERE snapshot_id=%s", (sid,))
    assert store.documents.review_document_input(sid) == (expected,generation)
    with store.documents._connect() as con:
        original = con.execute('SELECT envelope_payload FROM workflow.documents WHERE snapshot_id=%s', (sid,)).fetchone()['envelope_payload']
        # Privileged test-only poison: evaluating JSON deletion on this scalar
        # would fail. A prepared capture must use its compact projection instead
        # of materializing/inspecting unused extraction and processing archives.
        con.execute('ALTER TABLE workflow.documents DISABLE TRIGGER USER')
        con.execute("UPDATE workflow.documents SET envelope_payload='null'::jsonb WHERE snapshot_id=%s", (sid,))
    try:
        assert store.documents.review_document_input(sid) == (expected,generation)
    finally:
        with store.documents._connect() as con:
            con.execute('ALTER TABLE workflow.documents ENABLE TRIGGER USER')
            con.execute('UPDATE workflow.documents SET envelope_payload=%s::jsonb WHERE snapshot_id=%s', (_json_text(original),sid))
    updated = {**original, 'review_passes': {'fixture': {'object_id':'unchanged'}}}
    with store.documents._connect() as con:
        con.execute('UPDATE workflow.documents SET envelope_payload=%s::jsonb WHERE snapshot_id=%s', (_json_text(updated),sid))
    current, _ = store.documents.review_document_input(sid)
    assert current['review_passes'] == updated['review_passes']


def test_compact_capture_follows_lifecycle_trigger_on_implicit_envelope_repair(tmp_path, production_console):
    console, envelope, store, root, artifact = source_records(tmp_path, production_console)
    sid = envelope['snapshot_id']
    with store.documents._connect() as con:
        con.execute('ALTER TABLE workflow.documents DISABLE TRIGGER USER')
        try:
            con.execute("UPDATE workflow.documents SET envelope_payload=envelope_payload-'working_revision_id',review_read_envelope='{}'::jsonb WHERE snapshot_id=%s",(sid,))
        finally:
            con.execute('ALTER TABLE workflow.documents ENABLE TRIGGER USER')
        # SET omits envelope_payload; the existing lifecycle owner repairs it.
        con.execute('UPDATE workflow.documents SET revision=revision+1 WHERE snapshot_id=%s',(sid,))
        row = con.execute('SELECT review_read_envelope,review_read_envelope=workflow.review_read_envelope_for(envelope_payload) AS valid FROM workflow.documents WHERE snapshot_id=%s',(sid,)).fetchone()
        assert row['valid']
        assert row['review_read_envelope']['working_revision_id']
