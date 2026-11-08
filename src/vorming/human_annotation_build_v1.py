"""Exact human input sealing through the existing workflow attempt owner."""
from copy import deepcopy

from src.integrity_kernel import stable_hash
from src.vorming import human_annotation_v1 as annotations
from src.vorming.human_annotation_contract_v1 import MODE
from src.vorming.human_annotation_preview_v1 import inspect_document
from src.vorming.source_preparation_context_v1 import stored_extraction
from src.workflows.processing_archives_v1 import encoded
from src.workflows.workflow_transaction_v1 import workflow_transaction


def require_storage(con):
    if con.execute("SELECT to_regclass('workflow.annotation_seals') AS name").fetchone()['name'] is None:
        annotations.fail('annotation_build_storage_not_ready')
    annotations.require_input_storage(con)
    required = {
        ('annotation_seals', 'guard_annotation_seal_insert'),
        ('annotation_seals', 'guard_annotation_seal_history'),
        ('annotation_build_commands', 'guard_annotation_build_commands'),
        ('annotation_build_commands', 'guard_annotation_build_receipt'),
        ('processing_attempts', 'require_annotation_build_receipt'),
        ('formation_evidence_members', 'guard_formation_evidence_member'),
        ('annotation_sets', 'guard_annotation_source'),
        ('document_objects', 'guard_annotation_object_insert'),
        ('document_objects', 'guard_annotation_object_update'),
        ('document_objects', 'guard_annotation_object_delete'),
        ('document_objects', 'require_human_annotation_binding'),
        ('processing_attempts', 'guard_annotation_legacy_attempt'),
        ('processing_attempt_inputs', 'guard_annotation_legacy_attempt_input'),
        ('documents', 'guard_annotated_document'),
        ('documents', 'guard_active_formation_evidence'),
        ('formation_evidence_roots', 'guard_formation_evidence_root'),
        ('formation_evidence_roots', 'require_sealed_formation_evidence'),
        ('document_inputs', 'ab_guard_document_input_variant'),
    }
    present = {(row['table_name'], row['name']) for row in con.execute(
        "SELECT c.relname AS table_name,t.tgname AS name FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
        "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='workflow' AND t.tgenabled IN ('O','A')").fetchall()}
    constraint = con.execute("SELECT convalidated FROM pg_constraint WHERE conrelid='workflow.formation_evidence_roots'::regclass "
                             "AND conname='formation_evidence_producer' AND contype='c'").fetchone()
    if not required <= present or not constraint or not constraint['convalidated']:
        annotations.fail('annotation_build_storage_not_ready')


def _capture(con, snapshot_id):
    require_storage(con)
    row = con.execute('SELECT s.*,e.payload AS extraction,'
        'workflow.annotation_materialization_context(d) AS context '
        'FROM workflow.annotation_sets s JOIN workflow.documents d USING(snapshot_id) '
        'JOIN workflow.prepared_extraction_versions e ON e.record_hash=s.extraction_hash '
        'WHERE s.snapshot_id=%s', (snapshot_id,)).fetchone()
    if row is None:
        annotations.fail('annotation_source_not_prepared')
    if row['context']['class'] == 'beslisboom':
        annotations.fail('annotation_prose_required')
    entries = con.execute('SELECT v.annotation_id,v.revision,v.payload,v.payload_hash,v.author_id '
        'FROM workflow.annotation_heads h JOIN workflow.annotation_versions v '
        'USING(snapshot_id,annotation_id,revision) WHERE h.snapshot_id=%s ORDER BY h.position',
        (snapshot_id,)).fetchall()
    basis = {key: row[key] for key in ('snapshot_id', 'working_revision_id', 'extraction_hash',
                                     'source_identity', 'objects_revision', 'normalization', 'generation', 'context')}
    basis.update(version=MODE, entries=[{key: entry[key] for key in
                                       ('annotation_id', 'revision', 'payload_hash')} for entry in entries])
    return row, entries, {**basis, 'overview_hash': stable_hash(basis)}


def overview(console, *, actor_id, snapshot_id):
    annotations.authorize(console, actor_id, console._envelope(snapshot_id))
    with console.workflow_document_store._connect() as con:
        con.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        row, entries, basis = _capture(con, snapshot_id)
        active = con.execute("SELECT a.attempt_id,a.payload->>'state' AS state FROM workflow.annotation_build_commands c "
            "JOIN workflow.processing_attempts a ON a.attempt_id=c.attempt_id WHERE c.snapshot_id=%s "
            "ORDER BY a.started_at DESC,a.attempt_id DESC LIMIT 1", (snapshot_id,)).fetchone()
    fragments = stored_extraction({**row['source_identity'], 'prepared_source_extraction': row['extraction']})
    if fragments is None or row['extraction']['record_hash'] != row['extraction_hash']:
        annotations.fail('annotation_representation_stale')
    from src.vorming.prepared_source_views_v1 import prepare
    fragments = prepare(fragments).fragments
    inspection = inspect_document(entries, fragments=fragments)
    # Display is the existing source reader. A concurrent save requires a new
    # overview; its entries may never be presented under this seal's hash.
    view = annotations.overview(console, actor_id=actor_id, snapshot_id=snapshot_id)
    if view['generation'] != basis['generation']:
        annotations.fail('annotation_overview_stale')
    return {**view, 'title': basis['context']['title'], 'overview_hash': basis['overview_hash'], 'materialization_context': basis['context'],
            'inspection': inspection, 'current_build': dict(active) if active else None,
            'can_finalize': not inspection['findings'] and view['objects_revision'] == row['objects_revision']
                and (not active or active['state'] != 'running')}


