"""Real workflow authority: source -> saved selection -> seal -> leased build.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
from uuid import uuid4

import pytest

from src.operations_console_v1 import ConsoleError
from src.vorming import human_annotation_v1 as annotation
from src.vorming import human_annotation_build_v1 as build
from src.vorming.source_bound_fields_v3 import FIELDS
from tests.production_support import restart_production
from tests.test_human_annotation_postgres import anchor, command


def saved_source(production_console, tmp_path, *, review_option=None, source_status="unknown", context_function=None, **options):
    console = production_console(root=tmp_path, **options)
    actor = console.create_account(username='builder', password='human-build-secret', roles=('researcher', 'reviewer'))['account_id']
    reviewer = console.create_account(username='reviewer', password='human-build-secret', roles=('reviewer',))['account_id']
    sid = console.receive_source(actor_id=actor, filename='human.html', content_type='text/html',
        data=('<html><body><p>De kwetsbare huid verklaart de pijn.</p>'+('<p>Alleen bij klachten.</p><p>Onderzoek beschrijft dit verband.</p><p>De beoordeling betreft volwassenen.</p>' if context_function else '')+'</body></html>').encode(),
        ingest_kind='new', title='Menselijke opbouw', version='1.0', date='2026-11-08', live_url='',
        class_='richtlijn', family='test', named_reviewers=[reviewer] if review_option is None else [],
        review_choice={'contract':'review-configuration-v2','option':review_option,'four_eyes_required':False,
                       'reviewers':[] if review_option=='uploader_sole' else [reviewer], 'readers':[]} if review_option else None,
        source_status=source_status)['snapshot_id']
    view = annotation.prepare(console, actor_id=actor, snapshot_id=sid, expected_revision=console.objects_revision(sid))
    core = anchor(view, 'De kwetsbare')
    fields = {key: {'span': None, 'missing_reason': 'not_applicable'} for key in FIELDS}
    for field, text in [('subject_span', 'De kwetsbare huid'), ('predicate_span', 'verklaart'),
                        ('supported_object', 'de pijn')]:
        start = core['quote'].index(text)
        fields[field] = {'span': {'block_id': core['block_id'], 'start': start, 'end': start + len(text)},
                         'missing_reason': None, 'quote': text}
    fields.update(type_evidence_spans={'core': True}, support_span={'core': True})
    request = command(view, ranges=[core], status='ready')
    request['selection'].update(object_type='explanation', evidence_not_applicable=True,
                                field_evidence=fields, required_links=[])
    if context_function:
        request['selection']['ranges'] += [anchor(view,'Alleen',role='condition'),
            anchor(view,'Onderzoek',role='evidence',function=context_function),
            anchor(view,'De beoordeling',role='context')]
        request['selection']['evidence_not_applicable']=False
        condition=anchor(view,'Alleen',role='condition')
        fields['condition_span']={'span':{k:condition[k] for k in ('block_id','start','end')},
                                  'quote':condition['quote'],'missing_reason':None}
    annotation.save(console, actor_id=actor, **request)
    return console, actor, sid, request


def closing(view):
    return {'snapshot_id': view['snapshot_id'], 'command_id': str(uuid4()), 'overview_hash': view['overview_hash'],
            'expected_generation': view['generation'], 'expected_revision': view['objects_revision']}


@pytest.mark.parametrize('storage', ['legacy', 'v1'])
def test_saved_source_seal_restart_dispatch_build_and_human_evidence(tmp_path, production_console, monkeypatch, storage):
    monkeypatch.setenv('METIS_DOCUMENT_INPUT_STORAGE', storage)
    if storage == 'v1':
        monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE', 'v1')
    console, actor, sid, saved_request = saved_source(production_console, tmp_path)
    resumed = restart_production(console)
    view = build.overview(resumed, actor_id=actor, snapshot_id=sid)
    assert view['can_finalize'], view['inspection']
    close = closing(view)
    receipt = build.finalize(resumed, actor_id=actor, **close)
    assert build.finalize(restart_production(resumed), actor_id=actor, **close) == receipt
    from src.vorming.worker_handover_v1 import native_attempt
    pending = native_attempt(resumed, sid, receipt['attempt_id'])
    assert pending['kind'] == 'human_annotation_build'
    assert 'processing_configuration' not in pending and 'reserved_semantic_contract_version' not in pending
    def forbidden(*args, **kwargs):
        raise AssertionError('human build reached the model producer')
    monkeypatch.setattr(resumed, '_fragments_and_spec', forbidden)
    resumed.execute_source_selection(actor_id=actor, snapshot_id=sid, attempt=pending)
    latest = restart_production(console)
    assert build.finalize(latest, actor_id=actor, **close) == receipt
    objects = latest.snapshot_objects(sid, include_blocked=True)
    candidates = [obj for obj in objects if (obj.get('metadata') or {}).get('human_annotation')]
    assert len(candidates) == 1
    assert candidates[0]['content']['clean_text'] == 'De kwetsbare huid verklaart de pijn.'
    with latest.workflow_document_store._connect() as con:
        proof = con.execute('SELECT p.* FROM workflow.documents d JOIN workflow.formation_evidence_roots p '
            'ON p.proof_id=d.formation_evidence_id WHERE d.snapshot_id=%s', (sid,)).fetchone()
        attempts = con.execute('SELECT payload FROM workflow.processing_attempts WHERE snapshot_id=%s', (sid,)).fetchall()
        assert con.execute('SELECT count(*) AS n FROM workflow.annotation_seals WHERE snapshot_id=%s', (sid,)).fetchone()['n'] == 1
    assert len(attempts) == 1 and attempts[0]['payload']['state'] == 'succeeded'
    assert proof['sealed'] and proof['context_id'] is None and proof['annotation_seal_id'] == receipt['seal_id']
    from src.workflows.formation_task_store_v1 import FormationTaskStore
    evidence = FormationTaskStore(latest.workflow_document_store).read_formation_evidence(
        {'layout': 2, 'proof_id': proof['proof_id']}, envelope=latest._envelope(sid))
    assert evidence['header']['variant'] == 'human-annotation-v1'
    assert not any(role == 'replay' for role, _, _ in evidence['members'])
    assert not latest.snapshot_is_published(sid)
    assert latest.object_review_bindings(sid) == []
    assert annotation.save(latest, actor_id=actor, **saved_request)['revision'] == 1
    if storage == 'v1':
        import psycopg
        with pytest.raises(psycopg.Error, match='document_inputs_human_binding_changed'):
            with latest.workflow_document_store._connect() as con:
                con.execute("SELECT set_config('metis.document_storage_writer','v1',true)")
                con.execute("UPDATE workflow.document_inputs SET refs=(refs-'human')||jsonb_build_object('formation_variant','absent') WHERE snapshot_id=%s", (sid,))
    reviewer = latest._envelope(sid)['named_reviewers'][0]
    confirmed = latest.confirm_object_type(actor_id=reviewer, snapshot_id=sid,
        object_id=candidates[0]['object_id'], confirmed_object_type='explanation',
        expected_revision=latest.objects_revision(sid))
    assert confirmed['confirmed_object_type'] == 'explanation'
    assert confirmed['content'] == candidates[0]['content']


@pytest.mark.parametrize('storage', ['legacy', 'v1'])
def test_duplicate_claim_refused_without_losing_original_or_its_receipt(tmp_path, production_console, monkeypatch, storage):
    monkeypatch.setenv('METIS_DOCUMENT_INPUT_STORAGE', storage)
    if storage == 'v1':
        monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE', 'v1')
    console, actor, sid, request = saved_source(production_console, tmp_path)
    duplicate = {**deepcopy(request), 'command_id': str(uuid4()), 'annotation_id': str(uuid4()), 'expected_generation': 1}
    with pytest.raises(ConsoleError, match='annotation_core_duplicate') as conflict:
        annotation.save(console, actor_id=actor, **duplicate)
    assert conflict.value.conflicting_annotation_id == request['annotation_id']
    original = annotation.save(console, actor_id=actor, **request)
    assert original['generation'] == 1
    assert len(annotation.overview(console, actor_id=actor, snapshot_id=sid)['entries']) == 1


def test_corrected_source_blocks_old_job_after_restart(tmp_path, production_console):
    console, actor, sid, request = saved_source(production_console, tmp_path)
    receipt = build.finalize(console, actor_id=actor, **closing(build.overview(console, actor_id=actor, snapshot_id=sid)))
    correction = {**deepcopy(request), 'command_id': str(uuid4()), 'expected_generation': 1, 'expected_revision': 1}
    correction['selection']['status'] = 'draft'
    annotation.save(console, actor_id=actor, **correction)
    resumed = restart_production(console)
    from src.vorming.worker_handover_v1 import native_attempt
    pending = native_attempt(resumed, sid, receipt['attempt_id'])
    with pytest.raises(ConsoleError, match='annotation_seal_stale'):
        resumed.execute_source_selection(actor_id=actor, snapshot_id=sid, attempt=pending)
    assert resumed.snapshot_objects(sid, include_blocked=True) == []
    assert annotation.overview(resumed, actor_id=actor, snapshot_id=sid)['generation'] == 2


def test_concurrent_duplicate_finalize_is_one_seal_and_one_job(tmp_path, production_console):
    from concurrent.futures import ThreadPoolExecutor
    console, actor, sid, _ = saved_source(production_console, tmp_path)
    close = closing(build.overview(console, actor_id=actor, snapshot_id=sid))
    other = restart_production(console)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda kernel: build.finalize(kernel, actor_id=actor, **close), [console, other]))
    assert results[0] == results[1]
    with console.workflow_document_store._connect() as con:
        for table in ('annotation_seals', 'annotation_build_commands', 'processing_attempts'):
            assert con.execute(f'SELECT count(*) AS n FROM workflow.{table} WHERE snapshot_id=%s', (sid,)).fetchone()['n'] == 1
    with pytest.raises(ConsoleError, match='annotation_command_conflict'):
        build.finalize(console, actor_id=actor, **{**close, 'overview_hash': 'changed'})


@pytest.mark.parametrize('storage', ['legacy', 'v1'])
def test_metadata_change_invalidates_overview_without_changing_annotation_generation(tmp_path, production_console, monkeypatch, storage):
    monkeypatch.setenv('METIS_DOCUMENT_INPUT_STORAGE', storage)
    if storage == 'v1':
        monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE', 'v1')
    console, actor, sid, _ = saved_source(production_console, tmp_path)
    before = build.overview(console, actor_id=actor, snapshot_id=sid)
    changed = deepcopy(console._envelope(sid))
    changed['title'] = 'Nieuwe titel'
    console._commit_prepared_store(envelopes={sid: changed}, snapshot_id=sid)
    after = build.overview(console, actor_id=actor, snapshot_id=sid)
    assert after['generation'] == before['generation'] and after['overview_hash'] != before['overview_hash']
    with pytest.raises(ConsoleError, match='annotation_overview_stale'):
        build.finalize(console, actor_id=actor, **closing(before))
    with console.workflow_document_store._connect() as con:
        assert con.execute('SELECT count(*) AS n FROM workflow.processing_attempts WHERE snapshot_id=%s', (sid,)).fetchone()['n'] == 0


@pytest.mark.parametrize('storage', ['legacy', 'v1'])
def test_correction_after_prepared_proof_prevents_activation_and_preserves_both_inputs(tmp_path, production_console, monkeypatch, storage):
    monkeypatch.setenv('METIS_DOCUMENT_INPUT_STORAGE', storage)
    if storage == 'v1':
        monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE', 'v1')
    console, actor, sid, request = saved_source(production_console, tmp_path)
    receipt = build.finalize(console, actor_id=actor, **closing(build.overview(console, actor_id=actor, snapshot_id=sid)))
    from src.workflows import review_card_inputs_postgres_v1 as cards
    original = cards.prepare_activation
    def correct_before_commit(*args, **kwargs):
        prepared = original(*args, **kwargs)
        correction = {**deepcopy(request), 'command_id': str(uuid4()), 'expected_generation': 1, 'expected_revision': 1}
        correction['selection']['status'] = 'draft'
        annotation.save(restart_production(console), actor_id=actor, **correction)
        return prepared
    monkeypatch.setattr(cards, 'prepare_activation', correct_before_commit)
    from src.vorming.worker_handover_v1 import native_attempt
    with pytest.raises((ConsoleError, ValueError), match='formation_evidence_activation_changed|workflow_document_bundle_write_failed'):
        console.execute_source_selection(actor_id=actor, snapshot_id=sid, attempt=native_attempt(console, sid, receipt['attempt_id']))
    assert console.snapshot_objects(sid, include_blocked=True) == []
    with console.workflow_document_store._connect() as con:
        assert con.execute('SELECT formation_evidence_id FROM workflow.documents WHERE snapshot_id=%s', (sid,)).fetchone()['formation_evidence_id'] is None
        assert con.execute('SELECT count(*) AS n FROM workflow.formation_evidence_roots WHERE snapshot_id=%s AND sealed', (sid,)).fetchone()['n'] == 1
        assert con.execute('SELECT generation,current_seal_id FROM workflow.annotation_sets WHERE snapshot_id=%s', (sid,)).fetchone() == {'generation': 2, 'current_seal_id': None}


@pytest.mark.parametrize('built', [False, True])
@pytest.mark.parametrize('storage', ['legacy', 'v1'])
def test_backup_restores_exact_seal_job_and_human_proof(tmp_path, production_console, monkeypatch, built, storage):
    monkeypatch.setenv('METIS_DOCUMENT_INPUT_STORAGE', storage)
    if storage == 'v1':
        monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE', 'v1')
    console, actor, sid, _ = saved_source(production_console, tmp_path)
    receipt = build.finalize(console, actor_id=actor, **closing(build.overview(console, actor_id=actor, snapshot_id=sid)))
    from src.vorming.worker_handover_v1 import native_attempt
    if built:
        console.execute_source_selection(actor_id=actor, snapshot_id=sid, attempt=native_attempt(console, sid, receipt['attempt_id']))
        # Historical producer input remains exact when ordinary document
        # metadata subsequently advances; restore must not authorize a new build.
        changed = deepcopy(console._envelope(sid))
        changed['title'] = 'Titel na de opbouw'
        console._commit_prepared_store(envelopes={sid:changed}, snapshot_id=sid)
    from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
    from src.workflows.workflow_chain_recovery_v1 import PostgresWorkflowRecoveryAdapter
    from tests.postgres_support import database, install_schema
    from tests.production_support import production_application
    adapter = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(console.workflow_document_store.config))
    state = adapter.export_state()
    with database(console.workflow_document_store.config.dsn) as target_config:
        install_schema(target_config.dsn)
        target = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(target_config))
        target.restore_state(state)
        assert target.export_state()['formation_recovery'] == state['formation_recovery']
        restored = production_application(console.root, target_config, runtime=console.runtime,
            source_store=console.source_store).state.operations_kernel
        if not built:
            restored.execute_source_selection(actor_id=actor, snapshot_id=sid, attempt=native_attempt(restored, sid, receipt['attempt_id']))
        assert any((obj.get('metadata') or {}).get('human_annotation') for obj in restored.snapshot_objects(sid))


def test_disabled_native_boundary_refuses_finalize_and_retains_saved_work(tmp_path, production_console):
    console, actor, sid, _ = saved_source(production_console, tmp_path)
    close = closing(build.overview(console, actor_id=actor, snapshot_id=sid))
    with console.workflow_document_store._connect() as con:
        con.execute('ALTER TABLE workflow.document_objects DISABLE TRIGGER guard_annotation_object_insert')
    with pytest.raises(ConsoleError, match='annotation_build_storage_not_ready'):
        build.finalize(console, actor_id=actor, **close)
    assert len(annotation.overview(console, actor_id=actor, snapshot_id=sid)['entries']) == 1


def test_revoked_actor_cannot_reuse_receipt_or_claim_sealed_work(tmp_path, production_console):
    console, actor, sid, _ = saved_source(production_console, tmp_path)
    close = closing(build.overview(console, actor_id=actor, snapshot_id=sid))
    receipt = build.finalize(console, actor_id=actor, **close)
    console.workflow_identity_store.update_roles(actor, ['publisher'])
    with pytest.raises(ConsoleError, match='researcher_role_required'):
        build.finalize(console, actor_id=actor, **close)
    from src.vorming.worker_handover_v1 import native_attempt
    with pytest.raises(ConsoleError, match='researcher_role_required'):
        console.execute_source_selection(actor_id=actor, snapshot_id=sid, attempt=native_attempt(console, sid, receipt['attempt_id']))
    assert console.snapshot_objects(sid, include_blocked=True) == []


@pytest.mark.parametrize('corruption', ['trim_annotation', 'invent_result'])
def test_self_consistent_altered_proof_is_refused_before_activation(tmp_path, production_console, monkeypatch, corruption):
    import json
    from dataclasses import replace
    from src.workflows.formation_task_store_v1 import FormationTaskStore
    from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
    from src.workflows.processing_archives_v1 import encoded
    from src.integrity_kernel import stable_hash
    console, actor, sid, _ = saved_source(production_console, tmp_path)
    receipt = build.finalize(console, actor_id=actor, **closing(build.overview(console, actor_id=actor, snapshot_id=sid)))
    original = FormationTaskStore.publish_formation_evidence
    def corrupt(store, envelope, prepared):
        members = []
        for role, key, digest, text in prepared.members:
            if corruption == 'trim_annotation' and role == 'annotation':
                continue
            if corruption == 'invent_result' and role == 'result':
                payload = json.loads(text)
                payload['content']['clean_text'] = 'Verzonnen uitspraak.'
                text, digest = encoded(payload), stable_hash(payload)
            members.append((role, key, digest, text))
        header = json.loads(prepared.header_text)
        header['manifest'] = [[role, key, digest] for role, key, digest, _ in members]
        return original(store, envelope, replace(prepared, members=tuple(members), header_text=encoded(header)))
    monkeypatch.setattr(FormationTaskStore, 'publish_formation_evidence', corrupt)
    from src.vorming.worker_handover_v1 import native_attempt
    with pytest.raises(WorkflowDocumentStoreError, match='formation_evidence_preparation_changed'):
        console.execute_source_selection(actor_id=actor, snapshot_id=sid, attempt=native_attempt(console, sid, receipt['attempt_id']))
    assert console.snapshot_objects(sid, include_blocked=True) == []
    assert annotation.overview(console, actor_id=actor, snapshot_id=sid)['generation'] == 1


def test_multiple_core_ranges_across_paragraphs_build_one_claim_with_essential_context(tmp_path, production_console):
    console = production_console(root=tmp_path)
    actor = console.create_account(username='multi', password='human-multi-secret', roles=('researcher','reviewer'))['account_id']
    sid = console.receive_source(actor_id=actor, filename='multi.html', content_type='text/html',
        data=b'<html><body><p>De kwetsbare huid</p><p>Alleen bij klachten.</p><p>verklaart de pijn.</p></body></html>',
        ingest_kind='new', title='Meerdere bereiken', version='1.0', date='2026-11-08', live_url='',
        class_='richtlijn', family='test', named_reviewers=[],
        review_choice={'contract':'review-configuration-v2','option':'uploader_sole',
                       'four_eyes_required':False,'reviewers':[],'readers':[]})['snapshot_id']
    view = annotation.prepare(console, actor_id=actor, snapshot_id=sid, expected_revision=console.objects_revision(sid))
    first, last, condition = anchor(view,'De kwetsbare'), anchor(view,'verklaart'), anchor(view,'Alleen',role='condition')
    fields = {field:{'span':None,'missing_reason':'not_applicable'} for field in FIELDS}
    for field, selected, text in [('subject_span',first,first['quote']), ('predicate_span',last,'verklaart'),
                                   ('supported_object',last,'de pijn'), ('condition_span',condition,condition['quote'])]:
        start = selected['quote'].index(text)
        fields[field] = {'span':{'block_id':selected['block_id'],'start':start,'end':start+len(text)},
                         'missing_reason':None,'quote':text}
    fields.update(type_evidence_spans={'core':True},support_span={'core':True})
    request = command(view, ranges=[first,last,condition], status='ready')
    request['selection'].update(object_type='explanation', evidence_not_applicable=True, field_evidence=fields, required_links=[])
    annotation.save(console, actor_id=actor, **request)
    receipt = build.finalize(console, actor_id=actor, **closing(build.overview(console, actor_id=actor, snapshot_id=sid)))
    from src.vorming.worker_handover_v1 import native_attempt
    console.execute_source_selection(actor_id=actor, snapshot_id=sid, attempt=native_attempt(console, sid, receipt['attempt_id']))
    claims = [obj for obj in console.snapshot_objects(sid) if (obj.get('metadata') or {}).get('human_annotation')]
    assert len(claims) == 1 and claims[0]['content']['clean_text'] == 'De kwetsbare huid verklaart de pijn.'
    assert len(claims[0]['metadata']['semantic_passage']['spans']) == 2
    assert claims[0]['metadata']['source_bound_context']['entries'][0]['required_for_meaning'] is True
    assert claims[0]['metadata']['source_bound_context']['entries'][0]['text'] == 'Alleen bij klachten.'


def test_expired_worker_cannot_activate_after_same_job_is_handed_over(tmp_path, production_console):
    import time
    from datetime import timedelta
    from src.vorming.source_processing_dispatch_v1 import claim, pending
    from src.vorming.worker_handover_v1 import locked, worker_execution
    from src.vorming.processing_retry_v1 import now
    console, actor, sid, _ = saved_source(production_console, tmp_path)
    receipt = build.finalize(console, actor_id=actor, **closing(build.overview(console, actor_id=actor, snapshot_id=sid)))
    original = claim(console, snapshot_id=sid, attempt_id=receipt['attempt_id'], actor_id=actor)
    with locked(console, sid, receipt['attempt_id']) as (_, _, _, active):
        active['dispatch']['lease_expires_at'] = (now()-timedelta(seconds=1)).isoformat()
    fresh = restart_production(console)
    discovered = pending(fresh)
    assert any(attempt['attempt_id'] == receipt['attempt_id'] for _, attempt in discovered)
    replacement = claim(fresh, snapshot_id=sid, attempt_id=receipt['attempt_id'], actor_id=actor)
    assert replacement['dispatch']['token'] != original['dispatch']['token']
    with pytest.raises(ConsoleError, match='processing_command_conflict'):
        console._execute_source_attempt(actor_id=actor, snapshot_id=sid, attempt=original, deadline=time.monotonic()+60)
    assert console.snapshot_objects(sid, include_blocked=True) == []
    with worker_execution(None, console=fresh, sid=sid, attempt=replacement):
        fresh._execute_source_attempt(actor_id=actor, snapshot_id=sid, attempt=replacement, deadline=time.monotonic()+60)
    with fresh.workflow_document_store._connect() as con:
        assert con.execute('SELECT count(*) AS n FROM workflow.processing_attempts WHERE snapshot_id=%s', (sid,)).fetchone()['n'] == 1
    assert any((obj.get('metadata') or {}).get('human_annotation') for obj in fresh.snapshot_objects(sid))


def test_old_candidate_writer_cannot_change_a_materialised_human_claim(tmp_path, production_console):
    import psycopg
    from src.workflows.workflow_documents_postgres_v1 import _json_text
    from src.vorming.worker_handover_v1 import native_attempt
    console, actor, sid, _ = saved_source(production_console, tmp_path)
    receipt = build.finalize(console, actor_id=actor, **closing(build.overview(console, actor_id=actor, snapshot_id=sid)))
    console.execute_source_selection(actor_id=actor, snapshot_id=sid, attempt=native_attempt(console, sid, receipt['attempt_id']))
    original = next(obj for obj in console.snapshot_objects(sid) if (obj.get('metadata') or {}).get('human_annotation'))
    changed = deepcopy(original)
    changed['content']['clean_text'] = 'Door een andere route verzonnen.'
    with pytest.raises(psycopg.Error, match='annotation_activation_not_available'):
        with console.workflow_document_store._connect() as con:
            con.execute('UPDATE workflow.document_objects SET payload=%s::jsonb WHERE snapshot_id=%s AND object_id=%s',
                        (_json_text(changed),sid,original['object_id']))
    assert next(obj for obj in console.snapshot_objects(sid) if obj['object_id']==original['object_id']) == original
    with pytest.raises(ConsoleError, match='annotation_source_owned'):
        console.reserve_source_selection(actor_id=actor, snapshot_id=sid, command_id='old-route',
                                         expected_revision=console.objects_revision(sid))


@pytest.mark.parametrize('fault', ['missing_receipt', 'changed_request_hash'])
def test_partial_build_receipt_archive_is_refused_atomically(tmp_path, production_console, fault):
    from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
    from src.workflows.workflow_chain_recovery_v1 import PostgresWorkflowRecoveryAdapter
    from src.publication.publication_chain_recovery_v1 import PublicationChainRecoveryError
    from tests.postgres_support import database, install_schema
    console, actor, sid, _ = saved_source(production_console, tmp_path)
    build.finalize(console, actor_id=actor, **closing(build.overview(console, actor_id=actor, snapshot_id=sid)))
    state = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(console.workflow_document_store.config)).export_state()
    rows = state['formation_recovery']['tables']['annotation_build_commands']
    if fault == 'missing_receipt':
        rows.clear()
    else:
        rows[0]['request_hash'] = '0'*64
    with database(console.workflow_document_store.config.dsn) as target_config:
        install_schema(target_config.dsn)
        target = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(target_config))
        with pytest.raises(PublicationChainRecoveryError):
            target.restore_state(state)
        target.assert_empty()


def test_version_ten_upgrade_keeps_input_but_never_invents_a_seal(tmp_path, production_console):
    from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
    from src.workflows.workflow_chain_recovery_v1 import PostgresWorkflowRecoveryAdapter, _upgrade_workflow_state
    from src.publication.publication_chain_recovery_v1 import PublicationChainRecoveryError
    from src.workflows.formation_recovery_v1 import BUILD_TABLES
    console, _, _, _ = saved_source(production_console, tmp_path)
    current = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(console.workflow_document_store.config)).export_state()
    old = deepcopy(current)
    old['workflow_recovery_version'] = 10
    old['formation_recovery']['version'] = 3
    for table in BUILD_TABLES:
        del old['formation_recovery']['tables'][table]
    for row in old['formation_recovery']['tables']['annotation_sets']:
        del row['current_seal_id']
    assert _upgrade_workflow_state(old)['formation_recovery'] == current['formation_recovery']
    del old['formation_recovery']
    with pytest.raises(PublicationChainRecoveryError, match='missing_reexport_required'):
        _upgrade_workflow_state(old)


def test_legacy_context_route_cannot_add_context_outside_the_original_annotation(tmp_path, production_console):
    console, actor, sid, _ = saved_source(production_console, tmp_path, context_function='supported_by')
    receipt = build.finalize(console, actor_id=actor, **closing(build.overview(console, actor_id=actor, snapshot_id=sid)))
    from src.vorming.worker_handover_v1 import native_attempt
    console.execute_source_selection(actor_id=actor, snapshot_id=sid, attempt=native_attempt(console, sid, receipt['attempt_id']))
    before = console.snapshot_objects(sid)
    source = next(obj for obj in before if (obj.get('metadata') or {}).get('source_accountability'))
    target = next(obj for obj in before if (obj.get('metadata') or {}).get('human_annotation'))
    with pytest.raises(ConsoleError, match='annotation_source_owned'):
        console.confirm_source_context(actor_id=console._envelope(sid)['named_reviewers'][0], snapshot_id=sid,
            source_object_id=source['object_id'], role='context', target_object_ids=[target['object_id']],
            reason='Een oude route mag de bronannotatie niet vervangen.', command_id=str(uuid4()),
            expected_revision=console.objects_revision(sid))
    assert console.snapshot_objects(sid) == before


def test_unowned_model_source_cannot_claim_human_provenance_without_human_evidence(tmp_path, production_console):
    import psycopg
    from tests.test_d5_4_review_interaction_evidence import _system
    from src.workflows.workflow_documents_postgres_v1 import _json_text
    console, _, sid, oid = _system(tmp_path, production_console=production_console)
    original = next(obj for obj in console.snapshot_objects(sid) if obj['object_id'] == oid)
    forged = deepcopy(original)
    forged.setdefault('metadata', {})['human_annotation'] = {
        'annotation_id':str(uuid4()), 'revision':1, 'payload_hash':'a'*64}
    with pytest.raises(psycopg.Error, match='annotation_activation_not_available'):
        with console.workflow_document_store._connect() as con:
            con.execute('UPDATE workflow.document_objects SET payload=%s::jsonb WHERE snapshot_id=%s AND object_id=%s',
                        (_json_text(forged), sid, oid))
            # Isolate this deferred producer boundary before the separate
            # generic frontier/canonical integrity checks also reject forgery.
            con.execute('SET CONSTRAINTS workflow.require_human_annotation_binding IMMEDIATE')
    assert next(obj for obj in console.snapshot_objects(sid) if obj['object_id'] == oid) == original


@pytest.mark.parametrize('option', ['uploader_sole', 'one_other'])
@pytest.mark.parametrize('function', ['supported_by', 'explains'])
def test_human_chain_preserves_ingest_review_then_publishes_to_real_api_and_mcp_status(
        tmp_path, production_console, option, function):
    from tests.test_vsa_publish_readiness_ui_v1 import MemorySourceStore, _complete_review
    console, actor, sid, _ = saved_source(production_console, tmp_path, review_option=option,
        source_status='established', context_function=function, immutable_source_store=MemorySourceStore())
    chosen = deepcopy(console._envelope(sid)['review_configuration'])
    resumed = restart_production(console)
    close = closing(build.overview(resumed, actor_id=actor, snapshot_id=sid))
    receipt = build.finalize(resumed, actor_id=actor, **close)
    from src.vorming.worker_handover_v1 import native_attempt
    resumed.execute_source_selection(actor_id=actor, snapshot_id=sid,
        attempt=native_attempt(resumed, sid, receipt['attempt_id']))
    assert resumed._envelope(sid)['review_configuration'] == chosen
    from src.product_api_v1 import create_product_app
    from tests.test_product_api_v1 import paths, registry, headers
    from starlette.testclient import TestClient
    target = next(obj for obj in resumed.snapshot_objects(sid) if (obj.get('metadata') or {}).get('human_annotation'))
    public = TestClient(create_product_app('real', paths=paths(tmp_path), tenant_registry=registry(docs=('*',)),
        canonical_publication_store=resumed.canonical_publication_store,
        immutable_source_store=resumed.immutable_source_store))
    assert public.get('/v1/knowledge/'+target['object_id'], headers=headers()).status_code == 404
    publisher = resumed.create_account(username='publisher', password='human-publish-secret', roles=('publisher',))
    refused = resumed.publish(actor_id=publisher['account_id'], snapshot_id=sid)
    assert refused['status'] == 'BLOCKED'
    assert 'review_work_incomplete' in refused['blockers']
    assert resumed.canonical_publication_store.active_registry_summary(sid) == []
    reviewer = actor if option == 'uploader_sole' else chosen['reviewers'][0]
    _complete_review(resumed, {'reviewer':{'account_id':reviewer}}, {'snapshot_id':sid})
    readiness = resumed.publication_readiness(sid)
    assert readiness['publication_ready'], readiness['blockers']
    result = resumed.publish(actor_id=publisher['account_id'], snapshot_id=sid)
    response = public.get('/v1/knowledge/'+target['object_id'], headers=headers())
    assert response.status_code == 200, response.text
    assert response.json()['release']['release_id'] == result['release_id']
    assert response.json()['synthetic_fixture'] is False
    assert 'Alleen bij klachten.' in response.json()['content']
    assert 'De beoordeling betreft volwassenen.' in response.json()['content']
    assert ('Onderbouwt de uitspraak' if function=='supported_by' else 'Verklaart de uitspraak') in response.json()['content']
    from src.settings.metis_mcp_queries_v1 import McpQueries
    status = McpQueries(restart_production(resumed), 'https://testserver').read(publisher,
        'get_publication_status', {'snapshot_id':sid})
    assert status['active_registry_object_count'] == result['published_items']
    assert any(row['object_id'] == target['object_id'] for row in status['active_registry_rows']['items'])
