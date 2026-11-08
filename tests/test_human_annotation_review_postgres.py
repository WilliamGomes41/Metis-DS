"""Human corrections use the actual workflow/revision/review authorities.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: beschikbaarheid
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
from uuid import uuid4

import pytest

from src.operations_console_v1 import ConsoleError
from src.vorming import human_annotation_v1 as annotation
from src.vorming import human_annotation_build_v1 as build
from tests.production_support import restart_production
from tests.test_human_annotation_build_postgres import saved_source, closing
from tests.test_human_annotation_postgres import anchor, command
from tests.ko_review_fixture_support import affirmative_assessment
from src.vorming.source_bound_fields_v3 import FIELDS


def execute_build(console, actor, sid):
    receipt = build.finalize(console, actor_id=actor,
        **closing(build.overview(console, actor_id=actor, snapshot_id=sid)))
    from src.vorming.worker_handover_v1 import native_attempt
    console.execute_source_selection(actor_id=actor, snapshot_id=sid,
        attempt=native_attempt(console, sid, receipt['attempt_id']))
    return receipt


def candidate(console, sid):
    return next(obj for obj in console.snapshot_objects(sid)
                if (obj.get('metadata') or {}).get('human_annotation'))


def correction_request(console, sid, original):
    view = annotation.overview(console, actor_id=console._envelope(sid)['uploader_account_id'], snapshot_id=sid)
    saved = next(e for e in view['entries'] if e['annotation_id'] == original['annotation_id'])
    return {**deepcopy(original), 'command_id': str(uuid4()),
        'expected_revision': saved['revision'], 'expected_generation': view['generation'],
        'expected_objects_revision': view['objects_revision']}


def approve(console, sid, oid, actor):
    from src.vorming.human_annotation_projection_v1 import has_literal_support
    obj = next(o for o in console.snapshot_objects(sid) if o['object_id'] == oid)
    console.review_object(actor_id=actor, snapshot_id=sid, object_id=oid,
        decision='approve', confirmed_object_type='explanation',
        assessment=affirmative_assessment(),
        evidence_not_applicable=not has_literal_support(obj, console.review_source_fragments(sid)))


def save_second_claim(console, actor, sid):
    view = annotation.overview(console, actor_id=actor, snapshot_id=sid)
    core = anchor(view, 'De beoordeling')
    fields = {key: {'span': None, 'missing_reason': 'not_applicable'} for key in FIELDS}
    for field, text in [('subject_span', 'De beoordeling'), ('predicate_span', 'betreft'),
                        ('supported_object', 'volwassenen')]:
        start = core['quote'].index(text)
        fields[field] = {'span': {'block_id': core['block_id'], 'start': start, 'end': start + len(text)},
                         'missing_reason': None, 'quote': text}
    fields.update(type_evidence_spans={'core': True}, support_span={'core': True})
    request = command(view, ranges=[core, anchor(view, 'Onderzoek', role='evidence', function='supported_by')], status='ready')
    request['selection'].update(object_type='explanation', evidence_not_applicable=False,
                                field_evidence=fields, required_links=[])
    annotation.save(console, actor_id=actor, **request)
    return request


@pytest.mark.parametrize('storage', ['legacy', 'v1'])
def test_original_annotation_corrects_evidence_without_losing_confirmed_type(
        production_console, tmp_path, monkeypatch, storage):
    monkeypatch.setenv('METIS_DOCUMENT_INPUT_STORAGE', storage)
    if storage == 'v1':
        monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE', 'v1')
    console, actor, sid, original = saved_source(production_console, tmp_path,
        context_function='supported_by')
    first = execute_build(console, actor, sid)
    reviewer = console._envelope(sid)['named_reviewers'][0]
    before = candidate(console, sid)
    console.confirm_object_type(actor_id=reviewer, snapshot_id=sid,
        object_id=before['object_id'], confirmed_object_type='explanation',
        expected_revision=console.objects_revision(sid))
    before = candidate(console, sid)
    correction = {**deepcopy(original), 'command_id': str(uuid4()),
        'expected_revision': 1, 'expected_generation': 1,
        'expected_objects_revision': console.objects_revision(sid)}
    evidence = next(a for a in correction['selection']['ranges'] if a['role'] == 'evidence')
    evidence['evidence_function'] = 'explains'
    saved = annotation.save(console, actor_id=reviewer, **correction)
    assert saved['revision'] == 2
    resumed = restart_production(console)
    assert annotation.save(resumed, actor_id=reviewer, **correction) == saved
    assert candidate(resumed, sid) == before  # input save never edits source text
    second = execute_build(resumed, reviewer, sid)
    after = candidate(restart_production(resumed), sid)
    assert second['seal_id'] != first['seal_id']
    assert after['object_id'] == before['object_id']
    assert after['object_version'] != before['object_version']
    assert after['confirmed_object_type'] == 'explanation'
    assert after['metadata']['human_annotation']['annotation_id'] == original['annotation_id']
    assert after['metadata']['human_annotation']['revision'] == 2
    assert after['metadata']['revision_lineage']['previous_object_version'] == before['object_version']
    assert after['governance']['validation_status'] == 'needs_review'
    assert not any(b['valid'] for b in resumed.object_review_bindings(sid))


def test_postactivation_save_requires_exact_object_frontier(production_console, tmp_path):
    console, actor, sid, original = saved_source(production_console, tmp_path)
    execute_build(console, actor, sid)
    correction = {**deepcopy(original), 'command_id': str(uuid4()),
        'expected_revision': 1, 'expected_generation': 1,
        'expected_objects_revision': 'stale-frontier'}
    correction['selection']['status'] = 'draft'
    with pytest.raises(ConsoleError, match='annotation_objects_stale'):
        annotation.save(console, actor_id=actor, **correction)
    assert annotation.overview(console, actor_id=actor, snapshot_id=sid)['generation'] == 1


def test_pending_correction_revokes_only_affected_review_and_cannot_reapprove_old_version(production_console, tmp_path):
    console, actor, sid, original = saved_source(production_console, tmp_path, context_function='supported_by')
    second = save_second_claim(console, actor, sid)
    execute_build(console, actor, sid)
    reviewer = console._envelope(sid)['named_reviewers'][0]
    objects = {o['metadata']['human_annotation']['annotation_id']: o for o in console.snapshot_objects(sid)
               if (o.get('metadata') or {}).get('human_annotation')}
    first_id, second_id = objects[original['annotation_id']]['object_id'], objects[second['annotation_id']]['object_id']
    for oid in (first_id, second_id):
        approve(console, sid, oid, reviewer)
    untouched = next(o for o in console.snapshot_objects(sid) if o['object_id'] == second_id)
    kept_bindings = [b for b in console.object_review_bindings(sid) if b['object_id'] == second_id]
    request = correction_request(console, sid, original)
    next(a for a in request['selection']['ranges'] if a['role'] == 'evidence')['evidence_function'] = 'explains'
    saved = annotation.save(console, actor_id=reviewer, **request)
    assert saved['revision'] == 2
    resumed = restart_production(console)
    assert not any(b['valid'] for b in resumed.object_review_bindings(sid) if b['object_id'] == first_id)
    assert [b for b in resumed.object_review_bindings(sid) if b['object_id'] == second_id] == kept_bindings
    with pytest.raises(ConsoleError, match='annotation_correction_pending'):
        approve(resumed, sid, first_id, reviewer)
    execute_build(resumed, reviewer, sid)
    latest = restart_production(resumed)
    assert next(o for o in latest.snapshot_objects(sid) if o['object_id'] == second_id) == untouched
    assert [b for b in latest.object_review_bindings(sid) if b['object_id'] == second_id] == kept_bindings
    assert candidate(latest, sid)['object_version'] != objects[original['annotation_id']]['object_version']


def test_repeated_unchanged_save_after_activation_preserves_version_and_approval(production_console, tmp_path):
    console, actor, sid, original = saved_source(production_console, tmp_path)
    execute_build(console, actor, sid)
    reviewer = console._envelope(sid)['named_reviewers'][0]
    approve(console, sid, candidate(console, sid)['object_id'], reviewer)
    before = console.snapshot_objects(sid, include_blocked=True)
    bindings = console.object_review_bindings(sid)
    result = annotation.save(console, actor_id=reviewer, **correction_request(console, sid, original))
    assert result['revision'] == 1 and result['generation'] == 1
    assert console.snapshot_objects(sid, include_blocked=True) == before
    assert console.object_review_bindings(sid) == bindings


def test_core_change_keeps_explicit_identity_and_historical_human_evidence(production_console, tmp_path):
    console, actor, sid, original = saved_source(production_console, tmp_path, context_function='supported_by')
    first = execute_build(console, actor, sid)
    before = candidate(console, sid)
    request = correction_request(console, sid, original)
    view = annotation.overview(console, actor_id=actor, snapshot_id=sid)
    extra = anchor(view, 'Alleen')
    request['selection']['ranges'].insert(1, extra)
    annotation.save(console, actor_id=actor, **request)
    execute_build(console, actor, sid)
    after = candidate(console, sid)
    assert after['object_id'] == before['object_id']
    assert after['object_version'] != before['object_version']
    assert after['content']['clean_text'] == 'De kwetsbare huid verklaart de pijn. Alleen bij klachten.'
    assert before in console.snapshot_objects(sid, include_blocked=True)
    from src.workflows.formation_task_store_v1 import FormationTaskStore
    with console.workflow_document_store._connect() as con:
        refs = [r['proof_id'] for r in con.execute('SELECT proof_id FROM workflow.formation_evidence_roots WHERE snapshot_id=%s', (sid,)).fetchall()]
    store = FormationTaskStore(console.workflow_document_store)
    proofs = [store.read_formation_evidence({'layout':2, 'proof_id':ref}, envelope=console._envelope(sid)) for ref in refs]
    assert len(proofs) == 2
    assert any(proof['header']['capture']['annotation_seal_id'] == first['seal_id'] for proof in proofs)


@pytest.mark.parametrize('storage', ['legacy', 'v1'])
def test_corrected_human_history_restores_exactly_in_empty_database(production_console, tmp_path, monkeypatch, storage):
    monkeypatch.setenv('METIS_DOCUMENT_INPUT_STORAGE', storage)
    if storage == 'v1':
        monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE', 'v1')
    console, actor, sid, original = saved_source(production_console, tmp_path, context_function='supported_by')
    execute_build(console, actor, sid)
    reviewer = console._envelope(sid)['named_reviewers'][0]
    approve(console, sid, candidate(console, sid)['object_id'], reviewer)
    for function in ('explains', 'supported_by'):
        request = correction_request(console, sid, original)
        next(a for a in request['selection']['ranges'] if a['role'] == 'evidence')['evidence_function'] = function
        annotation.save(console, actor_id=actor, **request)
        execute_build(console, actor, sid)
        approve(console, sid, candidate(console, sid)['object_id'], reviewer)
    reviewer = console._envelope(sid)['named_reviewers'][0]
    unchanged = annotation.save(console, actor_id=reviewer, **correction_request(console, sid, original))
    assert unchanged['unchanged'] is True
    from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
    from src.workflows.workflow_chain_recovery_v1 import PostgresWorkflowRecoveryAdapter
    from tests.postgres_support import database, install_schema
    from tests.production_support import production_application
    adapter = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(console.workflow_document_store.config))
    state = adapter.export_state()
    with database(console.workflow_document_store.config.dsn) as config:
        install_schema(config.dsn)
        target = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(config))
        target.restore_state(state)
        restored = production_application(console.root, config, runtime=console.runtime,
            source_store=console.source_store).state.operations_kernel
        assert target.export_state()['formation_recovery'] == state['formation_recovery']
        assert restored.snapshot_objects(sid, include_blocked=True) == console.snapshot_objects(sid, include_blocked=True)
        assert restored.object_review_bindings(sid) == console.object_review_bindings(sid)
        assert annotation.overview(restored, actor_id=actor, snapshot_id=sid) == annotation.overview(console, actor_id=actor, snapshot_id=sid)


def test_duplicate_concurrent_corrections_and_real_transaction_rollback(production_console, tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    console, actor, sid, original = saved_source(production_console, tmp_path, context_function='supported_by')
    execute_build(console, actor, sid)
    reviewer = console._envelope(sid)['named_reviewers'][0]
    approve(console, sid, candidate(console, sid)['object_id'], reviewer)
    request = correction_request(console, sid, original)
    next(a for a in request['selection']['ranges'] if a['role'] == 'evidence')['evidence_function'] = 'explains'
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda c: annotation.save(c, actor_id=reviewer, **request), [console, restart_production(console)]))
    assert results[0] == results[1]
    with pytest.raises(ConsoleError, match='annotation_objects_stale|annotation_write_conflict'):
        annotation.save(restart_production(console), actor_id=reviewer, **{**request, 'command_id': str(uuid4())})
    execute_build(console, reviewer, sid)
    approve(console, sid, candidate(console, sid)['object_id'], reviewer)
    before = annotation.overview(console, actor_id=actor, snapshot_id=sid)
    bindings = console.object_review_bindings(sid)
    request = correction_request(console, sid, original)
    request['selection']['status'] = 'draft'
    commit = console._commit_prepared_store
    def failed_commit(**kwargs):
        result = commit(**kwargs)
        # Real SQL exception after nested writes, before the save owner's commit.
        with console.workflow_document_store._connect() as con:
            con.execute('SELECT 1/0')
        return result
    monkeypatch.setattr(console, '_commit_prepared_store', failed_commit)
    import psycopg
    with pytest.raises(psycopg.Error):
        annotation.save(console, actor_id=reviewer, **request)
    resumed = restart_production(console)
    assert annotation.overview(resumed, actor_id=actor, snapshot_id=sid) == before
    assert resumed.object_review_bindings(sid) == bindings


@pytest.mark.parametrize('option', ['uploader_sole', 'one_other'])
def test_correct_review_publish_serving_and_published_immutability(production_console, tmp_path, option):
    from tests.test_vsa_publish_readiness_ui_v1 import MemorySourceStore, _complete_review
    console, actor, sid, original = saved_source(production_console, tmp_path, review_option=option,
        source_status='established', context_function='supported_by', immutable_source_store=MemorySourceStore())
    chosen = deepcopy(console._envelope(sid)['review_configuration'])
    execute_build(console, actor, sid)
    reviewer = actor if option == 'uploader_sole' else chosen['reviewers'][0]
    _complete_review(console, {'reviewer': {'account_id': reviewer}}, {'snapshot_id': sid})
    assert console.publication_readiness(sid)['publication_ready']
    oid = candidate(console, sid)['object_id']
    request = correction_request(console, sid, original)
    next(a for a in request['selection']['ranges'] if a['role'] == 'evidence')['evidence_function'] = 'explains'
    annotation.save(console, actor_id=reviewer, **request)
    publisher = console.create_account(username='publisher', password='human-publish-secret', roles=('publisher',))
    refused = console.publish(actor_id=publisher['account_id'], snapshot_id=sid)
    assert refused['status'] == 'BLOCKED'
    resumed = restart_production(console)
    execute_build(resumed, reviewer, sid)
    assert resumed._envelope(sid)['review_configuration'] == chosen
    assert resumed.publish(actor_id=publisher['account_id'], snapshot_id=sid)['status'] == 'BLOCKED'
    approve(resumed, sid, oid, reviewer)
    readiness = resumed.publication_readiness(sid)
    assert readiness['publication_ready'], readiness['blockers']
    result = resumed.publish(actor_id=publisher['account_id'], snapshot_id=sid)
    from src.product_api_v1 import create_product_app
    from tests.test_product_api_v1 import paths, registry, headers
    from starlette.testclient import TestClient
    public = TestClient(create_product_app('real', paths=paths(tmp_path), tenant_registry=registry(docs=('*',)),
        canonical_publication_store=resumed.canonical_publication_store,
        immutable_source_store=resumed.immutable_source_store))
    response = public.get('/v1/knowledge/' + oid, headers=headers())
    assert response.status_code == 200
    assert response.json()['release']['release_id'] == result['release_id']
    assert 'Verklaart de uitspraak' in response.json()['content']
    frozen = resumed.snapshot_objects(sid, include_blocked=True)
    with pytest.raises(ConsoleError, match='published_working_revision_immutable'):
        annotation.save(resumed, actor_id=actor, **correction_request(resumed, sid, original))
    assert restart_production(resumed).snapshot_objects(sid, include_blocked=True) == frozen
    from src.settings.metis_mcp_queries_v1 import McpQueries
    status = McpQueries(restart_production(resumed), 'https://testserver').read(publisher,
        'get_publication_status', {'snapshot_id': sid})
    assert status['active_registry_object_count'] == result['published_items']


def test_current_incoming_dependency_loses_review_but_retains_confirmed_relation(production_console, tmp_path):
    console, actor, sid, original = saved_source(production_console, tmp_path, context_function='supported_by')
    second = save_second_claim(console, actor, sid)
    execute_build(console, actor, sid)
    reviewer = console._envelope(sid)['named_reviewers'][0]
    objects = {o['metadata']['human_annotation']['annotation_id']: o for o in console.snapshot_objects(sid)
               if (o.get('metadata') or {}).get('human_annotation')}
    first_id, second_id = objects[original['annotation_id']]['object_id'], objects[second['annotation_id']]['object_id']
    console.confirm_relations(actor_id=reviewer, snapshot_id=sid, object_id=second_id,
        relations=[{'relation_type':'supported_by', 'target_object_id':first_id}],
        expected_revision=console.objects_revision(sid))
    for oid in (first_id, second_id):
        approve(console, sid, oid, reviewer)
    prior = next(o for o in console.snapshot_objects(sid) if o['object_id'] == second_id)
    request = correction_request(console, sid, original)
    next(a for a in request['selection']['ranges'] if a['role'] == 'evidence')['evidence_function'] = 'explains'
    annotation.save(console, actor_id=reviewer, **request)
    assert not any(b['valid'] for b in console.object_review_bindings(sid) if b['object_id'] in {first_id, second_id})
    with pytest.raises(ConsoleError, match='annotation_correction_pending'):
        approve(console, sid, second_id, reviewer)
    execute_build(console, reviewer, sid)
    current = next(o for o in console.snapshot_objects(sid) if o['object_id'] == second_id)
    assert current['confirmed_relations'] == prior['confirmed_relations']
    assert current['object_version'] == prior['object_version']
    assert current['governance']['validation_status'] == 'needs_review'


@pytest.mark.parametrize('winner', ['correction', 'publication'])
def test_native_correction_publication_serializes_one_winner(production_console, tmp_path, winner):
    from concurrent.futures import ThreadPoolExecutor
    from src.workflows.workflow_transaction_v1 import workflow_transaction
    from tests.test_vsa_publish_readiness_ui_v1 import MemorySourceStore, _complete_review
    console, actor, sid, original = saved_source(production_console, tmp_path, review_option='uploader_sole',
        source_status='established', context_function='supported_by', immutable_source_store=MemorySourceStore())
    execute_build(console, actor, sid)
    _complete_review(console, {'reviewer': {'account_id': actor}}, {'snapshot_id': sid})
    assert console.publication_readiness(sid)['publication_ready']
    publisher = console.create_account(username='publisher', password='human-publish-secret', roles=('publisher',))['account_id']
    request = correction_request(console, sid, original)
    next(a for a in request['selection']['ranges'] if a['role'] == 'evidence')['evidence_function'] = 'explains'
    from tests.production_support import production_application
    other = production_application(console.root, console.workflow_document_store.config,
        runtime=tmp_path/'other-runtime', source_store=console.source_store,
        immutable_source_store=console.immutable_source_store).state.operations_kernel
    with ThreadPoolExecutor(1) as pool:
        with console._store_write_lock(), workflow_transaction(console.workflow_review_store) as con:
            console.workflow_review_store._lock_authorizations(con)
            console._lock_document_row(con, sid)
            if winner == 'correction':
                pending = pool.submit(other.publish, actor_id=publisher, snapshot_id=sid)
                annotation.save(console, actor_id=actor, **request)
            else:
                pending = pool.submit(annotation.save, other, actor_id=actor, **request)
                result = console.publish(actor_id=publisher, snapshot_id=sid)
                assert result['status'] != 'BLOCKED'
        if winner == 'correction':
            assert pending.result(timeout=15)['status'] == 'BLOCKED'
        else:
            with pytest.raises(ConsoleError, match='published_working_revision_immutable'):
                pending.result(timeout=15)
    latest = restart_production(console)
    assert latest.snapshot_is_published(sid) == (winner == 'publication')
    assert annotation.overview(latest, actor_id=actor, snapshot_id=sid)['generation'] == (1 if winner == 'publication' else 2)


def test_old_correction_writer_and_missing_revision_guard_fail_closed(production_console, tmp_path):
    console, actor, sid, original = saved_source(production_console, tmp_path)
    execute_build(console, actor, sid)
    before = console.snapshot_objects(sid, include_blocked=True)
    with pytest.raises(ConsoleError, match='annotation_source_owned'):
        console.correct_object(actor_id=actor, snapshot_id=sid, object_id=candidate(console, sid)['object_id'],
            patch={'reason':'old source writer', 'operations':[{'op':'set','path':'content.clean_text','value':'kwetsbare huid verklaart de pijn.'}]},
            expected_revision=console.objects_revision(sid))
    with console.workflow_document_store._connect() as con:
        con.execute('ALTER TABLE workflow.publish_authorizations DISABLE TRIGGER guard_annotation_pending_approval')
    request = correction_request(console, sid, original)
    request['selection']['status'] = 'draft'
    with pytest.raises(ConsoleError, match='annotation_revision_storage_not_ready'):
        annotation.save(console, actor_id=actor, **request)
    assert console.snapshot_objects(sid, include_blocked=True) == before


@pytest.mark.parametrize('function', ['supported_by', 'explains'])
def test_literal_evidence_is_reviewed_without_fabricating_an_evidence_object_or_na(production_console, tmp_path, function):
    console, actor, sid, _ = saved_source(production_console, tmp_path, context_function=function)
    execute_build(console, actor, sid)
    reviewer = console._envelope(sid)['named_reviewers'][0]
    obj = candidate(console, sid)
    assert console.object_review_bindings(sid) == []
    with pytest.raises(ConsoleError) as conflict:
        console.review_object(actor_id=reviewer, snapshot_id=sid, object_id=obj['object_id'],
            decision='approve', confirmed_object_type='explanation', assessment=affirmative_assessment(),
            evidence_not_applicable=True)
    assert conflict.value.code == 'supporting_evidence_choice_conflict'
    approve(console, sid, obj['object_id'], reviewer)
    own = [b for b in console.object_review_bindings(sid) if b['object_id'] == obj['object_id'] and b['valid']]
    assert len(own) == 1 and own[0]['supporting_evidence']['applicability'] == 'linked'
    assert len([o for o in console.snapshot_objects(sid) if (o.get('metadata') or {}).get('human_annotation')]) == 1


@pytest.mark.parametrize('option', ['two_others', 'uploader_and_other'])
def test_correction_preserves_required_independent_ingest_reviewers(production_console, tmp_path, option):
    from src.review.review_duty_v1 import review_stage, SECOND_REVIEW
    console, actor, sid, original = saved_source(production_console, tmp_path, review_option=option,
        four_eyes=True, context_function='supported_by')
    chosen = deepcopy(console._envelope(sid)['review_configuration'])
    policy = deepcopy(console._envelope(sid)['review_policy'])
    first = policy['primary']
    second = policy['assignments'][0]['reviewer_id']
    execute_build(console, actor, sid)
    for cycle in range(2):
        obj = candidate(console, sid)
        approve(console, sid, obj['object_id'], first)
        obj = candidate(console, sid)
        assert review_stage(obj, review_path='richtlijn', bindings=console.object_review_bindings(sid),
                            fragments=console.review_source_fragments(sid)) == SECOND_REVIEW
        # The existing owner treats the same person's already exact judgment
        # as a replay. It must never count it as an independent second vote.
        console.approve_second_review(actor_id=first, snapshot_id=sid, object_id=obj['object_id'],
            assessment=affirmative_assessment())
        assert {b['reviewer_id'] for b in console.object_review_bindings(sid) if b['valid']} == {first}
        assert review_stage(candidate(console, sid), review_path='richtlijn', bindings=console.object_review_bindings(sid),
                            fragments=console.review_source_fragments(sid)) == SECOND_REVIEW
        console.approve_second_review(actor_id=second, snapshot_id=sid, object_id=obj['object_id'],
            assessment=affirmative_assessment())
        assert len({b['reviewer_id'] for b in console.object_review_bindings(sid) if b['valid']}) == 2
        if cycle == 0:
            request = correction_request(console, sid, original)
            next(a for a in request['selection']['ranges'] if a['role'] == 'evidence')['evidence_function'] = 'explains'
            annotation.save(console, actor_id=actor, **request)
            assert not any(b['valid'] for b in console.object_review_bindings(sid))
            execute_build(console, actor, sid)
    assert console._envelope(sid)['review_configuration'] == chosen
    assert console._envelope(sid)['review_policy'] == policy


def test_preparing_correction_does_not_hold_shared_writer_or_source_read_lock(production_console, tmp_path, monkeypatch):
    from threading import Event
    from concurrent.futures import ThreadPoolExecutor
    from src.workflows.formation_task_store_v1 import FormationTaskStore
    console, actor, sid, original = saved_source(production_console, tmp_path, context_function='supported_by')
    execute_build(console, actor, sid)
    request = correction_request(console, sid, original)
    next(a for a in request['selection']['ranges'] if a['role'] == 'evidence')['evidence_function'] = 'explains'
    annotation.save(console, actor_id=actor, **request)
    receipt = build.finalize(console, actor_id=actor, **closing(build.overview(console, actor_id=actor, snapshot_id=sid)))
    from src.vorming.worker_handover_v1 import native_attempt
    paused, resume = Event(), Event()
    prepare = FormationTaskStore._prepare_human_evidence
    def paused_prepare(*args, **kwargs):
        paused.set()
        if not resume.wait(15):
            raise AssertionError('preparation was not resumed')
        return prepare(*args, **kwargs)
    monkeypatch.setattr(FormationTaskStore, '_prepare_human_evidence', paused_prepare)
    other = restart_production(console)
    with ThreadPoolExecutor(2) as pool:
        task = pool.submit(console.execute_source_selection, actor_id=actor, snapshot_id=sid,
            attempt=native_attempt(console, sid, receipt['attempt_id']))
        try:
            assert paused.wait(10)
            read = pool.submit(annotation.overview, other, actor_id=actor, snapshot_id=sid)
            assert read.result(timeout=5)['generation'] == 2
            write = pool.submit(other.create_account, username='during-build', password='human-build-secret', roles=('researcher',))
            assert write.result(timeout=5)['account_id']
        finally:
            resume.set()
        task.result(timeout=15)


@pytest.mark.parametrize('corrupt_role', ['candidate', 'result'])
def test_forged_raw_or_applied_correction_proof_cannot_activate(production_console, tmp_path, monkeypatch, corrupt_role):
    import json
    from dataclasses import replace
    from src.integrity_kernel import stable_hash
    from src.workflows.processing_archives_v1 import encoded
    from src.workflows.formation_task_store_v1 import FormationTaskStore
    from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
    console, actor, sid, original = saved_source(production_console, tmp_path, context_function='supported_by')
    execute_build(console, actor, sid)
    request = correction_request(console, sid, original)
    next(a for a in request['selection']['ranges'] if a['role'] == 'evidence')['evidence_function'] = 'explains'
    annotation.save(console, actor_id=actor, **request)
    before = console.snapshot_objects(sid, include_blocked=True)
    publish = FormationTaskStore.publish_formation_evidence
    def corrupt(store, envelope, prepared):
        members = []
        for role, key, digest, text in prepared.members:
            if role == corrupt_role:
                payload = json.loads(text)
                payload['content']['clean_text'] = 'Verzonnen uitspraak.'
                text, digest = encoded(payload), stable_hash(payload)
            members.append((role, key, digest, text))
        header = json.loads(prepared.header_text)
        header['manifest'] = [[role, key, digest] for role, key, digest, _ in members]
        return publish(store, envelope, replace(prepared, members=tuple(members), header_text=encoded(header)))
    monkeypatch.setattr(FormationTaskStore, 'publish_formation_evidence', corrupt)
    with pytest.raises(WorkflowDocumentStoreError, match='formation_evidence_preparation_changed'):
        execute_build(console, actor, sid)
    assert restart_production(console).snapshot_objects(sid, include_blocked=True) == before


def test_restore_cannot_resurrect_approval_for_pending_annotation(production_console, tmp_path):
    from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
    from src.workflows.workflow_chain_recovery_v1 import PostgresWorkflowRecoveryAdapter
    from src.publication.publication_chain_recovery_v1 import PublicationChainRecoveryError
    from tests.postgres_support import database, install_schema
    console, actor, sid, original = saved_source(production_console, tmp_path, context_function='supported_by')
    execute_build(console, actor, sid)
    reviewer = console._envelope(sid)['named_reviewers'][0]
    approve(console, sid, candidate(console, sid)['object_id'], reviewer)
    request = correction_request(console, sid, original)
    request['selection']['status'] = 'draft'
    annotation.save(console, actor_id=actor, **request)
    source = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(console.workflow_document_store.config))
    archive = source.export_state()
    for row in archive['workflow_tables']['publish_authorizations']:
        row['valid'] = True
        row['authorization_payload']['valid'] = True
    with database(console.workflow_document_store.config.dsn) as config:
        install_schema(config.dsn)
        target = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(config))
        with pytest.raises(PublicationChainRecoveryError):
            target.restore_state(archive)
        assert target.export_state()['workflow_tables']['documents'] == []


def test_v11_human_proof_upgrade_preserves_absent_review_payload_without_invention(production_console, tmp_path):
    from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
    from src.workflows.workflow_chain_recovery_v1 import PostgresWorkflowRecoveryAdapter, _upgrade_workflow_state
    console, actor, sid, _ = saved_source(production_console, tmp_path)
    execute_build(console, actor, sid)
    reviewer = console._envelope(sid)['named_reviewers'][0]
    approve(console, sid, candidate(console, sid)['object_id'], reviewer)
    state = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(console.workflow_document_store.config)).export_state()
    old = deepcopy(state)
    old['workflow_recovery_version'] = 11
    old['formation_recovery']['version'] = 4
    for row in old['workflow_tables']['publish_authorizations']:
        del row['authorization_payload']
    upgraded = _upgrade_workflow_state(old)
    assert all(row['authorization_payload'] is None for row in upgraded['workflow_tables']['publish_authorizations'])
    assert upgraded['formation_recovery'] == state['formation_recovery']
    assert 'authorization_payload' not in old['workflow_tables']['publish_authorizations'][0]


def test_structural_dependency_does_not_revoke_an_unchanged_claim_review(production_console, tmp_path):
    console, actor, sid, original = saved_source(production_console, tmp_path, context_function='supported_by')
    second = save_second_claim(console, actor, sid)
    execute_build(console, actor, sid)
    reviewer = console._envelope(sid)['named_reviewers'][0]
    objects = {o['metadata']['human_annotation']['annotation_id']: o for o in console.snapshot_objects(sid)
               if (o.get('metadata') or {}).get('human_annotation')}
    first_id, second_id = objects[original['annotation_id']]['object_id'], objects[second['annotation_id']]['object_id']
    console.confirm_relations(actor_id=reviewer, snapshot_id=sid, object_id=first_id,
        relations=[{'relation_type':'parent', 'target_object_id':second_id}],
        expected_revision=console.objects_revision(sid))
    for oid in (first_id, second_id):
        approve(console, sid, oid, reviewer)
    first_binding = [b for b in console.object_review_bindings(sid) if b['object_id'] == first_id]
    request = correction_request(console, sid, second)
    next(a for a in request['selection']['ranges'] if a['role'] == 'evidence')['evidence_function'] = 'explains'
    annotation.save(console, actor_id=reviewer, **request)
    assert [b for b in console.object_review_bindings(sid) if b['object_id'] == first_id] == first_binding
    execute_build(console, reviewer, sid)
    assert [b for b in console.object_review_bindings(sid) if b['object_id'] == first_id] == first_binding


def test_full_http_upload_pause_correction_build_review_publish_api_mcp_chain(production_console, tmp_path):
    from time import monotonic, sleep
    from urllib.parse import urlsplit, parse_qs
    from starlette.testclient import TestClient
    from tests.production_support import application_for
    from tests.test_vsa_publish_readiness_ui_v1 import MemorySourceStore
    from tests.test_ko_new_pages import compact_submission
    from tests.test_formation_repair_workplace import form_data
    console = production_console(root=tmp_path, immutable_source_store=MemorySourceStore())
    actor = console.create_account(username='http-human', password='http-human-secret', roles=('researcher','reviewer'))['account_id']
    publisher = console.create_account(username='publisher', password='http-publish-secret', roles=('publisher',))
    html = ('<html><body><p>De kwetsbare huid verklaart de pijn.</p><p>Alleen bij klachten.</p>'
            '<p>Onderzoek beschrijft dit verband.</p><p>De beoordeling betreft volwassenen.</p></body></html>')
    def login(client):
        assert client.post('/login', data={'username':'http-human','password':'http-human-secret'}, follow_redirects=False).status_code == 303
    with TestClient(application_for(console)) as client:
        login(client)
        uploaded = client.post('/ingest', data={'ingest_kind':'new','title':'Volledige menselijke HTTP-keten',
            'version':'1.0','date':'2026-11-08','class_':'richtlijn','family':'test','review_mode':'choice',
            'review_option':'uploader_sole','source_status':'established'}, files={'file':('human.html',html.encode(),'text/html')})
        assert uploaded.status_code == 200, uploaded.text
        sid = parse_qs(urlsplit(str(uploaded.url)).query)['document'][0]
        opened = client.post('/annotations/source', data={'document':sid,'expected_revision':console.objects_revision(sid)})
        assert opened.status_code == 200
        view = client.get('/annotations/api', params={'document':sid}).json()
        core = anchor(view, 'De kwetsbare')
        condition = anchor(view, 'Alleen', role='condition')
        fields = {key:{'span':None,'missing_reason':'not_applicable'} for key in FIELDS}
        for field, selected, text in [('subject_span',core,'De kwetsbare huid'), ('predicate_span',core,'verklaart'),
                ('supported_object',core,'de pijn'), ('condition_span',condition,condition['quote'])]:
            start = selected['quote'].index(text)
            fields[field] = {'span':{'block_id':selected['block_id'],'start':start,'end':start+len(text)},'missing_reason':None,'quote':text}
        fields.update(type_evidence_spans={'core':True},support_span={'core':True})
        request = command(view, ranges=[core,condition,anchor(view,'Onderzoek',role='evidence',function='supported_by'),
            anchor(view,'De beoordeling',role='context')], status='ready')
        request['selection'].update(object_type='explanation', evidence_not_applicable=False,field_evidence=fields,required_links=[])
        saved = client.post('/annotations/api', json=request)
        assert saved.status_code == 200, saved.text
    resumed = restart_production(console)
    with TestClient(application_for(resumed)) as client:
        login(client)
        assert client.get('/annotations/api',params={'document':sid}).json()['entries'][0]['annotation_id'] == request['annotation_id']
        for cycle in range(2):
            page = client.get('/annotations', params={'document':sid,'overview':'true'})
            assert page.status_code == 200 and 'Alleen bij klachten.' in page.text
            closed = client.post('/annotations/finalize', data=form_data(page, '/annotations/finalize'))
            assert closed.status_code == 200, closed.text
            attempt = parse_qs(urlsplit(str(closed.url)).query)['attempt'][0]
            deadline = monotonic()+10
            while monotonic()<deadline:
                state = client.get('/annotations/build/api',params={'document':sid,'attempt':attempt}).json()
                if state['state'] != 'running':
                    break
                sleep(.05)
            assert state['state'] == 'succeeded', state
            if cycle == 0:
                corrected = correction_request(resumed, sid, request)
                next(a for a in corrected['selection']['ranges'] if a['role']=='evidence')['evidence_function'] = 'explains'
                assert client.post('/annotations/api',json=corrected).status_code == 200
        obj = candidate(resumed, sid)
        review = client.get('/review', params={'document':sid,'object':obj['object_id']})
        assert review.status_code == 200 and 'Verklaart de uitspraak' in review.text
        judgment = compact_submission(review)
        judgment.pop('evidence_not_applicable')
        saved = client.post('/review', data=judgment)
        assert saved.status_code == 200 and 'data-review-receipt' in saved.text
        assert 'data-ko-assessment-form' not in client.get('/review',params={'document':sid,'object':obj['object_id']}).text
    readiness = resumed.publication_readiness(sid)
    assert readiness['publication_ready'], readiness['blockers']
    release = resumed.publish(actor_id=publisher['account_id'], snapshot_id=sid)
    from src.product_api_v1 import create_product_app
    from tests.test_product_api_v1 import paths, registry, headers
    public = TestClient(create_product_app('real', paths=paths(tmp_path), tenant_registry=registry(docs=('*',)),
        canonical_publication_store=resumed.canonical_publication_store,immutable_source_store=resumed.immutable_source_store))
    result = public.get('/v1/knowledge/'+obj['object_id'],headers=headers())
    assert result.status_code == 200 and result.json()['release']['release_id'] == release['release_id']
    assert 'Verklaart de uitspraak' in result.json()['content']
    from src.settings.metis_mcp_queries_v1 import McpQueries
    queries = McpQueries(restart_production(resumed), 'https://testserver')
    status = queries.read(publisher, 'get_publication_status', {'snapshot_id':sid})
    assert status['active_registry_object_count'] == release['published_items']
    passages = queries.read(publisher, 'get_passages', {'snapshot_id':sid,'object_id':obj['object_id']})
    assert passages['items'][0]['object_version'] == candidate(resumed, sid)['object_version']


def test_source_policy_is_pinned_and_legacy_seals_keep_their_original_output(production_console, tmp_path):
    from src.vorming.human_annotation_materialisation_v1 import build_objects
    from src.vorming.source_accountability_v1 import evidence_of, is_source_record, VERSION, CONTAINERS_VERSION
    console, actor, sid, _ = saved_source(production_console, tmp_path, context_function='supported_by')
    receipt = execute_build(console, actor, sid)
    with console.workflow_document_store._connect() as con:
        seal = con.execute('SELECT payload FROM workflow.annotation_seals WHERE seal_id=%s', (receipt['seal_id'],)).fetchone()['payload']
        entries = con.execute('SELECT v.annotation_id,v.revision,v.payload,v.payload_hash FROM workflow.annotation_heads h JOIN workflow.annotation_versions v USING(snapshot_id,annotation_id,revision) WHERE h.snapshot_id=%s ORDER BY h.position', (sid,)).fetchall()
    fragments = console.review_source_fragments(sid)
    current = build_objects(seal, entries, fragments=fragments)
    assert {evidence_of(o)['version'] for o in current if is_source_record(o)} == {CONTAINERS_VERSION}
    legacy = deepcopy(seal)
    legacy.pop('source_accountability_version')
    original = build_objects(legacy, entries, fragments=fragments)
    assert {evidence_of(o)['version'] for o in original if is_source_record(o)} == {VERSION}
    assert build_objects(legacy, entries, fragments=fragments) == original
    assert [o['content'] for o in original] == [o['content'] for o in current]
    invalid = {**seal, 'source_accountability_version':'unknown-policy'}
    with pytest.raises(ValueError, match='annotation_source_policy_invalid'):
        build_objects(invalid, entries, fragments=fragments)