def finalize(console, *, actor_id, snapshot_id, command_id, overview_hash,
             expected_generation, expected_revision):
    if (not isinstance(command_id, str) or not 1 <= len(command_id) <= 128
            or type(expected_generation) is not int or expected_generation < 0
            or not isinstance(expected_revision, str)):
        annotations.fail('annotation_command_invalid')
    request_hash = stable_hash({'actor_id': actor_id, 'overview_hash': overview_hash,
                               'generation': expected_generation, 'objects_revision': expected_revision})
    # A successful command remains idempotent after its object frontier moved.
    # Authorization is rechecked, never inferred from possession of a receipt.
    annotations.authorize(console, actor_id, console._envelope(snapshot_id))
    with console.workflow_document_store._connect() as con:
        require_storage(con)
        receipt = con.execute('SELECT request_hash,result FROM workflow.annotation_build_commands '
            'WHERE snapshot_id=%s AND command_id=%s', (snapshot_id, command_id)).fetchone()
    if receipt:
        if receipt['request_hash'] != request_hash:
            annotations.fail('annotation_command_conflict')
        return receipt['result']
    view = overview(console, actor_id=actor_id, snapshot_id=snapshot_id)
    if not view['can_finalize']:
        if view['current_build'] and view['current_build']['state'] == 'running':
            annotations.fail('processing_attempt_in_progress')
        annotations.fail('annotation_document_incomplete')
    with workflow_transaction(console.workflow_document_store) as con:
        annotations._locked(console, con, actor_id, snapshot_id)
        con.execute('SELECT snapshot_id FROM workflow.annotation_sets WHERE snapshot_id=%s FOR UPDATE', (snapshot_id,))
        row, _, basis = _capture(con, snapshot_id)
        receipt = con.execute('SELECT request_hash,result FROM workflow.annotation_build_commands '
            'WHERE snapshot_id=%s AND command_id=%s', (snapshot_id, command_id)).fetchone()
        if receipt:
            if receipt['request_hash'] != request_hash:
                annotations.fail('annotation_command_conflict')
            return receipt['result']
        if (basis['overview_hash'] != overview_hash or view['overview_hash'] != overview_hash
                or row['generation'] != expected_generation
                or row['objects_revision'] != expected_revision
                or console.workflow_document_store.objects_revision(snapshot_id) != expected_revision):
            annotations.fail('annotation_overview_stale')
        seal_id = stable_hash(basis)
        con.execute('INSERT INTO workflow.annotation_seals(seal_id,snapshot_id,extraction_hash,generation,'
            'overview_hash,payload,payload_text,created_by) VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s,%s) '
            'ON CONFLICT(seal_id) DO NOTHING', (seal_id, snapshot_id, row['extraction_hash'], row['generation'],
                overview_hash, encoded(basis), encoded(basis), actor_id))
        if row['current_seal_id'] != seal_id:
            con.execute('UPDATE workflow.annotation_sets SET current_seal_id=%s WHERE snapshot_id=%s', (seal_id, snapshot_id))
        envelope = deepcopy(console._processing_command_envelope(snapshot_id, command_id=command_id))
        from src.workflows.formation_task_store_v1 import FormationTaskStore
        # Preserve exact terminal inline history before its representation is
        # moved by the existing document writer, never reopen old model work.
        FormationTaskStore.save_attempts(con, snapshot_id, envelope.get('processing_attempts') or [])
        envelope['processing_storage'] = 'task-v1'
        from src.vorming.processing_retry_v1 import reserve, now
        attempt, fresh = reserve(envelope, command_id=command_id, actor_id=actor_id, revision=expected_revision,
            clock=now(), limits=console._processing_limits(), kind='human_annotation_build', annotation_seal_id=seal_id)
        if not fresh:
            annotations.fail('annotation_command_conflict')
        attempt['dispatch'] = {'version': 'source-dispatch-v2', 'state': 'pending'}
        result = {'seal_id': seal_id, 'attempt_id': attempt['attempt_id'], 'generation': row['generation'],
                  'overview_hash': overview_hash}
        console._commit_prepared_store(envelopes={snapshot_id: envelope}, snapshot_id=snapshot_id)
        con.execute('INSERT INTO workflow.annotation_build_commands(snapshot_id,command_id,actor_id,request_hash,'
            'seal_id,attempt_id,result) VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb)',
            (snapshot_id, command_id, actor_id, request_hash, seal_id, attempt['attempt_id'], encoded(result)))
    return result


def execute(console, *, actor_id, snapshot_id, attempt, deadline):
    """Existing claimed delivery, source/proof preparation, one bundle commit."""
    import time
    from src.workflows.formation_task_store_v1 import FormationTaskStore
    from src.workflows.formation_evidence_v1 import human_capture
    from src.vorming.worker_handover_v1 import locked, validate
    from src.vorming.processing_retry_v1 import finish
    store = FormationTaskStore(console.workflow_document_store)
    envelope = deepcopy(console._processing_command_envelope(snapshot_id, attempt_id=attempt['attempt_id']))
    console._verified_source_bytes(envelope)
    with console.workflow_document_store._connect() as con:
        _, seal, _, _ = human_capture(con, snapshot_id, attempt['attempt_id'])
    extraction = store.retained_extraction(envelope, seal['extraction_hash'])
    fragments = stored_extraction({**envelope, 'prepared_source_extraction': extraction})
    from src.vorming.prepared_source_views_v1 import prepare
    source_ref = store.publish_review_source(store.prepare_review_source(
        {'snapshot_id': snapshot_id, 'extraction_hash': seal['extraction_hash']}, prepare(fragments).payload))
    with locked(console, snapshot_id, attempt['attempt_id']) as (con, document, row, active):
        validate(console, con, document, row, active)
        if active['dispatch'].get('token') != attempt['dispatch']['token']:
            annotations.fail('processing_command_conflict')
        active.setdefault('diagnostic', {})['review_source_ref'] = source_ref
    prepared = store.prepare_formation_evidence(envelope, attempt_id=attempt['attempt_id'])
    proof_ref = store.publish_formation_evidence(envelope, prepared)
    import json
    objects = [json.loads(payload) for role, _, _, payload in prepared.members if role == 'result']
    with locked(console, snapshot_id, attempt['attempt_id']) as (con, document, row, active):
        validate(console, con, document, row, active)
        if active['dispatch'].get('token') != attempt['dispatch']['token']:
            annotations.fail('processing_command_conflict')
        active['diagnostic'].update(formation_evidence_ref=proof_ref,
            final_validation={'version': 3, 'stage': 'sealed', 'formation_evidence_ref': proof_ref})
    prepared_envelope = deepcopy(console._processing_command_envelope(snapshot_id, attempt_id=attempt['attempt_id']))
    if '_document_inputs' in prepared_envelope:
        prepared_envelope.pop('quality_processing_runs', None)
    prepared_envelope.update(prepared_source_extraction=extraction, human_formation_ref=proof_ref,
        state='captured_not_published', publication_eligibility='eligible_for_transform_and_review'
            if envelope.get('immutable_storage_locator') else 'blocked_pending_immutable_storage')
    prepared_envelope.pop('processing_blocker', None)
    if prepared_envelope.get('replaces_snapshot_id'):
        prepared_envelope['object_diff'] = console._diff_objects(
            console.snapshot_objects(prepared_envelope['replaces_snapshot_id']), objects)
    from src.settings.quality_evidence_v1 import record_processing
    record_processing(prepared_envelope, objects, fragments=fragments, replay=None, started_at=attempt['started_at'])
    prepared_envelope['quality_processing_runs'][-1].update(
        attempt_id=attempt['attempt_id'], execution=MODE, annotation_seal_id=attempt['annotation_seal_id'])
    from src.workflows.review_card_inputs_postgres_v1 import prepare_activation
    review_preparation = prepare_activation(console.workflow_document_store, prepared_envelope, objects, fragments)
    if '_document_inputs' in prepared_envelope:
        prepared_envelope = console.workflow_document_store.prepare_producer_inputs(prepared_envelope)
    with console._reprocessing_transaction(snapshot_id):
        annotations.authorize(console, actor_id, console._envelope(snapshot_id))
        console._assert_source_work_unchanged(envelope, seal['objects_revision'], 'published_objects_must_not_be_rewritten')
        if envelope.get('successor_guard'):
            from src.review.decision_successor_v1 import assert_parent_current
            assert_parent_current(console, envelope)
        if time.monotonic() >= deadline:
            annotations.fail('processing_attempt_expired')
        from src.vorming.processing_retry_v1 import assert_active, now
        current = console._processing_command_envelope(snapshot_id, attempt_id=attempt['attempt_id'])
        active = assert_active(current, attempt['attempt_id'], now())
        if active['dispatch'].get('token') != attempt['dispatch']['token']:
            annotations.fail('processing_command_conflict')
        from src.vorming.attempt_diagnostics_v1 import merge_diagnostics
        merge_diagnostics(prepared_envelope, current)
        finish(prepared_envelope, attempt['attempt_id'], state='succeeded')
        console._commit_prepared_store(objects=(snapshot_id, objects), envelopes={snapshot_id: prepared_envelope},
            bindings={snapshot_id: []}, expected_revision=seal['objects_revision'],
            review_card_preparation=review_preparation, formation_activation_ref=proof_ref)
    return console._receipt(console._envelope(snapshot_id))
